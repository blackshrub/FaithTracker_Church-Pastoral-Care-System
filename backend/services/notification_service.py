import logging
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

import httpx

from enums import NotificationChannel, NotificationStatus
from models import generate_uuid
from constants import API_MAX_RETRIES, API_RETRY_DELAYS, API_RETRY_TIMEOUT

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, db, whatsapp_gateway_url: Optional[str] = None):
        self._db = db
        self._whatsapp_url = whatsapp_gateway_url
    
    async def send_whatsapp(
        self,
        phone: str,
        message: str,
        church_id: str,
        member_id: Optional[str] = None,
        event_id: Optional[str] = None,
        retry: bool = True
    ) -> Dict[str, Any]:
        if not self._whatsapp_url:
            logger.warning("WhatsApp gateway not configured")
            return {"success": False, "error": "WhatsApp gateway not configured"}
        
        notification_id = generate_uuid()
        
        log_entry = {
            "id": notification_id,
            "church_id": church_id,
            "member_id": member_id,
            "event_id": event_id,
            "channel": NotificationChannel.WHATSAPP.value,
            "recipient": phone,
            "message": message[:500],
            "status": NotificationStatus.PENDING.value,
            "created_at": datetime.now(timezone.utc),
            "attempts": 0,
        }
        await self._db.notification_logs.insert_one(log_entry)
        
        asyncio.create_task(
            self._send_whatsapp_background(
                notification_id=notification_id,
                phone=phone,
                message=message,
                retry=retry
            )
        )
        
        return {"success": True, "notification_id": notification_id}
    
    async def _send_whatsapp_background(
        self,
        notification_id: str,
        phone: str,
        message: str,
        retry: bool = True
    ) -> None:
        max_attempts = API_MAX_RETRIES if retry else 1
        last_error = None
        
        for attempt in range(max_attempts):
            try:
                await self._db.notification_logs.update_one(
                    {"id": notification_id},
                    {"$inc": {"attempts": 1}}
                )
                
                from services.http_client import get_http_client
                client = await get_http_client()
                response = await client.post(
                    f"{self._whatsapp_url}/send/message",
                    json={"phone": phone, "message": message},
                    timeout=API_RETRY_TIMEOUT,
                )

                if response.status_code in (200, 201):
                    await self._db.notification_logs.update_one(
                        {"id": notification_id},
                        {"$set": {
                            "status": NotificationStatus.SENT.value,
                            "sent_at": datetime.now(timezone.utc),
                            "response": response.json() if response.text else None
                        }}
                    )
                    logger.info(f"WhatsApp sent to {phone}")
                    return

                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                    
            except httpx.TimeoutException as e:
                last_error = f"Timeout: {str(e)}"
            except httpx.ConnectError as e:
                last_error = f"Connection error: {str(e)}"
            except Exception as e:
                last_error = f"Error: {str(e)}"
            
            if attempt < max_attempts - 1:
                delay = API_RETRY_DELAYS[min(attempt, len(API_RETRY_DELAYS) - 1)]
                logger.warning(
                    f"WhatsApp to {phone} failed (attempt {attempt + 1}/{max_attempts}): "
                    f"{last_error}. Retrying in {delay}s..."
                )
                await asyncio.sleep(delay)
        
        await self._db.notification_logs.update_one(
            {"id": notification_id},
            {"$set": {
                "status": NotificationStatus.FAILED.value,
                "error": last_error,
                "failed_at": datetime.now(timezone.utc)
            }}
        )
        logger.error(f"WhatsApp to {phone} failed after {max_attempts} attempts: {last_error}")
    
    async def send_bulk_whatsapp(
        self,
        recipients: List[Dict[str, str]],
        church_id: str,
        delay_between: float = 0.5
    ) -> Dict[str, Any]:
        results = {"sent": 0, "failed": 0, "notification_ids": []}
        
        for recipient in recipients:
            result = await self.send_whatsapp(
                phone=recipient["phone"],
                message=recipient["message"],
                church_id=church_id,
                member_id=recipient.get("member_id"),
                event_id=recipient.get("event_id"),
            )
            
            if result["success"]:
                results["sent"] += 1
                results["notification_ids"].append(result["notification_id"])
            else:
                results["failed"] += 1
            
            await asyncio.sleep(delay_between)
        
        return results
    
    async def get_notification_status(
        self,
        notification_id: str,
        church_id: str
    ) -> Optional[Dict[str, Any]]:
        return await self._db.notification_logs.find_one(
            {"id": notification_id, "church_id": church_id},
            {"_id": 0}
        )
    
    async def get_recent_notifications(
        self,
        church_id: str,
        member_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {"church_id": church_id}
        if member_id:
            query["member_id"] = member_id
        
        cursor = self._db.notification_logs.find(query, {"_id": 0})
        cursor = cursor.sort("created_at", -1).limit(limit)
        
        return await cursor.to_list(length=limit)
