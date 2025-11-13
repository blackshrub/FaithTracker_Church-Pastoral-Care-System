import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import date, datetime, timedelta, timezone
import logging
from motor.motor_asyncio import AsyncIOMotorClient
import os
import httpx

logger = logging.getLogger(__name__)

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

async def send_grief_stage_reminders():
    """Send reminders for grief stages due today"""
    try:
        today = date.today()
        
        # Find grief stages due today that haven't been completed or reminded
        stages = await db.grief_support.find({
            "scheduled_date": today.isoformat(),
            "completed": False,
            "reminder_sent": False
        }, {"_id": 0}).to_list(100)
        
        logger.info(f"Found {len(stages)} grief stages due for reminders today")
        
        for stage in stages:
            member = await db.members.find_one({"id": stage["member_id"]}, {"_id": 0})
            if not member:
                continue
            
            church_name = os.environ.get('CHURCH_NAME', 'Church')
            stage_names = {
                "1_week": "1 minggu / 1 week",
                "2_weeks": "2 minggu / 2 weeks",
                "1_month": "1 bulan / 1 month",
                "3_months": "3 bulan / 3 months",
                "6_months": "6 bulan / 6 months",
                "1_year": "1 tahun / 1 year"
            }
            stage_name = stage_names.get(stage["stage"], stage["stage"])
            
            message = f"{church_name} - Dukungan Dukacita / Grief Support Check-in: Sudah {stage_name} sejak kehilangan Anda. Kami memikirkan dan mendoakan Anda. Hubungi kami jika Anda memerlukan dukungan. / It has been {stage_name} since your loss. We are thinking of you and praying for you. Please reach out if you need support."
            
            result = await send_whatsapp(
                member['phone'],
                message,
                {
                    "id": str(uuid.uuid4()),
                    "grief_support_id": stage["id"],
                    "member_id": stage["member_id"]
                }
            )
            
            if result['success']:
                await db.grief_support.update_one(
                    {"id": stage["id"]},
                    {"$set": {"reminder_sent": True}}
                )
                logger.info(f"Grief reminder sent to {member['name']} for stage {stage['stage']}")
    
    except Exception as e:
        logger.error(f"Error sending grief reminders: {str(e)}")

async def send_birthday_reminders():
    """Send birthday reminders (7, 3, 1 days before)"""
    try:
        today = date.today()
        reminder_days = [7, 3, 1]
        
        for days_before in reminder_days:
            target_date = today + timedelta(days=days_before)
            
            # Find birthday events on target date
            events = await db.care_events.find({
                "event_type": "birthday",
                "event_date": target_date.isoformat(),
                "completed": False
            }, {"_id": 0}).to_list(100)
            
            for event in events:
                # Check if we already sent reminder for this timeframe
                log = await db.notification_logs.find_one({
                    "care_event_id": event["id"],
                    "message": {"$regex": f"{days_before} hari"}
                })
                
                if log:
                    continue  # Already sent
                
                member = await db.members.find_one({"id": event["member_id"]}, {"_id": 0})
                if not member:
                    continue
                
                church_name = os.environ.get('CHURCH_NAME', 'Church')
                message = f"{church_name} - Pengingat Ulang Tahun / Birthday Reminder: {days_before} hari lagi ulang tahun {member['name']} ({target_date.strftime('%d %B %Y')}). Jangan lupa untuk menghubungi! / {days_before} days until {member['name']}'s birthday. Don't forget to reach out!"
                
                await send_whatsapp(
                    member['phone'],
                    message,
                    {
                        "id": str(uuid.uuid4()),
                        "care_event_id": event["id"],
                        "member_id": event["member_id"]
                    }
                )
        
        logger.info(f"Birthday reminders check completed")
    except Exception as e:
        logger.error(f"Error sending birthday reminders: {str(e)}")

async def send_hospital_followup_reminders():
    """Send hospital discharge follow-up reminders (3, 7, 14 days after)"""
    try:
        today = date.today()
        followup_days = [3, 7, 14]
        
        for days_after in followup_days:
            discharge_date = today - timedelta(days=days_after)
            
            # Find hospital events with discharge on that date, not completed
            events = await db.care_events.find({
                "event_type": "hospital_visit",
                "discharge_date": discharge_date.isoformat(),
                "completed": False
            }, {"_id": 0}).to_list(100)
            
            for event in events:
                # Check if we already sent this specific followup
                log = await db.notification_logs.find_one({
                    "care_event_id": event["id"],
                    "message": {"$regex": f"{days_after} hari setelah"}
                })
                
                if log:
                    continue
                
                member = await db.members.find_one({"id": event["member_id"]}, {"_id": 0})
                if not member:
                    continue
                
                church_name = os.environ.get('CHURCH_NAME', 'Church')
                message = f"{church_name} - Tindak Lanjut Rumah Sakit / Hospital Follow-up: Sudah {days_after} hari setelah pulang dari {event.get('hospital_name', 'rumah sakit')}. Bagaimana kondisi Anda? Kami ingin tahu dan mendukung. / It has been {days_after} days since your discharge from {event.get('hospital_name', 'hospital')}. How are you doing? We want to know and support you."
                
                await send_whatsapp(
                    member['phone'],
                    message,
                    {
                        "id": str(uuid.uuid4()),
                        "care_event_id": event["id"],
                        "member_id": event["member_id"]
                    }
                )
        
        logger.info("Hospital follow-up reminders check completed")
    except Exception as e:
        logger.error(f"Error sending hospital follow-up reminders: {str(e)}")

async def daily_reminder_job():
    """Main daily reminder job - runs all reminder types"""
    logger.info("=" * 50)
    logger.info("Starting daily automated reminders")
    logger.info("=" * 50)
    
    await send_grief_stage_reminders()
    await send_birthday_reminders()
    await send_hospital_followup_reminders()
    
    logger.info("Daily automated reminders completed")

def start_scheduler():
    """Start the scheduler with daily job at 8 AM Jakarta time"""
    try:
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
        logger.info("Scheduler started - daily reminders will run at 8 AM Jakarta time")
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

# Import uuid for log context
import uuid