"""
Scheduler Module - Background jobs for FaithTracker Pastoral Care System
Handles daily reminders, cache refresh, and member data reconciliation
Uses APScheduler for timezone-aware job scheduling
"""

import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import logging
from motor.motor_asyncio import AsyncIOMotorClient
import os
import httpx
import uuid
import smtplib
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from utils import normalize_phone_number

logger = logging.getLogger(__name__)

# Jakarta timezone
JAKARTA_TZ = ZoneInfo("Asia/Jakarta")

def now_jakarta():
    """Get current datetime in Jakarta timezone"""
    return datetime.now(JAKARTA_TZ)

def today_jakarta():
    """Get current date in Jakarta timezone"""
    return now_jakarta().date()

# MongoDB connection
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'pastoral_care_db')]

scheduler = AsyncIOScheduler()

# Email configuration from environment
SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASS = os.environ.get('SMTP_PASS', '')
SMTP_FROM = os.environ.get('SMTP_FROM', SMTP_USER)
ALERT_EMAIL = os.environ.get('ALERT_EMAIL', os.environ.get('SMTP_USER', ''))

# Retry configuration
WHATSAPP_MAX_RETRIES = 3
WHATSAPP_RETRY_DELAYS = [2, 4, 8]  # Exponential backoff in seconds


async def send_email_alert(subject: str, body: str):
    """Send email alert for critical failures"""
    if not SMTP_USER or not SMTP_PASS or not ALERT_EMAIL:
        logger.warning("Email alert not configured - missing SMTP credentials")
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_FROM
        msg['To'] = ALERT_EMAIL
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        # Run SMTP in thread pool to avoid blocking
        def _send():
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _send)

        logger.info(f"Email alert sent to {ALERT_EMAIL}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email alert: {str(e)}")
        return False


async def send_whatsapp(phone: str, message: str, log_context: dict):
    """Send WhatsApp message with retry mechanism and email alert on failure"""
    last_error = None

    # Try environment variable first, then fall back to database settings
    whatsapp_url = os.environ.get('WHATSAPP_GATEWAY_URL')
    if not whatsapp_url:
        # Fall back to database settings
        settings = await db.settings.find_one({"type": "automation"})
        if settings and settings.get("data"):
            whatsapp_url = settings["data"].get("whatsappGateway")

    if not whatsapp_url:
        error_msg = "WhatsApp gateway not configured"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}

    phone_formatted = phone if phone.endswith('@s.whatsapp.net') else f"{phone}@s.whatsapp.net"

    # Retry loop with exponential backoff
    for attempt in range(WHATSAPP_MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=30.0) as http_client:
                response = await http_client.post(
                    f"{whatsapp_url}/send/message",
                    json={"phone": phone_formatted, "message": message}
                )
                result = response.json()

                # Check if successful
                if result.get('code') == 'SUCCESS':
                    # Log successful notification
                    await db.notification_logs.insert_one({
                        **log_context,
                        "channel": "whatsapp",
                        "recipient": phone_formatted,
                        "message": message,
                        "status": "sent",
                        "response_data": result,
                        "attempts": attempt + 1,
                        "created_at": datetime.now(timezone.utc)
                    })
                    return {"success": True, "result": result, "attempts": attempt + 1}

                # Not successful but got a response - check if retryable
                error_code = result.get('code', 'UNKNOWN')
                last_error = f"Gateway returned: {error_code}"

                # Don't retry for non-recoverable errors
                if error_code in ['INVALID_PHONE', 'NOT_REGISTERED']:
                    break

        except httpx.ConnectError as e:
            last_error = f"Connection error: {str(e)}"
        except httpx.TimeoutException as e:
            last_error = f"Timeout: {str(e)}"
        except Exception as e:
            last_error = f"Error: {str(e)}"

        # Log retry attempt
        if attempt < WHATSAPP_MAX_RETRIES - 1:
            delay = WHATSAPP_RETRY_DELAYS[attempt]
            logger.warning(f"WhatsApp send failed (attempt {attempt + 1}/{WHATSAPP_MAX_RETRIES}): {last_error}. Retrying in {delay}s...")
            await asyncio.sleep(delay)

    # All retries exhausted - log failure and send email alert
    logger.error(f"WhatsApp send failed after {WHATSAPP_MAX_RETRIES} attempts: {last_error}")

    await db.notification_logs.insert_one({
        **log_context,
        "channel": "whatsapp",
        "recipient": phone_formatted,
        "message": message,
        "status": "failed",
        "error": last_error,
        "attempts": WHATSAPP_MAX_RETRIES,
        "created_at": datetime.now(timezone.utc)
    })

    # Send email alert for persistent failure
    await send_email_alert(
        subject="[FaithTracker] WhatsApp Alert - Message Failed",
        body=f"""WhatsApp message delivery failed after {WHATSAPP_MAX_RETRIES} attempts.

Recipient: {phone_formatted}
Error: {last_error}
Time: {datetime.now(JAKARTA_TZ).strftime('%Y-%m-%d %H:%M:%S')} WIB

Message preview (first 200 chars):
{message[:200]}...

Please check:
1. WhatsApp Gateway status at https://gateway.gkbj.org
2. Gateway may need to be re-authenticated (scan QR code)
3. Check gateway container logs

---
FaithTracker Pastoral Care System
"""
    )

    return {"success": False, "error": last_error, "attempts": WHATSAPP_MAX_RETRIES}

