import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import logging
from motor.motor_asyncio import AsyncIOMotorClient
import os
import httpx
import uuid

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

async def send_whatsapp(phone: str, message: str, log_context: dict):
    """Send WhatsApp message and log result"""
    try:
        whatsapp_url = os.environ.get('WHATSAPP_GATEWAY_URL')
        if not whatsapp_url:
            return {"success": False, "error": "Gateway not configured"}
        
        phone_formatted = phone if phone.endswith('@s.whatsapp.net') else f"{phone}@s.whatsapp.net"
        
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.post(
                f"{whatsapp_url}/send/message",
                json={"phone": phone_formatted, "message": message}
            )
            result = response.json()
            
            # Log notification
            status = "sent" if result.get('code') == 'SUCCESS' else "failed"
            await db.notification_logs.insert_one({
                **log_context,
                "channel": "whatsapp",
                "recipient": phone_formatted,
                "message": message,
                "status": status,
                "response_data": result,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            
            return {"success": status == "sent", "result": result}
    except Exception as e:
        logger.error(f"WhatsApp send error: {str(e)}")
        return {"success": False, "error": str(e)}

async def generate_daily_digest_for_campus(campus_id: str, campus_name: str):
    """Generate daily digest for a specific campus"""
    try:
        today = today_jakarta()  # Use Jakarta timezone
        church_name = os.environ.get('CHURCH_NAME', 'Church')
        
        # 1. Birthdays today
        birthdays_today = await db.care_events.find({
            "campus_id": campus_id,
            "event_type": "birthday",
            "event_date": today.isoformat(),
            "completed": False
        }, {"_id": 0}).to_list(100)
        
        # Get member names for birthdays with wa.me links
        birthday_members = []
        for event in birthdays_today:
            member = await db.members.find_one({"id": event["member_id"]}, {"_id": 0})
            if member:
                phone_clean = member['phone'].replace('@s.whatsapp.net', '')
                birthday_members.append(f"  • {member['name']}\n    📱 wa.me/{phone_clean}")
        
        # 2. Birthdays this week (next 7 days)
        week_end = today + timedelta(days=7)
        birthdays_week = await db.care_events.find({
            "campus_id": campus_id,
            "event_type": "birthday",
            "event_date": {"$gte": (today + timedelta(days=1)).isoformat(), "$lte": week_end.isoformat()},
            "completed": False
        }, {"_id": 0}).to_list(100)
        
        birthday_week_members = []
        for event in birthdays_week:
            member = await db.members.find_one({"id": event["member_id"]}, {"_id": 0})
            if member:
                event_date = datetime.fromisoformat(event['event_date']).date() if isinstance(event['event_date'], str) else event['event_date']
                days_until = (event_date - today).days
                phone_clean = member['phone'].replace('@s.whatsapp.net', '')
                birthday_week_members.append(f"  • {member['name']} ({days_until} hari lagi)\n    📱 wa.me/{phone_clean}")
        
        # 3. Grief stages due today
        grief_due = await db.grief_support.find({
            "campus_id": campus_id,
            "scheduled_date": today.isoformat(),
            "completed": False
        }, {"_id": 0}).to_list(100)
        
        grief_members = []
        for stage in grief_due:
            member = await db.members.find_one({"id": stage["member_id"]}, {"_id": 0})
            if member:
                stage_names = {
                    "1_week": "1 minggu",
                    "2_weeks": "2 minggu", 
                    "1_month": "1 bulan",
                    "3_months": "3 bulan",
                    "6_months": "6 bulan",
                    "1_year": "1 tahun"
                }
                stage_name = stage_names.get(stage["stage"], stage["stage"])
                phone_clean = member['phone'].replace('@s.whatsapp.net', '')
                grief_members.append(f"  • {member['name']} ({stage_name} setelah dukacita)\n    📱 wa.me/{phone_clean}")
        
        # 4. Hospital follow-ups due
        followup_days = [3, 7, 14]
        hospital_followups = []
        for days_after in followup_days:
            discharge_date = today - timedelta(days=days_after)
            events = await db.care_events.find({
                "campus_id": campus_id,
                "event_type": "accident_illness",
                "discharge_date": discharge_date.isoformat(),
                "completed": False
            }, {"_id": 0}).to_list(100)
            
            for event in events:
                member = await db.members.find_one({"id": event["member_id"]}, {"_id": 0})
                if member:
                    phone_clean = member['phone'].replace('@s.whatsapp.net', '')
                    hospital_followups.append(f"  • {member['name']} ({days_after} hari setelah pulang dari {event.get('hospital_name', 'RS')})\n    📱 wa.me/{phone_clean}")
        
        # 5. Members at risk (30+ days no contact) - top 10
        members = await db.members.find({"campus_id": campus_id}, {"_id": 0}).to_list(1000)
        at_risk_list = []
        for member in members:
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
        
        at_risk_list.sort(key=lambda x: x[1], reverse=True)
        at_risk_top = at_risk_list[:10]
        at_risk_formatted = []
        for name, days, phone in at_risk_top:
            phone_clean = phone.replace('@s.whatsapp.net', '')
            at_risk_formatted.append(f"  • {name} ({days} hari)\n    📱 wa.me/{phone_clean}")
        
        # Build digest message
        digest_parts = []
        digest_parts.append(f"🏥 *{church_name} - {campus_name}*")
        digest_parts.append("📋 *TUGAS PERAWATAN PASTORAL HARI INI*")
        digest_parts.append(f"📅 {today.strftime('%d %B %Y')}")
        digest_parts.append("")
        
        if birthday_members:
            digest_parts.append(f"🎂 *ULANG TAHUN HARI INI ({len(birthday_members)}):*")
            digest_parts.extend(birthday_members[:20])
            digest_parts.append("")
        
        if grief_members:
            digest_parts.append(f"💔 *DUKUNGAN DUKACITA HARI INI ({len(grief_members)}):*")
            digest_parts.extend(grief_members)
            digest_parts.append("")
        
        if hospital_followups:
            digest_parts.append(f"🏥 *TINDAK LANJUT RUMAH SAKIT ({len(hospital_followups)}):*")
            digest_parts.extend(hospital_followups)
            digest_parts.append("")
        
        if at_risk_formatted:
            digest_parts.append(f"⚠️ *JEMAAT BERISIKO - PERLU PERHATIAN ({len(at_risk_list)} total):*")
            digest_parts.extend(at_risk_formatted)
            digest_parts.append("")
        
        if len(digest_parts) <= 4:  # Only header, no tasks
            digest_parts.append("✅ Tidak ada tugas mendesak hari ini!")
            digest_parts.append("")
        
        digest_parts.append("💡 _Silakan hubungi jemaat secara personal via WhatsApp/telepon_")
        digest_parts.append("🙏 _Tuhan memberkati pelayanan Anda_")
        
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
                "at_risk": len(at_risk_list)
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
               digest["stats"]["at_risk"] == 0:
                logger.info(f"  Skipping {campus_name} - no urgent tasks")
                continue
            
            # Get all pastoral team members for this campus
            pastoral_team = await db.users.find({
                "$or": [
                    {"campus_id": campus_id, "role": {"$in": ["campus_admin", "pastor"]}},
                    {"role": "full_admin"}  # Full admin gets digests from all campuses
                ],
                "is_active": True
            }, {"_id": 0}).to_list(100)
            
            logger.info(f"  {campus_name}: {len(pastoral_team)} team members, {sum(digest['stats'].values())} tasks")
            
            # Send to each team member
            for user in pastoral_team:
                result = await send_whatsapp(
                    user['phone'],
                    digest['message'],
                    {
                        "id": str(uuid.uuid4()),
                        "campus_id": campus_id,
                        "pastoral_team_user_id": user['id']
                    }
                )
                
                if result['success']:
                    total_sent += 1
                    logger.info(f"    ✓ Sent to {user['name']} ({user['phone']})")
                else:
                    total_failed += 1
                    logger.error(f"    ✗ Failed to send to {user['name']}: {result.get('error')}")
        
        logger.info("="*60)
        logger.info(f"Daily digest complete: {total_sent} sent, {total_failed} failed")
        logger.info("="*60)
        
    except Exception as e:
        logger.error(f"Error sending daily digest: {str(e)}")

async def refresh_all_dashboard_caches():
    """Refresh dashboard cache for all active campuses"""
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
            
            logger.info(f"✅ Dashboard cache refreshed for {campus['campus_name']} - {data['total_tasks']} tasks")
        
        # Clean up old cache entries (older than 2 days)
        two_days_ago = datetime.now(timezone.utc) - timedelta(days=2)
        await db.dashboard_cache.delete_many({"calculated_at": {"$lt": two_days_ago}})
        
        logger.info("Dashboard cache refresh complete")
        
    except Exception as e:
        logger.error(f"Error refreshing dashboard caches: {str(e)}")


async def daily_reminder_job():
    """Main daily reminder job - sends digest to pastoral team"""
    logger.info("==" * 30)
    logger.info("DAILY PASTORAL CARE DIGEST - Sending to Team")
    logger.info("==" * 30)
    
    # Refresh dashboard cache for all campuses first
    await refresh_all_dashboard_caches()
    
    # Send WhatsApp digests
    await send_daily_digest_to_pastoral_team()
    
    logger.info("Daily digest job completed")

def start_scheduler():
    """Start the scheduler with daily job at 8 AM Jakarta time"""
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
        
        # Run daily at 8 AM Jakarta time (Asia/Jakarta = UTC+7)
        scheduler.add_job(
            daily_reminder_job,
            'cron',
            hour=8,
            minute=0,
            timezone='Asia/Jakarta',
            id='daily_reminders',
            replace_existing=True
        )
        
        scheduler.start()
        logger.info("✅ Scheduler started successfully")
        logger.info("  - Midnight cache refresh: 00:00 Asia/Jakarta")
        logger.info("  - Daily digest: 08:00 Asia/Jakarta")
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