from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Query, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse, StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional, Dict, Any
from enum import Enum
import uuid
from datetime import datetime, timezone, timedelta, date
import httpx
from PIL import Image
import io
import csv
import json as json_lib
from jose import JWTError, jwt
from passlib.context import CryptContext
from scheduler import start_scheduler, stop_scheduler, daily_reminder_job

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
    ACCIDENT_ILLNESS = "accident_illness"  # Merged hospital_visit into this
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

class UserRole(str, Enum):
    FULL_ADMIN = "full_admin"  # Can access all campuses
    CAMPUS_ADMIN = "campus_admin"  # Can manage their campus only
    PASTOR = "pastor"  # Regular pastoral care staff

# ==================== AUTH CONFIGURATION ====================

SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'your-secret-key-change-in-production')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if user is None:
        raise credentials_exception
    return user

async def get_current_admin(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") not in [UserRole.FULL_ADMIN, UserRole.CAMPUS_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user

async def get_full_admin(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != UserRole.FULL_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Full admin privileges required"
        )
    return current_user

def get_campus_filter(current_user: dict):
    """Get campus filter for queries based on user role"""
    if current_user.get("role") == UserRole.FULL_ADMIN:
        return {}  # Full admin sees all campuses
    elif current_user.get("campus_id"):
        return {"campus_id": current_user["campus_id"]}  # Campus-specific user
    else:
        return {"campus_id": None}  # Fallback

# ==================== MODELS ====================

class CampusCreate(BaseModel):
    campus_name: str
    location: Optional[str] = None

class Campus(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    campus_name: str
    location: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class FamilyGroupCreate(BaseModel):
    group_name: str
    campus_id: str

class FamilyGroup(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    group_name: str
    campus_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class MemberCreate(BaseModel):
    name: str
    phone: str
    campus_id: str
    family_group_id: Optional[str] = None
    family_group_name: Optional[str] = None
    external_member_id: Optional[str] = None
    notes: Optional[str] = None
    birth_date: Optional[date] = None
    email: Optional[str] = None
    address: Optional[str] = None
    category: Optional[str] = None
    gender: Optional[str] = None
    blood_type: Optional[str] = None
    marital_status: Optional[str] = None
    membership_status: Optional[str] = None
    age: Optional[int] = None

class MemberUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    family_group_id: Optional[str] = None
    external_member_id: Optional[str] = None
    notes: Optional[str] = None
    birth_date: Optional[date] = None
    email: Optional[str] = None
    address: Optional[str] = None
    category: Optional[str] = None
    gender: Optional[str] = None
    blood_type: Optional[str] = None
    marital_status: Optional[str] = None
    membership_status: Optional[str] = None

class Member(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    phone: str
    campus_id: str
    photo_url: Optional[str] = None
    family_group_id: Optional[str] = None
    last_contact_date: Optional[datetime] = None
    engagement_status: EngagementStatus = EngagementStatus.ACTIVE
    days_since_last_contact: int = 0
    external_member_id: Optional[str] = None
    notes: Optional[str] = None
    birth_date: Optional[date] = None
    email: Optional[str] = None
    address: Optional[str] = None
    category: Optional[str] = None
    gender: Optional[str] = None
    blood_type: Optional[str] = None
    marital_status: Optional[str] = None
    membership_status: Optional[str] = None
    age: Optional[int] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class VisitationLogEntry(BaseModel):
    visitor_name: str
    visit_date: date
    notes: str
    prayer_offered: bool = False

class CareEventCreate(BaseModel):
    member_id: str
    campus_id: str
    event_type: EventType
    event_date: date
    title: str
    description: Optional[str] = None
    
    # Grief support fields
    grief_relationship: Optional[str] = None
    
    # Accident/illness fields (merged from hospital)
    hospital_name: Optional[str] = None
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
    campus_id: str
    event_type: EventType
    event_date: date
    title: str
    description: Optional[str] = None
    completed: bool = False
    completed_at: Optional[datetime] = None
    
    # Grief support fields (only relationship, use event_date as mourning date)
    grief_relationship: Optional[str] = None
    grief_stage: Optional[GriefStage] = None
    
    # Accident/illness fields (merged from hospital, only hospital_name, use event_date as admission)
    hospital_name: Optional[str] = None
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
    campus_id: str
    stage: GriefStage
    scheduled_date: date
    completed: bool = False
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None
    reminder_sent: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AccidentFollowup(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    care_event_id: str
    member_id: str
    campus_id: str
    stage: str  # "first_followup", "second_followup", "final_followup"
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
    member_id: Optional[str] = None
    campus_id: Optional[str] = None
    pastoral_team_user_id: Optional[str] = None  # If sent to pastoral team
    channel: NotificationChannel
    recipient: str
    message: str
    status: NotificationStatus
    response_data: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# User Authentication Models
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: UserRole = UserRole.PASTOR
    campus_id: Optional[str] = None  # Required for campus_admin and pastor, null for full_admin
    phone: str  # Pastoral team member's phone for receiving reminders

class UserLogin(BaseModel):
    email: EmailStr
    password: str
    campus_id: Optional[str] = None  # Campus selection at login

class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    name: str
    role: UserRole
    campus_id: Optional[str] = None
    phone: str  # For receiving pastoral care task reminders
    hashed_password: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserResponse(BaseModel):
    id: str
    email: EmailStr
    name: str
    role: UserRole
    campus_id: Optional[str] = None
    campus_name: Optional[str] = None
    phone: str
    is_active: bool
    created_at: datetime

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

# ==================== UTILITY FUNCTIONS ====================

def calculate_engagement_status(last_contact: Optional[datetime]) -> tuple[EngagementStatus, int]:
    """Calculate engagement status and days since last contact"""
    if not last_contact:
        return EngagementStatus.INACTIVE, 999
    
    # Handle string dates
    if isinstance(last_contact, str):
        try:
            last_contact = datetime.fromisoformat(last_contact)
        except:
            return EngagementStatus.INACTIVE, 999
    
    # Make timezone-aware if needed
    if last_contact.tzinfo is None:
        last_contact = last_contact.replace(tzinfo=timezone.utc)
    
    now = datetime.now(timezone.utc)
    days_since = (now - last_contact).days
    
    if days_since < 30:
        return EngagementStatus.ACTIVE, days_since
    elif days_since < 60:
        return EngagementStatus.AT_RISK, days_since
    else:
        return EngagementStatus.INACTIVE, days_since

def generate_accident_followup_timeline(event_date: date, care_event_id: str, member_id: str, campus_id: str) -> List[Dict[str, Any]]:
    """Generate 3-stage accident/illness follow-up timeline"""
    # Get settings from localStorage or use defaults
    stages = [
        ("first_followup", 3),
        ("second_followup", 7),
        ("final_followup", 14),
    ]
    
    timeline = []
    for stage, days_offset in stages:
        scheduled_date = event_date + timedelta(days=days_offset)
        followup_stage = {
            "id": str(uuid.uuid4()),
            "care_event_id": care_event_id,
            "member_id": member_id,
            "campus_id": campus_id,
            "stage": stage,
            "scheduled_date": scheduled_date.isoformat(),
            "completed": False,
            "completed_at": None,
            "notes": None,
            "reminder_sent": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        timeline.append(followup_stage)
    
    return timeline

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

# ==================== CAMPUS ENDPOINTS ====================

@api_router.post("/campuses", response_model=Campus)
async def create_campus(campus: CampusCreate, current_admin: dict = Depends(get_full_admin)):
    """Create a new campus (full admin only)"""
    try:
        campus_obj = Campus(
            campus_name=campus.campus_name,
            location=campus.location
        )
        await db.campuses.insert_one(campus_obj.model_dump())
        return campus_obj
    except Exception as e:
        logger.error(f"Error creating campus: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/campuses", response_model=List[Campus])
async def list_campuses():
    """List all campuses (public for login selection)"""
    try:
        campuses = await db.campuses.find({"is_active": True}, {"_id": 0}).to_list(100)
        return campuses
    except Exception as e:
        logger.error(f"Error listing campuses: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/campuses/{campus_id}", response_model=Campus)
async def get_campus(campus_id: str):
    """Get campus by ID"""
    try:
        campus = await db.campuses.find_one({"id": campus_id}, {"_id": 0})
        if not campus:
            raise HTTPException(status_code=404, detail="Campus not found")
        return campus
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting campus: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.put("/campuses/{campus_id}", response_model=Campus)
async def update_campus(campus_id: str, update: CampusCreate, current_admin: dict = Depends(get_full_admin)):
    """Update campus (full admin only)"""
    try:
        result = await db.campuses.update_one(
            {"id": campus_id},
            {"$set": {
                **update.model_dump(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Campus not found")
        return await get_campus(campus_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating campus: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== AUTHENTICATION ENDPOINTS ====================

@api_router.post("/auth/register", response_model=UserResponse)
async def register_user(user_data: UserCreate, current_admin: dict = Depends(get_current_admin)):
    """Register a new user (admin only)"""
    try:
        # Check if email already exists
        existing = await db.users.find_one({"email": user_data.email}, {"_id": 0})
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Validate campus_id for non-full-admin users
        if user_data.role != UserRole.FULL_ADMIN and not user_data.campus_id:
            raise HTTPException(status_code=400, detail="campus_id required for campus admin and pastor roles")
        
        user = User(
            email=user_data.email,
            name=user_data.name,
            role=user_data.role,
            campus_id=user_data.campus_id,
            phone=user_data.phone,
            hashed_password=get_password_hash(user_data.password)
        )
        
        await db.users.insert_one(user.model_dump())
        
        campus_name = None
        if user.campus_id:
            campus = await db.campuses.find_one({"id": user.campus_id}, {"_id": 0})
            campus_name = campus["campus_name"] if campus else None
        
        return UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role,
            campus_id=user.campus_id,
            campus_name=campus_name,
            phone=user.phone,
            is_active=user.is_active,
            created_at=user.created_at
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(user_data: UserLogin):
    """Login and get access token"""
    try:
        user = await db.users.find_one({"email": user_data.email}, {"_id": 0})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        if not verify_password(user_data.password, user["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        if not user.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is disabled"
            )
        
        # For campus-specific users, validate campus_id
        if user.get("role") in [UserRole.CAMPUS_ADMIN, UserRole.PASTOR]:
            if user_data.campus_id and user["campus_id"] != user_data.campus_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have access to this campus"
                )
        
        access_token = create_access_token(data={"sub": user["id"]})
        
        campus_name = None
        if user.get("campus_id"):
            campus = await db.campuses.find_one({"id": user["campus_id"]}, {"_id": 0})
            campus_name = campus["campus_name"] if campus else None
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=UserResponse(
                id=user["id"],
                email=user["email"],
                name=user["name"],
                role=user["role"],
                campus_id=user.get("campus_id"),
                campus_name=campus_name,
                phone=user["phone"],
                is_active=user.get("is_active", True),
                created_at=user["created_at"]
            )
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error logging in: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current logged-in user info"""
    campus_name = None
    if current_user.get("campus_id"):
        campus = await db.campuses.find_one({"id": current_user["campus_id"]}, {"_id": 0})
        campus_name = campus["campus_name"] if campus else None
    
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        name=current_user["name"],
        role=current_user["role"],
        campus_id=current_user.get("campus_id"),
        campus_name=campus_name,
        phone=current_user["phone"],
        is_active=current_user.get("is_active", True),
        created_at=current_user["created_at"]
    )

@api_router.get("/users", response_model=List[UserResponse])
async def list_users(current_admin: dict = Depends(get_current_admin)):
    """List all users (admin only)"""
    try:
        query = {}
        # Campus admins only see users in their campus
        if current_admin.get("role") == UserRole.CAMPUS_ADMIN:
            query["campus_id"] = current_admin["campus_id"]
        
        users = await db.users.find(query, {"_id": 0}).to_list(100)
        
        result = []
        for u in users:
            campus_name = None
            if u.get("campus_id"):
                campus = await db.campuses.find_one({"id": u["campus_id"]}, {"_id": 0})
                campus_name = campus["campus_name"] if campus else None
            
            result.append(UserResponse(
                id=u["id"],
                email=u["email"],
                name=u["name"],
                role=u["role"],
                campus_id=u.get("campus_id"),
                campus_name=campus_name,
                phone=u["phone"],
                is_active=u.get("is_active", True),
                created_at=u["created_at"]
            ))
        
        return result
    except Exception as e:
        logger.error(f"Error listing users: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.delete("/users/{user_id}")
async def delete_user(user_id: str, current_admin: dict = Depends(get_current_admin)):
    """Delete a user (admin only)"""
    try:
        # Prevent deleting self
        if user_id == current_admin["id"]:
            raise HTTPException(status_code=400, detail="Cannot delete your own account")
        
        result = await db.users.delete_one({"id": user_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {"success": True, "message": "User deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== MEMBER ENDPOINTS ====================

@api_router.post("/members", response_model=Member)
async def create_member(member: MemberCreate, current_user: dict = Depends(get_current_user)):
    """Create a new member"""
    try:
        # For campus-specific users, enforce their campus
        campus_id = member.campus_id
        if current_user.get("role") in [UserRole.CAMPUS_ADMIN, UserRole.PASTOR]:
            campus_id = current_user["campus_id"]
        
        # Handle family group
        family_group_id = member.family_group_id
        
        if member.family_group_name and not family_group_id:
            # Create new family group
            family_group = FamilyGroup(group_name=member.family_group_name, campus_id=campus_id)
            await db.family_groups.insert_one(family_group.model_dump())
            family_group_id = family_group.id
        
        member_obj = Member(
            name=member.name,
            phone=member.phone,
            campus_id=campus_id,
            family_group_id=family_group_id,
            external_member_id=member.external_member_id,
            notes=member.notes,
            birth_date=member.birth_date,
            email=member.email,
            address=member.address
        )
        
        member_dict = member_obj.model_dump()
        if member_dict.get('birth_date'):
            member_dict['birth_date'] = member_dict['birth_date'].isoformat() if isinstance(member_dict['birth_date'], date) else member_dict['birth_date']
        
        await db.members.insert_one(member_dict)
        return member_obj
    except Exception as e:
        logger.error(f"Error creating member: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/members", response_model=List[Member])
async def list_members(
    engagement_status: Optional[EngagementStatus] = None,
    family_group_id: Optional[str] = None,
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """List all members with optional filters"""
    try:
        query = get_campus_filter(current_user)
        
        if engagement_status:
            query["engagement_status"] = engagement_status
        
        if family_group_id:
            query["family_group_id"] = family_group_id
        
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"phone": {"$regex": search, "$options": "i"}}
            ]
        
        members = await db.members.find(query, {"_id": 0}).to_list(2000)
        
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
async def create_care_event(event: CareEventCreate, current_user: dict = Depends(get_current_user)):
    """Create a new care event"""
    try:
        # For campus-specific users, enforce their campus
        campus_id = event.campus_id
        if current_user.get("role") in [UserRole.CAMPUS_ADMIN, UserRole.PASTOR]:
            campus_id = current_user["campus_id"]
        
        care_event = CareEvent(
            member_id=event.member_id,
            campus_id=campus_id,
            event_type=event.event_type,
            event_date=event.event_date,
            title=event.title,
            description=event.description,
            grief_relationship=event.grief_relationship,
            hospital_name=event.hospital_name,
            aid_type=event.aid_type,
            aid_amount=event.aid_amount,
            aid_notes=event.aid_notes
        )
        
        # Add initial visitation log if hospital visit
        if event.initial_visitation:
            care_event.visitation_log = [event.initial_visitation.model_dump()]
        
        # Serialize for MongoDB
        event_dict = care_event.model_dump()
        event_dict['event_date'] = event_dict['event_date'].isoformat() if isinstance(event_dict['event_date'], date) else event_dict['event_date']
        if event_dict.get('mourning_service_date'):
            event_dict['mourning_service_date'] = event_dict['mourning_service_date'].isoformat() if isinstance(event_dict['mourning_service_date'], date) else event_dict['mourning_service_date']
        if event_dict.get('admission_date'):
            event_dict['admission_date'] = event_dict['admission_date'].isoformat() if isinstance(event_dict['admission_date'], date) else event_dict['admission_date']
        if event_dict.get('discharge_date'):
            event_dict['discharge_date'] = event_dict['discharge_date'].isoformat() if isinstance(event_dict['discharge_date'], date) else event_dict['discharge_date']
        
        await db.care_events.insert_one(event_dict)
        
        # Update member's last contact date
        await db.members.update_one(
            {"id": event.member_id},
            {"$set": {
                "last_contact_date": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        # Auto-generate grief support timeline if grief/loss event (use event_date as mourning date)
        if event.event_type == EventType.GRIEF_LOSS:
            timeline = generate_grief_timeline(
                event.event_date,  # Use event_date as mourning date
                care_event.id,
                event.member_id
            )
            if timeline:
                # Add campus_id to all timeline stages
                for stage in timeline:
                    stage['campus_id'] = campus_id
                await db.grief_support.insert_many(timeline)
                logger.info(f"Generated {len(timeline)} grief support stages for member {event.member_id}")
        
        # Auto-generate accident/illness follow-up timeline
        if event.event_type == EventType.ACCIDENT_ILLNESS:
            timeline = generate_accident_followup_timeline(
                event.event_date,
                care_event.id,
                event.member_id,
                campus_id
            )
            if timeline:
                await db.accident_followup.insert_many(timeline)
                logger.info(f"Generated {len(timeline)} accident follow-up stages for member {event.member_id}")
        
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
    """Get accident/illness events needing follow-up"""
    try:
        # Find accident/illness events (merged from hospital) with discharge date but no completion
        events = await db.care_events.find({
            "event_type": "accident_illness",  # Updated from hospital_visit
            "completed": False
        }, {"_id": 0}).to_list(100)
        
        followup_due = []
        today = date.today()
        
        for event in events:
            # Use event_date instead of discharge_date for follow-up calculation
            event_date = event.get('event_date')
            if isinstance(event_date, str):
                event_date = date.fromisoformat(event_date)
            
            days_since_event = (today - event_date).days
            
            # Check if follow-up is due (3 days, 7 days, 14 days after event)
            if days_since_event in [3, 7, 14]:
                followup_due.append({
                    **event,
                    "days_since_event": days_since_event,
                    "followup_reason": f"{days_since_event} days after accident/illness"
                })
        
        return followup_due
    except Exception as e:
        logger.error(f"Error getting hospital followup: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== GRIEF SUPPORT ENDPOINTS ====================

@api_router.get("/grief-support", response_model=List[GriefSupport])
async def list_grief_support(completed: Optional[bool] = None):
    """List all grief support stages"""
    try:
        query = {}
        if completed is not None:
            query["completed"] = completed
        
        stages = await db.grief_support.find(query, {"_id": 0}).sort("scheduled_date", 1).to_list(1000)
        return stages
    except Exception as e:
        logger.error(f"Error listing grief support: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/grief-support/member/{member_id}", response_model=List[GriefSupport])
async def get_member_grief_timeline(member_id: str):
    """Get grief timeline for specific member"""
    try:
        timeline = await db.grief_support.find(
            {"member_id": member_id},
            {"_id": 0}
        ).sort("scheduled_date", 1).to_list(100)
        
        return timeline
    except Exception as e:
        logger.error(f"Error getting member grief timeline: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/grief-support/{stage_id}/complete")
async def complete_grief_stage(stage_id: str, notes: Optional[str] = None):
    """Mark grief stage as completed with notes"""
    try:
        update_data = {
            "completed": True,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        if notes:
            update_data["notes"] = notes
        
        result = await db.grief_support.update_one(
            {"id": stage_id},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Grief stage not found")
        
        # Update member's last contact date
        stage = await db.grief_support.find_one({"id": stage_id}, {"_id": 0})
        if stage:
            await db.members.update_one(
                {"id": stage["member_id"]},
                {"$set": {"last_contact_date": datetime.now(timezone.utc).isoformat()}}
            )
        
        return {"success": True, "message": "Grief stage marked as completed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing grief stage: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/grief-support/{stage_id}/send-reminder")
async def send_grief_reminder(stage_id: str):
    """Send WhatsApp reminder for grief stage"""
    try:
        stage = await db.grief_support.find_one({"id": stage_id}, {"_id": 0})
        if not stage:
            raise HTTPException(status_code=404, detail="Grief stage not found")
        
        member = await db.members.find_one({"id": stage["member_id"]}, {"_id": 0})
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")
        
        church_name = os.environ.get('CHURCH_NAME', 'Church')
        stage_names = {
            "1_week": "1 week",
            "2_weeks": "2 weeks",
            "1_month": "1 month",
            "3_months": "3 months",
            "6_months": "6 months",
            "1_year": "1 year"
        }
        stage_name = stage_names.get(stage["stage"], stage["stage"])
        
        message = f"{church_name} - Grief Support Check-in: It has been {stage_name} since your loss. We are thinking of you and praying for you. Please reach out if you need support."
        
        result = await send_whatsapp_message(
            member['phone'],
            message,
            grief_support_id=stage_id,
            member_id=stage['member_id']
        )
        
        if result['success']:
            await db.grief_support.update_one(
                {"id": stage_id},
                {"$set": {"reminder_sent": True, "updated_at": datetime.now(timezone.utc).isoformat()}}
            )
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending grief reminder: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/accident-followup/member/{member_id}")
async def get_member_accident_timeline(member_id: str):
    """Get accident follow-up timeline for specific member"""
    try:
        timeline = await db.accident_followup.find(
            {"member_id": member_id},
            {"_id": 0}
        ).sort("scheduled_date", 1).to_list(100)
        
        return timeline
    except Exception as e:
        logger.error(f"Error getting member accident timeline: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/accident-followup/{stage_id}/complete")
async def complete_accident_stage(stage_id: str, notes: Optional[str] = None):
    """Mark accident follow-up stage as completed"""
    try:
        update_data = {
            "completed": True,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        if notes:
            update_data["notes"] = notes
        
        result = await db.accident_followup.update_one(
            {"id": stage_id},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Accident follow-up stage not found")
        
        # Update member's last contact date
        stage = await db.accident_followup.find_one({"id": stage_id}, {"_id": 0})
        if stage:
            await db.members.update_one(
                {"id": stage["member_id"]},
                {"$set": {"last_contact_date": datetime.now(timezone.utc).isoformat()}}
            )
        
        return {"success": True, "message": "Accident follow-up stage completed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing accident stage: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== FINANCIAL AID ENDPOINTS ====================

@api_router.get("/financial-aid/summary")
async def get_financial_aid_summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Get financial aid summary by type and date range"""
    try:
        query = {"event_type": EventType.FINANCIAL_AID}
        
        if start_date:
            query["event_date"] = {"$gte": start_date}
        if end_date:
            if "event_date" in query:
                query["event_date"]["$lte"] = end_date
            else:
                query["event_date"] = {"$lte": end_date}
        
        events = await db.care_events.find(query, {"_id": 0}).to_list(1000)
        
        # Calculate totals by type
        totals_by_type = {}
        total_amount = 0
        
        for event in events:
            aid_type = event.get('aid_type', 'other')
            amount = event.get('aid_amount', 0) or 0
            
            if aid_type not in totals_by_type:
                totals_by_type[aid_type] = {"count": 0, "total_amount": 0}
            
            totals_by_type[aid_type]["count"] += 1
            totals_by_type[aid_type]["total_amount"] += amount
            total_amount += amount
        
        return {
            "total_amount": total_amount,
            "total_count": len(events),
            "by_type": totals_by_type
        }
    except Exception as e:
        logger.error(f"Error getting financial aid summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/financial-aid/member/{member_id}")
async def get_member_financial_aid(member_id: str):
    """Get all financial aid given to a member"""
    try:
        aid_events = await db.care_events.find({
            "member_id": member_id,
            "event_type": EventType.FINANCIAL_AID
        }, {"_id": 0}).sort("event_date", -1).to_list(100)
        
        total_amount = sum(event.get('aid_amount', 0) or 0 for event in aid_events)
        
        return {
            "member_id": member_id,
            "total_amount": total_amount,
            "aid_count": len(aid_events),
            "aid_history": aid_events
        }
    except Exception as e:
        logger.error(f"Error getting member financial aid: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== DASHBOARD ENDPOINTS ====================

@api_router.get("/dashboard/stats")
async def get_dashboard_stats():
    """Get overall dashboard statistics"""
    try:
        total_members = await db.members.count_documents({})
        
        # Active grief support count
        active_grief = await db.grief_support.count_documents({"completed": False})
        
        # At-risk members
        members = await db.members.find({}, {"_id": 0, "last_contact_date": 1}).to_list(1000)
        at_risk_count = 0
        for member in members:
            last_contact = member.get('last_contact_date')
            if last_contact and isinstance(last_contact, str):
                last_contact = datetime.fromisoformat(last_contact)
            status, _ = calculate_engagement_status(last_contact)
            if status in [EngagementStatus.AT_RISK, EngagementStatus.INACTIVE]:
                at_risk_count += 1
        
        # This month's financial aid
        today = date.today()
        month_start = today.replace(day=1).isoformat()
        month_aid = await db.care_events.find({
            "event_type": EventType.FINANCIAL_AID,
            "event_date": {"$gte": month_start}
        }, {"_id": 0, "aid_amount": 1}).to_list(1000)
        
        total_aid = sum(event.get('aid_amount', 0) or 0 for event in month_aid)
        
        return {
            "total_members": total_members,
            "active_grief_support": active_grief,
            "members_at_risk": at_risk_count,
            "month_financial_aid": total_aid
        }
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/dashboard/upcoming")
async def get_upcoming_events(days: int = 7):
    """Get upcoming events for next N days"""
    try:
        today = date.today()
        future_date = today + timedelta(days=days)
        
        events = await db.care_events.find({
            "event_date": {
                "$gte": today.isoformat(),
                "$lte": future_date.isoformat()
            },
            "completed": False
        }, {"_id": 0}).sort("event_date", 1).to_list(100)
        
        # Get member info for each event
        for event in events:
            member = await db.members.find_one({"id": event["member_id"]}, {"_id": 0, "name": 1, "phone": 1})
            if member:
                event["member_name"] = member["name"]
        
        return events
    except Exception as e:
        logger.error(f"Error getting upcoming events: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/dashboard/grief-active")
async def get_active_grief_support():
    """Get members currently in grief support timeline"""
    try:
        # Get all incomplete grief stages
        stages = await db.grief_support.find(
            {"completed": False},
            {"_id": 0}
        ).sort("scheduled_date", 1).to_list(100)
        
        # Group by member
        member_grief = {}
        for stage in stages:
            member_id = stage["member_id"]
            if member_id not in member_grief:
                member = await db.members.find_one({"id": member_id}, {"_id": 0, "name": 1, "phone": 1})
                member_grief[member_id] = {
                    "member_id": member_id,
                    "member_name": member["name"] if member else "Unknown",
                    "stages": []
                }
            
            member_grief[member_id]["stages"].append(stage)
        
        return list(member_grief.values())
    except Exception as e:
        logger.error(f"Error getting active grief support: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/dashboard/recent-activity")
async def get_recent_activity(limit: int = 20):
    """Get recent care events"""
    try:
        events = await db.care_events.find(
            {},
            {"_id": 0}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        
        # Add member names
        for event in events:
            member = await db.members.find_one({"id": event["member_id"]}, {"_id": 0, "name": 1})
            if member:
                event["member_name"] = member["name"]
        
        return events
    except Exception as e:
        logger.error(f"Error getting recent activity: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== ANALYTICS ENDPOINTS ====================

@api_router.get("/analytics/engagement-trends")
async def get_engagement_trends(days: int = 30):
    """Get engagement trends over time"""
    try:
        start_date = date.today() - timedelta(days=days)
        
        events = await db.care_events.find({
            "event_date": {"$gte": start_date.isoformat()}
        }, {"_id": 0, "event_date": 1}).to_list(1000)
        
        # Count by date
        date_counts = {}
        for event in events:
            event_date = event.get('event_date')
            if isinstance(event_date, str):
                event_date = event_date[:10]  # Get just the date part
            date_counts[event_date] = date_counts.get(event_date, 0) + 1
        
        # Format for chart
        trends = [{"date": d, "count": c} for d, c in sorted(date_counts.items())]
        
        return trends
    except Exception as e:
        logger.error(f"Error getting engagement trends: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/analytics/care-events-by-type")
async def get_care_events_by_type():
    """Get distribution of care events by type"""
    try:
        events = await db.care_events.find({}, {"_id": 0, "event_type": 1}).to_list(10000)
        
        type_counts = {}
        for event in events:
            event_type = event.get('event_type')
            type_counts[event_type] = type_counts.get(event_type, 0) + 1
        
        return [{"type": t, "count": c} for t, c in type_counts.items()]
    except Exception as e:
        logger.error(f"Error getting events by type: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/analytics/grief-completion-rate")
async def get_grief_completion_rate():
    """Get grief support completion rate"""
    try:
        total_stages = await db.grief_support.count_documents({})
        completed_stages = await db.grief_support.count_documents({"completed": True})
        
        completion_rate = (completed_stages / total_stages * 100) if total_stages > 0 else 0
        
        return {
            "total_stages": total_stages,
            "completed_stages": completed_stages,
            "pending_stages": total_stages - completed_stages,
            "completion_rate": round(completion_rate, 2)
        }
    except Exception as e:
        logger.error(f"Error getting grief completion rate: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== API SYNC ENDPOINTS ====================

@api_router.post("/sync/members/from-api")
async def sync_members_from_external_api(
    api_url: str,
    api_key: Optional[str] = None,
    current_admin: dict = Depends(get_current_admin)
):
    """Continuously sync members from external API"""
    try:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(api_url, headers=headers)
            external_members = response.json()
        
        synced_count = 0
        errors = []
        
        for ext_member in external_members:
            try:
                # Check if member exists by external_member_id
                existing = await db.members.find_one(
                    {"external_member_id": ext_member.get('id')},
                    {"_id": 0}
                )
                
                if existing:
                    # Update existing member
                    await db.members.update_one(
                        {"id": existing["id"]},
                        {"$set": {
                            "name": ext_member.get('name'),
                            "phone": ext_member.get('phone'),
                            "email": ext_member.get('email'),
                            "updated_at": datetime.now(timezone.utc).isoformat()
                        }}
                    )
                else:
                    # Create new member
                    member = Member(
                        name=ext_member.get('name'),
                        phone=ext_member.get('phone'),
                        campus_id=ext_member.get('campus_id', current_admin.get('campus_id')),
                        external_member_id=ext_member.get('id'),
                        email=ext_member.get('email')
                    )
                    member_dict = member.model_dump()
                    if member_dict.get('birth_date'):
                        member_dict['birth_date'] = member_dict['birth_date'].isoformat()
                    await db.members.insert_one(member_dict)
                
                synced_count += 1
            except Exception as e:
                errors.append(f"Error syncing {ext_member.get('name')}: {str(e)}")
        
        return {
            "success": True,
            "synced_count": synced_count,
            "total_received": len(external_members),
            "errors": errors
        }
    except Exception as e:
        logger.error(f"API sync error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/sync/members/webhook")
async def member_sync_webhook(current_admin: dict = Depends(get_current_admin)):
    """Webhook URL for external system to push member updates"""
    return {
        "webhook_url": f"{os.environ.get('BACKEND_URL', 'http://localhost:8001')}/api/sync/members/from-api",
        "method": "POST",
        "description": "External system can POST member data here for continuous sync"
    }

# ==================== IMPORT/EXPORT ENDPOINTS ====================

@api_router.post("/import/members/csv")
async def import_members_csv(file: UploadFile = File(...)):
    """Import members from CSV file"""
    try:
        contents = await file.read()
        decoded = contents.decode('utf-8')
        reader = csv.DictReader(io.StringIO(decoded))
        
        imported_count = 0
        errors = []
        
        for row in reader:
            try:
                # Create member from CSV row
                member = Member(
                    name=row.get('name', ''),
                    phone=row.get('phone', ''),
                    external_member_id=row.get('external_member_id'),
                    notes=row.get('notes')
                )
                
                await db.members.insert_one(member.model_dump())
                imported_count += 1
            except Exception as e:
                errors.append(f"Row error: {str(e)}")
        
        return {
            "success": True,
            "imported_count": imported_count,
            "errors": errors
        }
    except Exception as e:
        logger.error(f"Error importing CSV: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/import/members/json")
async def import_members_json(members: List[Dict[str, Any]]):
    """Import members from JSON array"""
    try:
        imported_count = 0
        errors = []
        
        for member_data in members:
            try:
                member = Member(
                    name=member_data.get('name', ''),
                    phone=member_data.get('phone', ''),
                    external_member_id=member_data.get('external_member_id'),
                    notes=member_data.get('notes')
                )
                
                await db.members.insert_one(member.model_dump())
                imported_count += 1
            except Exception as e:
                errors.append(f"Member error: {str(e)}")
        
        return {
            "success": True,
            "imported_count": imported_count,
            "errors": errors
        }
    except Exception as e:
        logger.error(f"Error importing JSON: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/export/members/csv")
async def export_members_csv():
    """Export members to CSV file"""
    try:
        members = await db.members.find({}, {"_id": 0}).to_list(10000)
        
        output = io.StringIO()
        if members:
            fieldnames = ['id', 'name', 'phone', 'family_group_id', 'external_member_id', 
                         'last_contact_date', 'engagement_status', 'days_since_last_contact', 'notes']
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            
            for member in members:
                # Update engagement status
                if member.get('last_contact_date'):
                    if isinstance(member['last_contact_date'], str):
                        member['last_contact_date'] = datetime.fromisoformat(member['last_contact_date'])
                
                status, days = calculate_engagement_status(member.get('last_contact_date'))
                member['engagement_status'] = status
                member['days_since_last_contact'] = days
                
                # Convert dates to strings
                if member.get('last_contact_date'):
                    member['last_contact_date'] = member['last_contact_date'].isoformat()
                
                writer.writerow({k: member.get(k, '') for k in fieldnames})
        
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=members.csv"}
        )
    except Exception as e:
        logger.error(f"Error exporting members CSV: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/export/care-events/csv")
async def export_care_events_csv():
    """Export care events to CSV file"""
    try:
        events = await db.care_events.find({}, {"_id": 0}).to_list(10000)
        
        output = io.StringIO()
        if events:
            fieldnames = ['id', 'member_id', 'event_type', 'event_date', 'title', 'description', 
                         'completed', 'aid_type', 'aid_amount', 'hospital_name']
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            
            for event in events:
                # Convert dates
                if event.get('event_date'):
                    event['event_date'] = str(event['event_date'])
                
                writer.writerow({k: event.get(k, '') for k in fieldnames})
        
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=care_events.csv"}
        )
    except Exception as e:
        logger.error(f"Error exporting care events CSV: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== INTEGRATION TEST ENDPOINTS ====================

class WhatsAppTestRequest(BaseModel):
    phone: str
    message: str

class WhatsAppTestResponse(BaseModel):
    success: bool
    message: str
    details: Optional[dict] = None

@api_router.post("/integrations/ping/whatsapp", response_model=WhatsAppTestResponse)
async def test_whatsapp_integration(request: WhatsAppTestRequest):
    """Test WhatsApp gateway integration by sending a test message"""
    try:
        result = await send_whatsapp_message(request.phone, request.message, member_id="test")
        
        if result['success']:
            return WhatsAppTestResponse(
                success=True,
                message=f"✅ WhatsApp message sent successfully to {request.phone}!",
                details=result
            )
        else:
            return WhatsAppTestResponse(
                success=False,
                message=f"❌ Failed to send WhatsApp message: {result.get('error', 'Unknown error')}",
                details=result
            )
    except Exception as e:
        logger.error(f"WhatsApp integration error: {str(e)}")
        return WhatsAppTestResponse(
            success=False,
            message=f"❌ Error: {str(e)}",
            details={"error": str(e)}
        )

@api_router.get("/integrations/ping/email")
async def test_email_integration():
    """Email integration test - currently pending provider configuration"""
    return {
        "success": False,
        "message": "📧 Email integration pending provider configuration. Currently WhatsApp-only mode.",
        "pending_provider": True
    }

# ==================== NOTIFICATION LOGS ENDPOINTS ====================

@api_router.get("/notification-logs")
async def get_notification_logs(
    limit: int = Query(100, le=500),
    status: Optional[NotificationStatus] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get notification logs with filtering"""
    try:
        query = get_campus_filter(current_user)
        
        if status:
            query["status"] = status
        
        logs = await db.notification_logs.find(
            query,
            {"_id": 0}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        
        return logs
    except Exception as e:
        logger.error(f"Error getting notification logs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== AUTOMATED REMINDERS ENDPOINTS ====================

@api_router.post("/reminders/run-now")
async def run_reminders_now(current_admin: dict = Depends(get_current_admin)):
    """Manually trigger daily reminder job (admin only)"""
    try:
        logger.info(f"Manual reminder trigger by {current_admin['email']}")
        await daily_reminder_job()
        return {"success": True, "message": "Automated reminders executed successfully"}
    except Exception as e:
        logger.error(f"Error running reminders: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/reminders/stats")
async def get_reminder_stats():
    """Get reminder statistics for today"""
    try:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Count notifications sent today
        logs = await db.notification_logs.find({
            "created_at": {"$gte": today_start.isoformat()}
        }, {"_id": 0}).to_list(1000)
        
        sent_count = sum(1 for log in logs if log.get('status') == 'sent')
        failed_count = sum(1 for log in logs if log.get('status') == 'failed')
        
        # Count pending grief stages due today
        today = date.today()
        grief_due = await db.grief_support.count_documents({
            "scheduled_date": today.isoformat(),
            "completed": False
        })
        
        # Count birthdays in next 7 days
        future_date = today + timedelta(days=7)
        birthdays_upcoming = await db.care_events.count_documents({
            "event_type": "birthday",
            "event_date": {"$gte": today.isoformat(), "$lte": future_date.isoformat()},
            "completed": False
        })
        
        return {
            "reminders_sent_today": sent_count,
            "reminders_failed_today": failed_count,
            "grief_stages_due_today": grief_due,
            "birthdays_next_7_days": birthdays_upcoming
        }
    except Exception as e:
        logger.error(f"Error getting reminder stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== STATIC FILES ====================

@api_router.get("/uploads/{filename}")
async def get_uploaded_file(filename: str):
    """Serve uploaded files"""
    filepath = Path(ROOT_DIR) / "uploads" / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(filepath)

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def create_default_admin():
    """Create default full admin user if none exists"""
    try:
        admin_count = await db.users.count_documents({"role": UserRole.FULL_ADMIN})
        if admin_count == 0:
            default_admin = User(
                email="admin@gkbj.church",
                name="Full Administrator",
                role=UserRole.FULL_ADMIN,
                campus_id=None,  # Full admin has access to all campuses
                phone="6281290080025",  # Admin's phone for receiving system alerts
                hashed_password=get_password_hash("admin123"),
                is_active=True
            )
            await db.users.insert_one(default_admin.model_dump())
            logger.info("Default full admin user created: admin@gkbj.church / admin123")
        
        # Start automated reminder scheduler
        start_scheduler()
    except Exception as e:
        logger.error(f"Error in startup: {str(e)}")

@app.on_event("shutdown")
async def shutdown_db_client():
    stop_scheduler()
    client.close()