async def generate_daily_digest_for_campus(campus_id: str, campus_name: str):
    """Generate daily digest for a specific campus"""
    try:
        today = today_jakarta()  # Use Jakarta timezone
        church_name = os.environ.get('CHURCH_NAME', 'Church')

        # 1. Birthdays today
        # Birthday events store original birth_date (e.g., "1980-05-15"), not current year's date
        # We need to find members whose birth month/day matches today
        birthday_members = []
        birthday_week_members = []

        # Get all members with birth_date in this campus
        # Note: MongoDB $and is required for multiple conditions on same field
        members_with_birthday = await db.members.find(
            {
                "campus_id": campus_id,
                "birth_date": {"$exists": True, "$type": "string", "$ne": ""}
            },
            {"_id": 0, "id": 1, "name": 1, "phone": 1, "birth_date": 1}
        ).to_list(5000)

        today_month_day = (today.month, today.day)
        week_ahead = today + timedelta(days=7)

        for member in members_with_birthday:
            try:
                birth_date = datetime.strptime(member["birth_date"], '%Y-%m-%d').date()
                this_year_birthday = birth_date.replace(year=today.year)

                # Handle leap year edge case (Feb 29 -> Feb 28 if not leap year)
                if birth_date.month == 2 and birth_date.day == 29:
                    try:
                        this_year_birthday = birth_date.replace(year=today.year)
                    except ValueError:
                        this_year_birthday = birth_date.replace(year=today.year, day=28)

                # Check if birthday event exists and is not completed
                event = await db.care_events.find_one(
                    {"member_id": member["id"], "event_type": "birthday", "completed": False, "ignored": {"$ne": True}},
                    {"_id": 0}
                )

                if not event:
                    continue

                # Skip members without phone number
                if not member.get('phone'):
                    continue

                phone_clean = member['phone'].replace('@s.whatsapp.net', '')

                if this_year_birthday == today:
                    # Birthday TODAY
                    birthday_members.append(f"  - {member['name']}\n    wa.me/{phone_clean}")
                elif today < this_year_birthday <= week_ahead:
                    # Birthday in next 7 days
                    days_until = (this_year_birthday - today).days
                    birthday_week_members.append(f"  - {member['name']} ({days_until} hari lagi)\n    wa.me/{phone_clean}")
            except (ValueError, KeyError, TypeError):
                # TypeError: birth_date is None/not a string
                # ValueError: invalid date format
                # KeyError: missing field
                continue

        # 3. Grief stages due today
        grief_due = await db.grief_support.find({
            "campus_id": campus_id,
            "scheduled_date": today.isoformat(),
            "completed": False
        }, {"_id": 0}).to_list(100)

        grief_members = []
        grief_stage_names = {
            "1_week": "1 minggu",
            "2_weeks": "2 minggu",
            "1_month": "1 bulan",
            "3_months": "3 bulan",
            "6_months": "6 bulan",
            "1_year": "1 tahun"
        }
        for stage in grief_due:
            member = await db.members.find_one({"id": stage["member_id"]}, {"_id": 0})
            if member and member.get('phone'):
                stage_name = grief_stage_names.get(stage["stage"], stage["stage"])
                phone_clean = member['phone'].replace('@s.whatsapp.net', '')
                grief_members.append(f"  - {member['name']} ({stage_name} setelah dukacita)\n    wa.me/{phone_clean}")

        # 3b. OVERDUE Grief stages (past due, not completed)
        overdue_grief = await db.grief_support.find({
            "campus_id": campus_id,
            "scheduled_date": {"$lt": today.isoformat()},
            "completed": False
        }, {"_id": 0}).to_list(100)

        overdue_grief_members = []
        for stage in overdue_grief:
            member = await db.members.find_one({"id": stage["member_id"]}, {"_id": 0})
            if member and member.get('phone'):
                stage_name = grief_stage_names.get(stage["stage"], stage["stage"])
                days_overdue = (today - date.fromisoformat(stage["scheduled_date"])).days
                phone_clean = member['phone'].replace('@s.whatsapp.net', '')
                overdue_grief_members.append(f"  - {member['name']} ({stage_name}, {days_overdue} hari terlambat)\n    wa.me/{phone_clean}")

        # 4. Accident/illness follow-ups due today
        # Query accident_followup collection (similar to grief_support) with scheduled_date
        accident_followups_due = await db.accident_followup.find({
            "campus_id": campus_id,
            "scheduled_date": today.isoformat(),
            "completed": False,
            "ignored": {"$ne": True}
        }, {"_id": 0}).to_list(100)

        hospital_followups = []
        hospital_stage_names = {
            "first_followup": "tindak lanjut ke-1",
            "second_followup": "tindak lanjut ke-2",
            "final_followup": "tindak lanjut akhir"
        }

        for followup in accident_followups_due:
            member = await db.members.find_one({"id": followup["member_id"]}, {"_id": 0})
            if member and member.get('phone'):
                stage_name = hospital_stage_names.get(followup.get("stage"), followup.get("stage", "tindak lanjut"))
                phone_clean = member['phone'].replace('@s.whatsapp.net', '')
                hospital_followups.append(f"  - {member['name']} ({stage_name})\n    wa.me/{phone_clean}")

        # 4b. OVERDUE Hospital follow-ups (past due, not completed)
        overdue_hospital = await db.accident_followup.find({
            "campus_id": campus_id,
            "scheduled_date": {"$lt": today.isoformat()},
            "completed": False,
            "ignored": {"$ne": True}
        }, {"_id": 0}).to_list(100)

        overdue_hospital_members = []
        for followup in overdue_hospital:
            member = await db.members.find_one({"id": followup["member_id"]}, {"_id": 0})
            if member and member.get('phone'):
                stage_name = hospital_stage_names.get(followup.get("stage"), followup.get("stage", "tindak lanjut"))
                days_overdue = (today - date.fromisoformat(followup["scheduled_date"])).days
                phone_clean = member['phone'].replace('@s.whatsapp.net', '')
                overdue_hospital_members.append(f"  - {member['name']} ({stage_name}, {days_overdue} hari terlambat)\n    wa.me/{phone_clean}")

        # 5. Financial aid due today
        financial_aid_due = await db.financial_aid_schedules.find({
            "campus_id": campus_id,
            "next_occurrence": today.isoformat(),
            "is_active": True
        }, {"_id": 0}).to_list(100)

        financial_aid_members = []
        aid_type_names = {
            "education": "Pendidikan",
            "medical": "Kesehatan",
            "living": "Kebutuhan Hidup",
            "other": "Lainnya"
        }
        for aid in financial_aid_due:
            member = await db.members.find_one({"id": aid["member_id"]}, {"_id": 0})
            if member and member.get('phone'):
                aid_type = aid_type_names.get(aid.get("aid_type"), aid.get("aid_type", "Bantuan"))
                phone_clean = member['phone'].replace('@s.whatsapp.net', '')
                financial_aid_members.append(f"  - {member['name']} ({aid_type})\n    wa.me/{phone_clean}")

        # 5b. OVERDUE Financial aid (past due, still active)
        overdue_financial_aid = await db.financial_aid_schedules.find({
            "campus_id": campus_id,
            "next_occurrence": {"$lt": today.isoformat()},
            "is_active": True
        }, {"_id": 0}).to_list(100)

        overdue_financial_members = []
        for aid in overdue_financial_aid:
            member = await db.members.find_one({"id": aid["member_id"]}, {"_id": 0})
            if member and member.get('phone'):
                aid_type = aid_type_names.get(aid.get("aid_type"), aid.get("aid_type", "Bantuan"))
                days_overdue = (today - date.fromisoformat(aid["next_occurrence"])).days
                phone_clean = member['phone'].replace('@s.whatsapp.net', '')
                overdue_financial_members.append(f"  - {member['name']} ({aid_type}, {days_overdue} hari terlambat)\n    wa.me/{phone_clean}")


        # 7. Pastoral Notes with overdue follow-ups (due today or past due)
        overdue_notes_query = {
            "campus_id": campus_id,
            "follow_up_date": {"$lte": today.isoformat()},
            "follow_up_completed": False,
            "is_private": {"$ne": True}  # Don't include private notes in digest
        }

        overdue_notes = await db.pastoral_notes.find(
            overdue_notes_query,
            {"_id": 0}
        ).to_list(100)

        overdue_notes_formatted = []
        notes_due_today = []

        category_names = {
            "special_needs": "Kebutuhan Khusus",
            "health": "Kesehatan",
            "financial": "Keuangan",
            "spiritual": "Rohani",
            "family": "Keluarga",
            "work": "Pekerjaan",
            "other": "Lainnya"
        }

        for note in overdue_notes:
            member = await db.members.find_one({"id": note["member_id"]}, {"_id": 0, "name": 1, "phone": 1})
            if member and member.get('phone'):
                phone_clean = member['phone'].replace('@s.whatsapp.net', '')
                note_date = date.fromisoformat(note["follow_up_date"])

                category_display = category_names.get(note.get("category"), "")
                category_str = f" [{category_display}]" if category_display else ""

                if note_date == today:
                    notes_due_today.append(
                        f"  - {member['name']}{category_str}\n"
                        f"    {note['title'][:50]}{'...' if len(note['title']) > 50 else ''}\n"
                        f"    wa.me/{phone_clean}"
                    )
                else:
                    days_overdue = (today - note_date).days
                    overdue_notes_formatted.append(
                        f"  - {member['name']}{category_str} ({days_overdue} hari terlambat)\n"
                        f"    {note['title'][:50]}{'...' if len(note['title']) > 50 else ''}\n"
                        f"    wa.me/{phone_clean}"
                    )

        # 6. Members at risk / disconnected (30+ days no contact) - RANDOMIZED sample of 10
        members = await db.members.find({"campus_id": campus_id}, {"_id": 0}).to_list(5000)
        at_risk_list = []
        for member in members:
            # Skip members without phone number
            if not member.get('phone'):
                continue

            last_contact = member.get('last_contact_date')
            if last_contact:
                if isinstance(last_contact, str):
                    last_contact = datetime.fromisoformat(last_contact)
                if last_contact.tzinfo is None:
                    last_contact = last_contact.replace(tzinfo=timezone.utc)
                days = (datetime.now(timezone.utc) - last_contact).days
            else:
                days = 999

            if days >= 30:
                at_risk_list.append((member['name'], days, member['phone']))

        # Randomize the list and pick 10 random members (different each day)
        # Use today's date as seed for consistent results within the same day
        random.seed(today.isoformat() + campus_id)
        at_risk_sample = random.sample(at_risk_list, min(10, len(at_risk_list))) if at_risk_list else []
        at_risk_formatted = []
        for name, days, phone in at_risk_sample:
            phone_clean = phone.replace('@s.whatsapp.net', '')
            at_risk_formatted.append(f"  - {name} ({days} hari)\n    wa.me/{phone_clean}")

        # Build digest message
        digest_parts = []
        digest_parts.append(f"*{church_name} - {campus_name}*")
        digest_parts.append("*TUGAS PERAWATAN PASTORAL HARI INI*")
        digest_parts.append(f"{today.strftime('%d %B %Y')}")
        digest_parts.append("")

        if birthday_members:
            digest_parts.append(f"*ULANG TAHUN HARI INI ({len(birthday_members)}):*")
            digest_parts.extend(birthday_members[:20])
            digest_parts.append("")

        if grief_members:
            digest_parts.append(f"*DUKUNGAN DUKACITA HARI INI ({len(grief_members)}):*")
            digest_parts.extend(grief_members)
            digest_parts.append("")

        if hospital_followups:
            digest_parts.append(f"*TINDAK LANJUT RUMAH SAKIT ({len(hospital_followups)}):*")
            digest_parts.extend(hospital_followups)
            digest_parts.append("")

        if financial_aid_members:
            digest_parts.append(f"*BANTUAN KEUANGAN HARI INI ({len(financial_aid_members)}):*")
            digest_parts.extend(financial_aid_members)
            digest_parts.append("")


        if notes_due_today:
            digest_parts.append(f"*CATATAN PASTORAL - TINDAK LANJUT HARI INI ({len(notes_due_today)}):*")
            digest_parts.extend(notes_due_today[:10])
            digest_parts.append("")

        # Overdue section - combine grief, hospital, financial aid, and pastoral notes overdue
        if overdue_grief_members or overdue_hospital_members or overdue_financial_members or overdue_notes_formatted:
            total_overdue = len(overdue_grief_members) + len(overdue_hospital_members) + len(overdue_financial_members) + len(overdue_notes_formatted)
            digest_parts.append(f"*TUGAS TERLAMBAT - PERLU SEGERA ({total_overdue}):*")
            if overdue_hospital_members:
                digest_parts.append("_Rumah Sakit:_")
                digest_parts.extend(overdue_hospital_members[:10])
            if overdue_grief_members:
                digest_parts.append("_Dukacita:_")
                digest_parts.extend(overdue_grief_members[:10])
            if overdue_financial_members:
                digest_parts.append("_Bantuan Keuangan:_")
                digest_parts.extend(overdue_financial_members[:10])
            if overdue_notes_formatted:
                digest_parts.append("_Catatan Pastoral:_")
                digest_parts.extend(overdue_notes_formatted[:10])
            digest_parts.append("")

        if at_risk_formatted:
            digest_parts.append(f"*JEMAAT BERISIKO - PERLU PERHATIAN ({len(at_risk_list)} total):*")
            digest_parts.extend(at_risk_formatted)
            digest_parts.append("")

        if len(digest_parts) <= 4:  # Only header, no tasks
            digest_parts.append("Tidak ada tugas mendesak hari ini!")
            digest_parts.append("")

        digest_parts.append("_Silakan hubungi jemaat secara personal via WhatsApp/telepon_")
        digest_parts.append("_Tuhan memberkati pelayanan Anda_")

        digest_message = "\n".join(digest_parts)

        return {
            "campus_id": campus_id,
            "campus_name": campus_name,
            "message": digest_message,
            "stats": {
                "birthdays_today": len(birthday_members),
                "birthdays_week": len(birthday_week_members),
                "grief_due": len(grief_members),
                "hospital_followups": len(hospital_followups),
                "financial_aid": len(financial_aid_members),
                "overdue_grief": len(overdue_grief_members),
                "overdue_hospital": len(overdue_hospital_members),
                "overdue_financial": len(overdue_financial_members),
                "at_risk": len(at_risk_list),
                "notes_due_today": len(notes_due_today),
                "overdue_notes": len(overdue_notes_formatted)
            }
        }
    except Exception as e:
        logger.error(f"Error generating digest for campus {campus_name}: {str(e)}")
        return None

