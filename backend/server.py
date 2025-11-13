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

# Continued in next message due to length...