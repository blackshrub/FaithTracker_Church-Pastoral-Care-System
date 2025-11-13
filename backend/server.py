from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse, StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from enum import Enum
import uuid
from datetime import datetime, timezone, timedelta, date
import httpx
from PIL import Image
import io
import csv
import json as json_lib

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'pastoral_care_db')]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== ENUMS ====================

class EngagementStatus(str, Enum):
    ACTIVE = "active"
    AT_RISK = "at_risk"
    INACTIVE = "inactive"

class EventType(str, Enum):
    BIRTHDAY = "birthday"
    CHILDBIRTH = "childbirth"
    GRIEF_LOSS = "grief_loss"
    NEW_HOUSE = "new_house"
    ACCIDENT_ILLNESS = "accident_illness"
    HOSPITAL_VISIT = "hospital_visit"
    FINANCIAL_AID = "financial_aid"
    REGULAR_CONTACT = "regular_contact"

class GriefStage(str, Enum):
    MOURNING = "mourning"
    ONE_WEEK = "1_week"
    TWO_WEEKS = "2_weeks"
    ONE_MONTH = "1_month"
    THREE_MONTHS = "3_months"
    SIX_MONTHS = "6_months"
    ONE_YEAR = "1_year"

class AidType(str, Enum):
    EDUCATION = "education"
    MEDICAL = "medical"
    EMERGENCY = "emergency"
    HOUSING = "housing"
    FOOD = "food"
    FUNERAL_COSTS = "funeral_costs"
    OTHER = "other"

class NotificationChannel(str, Enum):
    WHATSAPP = "whatsapp"
    EMAIL = "email"

class NotificationStatus(str, Enum):
    SENT = "sent"
    FAILED = "failed"
    PENDING = "pending"

# ==================== MODELS ====================

class FamilyGroupCreate(BaseModel):
    group_name: str