async def send_daily_digest_to_pastoral_team():
    """Send daily digest to all pastoral team members per campus"""
    try:
        logger.info("="*60)
        logger.info("SENDING DAILY DIGEST TO PASTORAL TEAM")
        logger.info("="*60)

        # Get all active campuses
        campuses = await db.campuses.find({"is_active": True}, {"_id": 0}).to_list(200)
        logger.info(f"Found {len(campuses)} active campuses")

        total_sent = 0
        total_failed = 0

        # Track users who have already received the digest to prevent duplicates
        sent_to_users = set()  # Track by user_id
        sent_to_phones = set()  # Track by phone number to prevent duplicate messages to same phone

        for campus in campuses:
            campus_id = campus["id"]
            campus_name = campus["campus_name"]

            # Generate digest for this campus
            digest = await generate_daily_digest_for_campus(campus_id, campus_name)

            if not digest:
                continue

            # Skip if no tasks
            if digest["stats"]["birthdays_today"] == 0 and \
               digest["stats"]["grief_due"] == 0 and \
               digest["stats"]["hospital_followups"] == 0 and \
               digest["stats"]["financial_aid"] == 0 and \
               digest["stats"]["overdue_grief"] == 0 and \
               digest["stats"]["overdue_hospital"] == 0 and \
               digest["stats"]["overdue_financial"] == 0 and \
               digest["stats"]["at_risk"] == 0 and \
               digest["stats"].get("notes_due_today", 0) == 0 and \
               digest["stats"].get("overdue_notes", 0) == 0:
                logger.info(f"  Skipping {campus_name} - no urgent tasks")
                continue

            # Get pastoral team members for this specific campus only (no full_admin here)
            pastoral_team = await db.users.find({
                "campus_id": campus_id,
                "role": {"$in": ["campus_admin", "pastor"]},
                "is_active": True
            }, {"_id": 0}).to_list(100)

            logger.info(f"  {campus_name}: {len(pastoral_team)} team members, {sum(digest['stats'].values())} tasks")

            # Send to each team member (skip if already sent by user_id OR phone)
            for user in pastoral_team:
                if user['id'] in sent_to_users:
                    logger.info(f"  Skipping {user['name']} (user already received digest)")
                    continue

                # Normalize phone for deduplication - use consistent format to catch duplicates
                raw_phone = user.get('phone', '').replace('@s.whatsapp.net', '')
                user_phone = normalize_phone_number(raw_phone) if raw_phone else ''
                if user_phone and user_phone in sent_to_phones:
                    logger.info(f"  Skipping {user['name']} (phone {user_phone} already received digest)")
                    sent_to_users.add(user['id'])  # Mark user as processed
                    continue

                try:
                    result = await send_whatsapp(
                        user['phone'],
                        digest['message'],
                        {
                            "id": str(uuid.uuid4()),
                            "campus_id": campus_id,
                            "pastoral_team_user_id": user['id']
                        })

                    sent_to_users.add(user['id'])
                    if user_phone:
                        sent_to_phones.add(user_phone)
                    if result.get("success"):
                        total_sent += 1
                        logger.info(f"  Sent digest to {user['name']} ({user['phone']})")
                    else:
                        total_failed += 1
                        logger.error(f"  Failed to send digest to {user['name']}: {result.get('error')}")

                except Exception as user_error:
                    total_failed += 1
                    logger.error(f"  Error sending digest to user {user.get('email')}: {str(user_error)}")

        # Handle full_admin users separately - send consolidated digest from first campus with tasks
        full_admins = await db.users.find({
            "role": "full_admin",
            "is_active": True
        }, {"_id": 0}).to_list(100)

        if full_admins:
            logger.info(f"\n  Sending digest to {len(full_admins)} full_admin users...")

            # Find first campus with tasks to send digest
            first_campus_digest = None
            for campus in campuses:
                digest = await generate_daily_digest_for_campus(campus["id"], campus["campus_name"])
                if digest and (digest["stats"]["birthdays_today"] > 0 or
                              digest["stats"]["grief_due"] > 0 or
                              digest["stats"]["hospital_followups"] > 0 or
                              digest["stats"]["financial_aid"] > 0 or
                              digest["stats"]["overdue_grief"] > 0 or
                              digest["stats"]["overdue_hospital"] > 0 or
                              digest["stats"]["overdue_financial"] > 0 or
                              digest["stats"]["at_risk"] > 0 or
                              digest["stats"].get("notes_due_today", 0) > 0 or
                              digest["stats"].get("overdue_notes", 0) > 0):
                    first_campus_digest = digest
                    break

            if first_campus_digest:
                for admin in full_admins:
                    if admin['id'] in sent_to_users:
                        logger.info(f"  Skipping {admin['name']} (user already received digest)")
                        continue

                    # Normalize phone for deduplication - use consistent format to catch duplicates
                    raw_admin_phone = admin.get('phone', '').replace('@s.whatsapp.net', '')
                    admin_phone = normalize_phone_number(raw_admin_phone) if raw_admin_phone else ''
                    if admin_phone and admin_phone in sent_to_phones:
                        logger.info(f"  Skipping {admin['name']} (phone {admin_phone} already received digest)")
                        sent_to_users.add(admin['id'])  # Mark user as processed
                        continue

                    try:
                        result = await send_whatsapp(
                            admin['phone'],
                            first_campus_digest['message'],
                            {
                                "id": str(uuid.uuid4()),
                                "campus_id": "all",
                                "pastoral_team_user_id": admin['id']
                            })

                        sent_to_users.add(admin['id'])
                        if admin_phone:
                            sent_to_phones.add(admin_phone)
                        if result.get("success"):
                            total_sent += 1
                            logger.info(f"  Sent digest to full_admin {admin['name']} ({admin['phone']})")
                        else:
                            total_failed += 1
                            logger.error(f"  Failed to send digest to full_admin {admin['name']}: {result.get('error')}")

                    except Exception as admin_error:
                        total_failed += 1
                        logger.error(f"  Error sending digest to full_admin {admin.get('email')}: {str(admin_error)}")

        logger.info(f"\nDaily reminder job completed")
        logger.info(f"   Campuses processed: {len(campuses)}")
        logger.info(f"   Messages sent: {total_sent}")
        logger.info(f"   Messages failed: {total_failed}")

        # Send summary email if there were failures
        if total_failed > 0:
            await send_email_alert(
                subject=f"[FaithTracker] Daily Digest Summary - {total_failed} Failed",
                body=f"""Daily Digest Job Summary

Time: {datetime.now(JAKARTA_TZ).strftime('%Y-%m-%d %H:%M:%S')} WIB
Campuses processed: {len(campuses)}
Messages sent: {total_sent}
Messages failed: {total_failed}

Please check the WhatsApp gateway status if failures persist.

---
FaithTracker Pastoral Care System
"""
            )

    except Exception as e:
        logger.error(f"Error in daily reminder job: {str(e)}")
        # Send error email
        await send_email_alert(
            subject="[FaithTracker] Daily Digest Job Failed",
            body=f"""Daily Digest Job encountered an error.

Error: {str(e)}
Time: {datetime.now(JAKARTA_TZ).strftime('%Y-%m-%d %H:%M:%S')} WIB

Please check the application logs for more details.

---
FaithTracker Pastoral Care System
"""
        )


async def member_reconciliation_job():
    """
    Daily reconciliation job to sync members from core API
    Runs at configured time to ensure data integrity (especially for webhook mode)
    """
    # Acquire distributed lock to prevent duplicate execution across workers
    if not await acquire_job_lock("member_reconciliation", ttl_seconds=1800):
        logger.info("Another worker is already running reconciliation - skipping")
        return

    try:
        logger.info("Starting daily member reconciliation...")

        # Import the shared sync function from server
        from server import perform_member_sync_for_campus

        # Get all campuses with sync enabled and reconciliation enabled
        sync_configs = await db.sync_configs.find({
            "is_enabled": True,
            "reconciliation_enabled": True
        }, {"_id": 0}).to_list(None)

        if not sync_configs:
            logger.info("No campuses configured for reconciliation")
            return

        total_synced = 0
        total_errors = 0

        for config in sync_configs:
            try:
                campus_id = config["campus_id"]
                logger.info(f"Reconciling campus: {campus_id}")

                # Call the shared sync function
                result = await perform_member_sync_for_campus(campus_id, sync_type="reconciliation")

                if result.get("success"):
                    stats = result.get("stats", {})
                    logger.info(
                        f"Campus {campus_id}: "
                        f"fetched={stats.get('fetched', 0)}, "
                        f"created={stats.get('created', 0)}, "
                        f"updated={stats.get('updated', 0)}, "
                        f"matched_by_name={stats.get('matched_by_name_phone', 0) + stats.get('matched_by_name_only', 0)}"
                    )
                    total_synced += stats.get('fetched', 0)
                else:
                    logger.error(f"Campus {campus_id} sync failed: {result.get('error')}")
                    total_errors += 1

            except Exception as campus_error:
                logger.error(f"Error reconciling campus {config.get('campus_id')}: {str(campus_error)}")
                total_errors += 1

        logger.info(f"Daily reconciliation complete: {total_synced} members synced, {total_errors} errors")

    except Exception as e:
        logger.error(f"Error in reconciliation job: {str(e)}")
    finally:
        await release_job_lock("member_reconciliation")