class FamilyGroup(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    group_name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class MemberCreate(BaseModel):
    name: str
    phone: str
    family_group_id: Optional[str] = None
    family_group_name: Optional[str] = None  # For creating new family group
    external_member_id: Optional[str] = None
    notes: Optional[str] = None

class MemberUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    family_group_id: Optional[str] = None
    external_member_id: Optional[str] = None
    notes: Optional[str] = None

class Member(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    phone: str
    photo_url: Optional[str] = None
    family_group_id: Optional[str] = None
    last_contact_date: Optional[datetime] = None
    engagement_status: EngagementStatus = EngagementStatus.ACTIVE
    days_since_last_contact: int = 0
    external_member_id: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class VisitationLogEntry(BaseModel):
    visitor_name: str
    visit_date: date
    notes: str
    prayer_offered: bool = False

class CareEventCreate(BaseModel):
    member_id: str
    event_type: EventType
    event_date: date
    title: str
    description: Optional[str] = None
    
    # Grief support fields
    grief_relationship: Optional[str] = None
    mourning_service_date: Optional[date] = None
    
    # Hospital visit fields
    hospital_name: Optional[str] = None
    admission_date: Optional[date] = None
    discharge_date: Optional[date] = None
    initial_visitation: Optional[VisitationLogEntry] = None
    
    # Financial aid fields
    aid_type: Optional[AidType] = None
    aid_amount: Optional[float] = None
    aid_notes: Optional[str] = None

class CareEventUpdate(BaseModel):
    event_type: Optional[EventType] = None
    event_date: Optional[date] = None
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    
    # Hospital fields
    discharge_date: Optional[date] = None

class CareEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    member_id: str
    event_type: EventType
    event_date: date
    title: str
    description: Optional[str] = None
    completed: bool = False
    completed_at: Optional[datetime] = None
    
    # Grief support fields
    grief_relationship: Optional[str] = None
    mourning_service_date: Optional[date] = None
    grief_stage: Optional[GriefStage] = None
    
    # Hospital visit fields
    hospital_name: Optional[str] = None
    admission_date: Optional[date] = None
    discharge_date: Optional[date] = None
    visitation_log: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Financial aid fields
    aid_type: Optional[AidType] = None
    aid_amount: Optional[float] = None
    aid_notes: Optional[str] = None
    
    reminder_sent: bool = False
    reminder_sent_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class GriefSupport(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    care_event_id: str
    member_id: str
    stage: GriefStage
    scheduled_date: date
    completed: bool = False
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None
    reminder_sent: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class NotificationLog(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    care_event_id: Optional[str] = None
    grief_support_id: Optional[str] = None
    member_id: str
    channel: NotificationChannel
    recipient: str
    message: str
    status: NotificationStatus
    response_data: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ==================== UTILITY FUNCTIONS ====================

def calculate_engagement_status(last_contact: Optional[datetime]) -> tuple[EngagementStatus, int]:
    """Calculate engagement status and days since last contact"""
    if not last_contact:
        return EngagementStatus.INACTIVE, 999
    
    days_since = (datetime.now(timezone.utc) - last_contact).days
    
    if days_since < 30:
        return EngagementStatus.ACTIVE, days_since
    elif days_since < 60:
        return EngagementStatus.AT_RISK, days_since
    else:
        return EngagementStatus.INACTIVE, days_since

def generate_grief_timeline(mourning_date: date, care_event_id: str, member_id: str) -> List[Dict[str, Any]]:
    """Generate 6-stage grief support timeline"""
    stages = [
        (GriefStage.ONE_WEEK, 7),
        (GriefStage.TWO_WEEKS, 14),
        (GriefStage.ONE_MONTH, 30),
        (GriefStage.THREE_MONTHS, 90),
        (GriefStage.SIX_MONTHS, 180),
        (GriefStage.ONE_YEAR, 365),
    ]
    
    timeline = []
    for stage, days_offset in stages:
        scheduled_date = mourning_date + timedelta(days=days_offset)
        grief_support = {
            "id": str(uuid.uuid4()),
            "care_event_id": care_event_id,
            "member_id": member_id,
            "stage": stage,
            "scheduled_date": scheduled_date.isoformat(),
            "completed": False,
            "completed_at": None,
            "notes": None,
            "reminder_sent": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        timeline.append(grief_support)
    
    return timeline

async def send_whatsapp_message(phone: str, message: str, care_event_id: Optional[str] = None, 
                                grief_support_id: Optional[str] = None, member_id: str = None) -> Dict[str, Any]:
    """Send WhatsApp message via gateway"""
    try:
        whatsapp_url = os.environ.get('WHATSAPP_GATEWAY_URL')
        if not whatsapp_url:
            raise Exception("WhatsApp gateway URL not configured")
        
        phone_formatted = phone if phone.endswith('@s.whatsapp.net') else f"{phone}@s.whatsapp.net"
        
        payload = {
            "phone": phone_formatted,
            "message": message
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{whatsapp_url}/send/message", json=payload)
            response_data = response.json()
            
            # Log notification
            status = NotificationStatus.SENT if response_data.get('code') == 'SUCCESS' else NotificationStatus.FAILED
            
            log_entry = NotificationLog(
                care_event_id=care_event_id,
                grief_support_id=grief_support_id,
                member_id=member_id,
                channel=NotificationChannel.WHATSAPP,
                recipient=phone_formatted,
                message=message,
                status=status,
                response_data=response_data
            )
            
            await db.notification_logs.insert_one(log_entry.model_dump())
            
            return {
                "success": status == NotificationStatus.SENT,
                "message_id": response_data.get('results', {}).get('message_id'),
                "response": response_data
            }
    except Exception as e:
        logger.error(f"WhatsApp send error: {str(e)}")
        # Log failed attempt
        if member_id:
            log_entry = NotificationLog(
                care_event_id=care_event_id,
                grief_support_id=grief_support_id,
                member_id=member_id,
                channel=NotificationChannel.WHATSAPP,
                recipient=phone,
                message=message,
                status=NotificationStatus.FAILED,
                response_data={"error": str(e)}
            )
            await db.notification_logs.insert_one(log_entry.model_dump())
        
        return {
            "success": False,
            "error": str(e)
        }

# ==================== MEMBER ENDPOINTS ====================

@api_router.post("/members", response_model=Member)
async def create_member(member: MemberCreate):
    """Create a new member"""
    try:
        # Handle family group
        family_group_id = member.family_group_id
        
        if member.family_group_name and not family_group_id:
            # Create new family group
            family_group = FamilyGroup(group_name=member.family_group_name)
            await db.family_groups.insert_one(family_group.model_dump())
            family_group_id = family_group.id
        
        member_obj = Member(
            name=member.name,
            phone=member.phone,
            family_group_id=family_group_id,
            external_member_id=member.external_member_id,
            notes=member.notes
        )
        
        await db.members.insert_one(member_obj.model_dump())
        return member_obj
    except Exception as e:
        logger.error(f"Error creating member: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/members", response_model=List[Member])
async def list_members(
    engagement_status: Optional[EngagementStatus] = None,
    family_group_id: Optional[str] = None,
    search: Optional[str] = None
):
    """List all members with optional filters"""
    try:
        query = {}
        
        if engagement_status:
            query["engagement_status"] = engagement_status
        
        if family_group_id:
            query["family_group_id"] = family_group_id
        
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"phone": {"$regex": search, "$options": "i"}}
            ]
        
        members = await db.members.find(query, {"_id": 0}).to_list(1000)
        
        # Update engagement status for each member
        for member in members:
            if member.get('last_contact_date'):
                if isinstance(member['last_contact_date'], str):
                    member['last_contact_date'] = datetime.fromisoformat(member['last_contact_date'])
            
            status, days = calculate_engagement_status(member.get('last_contact_date'))
            member['engagement_status'] = status
            member['days_since_last_contact'] = days
        
        return members
    except Exception as e:
        logger.error(f"Error listing members: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/members/at-risk", response_model=List[Member])
async def list_at_risk_members():
    """Get members with no contact in 30+ days"""
    try:
        members = await db.members.find({}, {"_id": 0}).to_list(1000)
        
        at_risk_members = []
        for member in members:
            if member.get('last_contact_date'):
                if isinstance(member['last_contact_date'], str):
                    member['last_contact_date'] = datetime.fromisoformat(member['last_contact_date'])
            
            status, days = calculate_engagement_status(member.get('last_contact_date'))
            member['engagement_status'] = status
            member['days_since_last_contact'] = days
            
            if status in [EngagementStatus.AT_RISK, EngagementStatus.INACTIVE]:
                at_risk_members.append(member)
        
        # Sort by days descending
        at_risk_members.sort(key=lambda x: x['days_since_last_contact'], reverse=True)
        
        return at_risk_members
    except Exception as e:
        logger.error(f"Error getting at-risk members: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/members/{member_id}", response_model=Member)
async def get_member(member_id: str):
    """Get member by ID"""
    try:
        member = await db.members.find_one({"id": member_id}, {"_id": 0})
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")
        
        if member.get('last_contact_date'):
            if isinstance(member['last_contact_date'], str):
                member['last_contact_date'] = datetime.fromisoformat(member['last_contact_date'])
        
        status, days = calculate_engagement_status(member.get('last_contact_date'))
        member['engagement_status'] = status
        member['days_since_last_contact'] = days
        
        return member
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting member: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.put("/members/{member_id}", response_model=Member)
async def update_member(member_id: str, update: MemberUpdate):
    """Update member"""
    try:
        update_data = {k: v for k, v in update.model_dump().items() if v is not None}
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        result = await db.members.update_one(
            {"id": member_id},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Member not found")
        
        return await get_member(member_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating member: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.delete("/members/{member_id}")
async def delete_member(member_id: str):
    """Delete member"""
    try:
        result = await db.members.delete_one({"id": member_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Member not found")
        
        # Also delete related care events and grief support
        await db.care_events.delete_many({"member_id": member_id})
        await db.grief_support.delete_many({"member_id": member_id})
        
        return {"success": True, "message": "Member deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting member: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/members/{member_id}/photo")
async def upload_member_photo(member_id: str, file: UploadFile = File(...)):
    """Upload member profile photo"""
    try:
        # Check member exists
        member = await db.members.find_one({"id": member_id}, {"_id": 0})
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")
        
        # Validate file type
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Read and process image
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))
        
        # Resize to 400x400
        image = image.convert('RGB')
        image.thumbnail((400, 400), Image.Resampling.LANCZOS)
        
        # Save
        filename = f"{member_id}.jpg"
        filepath = Path(ROOT_DIR) / "uploads" / filename
        image.save(filepath, "JPEG", quality=85)
        
        # Update member record
        photo_url = f"/uploads/{filename}"
        await db.members.update_one(
            {"id": member_id},
            {"$set": {"photo_url": photo_url, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        
        return {"success": True, "photo_url": photo_url}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading photo: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== FAMILY GROUP ENDPOINTS ====================

@api_router.post("/family-groups", response_model=FamilyGroup)
async def create_family_group(group: FamilyGroupCreate):
    """Create a new family group"""
    try:
        family_group = FamilyGroup(group_name=group.group_name)
        await db.family_groups.insert_one(family_group.model_dump())
        return family_group
    except Exception as e:
        logger.error(f"Error creating family group: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/family-groups", response_model=List[FamilyGroup])
async def list_family_groups():
    """List all family groups"""
    try:
        groups = await db.family_groups.find({}, {"_id": 0}).to_list(1000)
        return groups
    except Exception as e:
        logger.error(f"Error listing family groups: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/family-groups/{group_id}")
async def get_family_group(group_id: str):
    """Get family group with its members"""
    try:
        group = await db.family_groups.find_one({"id": group_id}, {"_id": 0})
        if not group:
            raise HTTPException(status_code=404, detail="Family group not found")
        
        members = await db.members.find({"family_group_id": group_id}, {"_id": 0}).to_list(100)
        
        return {
            **group,
            "members": members
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting family group: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== CARE EVENT ENDPOINTS ====================

@api_router.post("/care-events", response_model=CareEvent)
async def create_care_event(event: CareEventCreate):
    """Create a new care event"""
    try:
        care_event = CareEvent(
            member_id=event.member_id,
            event_type=event.event_type,
            event_date=event.event_date,
            title=event.title,
            description=event.description,
            grief_relationship=event.grief_relationship,
            mourning_service_date=event.mourning_service_date,
            hospital_name=event.hospital_name,
            admission_date=event.admission_date,
            discharge_date=event.discharge_date,
            aid_type=event.aid_type,
            aid_amount=event.aid_amount,
            aid_notes=event.aid_notes
        )
        
        # Add initial visitation log if hospital visit
        if event.initial_visitation:
            care_event.visitation_log = [event.initial_visitation.model_dump()]
        
        await db.care_events.insert_one(care_event.model_dump())
        
        # Update member's last contact date
        await db.members.update_one(
            {"id": event.member_id},
            {"$set": {
                "last_contact_date": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        # Auto-generate grief support timeline if grief/loss event
        if event.event_type == EventType.GRIEF_LOSS and event.mourning_service_date:
            timeline = generate_grief_timeline(
                event.mourning_service_date,
                care_event.id,
                event.member_id
            )
            if timeline:
                await db.grief_support.insert_many(timeline)
        
        return care_event
    except Exception as e:
        logger.error(f"Error creating care event: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/care-events", response_model=List[CareEvent])
async def list_care_events(
    event_type: Optional[EventType] = None,
    member_id: Optional[str] = None,
    completed: Optional[bool] = None
):
    """List care events with optional filters"""
    try:
        query = {}
        
        if event_type:
            query["event_type"] = event_type
        
        if member_id:
            query["member_id"] = member_id
        
        if completed is not None:
            query["completed"] = completed
        
        events = await db.care_events.find(query, {"_id": 0}).sort("event_date", -1).to_list(1000)
        return events
    except Exception as e:
        logger.error(f"Error listing care events: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/care-events/{event_id}", response_model=CareEvent)
async def get_care_event(event_id: str):
    """Get care event by ID"""
    try:
        event = await db.care_events.find_one({"id": event_id}, {"_id": 0})
        if not event:
            raise HTTPException(status_code=404, detail="Care event not found")
        return event
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting care event: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.put("/care-events/{event_id}", response_model=CareEvent)
async def update_care_event(event_id: str, update: CareEventUpdate):
    """Update care event"""
    try:
        update_data = {k: v for k, v in update.model_dump().items() if v is not None}
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        result = await db.care_events.update_one(
            {"id": event_id},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Care event not found")
        
        return await get_care_event(event_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating care event: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.delete("/care-events/{event_id}")
async def delete_care_event(event_id: str):
    """Delete care event"""
    try:
        result = await db.care_events.delete_one({"id": event_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Care event not found")
        
        # Also delete related grief support stages
        await db.grief_support.delete_many({"care_event_id": event_id})
        
        return {"success": True, "message": "Care event deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting care event: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/care-events/{event_id}/complete")
async def complete_care_event(event_id: str):
    """Mark care event as completed"""
    try:
        result = await db.care_events.update_one(
            {"id": event_id},
            {"$set": {
                "completed": True,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Care event not found")
        
        return {"success": True, "message": "Care event marked as completed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing care event: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/care-events/{event_id}/send-reminder")
async def send_care_event_reminder(event_id: str):
    """Send WhatsApp reminder for care event"""
    try:
        event = await db.care_events.find_one({"id": event_id}, {"_id": 0})
        if not event:
            raise HTTPException(status_code=404, detail="Care event not found")
        
        member = await db.members.find_one({"id": event["member_id"]}, {"_id": 0})
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")
        
        church_name = os.environ.get('CHURCH_NAME', 'Church')
        message = f"Reminder from {church_name}: {event['title']} for {member['name']} on {event['event_date']}"
        if event.get('description'):
            message += f". {event['description']}"
        
        result = await send_whatsapp_message(
            member['phone'],
            message,
            care_event_id=event_id,
            member_id=event['member_id']
        )
        
        if result['success']:
            await db.care_events.update_one(
                {"id": event_id},
                {"$set": {
                    "reminder_sent": True,
                    "reminder_sent_at": datetime.now(timezone.utc).isoformat()
                }}
            )
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending reminder: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/care-events/{event_id}/visitation-log")
async def add_visitation_log(event_id: str, entry: VisitationLogEntry):
    """Add visitation log entry to hospital visit"""
    try:
        event = await db.care_events.find_one({"id": event_id}, {"_id": 0})
        if not event:
            raise HTTPException(status_code=404, detail="Care event not found")
        
        log_entry = entry.model_dump()
        log_entry['visit_date'] = log_entry['visit_date'].isoformat() if isinstance(log_entry['visit_date'], date) else log_entry['visit_date']
        
        await db.care_events.update_one(
            {"id": event_id},
            {
                "$push": {"visitation_log": log_entry},
                "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
            }
        )
        
        return {"success": True, "message": "Visitation log added"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding visitation log: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/care-events/hospital/due-followup")
async def get_hospital_followup_due():
    """Get hospital events needing follow-up"""
    try:
        # Find hospital visits with discharge date but no completion
        events = await db.care_events.find({
            "event_type": EventType.HOSPITAL_VISIT,
            "discharge_date": {"$ne": None},
            "completed": False
        }, {"_id": 0}).to_list(100)
        
        followup_due = []
        today = date.today()
        
        for event in events:
            discharge = event.get('discharge_date')
            if isinstance(discharge, str):
                discharge = date.fromisoformat(discharge)
            
            days_since_discharge = (today - discharge).days
            
            # Check if follow-up is due (3 days, 1 week, 2 weeks)
            if days_since_discharge in [3, 7, 14]:
                followup_due.append({
                    **event,
                    "days_since_discharge": days_since_discharge,
                    "followup_reason": f"{days_since_discharge} days post-discharge"
                })
        
        return followup_due
    except Exception as e:
        logger.error(f"Error getting hospital followup: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== GRIEF SUPPORT ENDPOINTS ====================

@api_router.get("/grief-support", response_model=List[GriefSupport])
async def list_grief_support(completed: Optional[bool] = None):
    \"\"\"List all grief support stages\"\"\"
    try:
        query = {}
        if completed is not None:
            query[\"completed\"] = completed
        
        stages = await db.grief_support.find(query, {\"_id\": 0}).sort(\"scheduled_date\", 1).to_list(1000)
        return stages
    except Exception as e:
        logger.error(f\"Error listing grief support: {str(e)}\")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get(\"/grief-support/member/{member_id}\", response_model=List[GriefSupport])
async def get_member_grief_timeline(member_id: str):
    \"\"\"Get grief timeline for specific member\"\"\"
    try:
        timeline = await db.grief_support.find(\n            {\"member_id\": member_id},\n            {\"_id\": 0}\n        ).sort(\"scheduled_date\", 1).to_list(100)\n        \n        return timeline\n    except Exception as e:\n        logger.error(f\"Error getting member grief timeline: {str(e)}\")\n        raise HTTPException(status_code=500, detail=str(e))

@api_router.post(\"/grief-support/{stage_id}/complete\")\nasync def complete_grief_stage(stage_id: str, notes: Optional[str] = None):\n    \"\"\"Mark grief stage as completed with notes\"\"\"\n    try:\n        update_data = {\n            \"completed\": True,\n            \"completed_at\": datetime.now(timezone.utc).isoformat(),\n            \"updated_at\": datetime.now(timezone.utc).isoformat()\n        }\n        \n        if notes:\n            update_data[\"notes\"] = notes\n        \n        result = await db.grief_support.update_one(\n            {\"id\": stage_id},\n            {\"$set\": update_data}\n        )\n        \n        if result.matched_count == 0:\n            raise HTTPException(status_code=404, detail=\"Grief stage not found\")\n        \n        # Update member's last contact date\n        stage = await db.grief_support.find_one({\"id\": stage_id}, {\"_id\": 0})\n        if stage:\n            await db.members.update_one(\n                {\"id\": stage[\"member_id\"]},\n                {\"$set\": {\"last_contact_date\": datetime.now(timezone.utc).isoformat()}}\n            )\n        \n        return {\"success\": True, \"message\": \"Grief stage marked as completed\"}\n    except HTTPException:\n        raise\n    except Exception as e:\n        logger.error(f\"Error completing grief stage: {str(e)}\")\n        raise HTTPException(status_code=500, detail=str(e))

@api_router.post(\"/grief-support/{stage_id}/send-reminder\")\nasync def send_grief_reminder(stage_id: str):\n    \"\"\"Send WhatsApp reminder for grief stage\"\"\"\n    try:\n        stage = await db.grief_support.find_one({\"id\": stage_id}, {\"_id\": 0})\n        if not stage:\n            raise HTTPException(status_code=404, detail=\"Grief stage not found\")\n        \n        member = await db.members.find_one({\"id\": stage[\"member_id\"]}, {\"_id\": 0})\n        if not member:\n            raise HTTPException(status_code=404, detail=\"Member not found\")\n        \n        church_name = os.environ.get('CHURCH_NAME', 'Church')\n        stage_names = {\n            \"1_week\": \"1 week\",\n            \"2_weeks\": \"2 weeks\",\n            \"1_month\": \"1 month\",\n            \"3_months\": \"3 months\",\n            \"6_months\": \"6 months\",\n            \"1_year\": \"1 year\"\n        }\n        stage_name = stage_names.get(stage[\"stage\"], stage[\"stage\"])\n        \n        message = f\"{church_name} - Grief Support Check-in: It has been {stage_name} since your loss. We are thinking of you and praying for you. Please reach out if you need support.\"\n        \n        result = await send_whatsapp_message(\n            member['phone'],\n            message,\n            grief_support_id=stage_id,\n            member_id=stage['member_id']\n        )\n        \n        if result['success']:\n            await db.grief_support.update_one(\n                {\"id\": stage_id},\n                {\"$set\": {\"reminder_sent\": True, \"updated_at\": datetime.now(timezone.utc).isoformat()}}\n            )\n        \n        return result\n    except HTTPException:\n        raise\n    except Exception as e:\n        logger.error(f\"Error sending grief reminder: {str(e)}\")\n        raise HTTPException(status_code=500, detail=str(e))

# ==================== FINANCIAL AID ENDPOINTS ====================

@api_router.get(\"/financial-aid/summary\")\nasync def get_financial_aid_summary(\n    start_date: Optional[str] = None,\n    end_date: Optional[str] = None\n):\n    \"\"\"Get financial aid summary by type and date range\"\"\"\n    try:\n        query = {\"event_type\": EventType.FINANCIAL_AID}\n        \n        if start_date:\n            query[\"event_date\"] = {\"$gte\": start_date}\n        if end_date:\n            if \"event_date\" in query:\n                query[\"event_date\"][\"$lte\"] = end_date\n            else:\n                query[\"event_date\"] = {\"$lte\": end_date}\n        \n        events = await db.care_events.find(query, {\"_id\": 0}).to_list(1000)\n        \n        # Calculate totals by type\n        totals_by_type = {}\n        total_amount = 0\n        \n        for event in events:\n            aid_type = event.get('aid_type', 'other')\n            amount = event.get('aid_amount', 0) or 0\n            \n            if aid_type not in totals_by_type:\n                totals_by_type[aid_type] = {\"count\": 0, \"total_amount\": 0}\n            \n            totals_by_type[aid_type][\"count\"] += 1\n            totals_by_type[aid_type][\"total_amount\"] += amount\n            total_amount += amount\n        \n        return {\n            \"total_amount\": total_amount,\n            \"total_count\": len(events),\n            \"by_type\": totals_by_type\n        }\n    except Exception as e:\n        logger.error(f\"Error getting financial aid summary: {str(e)}\")\n        raise HTTPException(status_code=500, detail=str(e))

@api_router.get(\"/financial-aid/member/{member_id}\")\nasync def get_member_financial_aid(member_id: str):\n    \"\"\"Get all financial aid given to a member\"\"\"\n    try:\n        aid_events = await db.care_events.find({\n            \"member_id\": member_id,\n            \"event_type\": EventType.FINANCIAL_AID\n        }, {\"_id\": 0}).sort(\"event_date\", -1).to_list(100)\n        \n        total_amount = sum(event.get('aid_amount', 0) or 0 for event in aid_events)\n        \n        return {\n            \"member_id\": member_id,\n            \"total_amount\": total_amount,\n            \"aid_count\": len(aid_events),\n            \"aid_history\": aid_events\n        }\n    except Exception as e:\n        logger.error(f\"Error getting member financial aid: {str(e)}\")\n        raise HTTPException(status_code=500, detail=str(e))

# ==================== DASHBOARD ENDPOINTS ====================

@api_router.get(\"/dashboard/stats\")\nasync def get_dashboard_stats():\n    \"\"\"Get overall dashboard statistics\"\"\"\n    try:\n        total_members = await db.members.count_documents({})\n        \n        # Active grief support count\n        active_grief = await db.grief_support.count_documents({\"completed\": False})\n        \n        # At-risk members\n        members = await db.members.find({}, {\"_id\": 0, \"last_contact_date\": 1}).to_list(1000)\n        at_risk_count = 0\n        for member in members:\n            last_contact = member.get('last_contact_date')\n            if last_contact and isinstance(last_contact, str):\n                last_contact = datetime.fromisoformat(last_contact)\n            status, _ = calculate_engagement_status(last_contact)\n            if status in [EngagementStatus.AT_RISK, EngagementStatus.INACTIVE]:\n                at_risk_count += 1\n        \n        # This month's financial aid\n        today = date.today()\n        month_start = today.replace(day=1).isoformat()\n        month_aid = await db.care_events.find({\n            \"event_type\": EventType.FINANCIAL_AID,\n            \"event_date\": {\"$gte\": month_start}\n        }, {\"_id\": 0, \"aid_amount\": 1}).to_list(1000)\n        \n        total_aid = sum(event.get('aid_amount', 0) or 0 for event in month_aid)\n        \n        return {\n            \"total_members\": total_members,\n            \"active_grief_support\": active_grief,\n            \"members_at_risk\": at_risk_count,\n            \"month_financial_aid\": total_aid\n        }\n    except Exception as e:\n        logger.error(f\"Error getting dashboard stats: {str(e)}\")\n        raise HTTPException(status_code=500, detail=str(e))

@api_router.get(\"/dashboard/upcoming\")\nasync def get_upcoming_events(days: int = 7):\n    \"\"\"Get upcoming events for next N days\"\"\"\n    try:\n        today = date.today()\n        future_date = today + timedelta(days=days)\n        \n        events = await db.care_events.find({\n            \"event_date\": {\n                \"$gte\": today.isoformat(),\n                \"$lte\": future_date.isoformat()\n            },\n            \"completed\": False\n        }, {\"_id\": 0}).sort(\"event_date\", 1).to_list(100)\n        \n        # Get member info for each event\n        for event in events:\n            member = await db.members.find_one({\"id\": event[\"member_id\"]}, {\"_id\": 0, \"name\": 1, \"phone\": 1})\n            if member:\n                event[\"member_name\"] = member[\"name\"]\n        \n        return events\n    except Exception as e:\n        logger.error(f\"Error getting upcoming events: {str(e)}\")\n        raise HTTPException(status_code=500, detail=str(e))

@api_router.get(\"/dashboard/grief-active\")\nasync def get_active_grief_support():\n    \"\"\"Get members currently in grief support timeline\"\"\"\n    try:\n        # Get all incomplete grief stages\n        stages = await db.grief_support.find(\n            {\"completed\": False},\n            {\"_id\": 0}\n        ).sort(\"scheduled_date\", 1).to_list(100)\n        \n        # Group by member\n        member_grief = {}\n        for stage in stages:\n            member_id = stage[\"member_id\"]\n            if member_id not in member_grief:\n                member = await db.members.find_one({\"id\": member_id}, {\"_id\": 0, \"name\": 1, \"phone\": 1})\n                member_grief[member_id] = {\n                    \"member_id\": member_id,\n                    \"member_name\": member[\"name\"] if member else \"Unknown\",\n                    \"stages\": []\n                }\n            \n            member_grief[member_id][\"stages\"].append(stage)\n        \n        return list(member_grief.values())\n    except Exception as e:\n        logger.error(f\"Error getting active grief support: {str(e)}\")\n        raise HTTPException(status_code=500, detail=str(e))

@api_router.get(\"/dashboard/recent-activity\")\nasync def get_recent_activity(limit: int = 20):\n    \"\"\"Get recent care events\"\"\"\n    try:\n        events = await db.care_events.find(\n            {},\n            {\"_id\": 0}\n        ).sort(\"created_at\", -1).limit(limit).to_list(limit)\n        \n        # Add member names\n        for event in events:\n            member = await db.members.find_one({\"id\": event[\"member_id\"]}, {\"_id\": 0, \"name\": 1})\n            if member:\n                event[\"member_name\"] = member[\"name\"]\n        \n        return events\n    except Exception as e:\n        logger.error(f\"Error getting recent activity: {str(e)}\")\n        raise HTTPException(status_code=500, detail=str(e))

# ==================== ANALYTICS ENDPOINTS ====================

@api_router.get(\"/analytics/engagement-trends\")\nasync def get_engagement_trends(days: int = 30):\n    \"\"\"Get engagement trends over time\"\"\"\n    try:\n        start_date = date.today() - timedelta(days=days)\n        \n        events = await db.care_events.find({\n            \"event_date\": {\"$gte\": start_date.isoformat()}\n        }, {\"_id\": 0, \"event_date\": 1}).to_list(1000)\n        \n        # Count by date\n        date_counts = {}\n        for event in events:\n            event_date = event.get('event_date')\n            if isinstance(event_date, str):\n                event_date = event_date[:10]  # Get just the date part\n            date_counts[event_date] = date_counts.get(event_date, 0) + 1\n        \n        # Format for chart\n        trends = [{\"date\": d, \"count\": c} for d, c in sorted(date_counts.items())]\n        \n        return trends\n    except Exception as e:\n        logger.error(f\"Error getting engagement trends: {str(e)}\")\n        raise HTTPException(status_code=500, detail=str(e))

@api_router.get(\"/analytics/care-events-by-type\")\nasync def get_care_events_by_type():\n    \"\"\"Get distribution of care events by type\"\"\"\n    try:\n        events = await db.care_events.find({}, {\"_id\": 0, \"event_type\": 1}).to_list(10000)\n        \n        type_counts = {}\n        for event in events:\n            event_type = event.get('event_type')\n            type_counts[event_type] = type_counts.get(event_type, 0) + 1\n        \n        return [{\"type\": t, \"count\": c} for t, c in type_counts.items()]\n    except Exception as e:\n        logger.error(f\"Error getting events by type: {str(e)}\")\n        raise HTTPException(status_code=500, detail=str(e))

@api_router.get(\"/analytics/grief-completion-rate\")\nasync def get_grief_completion_rate():\n    \"\"\"Get grief support completion rate\"\"\"\n    try:\n        total_stages = await db.grief_support.count_documents({})\n        completed_stages = await db.grief_support.count_documents({\"completed\": True})\n        \n        completion_rate = (completed_stages / total_stages * 100) if total_stages > 0 else 0\n        \n        return {\n            \"total_stages\": total_stages,\n            \"completed_stages\": completed_stages,\n            \"pending_stages\": total_stages - completed_stages,\n            \"completion_rate\": round(completion_rate, 2)\n        }\n    except Exception as e:\n        logger.error(f\"Error getting grief completion rate: {str(e)}\")\n        raise HTTPException(status_code=500, detail=str(e))

# ==================== IMPORT/EXPORT ENDPOINTS ====================

@api_router.post(\"/import/members/csv\")\nasync def import_members_csv(file: UploadFile = File(...)):\n    \"\"\"Import members from CSV file\"\"\"\n    try:\n        contents = await file.read()\n        decoded = contents.decode('utf-8')\n        reader = csv.DictReader(io.StringIO(decoded))\n        \n        imported_count = 0\n        errors = []\n        \n        for row in reader:\n            try:\n                # Create member from CSV row\n                member = Member(\n                    name=row.get('name', ''),\n                    phone=row.get('phone', ''),\n                    external_member_id=row.get('external_member_id'),\n                    notes=row.get('notes')\n                )\n                \n                await db.members.insert_one(member.model_dump())\n                imported_count += 1\n            except Exception as e:\n                errors.append(f\"Row error: {str(e)}\")\n        \n        return {\n            \"success\": True,\n            \"imported_count\": imported_count,\n            \"errors\": errors\n        }\n    except Exception as e:\n        logger.error(f\"Error importing CSV: {str(e)}\")\n        raise HTTPException(status_code=500, detail=str(e))

@api_router.post(\"/import/members/json\")\nasync def import_members_json(members: List[Dict[str, Any]]):\n    \"\"\"Import members from JSON array\"\"\"\n    try:\n        imported_count = 0\n        errors = []\n        \n        for member_data in members:\n            try:\n                member = Member(\n                    name=member_data.get('name', ''),\n                    phone=member_data.get('phone', ''),\n                    external_member_id=member_data.get('external_member_id'),\n                    notes=member_data.get('notes')\n                )\n                \n                await db.members.insert_one(member.model_dump())\n                imported_count += 1\n            except Exception as e:\n                errors.append(f\"Member error: {str(e)}\")\n        \n        return {\n            \"success\": True,\n            \"imported_count\": imported_count,\n            \"errors\": errors\n        }\n    except Exception as e:\n        logger.error(f\"Error importing JSON: {str(e)}\")\n        raise HTTPException(status_code=500, detail=str(e))

@api_router.get(\"/export/members/csv\")\nasync def export_members_csv():\n    \"\"\"Export members to CSV file\"\"\"\n    try:\n        members = await db.members.find({}, {\"_id\": 0}).to_list(10000)\n        \n        output = io.StringIO()\n        if members:\n            fieldnames = ['id', 'name', 'phone', 'family_group_id', 'external_member_id', \n                         'last_contact_date', 'engagement_status', 'days_since_last_contact', 'notes']\n            writer = csv.DictWriter(output, fieldnames=fieldnames)\n            writer.writeheader()\n            \n            for member in members:\n                # Update engagement status\n                if member.get('last_contact_date'):\n                    if isinstance(member['last_contact_date'], str):\n                        member['last_contact_date'] = datetime.fromisoformat(member['last_contact_date'])\n                \n                status, days = calculate_engagement_status(member.get('last_contact_date'))\n                member['engagement_status'] = status\n                member['days_since_last_contact'] = days\n                \n                # Convert dates to strings\n                if member.get('last_contact_date'):\n                    member['last_contact_date'] = member['last_contact_date'].isoformat()\n                \n                writer.writerow({k: member.get(k, '') for k in fieldnames})\n        \n        output.seek(0)\n        return StreamingResponse(\n            iter([output.getvalue()]),\n            media_type=\"text/csv\",\n            headers={\"Content-Disposition\": \"attachment; filename=members.csv\"}\n        )\n    except Exception as e:\n        logger.error(f\"Error exporting members CSV: {str(e)}\")\n        raise HTTPException(status_code=500, detail=str(e))

@api_router.get(\"/export/care-events/csv\")\nasync def export_care_events_csv():\n    \"\"\"Export care events to CSV file\"\"\"\n    try:\n        events = await db.care_events.find({}, {\"_id\": 0}).to_list(10000)\n        \n        output = io.StringIO()\n        if events:\n            fieldnames = ['id', 'member_id', 'event_type', 'event_date', 'title', 'description', \n                         'completed', 'aid_type', 'aid_amount', 'hospital_name']\n            writer = csv.DictWriter(output, fieldnames=fieldnames)\n            writer.writeheader()\n            \n            for event in events:\n                # Convert dates\n                if event.get('event_date'):\n                    event['event_date'] = str(event['event_date'])\n                \n                writer.writerow({k: event.get(k, '') for k in fieldnames})\n        \n        output.seek(0)\n        return StreamingResponse(\n            iter([output.getvalue()]),\n            media_type=\"text/csv\",\n            headers={\"Content-Disposition\": \"attachment; filename=care_events.csv\"}\n        )\n    except Exception as e:\n        logger.error(f\"Error exporting care events CSV: {str(e)}\")\n        raise HTTPException(status_code=500, detail=str(e))

# ==================== INTEGRATION TEST ENDPOINTS ====================

class WhatsAppTestRequest(BaseModel):
    phone: str
    message: str

class WhatsAppTestResponse(BaseModel):
    success: bool
    message: str
    details: Optional[dict] = None

@api_router.post(\"/integrations/ping/whatsapp\", response_model=WhatsAppTestResponse)
async def test_whatsapp_integration(request: WhatsAppTestRequest):
    \"\"\"Test WhatsApp gateway integration by sending a test message\"\"\"
    try:\n        result = await send_whatsapp_message(request.phone, request.message)\n        \n        if result['success']:\n            return WhatsAppTestResponse(\n                success=True,\n                message=f\"✅ WhatsApp message sent successfully to {request.phone}!\",\n                details=result\n            )\n        else:\n            return WhatsAppTestResponse(\n                success=False,\n                message=f\"❌ Failed to send WhatsApp message: {result.get('error', 'Unknown error')}\",\n                details=result\n            )\n    except Exception as e:\n        logger.error(f\"WhatsApp integration error: {str(e)}\")\n        return WhatsAppTestResponse(\n            success=False,\n            message=f\"❌ Error: {str(e)}\",\n            details={\"error\": str(e)}\n        )\n\n@api_router.get(\"/integrations/ping/email\")\nasync def test_email_integration():\n    \"\"\"Email integration test - currently pending provider configuration\"\"\"\n    return {\n        \"success\": False,\n        \"message\": \"📧 Email integration pending provider configuration. Currently WhatsApp-only mode.\",\n        \"pending_provider\": True\n    }\n\n# ==================== STATIC FILES ====================\n\n@api_router.get(\"/uploads/{filename}\")\nasync def get_uploaded_file(filename: str):\n    \"\"\"Serve uploaded files\"\"\"\n    filepath = Path(ROOT_DIR) / \"uploads\" / filename\n    if not filepath.exists():\n        raise HTTPException(status_code=404, detail=\"File not found\")\n    return FileResponse(filepath)\n\n# Include the router in the main app\napp.include_router(api_router)\n\napp.add_middleware(\n    CORSMiddleware,\n    allow_credentials=True,\n    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),\n    allow_methods=[\"*\"],\n    allow_headers=[\"*\"],\n)\n\n@app.on_event(\"shutdown\")\nasync def shutdown_db_client():\n    client.close()"