async def refresh_all_dashboard_caches():
    """Refresh dashboard cache for all active campuses"""
    # Acquire distributed lock to prevent duplicate execution across workers
    if not await acquire_job_lock("cache_refresh", ttl_seconds=300):
        logger.info("Another worker is already refreshing cache - skipping")
        return

    try:
        from server import db, calculate_dashboard_reminders, get_campus_timezone, get_date_in_timezone

        # Get all active campuses
        campuses = await db.campuses.find({"is_active": True}, {"_id": 0, "id": 1, "campus_name": 1, "timezone": 1}).to_list(None)

        logger.info(f"Refreshing dashboard cache for {len(campuses)} campuses...")

        for campus in campuses:
            campus_id = campus["id"]
            campus_tz = campus.get("timezone", "Asia/Jakarta")
            today_date = get_date_in_timezone(campus_tz)

            # Calculate fresh data
            data = await calculate_dashboard_reminders(campus_id, campus_tz, today_date)

            # Update cache
            cache_key = f"dashboard_reminders_{campus_id}_{today_date}"
            await db.dashboard_cache.update_one(
                {"cache_key": cache_key},
                {
                    "$set": {
                        "cache_key": cache_key,
                        "data": data,
                        "calculated_at": datetime.now(timezone.utc),
                        "expires_at": datetime.now(timezone.utc) + timedelta(hours=24)  # Cache for full day
                    }
                },
                upsert=True
            )

            logger.info(f"Dashboard cache refreshed for {campus['campus_name']} - {data['total_tasks']} tasks")

        # Clean up old cache entries (older than 2 days)
        two_days_ago = datetime.now(timezone.utc) - timedelta(days=2)
        await db.dashboard_cache.delete_many({"calculated_at": {"$lt": two_days_ago}})

        logger.info("Dashboard cache refresh complete")

    except Exception as e:
        logger.error(f"Error refreshing dashboard caches: {str(e)}")
    finally:
        await release_job_lock("cache_refresh")


async def acquire_job_lock(job_name: str, ttl_seconds: int = 300):
    """
    Acquire a distributed lock for a scheduled job to prevent duplicate execution
    across multiple worker processes.

    Args:
        job_name: Unique identifier for the job
        ttl_seconds: Lock expiration time (default 5 minutes)

    Returns:
        True if lock acquired, False otherwise
    """
    try:
        lock_id = f"job_lock_{job_name}_{today_jakarta().isoformat()}"
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl_seconds)

        # Try to insert lock document (will fail if already exists due to unique index)
        result = await db.job_locks.update_one(
            {
                "lock_id": lock_id,
                "$or": [
                    {"expires_at": {"$lt": now}},  # Lock expired
                    {"expires_at": {"$exists": False}}  # No expiry (shouldn't happen)
                ]
            },
            {
                "$set": {
                    "lock_id": lock_id,
                    "job_name": job_name,
                    "acquired_at": now,
                    "expires_at": expires_at
                }
            },
            upsert=True
        )

        # If we modified a document, we got the lock
        if result.matched_count > 0 or result.upserted_id:
            logger.info(f"Acquired lock for {job_name}")
            return True
        else:
            logger.info(f"Lock already held for {job_name} - skipping")
            return False

    except Exception as e:
        # If there's an error, assume we didn't get the lock
        logger.error(f"Error acquiring lock for {job_name}: {str(e)}")
        return False

async def release_job_lock(job_name: str):
    """Release the distributed lock for a job"""
    try:
        lock_id = f"job_lock_{job_name}_{today_jakarta().isoformat()}"
        await db.job_locks.delete_one({"lock_id": lock_id})
        logger.info(f"Released lock for {job_name}")
    except Exception as e:
        logger.error(f"Error releasing lock for {job_name}: {str(e)}")

async def daily_reminder_job():
    """Main daily reminder job - sends digest to pastoral team"""
    # Acquire distributed lock to prevent duplicate execution across workers
    if not await acquire_job_lock("daily_reminder", ttl_seconds=600):
        logger.info("Another worker is already running this job - skipping")
        return

    try:
        logger.info("==" * 30)
        logger.info("DAILY PASTORAL CARE DIGEST - Sending to Team")
        logger.info("==" * 30)

        # Refresh dashboard cache for all campuses first
        await refresh_all_dashboard_caches()

        # Send WhatsApp digests
        await send_daily_digest_to_pastoral_team()

        logger.info("Daily digest job completed")

    finally:
        # Always release the lock when done
        await release_job_lock("daily_reminder")

async def get_digest_time_from_db():
    """Get the digest time from database settings, default to 08:00"""
    try:
        settings = await db.settings.find_one({"type": "automation"})
        if settings and settings.get("data", {}).get("digestTime"):
            return settings["data"]["digestTime"]
        return "08:00"
    except Exception as e:
        logger.error(f"Error getting digest time from DB: {str(e)}")
        return "08:00"

def schedule_daily_digest(hour: int, minute: int):
    """Schedule or reschedule the daily digest job"""
    try:
        # Remove existing job if present
        try:
            scheduler.remove_job('daily_reminders')
        except Exception:
            pass

        # Add job with new time
        scheduler.add_job(
            daily_reminder_job,
            'cron',
            hour=hour,
            minute=minute,
            timezone='Asia/Jakarta',
            id='daily_reminders',
            name='Daily Pastoral Care Digest',
            replace_existing=True
        )
        logger.info(f"Daily digest scheduled for {hour:02d}:{minute:02d} Asia/Jakarta")
    except Exception as e:
        logger.error(f"Error scheduling daily digest: {str(e)}")

async def reschedule_daily_digest():
    """Reschedule daily digest based on current database settings"""
    digest_time = await get_digest_time_from_db()
    try:
        hour, minute = map(int, digest_time.split(":"))
        schedule_daily_digest(hour, minute)
    except ValueError:
        logger.error(f"Invalid digest time format: {digest_time}, using default 08:00")
        schedule_daily_digest(8, 0)

async def init_daily_digest_schedule():
    """Initialize daily digest schedule from database on startup"""
    await asyncio.sleep(2)  # Wait for DB connection to be ready
    await reschedule_daily_digest()

def start_scheduler():
    """Start the scheduler with jobs configured from database"""
    try:
        # Midnight job - Refresh dashboard cache when date changes
        scheduler.add_job(
            refresh_all_dashboard_caches,
            'cron',
            hour=0,
            minute=0,
            timezone='Asia/Jakarta',
            id='midnight_cache_refresh',
            name='Midnight Dashboard Cache Refresh',
            replace_existing=True
        )

        # Run daily reconciliation at 3 AM Jakarta time
        scheduler.add_job(
            member_reconciliation_job,
            'cron',
            hour=3,
            minute=0,
            timezone='Asia/Jakarta',
            id='member_reconciliation',
            name='Daily Member Reconciliation',
            replace_existing=True
        )

        # Default daily digest at 8 AM (will be updated from DB shortly after startup)
        scheduler.add_job(
            daily_reminder_job,
            'cron',
            hour=8,
            minute=0,
            timezone='Asia/Jakarta',
            id='daily_reminders',
            name='Daily Pastoral Care Digest',
            replace_existing=True
        )

        scheduler.start()

        # Schedule async initialization of digest time from database
        scheduler.add_job(
            init_daily_digest_schedule,
            'date',  # Run once
            id='init_digest_schedule',
            name='Initialize Digest Schedule from DB',
            replace_existing=True
        )

        logger.info("Scheduler started successfully")
        logger.info("  - Midnight cache refresh: 00:00 Asia/Jakarta")
        logger.info("  - Daily digest: 08:00 Asia/Jakarta (loading from DB...)")
        logger.info("  - Member reconciliation: 03:00 Asia/Jakarta")
    except Exception as e:
        logger.error(f"Error starting scheduler: {str(e)}")

def stop_scheduler():
    """Stop the scheduler"""
    try:
        if scheduler.running:
            scheduler.shutdown()
            logger.info("Scheduler stopped")
    except Exception as e:
        logger.error(f"Error stopping scheduler: {str(e)}")
