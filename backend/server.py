from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Query, Depends, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse, StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import secrets
import hmac
import hashlib
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional, Dict, Any
from enum import Enum
import uuid
from datetime import datetime, timezone, timedelta, date
from zoneinfo import ZoneInfo

# Jakarta timezone (UTC+7)
JAKARTA_TZ = ZoneInfo("Asia/Jakarta")

def now_jakarta():
    """Get current time in Jakarta timezone"""
    return datetime.now(JAKARTA_TZ)

def to_jakarta(dt):
    """Convert datetime to Jakarta timezone"""
    if dt.tzinfo is None:
        # Assume UTC if no timezone
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(JAKARTA_TZ)

def get_jakarta_date_str():
    """Get current date in Jakarta as YYYY-MM-DD string"""
    return now_jakarta().strftime('%Y-%m-%d')
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
    DISCONNECTED = "disconnected"

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

class ScheduleFrequency(str, Enum):
    ONE_TIME = "one_time"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ANNUALLY = "annually"

class WeekDay(str, Enum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class ActivityActionType(str, Enum):
    COMPLETE_TASK = "complete_task"
    IGNORE_TASK = "ignore_task"
    UNIGNORE_TASK = "unignore_task"
    SEND_REMINDER = "send_reminder"
    STOP_SCHEDULE = "stop_schedule"
    CLEAR_IGNORED = "clear_ignored"
    CREATE_MEMBER = "create_member"
    UPDATE_MEMBER = "update_member"
    DELETE_MEMBER = "delete_member"
    CREATE_CARE_EVENT = "create_care_event"
    UPDATE_CARE_EVENT = "update_care_event"
    DELETE_CARE_EVENT = "delete_care_event"

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
    timezone: str = "Asia/Jakarta"  # Default to UTC+7

class Campus(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    campus_name: str
    location: Optional[str] = None
    timezone: str = "Asia/Jakarta"  # Campus timezone (default UTC+7)
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
    phone: Optional[str] = None
    campus_id: str
    family_group_id: Optional[str] = None
    family_group_name: Optional[str] = None
    external_member_id: Optional[str] = None
    notes: Optional[str] = None
    birth_date: Optional[date] = None
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
    phone: Optional[str] = None  # Some members may not have phone numbers
    campus_id: str
    photo_url: Optional[str] = None
    family_group_id: Optional[str] = None
    last_contact_date: Optional[datetime] = None
    engagement_status: EngagementStatus = EngagementStatus.ACTIVE
    days_since_last_contact: int = 0
    is_archived: bool = False
    archived_at: Optional[datetime] = None
    archived_reason: Optional[str] = None
    external_member_id: Optional[str] = None
    notes: Optional[str] = None
    birth_date: Optional[date] = None
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
    completed_by_user_id: Optional[str] = None
    completed_by_user_name: Optional[str] = None
    
    ignored: bool = False
    ignored_at: Optional[datetime] = None
    ignored_by: Optional[str] = None
    ignored_by_name: Optional[str] = None
    
    created_by_user_id: Optional[str] = None
    created_by_user_name: Optional[str] = None
    
    # Member information (enriched from members collection)
    member_name: Optional[str] = None
    
    # Grief support fields (only relationship, use event_date as mourning date)
    grief_relationship: Optional[str] = None
    grief_stage: Optional[GriefStage] = None
    grief_stage_id: Optional[str] = None  # Link to grief_support stage (for timeline entries)
    
    # Accident/illness fields (merged from hospital, only hospital_name, use event_date as admission)
    hospital_name: Optional[str] = None
    accident_stage_id: Optional[str] = None  # Link to accident_followup stage (for timeline entries)
    visitation_log: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Financial aid fields
    aid_type: Optional[AidType] = None
    aid_amount: Optional[float] = None
    aid_notes: Optional[str] = None
    
    reminder_sent: bool = False
    reminder_sent_at: Optional[datetime] = None
    reminder_sent_by_user_id: Optional[str] = None
    reminder_sent_by_user_name: Optional[str] = None
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
    ignored: bool = False
    ignored_at: Optional[datetime] = None
    ignored_by: Optional[str] = None
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
    ignored: bool = False
    ignored_at: Optional[datetime] = None
    ignored_by: Optional[str] = None
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

class FinancialAidSchedule(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    member_id: str
    campus_id: str
    title: str
    aid_type: AidType
    aid_amount: float
    frequency: ScheduleFrequency
    
    # Date fields
    start_date: date
    end_date: Optional[date] = None  # None means no end
    
    # Weekly specific
    day_of_week: Optional[WeekDay] = None
    
    # Monthly specific
    day_of_month: Optional[int] = None  # 1-31
    
    # Annual specific
    month_of_year: Optional[int] = None  # 1-12
    
    # Tracking
    is_active: bool = True
    ignored_occurrences: List[str] = []  # List of dates (YYYY-MM-DD) that were ignored
    next_occurrence: date
    occurrences_completed: int = 0
    created_by: str  # User ID who created the schedule
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# User Authentication Models
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: UserRole = UserRole.PASTOR
    campus_id: Optional[str] = None  # Required for campus_admin and pastor, null for full_admin
    phone: str  # Pastoral team member's phone for receiving reminders

class UserUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    password: Optional[str] = None
    role: Optional[UserRole] = None
    campus_id: Optional[str] = None

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
    photo_url: Optional[str] = None
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
    photo_url: Optional[str] = None
    is_active: bool
    created_at: datetime

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse


class ActivityLog(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    campus_id: str
    user_id: str
    user_name: str
    user_photo_url: Optional[str] = None
    action_type: ActivityActionType
    member_id: Optional[str] = None
    member_name: Optional[str] = None
    care_event_id: Optional[str] = None
    event_type: Optional[EventType] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ActivityLogResponse(BaseModel):
    id: str
    campus_id: str
    user_id: str
    user_name: str
    user_photo_url: Optional[str] = None
    action_type: str
    member_id: Optional[str] = None
    member_name: Optional[str] = None
    care_event_id: Optional[str] = None
    event_type: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime


# ==================== SYNC MODELS ====================

class SyncConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    campus_id: str  # FaithTracker campus ID
    core_church_id: Optional[str] = None  # Core system's church_id (for webhook matching)
    sync_method: str = "polling"  # "polling" or "webhook"
    api_base_url: str  # e.g., https://faithflow.yourdomain.com
    api_email: str
    api_password: str  # Encrypted in database
    webhook_secret: str = Field(default_factory=lambda: secrets.token_urlsafe(32))  # For signature verification
    is_enabled: bool = False
    polling_interval_hours: int = 6  # For polling method
    reconciliation_enabled: bool = False  # Daily 3 AM reconciliation (recommended for webhook mode)
    reconciliation_time: str = "03:00"  # Time for daily reconciliation (HH:MM format)
    
    # Sync filters (optional - empty means sync all)
    filter_mode: str = "include"  # "include" or "exclude"
    filter_rules: Optional[List[Dict[str, Any]]] = None  # Dynamic filter rules
    # Example: [{"field": "gender", "operator": "equals", "value": "Female"}, {"field": "age", "operator": "between", "value": [18, 35]}]
    
    last_sync_at: Optional[datetime] = None
    last_sync_status: Optional[str] = None  # success, error
    last_sync_message: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SyncConfigCreate(BaseModel):
    sync_method: str = "polling"
    api_base_url: str
    api_email: str
    api_password: str
    polling_interval_hours: int = 6
    reconciliation_enabled: bool = False
    reconciliation_time: str = "03:00"
    filter_mode: str = "include"
    filter_rules: Optional[List[Dict[str, Any]]] = None
    is_enabled: bool = False

class SyncLog(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    campus_id: str
    sync_type: str  # manual, scheduled, webhook
    status: str  # success, error, partial
    members_fetched: int = 0
    members_created: int = 0
    members_updated: int = 0
    members_archived: int = 0
    members_unarchived: int = 0
    error_message: Optional[str] = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None


# ==================== UTILITY FUNCTIONS ====================

async def get_engagement_settings():
    """Get engagement threshold settings from database"""
    try:
        settings = await db.settings.find_one({"key": "engagement_thresholds"}, {"_id": 0})
        if settings:
            return settings.get("data", {"atRiskDays": 60, "disconnectedDays": 90})
        return {"atRiskDays": 60, "disconnectedDays": 90}
    except:
        return {"atRiskDays": 60, "disconnectedDays": 90}

async def get_writeoff_settings():
    """Get overdue write-off threshold settings from database"""
    try:
        settings = await db.settings.find_one({"key": "overdue_writeoff"}, {"_id": 0})
        if settings:
            return settings.get("data", {
                "birthday": 7,
                "financial_aid": 0,
                "accident_illness": 14,
                "grief_support": 14
            })
        return {
            "birthday": 7,
            "financial_aid": 0,
            "accident_illness": 14,
            "grief_support": 14
        }
    except:
        return {
            "birthday": 7,
            "financial_aid": 0,
            "accident_illness": 14,
            "grief_support": 14
        }

async def calculate_engagement_status_async(last_contact: Optional[datetime]) -> tuple[EngagementStatus, int]:
    """Calculate engagement status using configurable thresholds"""
    settings = await get_engagement_settings()
    at_risk_days = settings.get("atRiskDays", 60)
    disconnected_days = settings.get("disconnectedDays", 90)
    
    if not last_contact:
        return EngagementStatus.DISCONNECTED, 999
    
    # Handle string dates
    if isinstance(last_contact, str):
        try:
            last_contact = datetime.fromisoformat(last_contact)
        except:
            return EngagementStatus.DISCONNECTED, 999
    
    # Make timezone-aware if needed
    if last_contact.tzinfo is None:
        last_contact = last_contact.replace(tzinfo=timezone.utc)
    
    now = datetime.now(timezone.utc)
    days_since = (now - last_contact).days
    
    if days_since < at_risk_days:
        return EngagementStatus.ACTIVE, days_since
    elif days_since < disconnected_days:
        return EngagementStatus.AT_RISK, days_since
    else:
        return EngagementStatus.DISCONNECTED, days_since

def calculate_engagement_status(last_contact: Optional[datetime], at_risk_days: int = 60, disconnected_days: int = 90) -> tuple[EngagementStatus, int]:
    """Calculate engagement status and days since last contact (with configurable thresholds)"""
    if not last_contact:
        return EngagementStatus.DISCONNECTED, 999
    
    # Handle string dates
    if isinstance(last_contact, str):
        try:
            last_contact = datetime.fromisoformat(last_contact)
        except:
            return EngagementStatus.DISCONNECTED, 999
    
    # Make timezone-aware if needed
    if last_contact.tzinfo is None:
        last_contact = last_contact.replace(tzinfo=timezone.utc)
    
    now = datetime.now(timezone.utc)
    days_since = (now - last_contact).days
    
    if days_since < at_risk_days:
        return EngagementStatus.ACTIVE, days_since
    elif days_since < disconnected_days:
        return EngagementStatus.AT_RISK, days_since
    else:
        return EngagementStatus.DISCONNECTED, days_since


def normalize_phone_number(phone: str, default_country_code: str = "+62") -> str:
    """
    Normalize phone number to international format.
    Handles Indonesian phone numbers starting with 0.
    
    Examples:
        081234567890 -> +6281234567890
        62812345678 -> +62812345678
        +6281234567890 -> +6281234567890
    """
    if not phone:
        return phone
    
    # Remove whitespace and common separators
    phone = phone.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    
    # Already has + prefix
    if phone.startswith("+"):
        return phone
    
    # Starts with country code without +
    if phone.startswith("62"):
        return f"+{phone}"
    
    # Starts with 0 (local Indonesian format)
    if phone.startswith("0"):
        return f"{default_country_code}{phone[1:]}"
    
    # No recognizable prefix - assume it needs country code
    return f"{default_country_code}{phone}"


async def log_activity(
    campus_id: str,
    user_id: str,
    user_name: str,
    action_type: ActivityActionType,
    member_id: Optional[str] = None,
    member_name: Optional[str] = None,
    care_event_id: Optional[str] = None,
    event_type: Optional[EventType] = None,
    notes: Optional[str] = None,
    user_photo_url: Optional[str] = None
):
    """Log user activity for accountability tracking"""
    try:
        activity = ActivityLog(
            campus_id=campus_id,
            user_id=user_id,
            user_name=user_name,
            user_photo_url=user_photo_url,
            action_type=action_type,
            member_id=member_id,
            member_name=member_name,
            care_event_id=care_event_id,
            event_type=event_type,
            notes=notes
        )
        await db.activity_logs.insert_one(activity.model_dump())
        logger.info(f"Activity logged: {user_name} - {action_type} - {member_name}")
    except Exception as e:
        logger.error(f"Error logging activity: {str(e)}")
        # Don't fail the main operation if logging fails
        pass

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
        
        # Normalize phone number to international format
        phone_normalized = normalize_phone_number(phone)
        phone_formatted = phone_normalized if phone_normalized.endswith('@s.whatsapp.net') else f"{phone_normalized}@s.whatsapp.net"
        
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
            phone=normalize_phone_number(user_data.phone),
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
        
        # For full admins, use the selected campus_id from login
        active_campus_id = user.get("campus_id")
        if user.get("role") == UserRole.FULL_ADMIN:
            if user_data.campus_id:
                # Full admin selected a specific campus
                active_campus_id = user_data.campus_id
                # Update user's active campus
                await db.users.update_one(
                    {"id": user["id"]},
                    {"$set": {"campus_id": user_data.campus_id, "updated_at": datetime.now(timezone.utc).isoformat()}}
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Please select a campus to continue"
                )
        
        access_token = create_access_token(data={"sub": user["id"]})
        
        campus_name = None
        if active_campus_id:
            campus = await db.campuses.find_one({"id": active_campus_id}, {"_id": 0})
            campus_name = campus["campus_name"] if campus else None
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=UserResponse(
                id=user["id"],
                email=user["email"],
                name=user["name"],
                role=user["role"],
                campus_id=active_campus_id,
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

@api_router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: str, update: UserUpdate, current_user: dict = Depends(get_current_user)):
    """Update a user (full admin only)"""
    if current_user["role"] != "full_admin":
        raise HTTPException(status_code=403, detail="Only full administrators can update users")
    
    try:
        update_data = {k: v for k, v in update.model_dump().items() if v is not None}
        
        # Normalize phone number if provided
        if 'phone' in update_data and update_data['phone']:
            update_data['phone'] = normalize_phone_number(update_data['phone'])
        
        # Hash password if provided
        if 'password' in update_data:
            update_data['hashed_password'] = get_password_hash(update_data['password'])
            del update_data['password']
        
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        result = await db.users.update_one(
            {"id": user_id},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
        
        updated_user = await db.users.find_one({"id": user_id}, {"_id": 0})
        
        # Get campus name if campus_id exists
        if updated_user.get("campus_id"):
            campus = await db.campuses.find_one({"id": updated_user["campus_id"]}, {"_id": 0})
            updated_user["campus_name"] = campus["campus_name"] if campus else None
        
        return updated_user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/users/{user_id}/photo")
async def upload_user_photo(user_id: str, file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    """Upload user profile photo"""
    # Users can upload their own photo or full admin can upload for others
    if current_user["id"] != user_id and current_user["role"] != "full_admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        # Validate file type
        allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/webp", "image/heic", "image/heif"]
        if file.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail="Invalid file type. Only images allowed.")
        
        # Create uploads directory if not exists
        upload_dir = Path(ROOT_DIR) / "user_photos"
        upload_dir.mkdir(exist_ok=True)
        
        # Generate filename
        file_ext = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
        filename = f"USER-{user_id[:8]}.{file_ext}"
        filepath = upload_dir / filename
        
        # Save file
        contents = await file.read()
        
        # Resize image to 400x400
        img = Image.open(BytesIO(contents))
        img = img.convert('RGB')
        img.thumbnail((400, 400), Image.Resampling.LANCZOS)
        img.save(filepath, 'JPEG', quality=85)
        
        # Update user record
        photo_url = f"/api/user-photos/{filename}"
        await db.users.update_one(
            {"id": user_id},
            {"$set": {
                "photo_url": photo_url,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        return {"message": "Photo uploaded successfully", "photo_url": photo_url}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading user photo: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

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
            phone=normalize_phone_number(member.phone),
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
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=1000),
    engagement_status: Optional[EngagementStatus] = None,
    family_group_id: Optional[str] = None,
    search: Optional[str] = None,
    show_archived: bool = False,
    current_user: dict = Depends(get_current_user)
):
    """List all members with pagination"""
    try:
        query = get_campus_filter(current_user)
        
        # Exclude archived members by default (unless show_archived=true)
        if not show_archived:
            query["is_archived"] = {"$ne": True}
        else:
            query["is_archived"] = True
        
        if engagement_status:
            query["engagement_status"] = engagement_status
        
        if family_group_id:
            query["family_group_id"] = family_group_id
        
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},  # Partial name match
                {"phone": {"$regex": search, "$options": "i"}}  # Partial phone match
            ]
        
        # Calculate skip for pagination
        skip = (page - 1) * limit
        
        # Get total count for pagination metadata
        total = await db.members.count_documents(query)
        
        # Get paginated members
        members = await db.members.find(query, {"_id": 0}).skip(skip).limit(limit).to_list(limit)
        
        # Update engagement status for each member
        for member in members:
            if member.get('last_contact_date'):
                if isinstance(member['last_contact_date'], str):
                    member['last_contact_date'] = datetime.fromisoformat(member['last_contact_date'])
            
            status, days = calculate_engagement_status(member.get('last_contact_date'))
            member['engagement_status'] = status
            member['days_since_last_contact'] = days
        
        # Add pagination metadata as headers (keep response as array)
        # This maintains compatibility while providing pagination info
        
        return members
        
    except Exception as e:
        logger.error(f"Error listing members: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def invalidate_dashboard_cache(campus_id: str):
    """Invalidate dashboard cache for a specific campus - call after any data change"""
    try:
        # Get campus timezone to determine today's date
        campus_tz = await get_campus_timezone(campus_id)
        today_date = get_date_in_timezone(campus_tz)
        
        # Delete today's cache
        cache_key = f"dashboard_reminders_{campus_id}_{today_date}"
        await db.dashboard_cache.delete_one({"cache_key": cache_key})
        
        logger.info(f"Dashboard cache invalidated for campus {campus_id}")
    except Exception as e:
        logger.error(f"Error invalidating dashboard cache: {str(e)}")


@api_router.get("/dashboard/reminders")
async def get_dashboard_reminders(user: dict = Depends(get_current_user)):
    """
    Get pre-calculated dashboard reminders
    Optimized for fast loading - data refreshed daily
    """
    try:
        campus_id = user.get("campus_id")
        
        # For full admins without campus, use default campus or all campuses
        if not campus_id:
            # Get default campus
            default_campus = await db.campuses.find_one({"is_active": True}, {"_id": 0, "id": 1, "timezone": 1})
            if default_campus:
                campus_id = default_campus["id"]
            else:
                # No campus found, return empty
                return {
                    "birthdays_today": [],
                    "upcoming_birthdays": [],
                    "grief_today": [],
                    "accident_followup": [],
                    "at_risk_members": [],
                    "disconnected_members": [],
                    "financial_aid_due": [],
                    "ai_suggestions": [],
                    "total_tasks": 0
                }
        
        campus_tz = await get_campus_timezone(campus_id)
        today_date = get_date_in_timezone(campus_tz)
        
        # Check if we have cached data for today
        cache_key = f"dashboard_reminders_{user.get('campus_id')}_{today_date}"
        cached = await db.dashboard_cache.find_one({"cache_key": cache_key})
        
        if cached and cached.get("data"):
            return cached["data"]
        
        # If no cache, calculate now (fallback)
        data = await calculate_dashboard_reminders(user.get("campus_id"), campus_tz, today_date)
        
        # Cache for 1 hour
        cache_data = {
            "cache_key": cache_key,
            "data": data,
            "calculated_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=1)
        }
        
        await db.dashboard_cache.update_one(
            {"cache_key": cache_key},
            {"$set": cache_data},
            upsert=True
        )
        
        # Add cache version to response
        data["cache_version"] = cache_data["calculated_at"].isoformat()
        
        return data
        
    except Exception as e:
        logger.error(f"Error getting dashboard reminders: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def calculate_dashboard_reminders(campus_id: str, campus_tz, today_date: str):
    """Calculate all dashboard reminder data - optimized query"""
    try:
        logger.info(f"Calculating dashboard reminders for campus {campus_id}, date {today_date}")
        
        today = datetime.strptime(today_date, '%Y-%m-%d').date()
        tomorrow = today + timedelta(days=1)
        week_ahead = today + timedelta(days=7)
        
        # Get writeoff settings
        writeoff_settings = await get_writeoff_settings()
        
        # Fetch only necessary data with projection (exclude archived)
        members = await db.members.find(
            {"campus_id": campus_id, "is_archived": {"$ne": True}},
            {"_id": 0, "id": 1, "name": 1, "phone": 1, "photo_url": 1, "birth_date": 1, 
             "engagement_status": 1, "days_since_last_contact": 1}
        ).to_list(None)
        
        logger.info(f"Found {len(members)} members for campus {campus_id}")
        
        # Build member map for quick lookup and calculate ages
        member_map = {}
        for m in members:
            # Calculate age from birth_date
            age = None
            if m.get("birth_date"):
                try:
                    birth_date = datetime.strptime(m["birth_date"], '%Y-%m-%d').date()
                    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
                except:
                    pass
            m["age"] = age
            member_map[m["id"]] = m
        
        # Initialize all arrays at the beginning
        birthdays_today = []
        upcoming_birthdays = []
        today_tasks = []
        overdue_birthdays = []
        upcoming_tasks = []
        
        # Grief support due (today and overdue)
        grief_stages = await db.grief_support.find(
            {"campus_id": campus_id, "completed": False, "ignored": {"$ne": True}},
            {"_id": 0}
        ).to_list(None)
        
        logger.info(f"Found {len(grief_stages)} incomplete grief stages for campus")
        
        # Accident follow-ups due
        accident_followups = await db.accident_followup.find(
            {"campus_id": campus_id, "completed": False, "ignored": {"$ne": True}},
            {"_id": 0}
        ).to_list(None)
        
        accident_today = []
        accident_writeoff = writeoff_settings.get("accident_illness", 14)
        
        for followup in accident_followups:
            sched_date = datetime.strptime(followup["scheduled_date"], '%Y-%m-%d').date()
            days_overdue = (today - sched_date).days
            
            if sched_date == today:
                # Due TODAY - add to today_tasks
                today_tasks.append({
                    "type": "accident_followup",
                    "date": followup["scheduled_date"],
                    "member_id": followup["member_id"],
                    "member_name": member_map.get(followup["member_id"], {}).get("name"),
                    "member_phone": member_map.get(followup["member_id"], {}).get("phone"),
                    "member_photo_url": member_map.get(followup["member_id"], {}).get("photo_url"),
                    "member_age": member_map.get(followup["member_id"], {}).get("age"),
                    "days_since_last_contact": member_map.get(followup["member_id"], {}).get("days_since_last_contact"),
                    "details": f"{followup['stage'].replace('_', ' ')}",
                    "data": followup
                })
            elif sched_date < today:
                # OVERDUE - check writeoff threshold for Follow-up tab
                if accident_writeoff == 0 or days_overdue <= accident_writeoff:
                    accident_today.append({
                        **followup,
                        "member_name": member_map.get(followup["member_id"], {}).get("name"),
                        "member_phone": member_map.get(followup["member_id"], {}).get("phone"),
                        "member_photo_url": member_map.get(followup["member_id"], {}).get("photo_url"),
                        "days_overdue": days_overdue
                    })
            elif tomorrow <= sched_date <= week_ahead:
                # UPCOMING (1-7 days ahead)
                upcoming_tasks.append({
                    "type": "accident_followup",
                    "date": followup["scheduled_date"],
                    "member_id": followup["member_id"],
                    "member_name": member_map.get(followup["member_id"], {}).get("name"),
                    "member_phone": member_map.get(followup["member_id"], {}).get("phone"),
                    "member_photo_url": member_map.get(followup["member_id"], {}).get("photo_url"),
                    "details": f"{followup['stage'].replace('_', ' ')}",
                    "data": followup
                })
        
        # At-risk and disconnected members
        at_risk = [m for m in members if m.get("engagement_status") == "at_risk"]
        disconnected = [m for m in members if m.get("engagement_status") == "disconnected"]
        
        # Financial aid - categorize by date
        aid_schedules = await db.financial_aid_schedules.find(
            {"campus_id": campus_id, "is_active": True, "ignored": {"$ne": True}},
            {"_id": 0}
        ).to_list(None)
        
        logger.info(f"Found {len(aid_schedules)} active financial aid schedules for campus")
        
        aid_due = []  # OVERDUE only (past due)
        for schedule in aid_schedules:
            # Use the pre-calculated next_occurrence field from schedule
            next_occurrence = schedule.get("next_occurrence")
            if not next_occurrence:
                continue
            
            try:
                next_date = datetime.strptime(next_occurrence, '%Y-%m-%d').date()
                
                logger.info(f"Financial aid schedule: next_date={next_date}, today={today}, next_date==today: {next_date == today}")
                
                # Due TODAY - add to today_tasks
                if next_date == today:
                    today_tasks.append({
                        "type": "financial_aid",
                        "date": next_occurrence,
                        "member_id": schedule["member_id"],
                        "member_name": member_map.get(schedule["member_id"], {}).get("name"),
                        "member_phone": member_map.get(schedule["member_id"], {}).get("phone"),
                        "member_photo_url": member_map.get(schedule["member_id"], {}).get("photo_url"),
                        "member_age": member_map.get(schedule["member_id"], {}).get("age"),
                        "days_since_last_contact": member_map.get(schedule["member_id"], {}).get("days_since_last_contact"),
                        "details": f"{schedule['frequency'].title()} - Rp {schedule['aid_amount']:,}",
                        "data": schedule
                    })
                    logger.info(f"Added financial aid to today_tasks: {schedule.get('member_id')}")
                # OVERDUE - add to aid_due (Aid tab)
                elif next_date < today:
                    days_overdue = (today - next_date).days
                    aid_due.append({
                        **schedule,
                        "next_due_date": next_occurrence,
                        "days_overdue": days_overdue,
                        "member_name": member_map.get(schedule["member_id"], {}).get("name"),
                        "member_phone": member_map.get(schedule["member_id"], {}).get("phone"),
                        "member_photo_url": member_map.get(schedule["member_id"], {}).get("photo_url")
                    })
                # UPCOMING (1-7 days ahead) - add to upcoming_tasks
                elif tomorrow <= next_date <= week_ahead:
                    days_until = (next_date - today).days
                    upcoming_tasks.append({
                        "type": "financial_aid",
                        "date": next_occurrence,
                        "member_id": schedule["member_id"],
                        "member_name": member_map.get(schedule["member_id"], {}).get("name"),
                        "member_phone": member_map.get(schedule["member_id"], {}).get("phone"),
                        "member_photo_url": member_map.get(schedule["member_id"], {}).get("photo_url"),
                        "details": f"{schedule['frequency'].title()} - Rp {schedule['aid_amount']:,}",
                        "data": schedule
                    })
            except Exception as e:
                logger.error(f"Error processing financial aid schedule {schedule.get('id')}: {str(e)}")
                continue
        
        # AI suggestions (top 10 at-risk)
        suggestions_list = sorted(at_risk + disconnected, 
                                 key=lambda x: x.get("days_since_last_contact", 0), 
                                 reverse=True)[:10]
        
        # Process all birthdays
        for member in members:
            if not member.get("birth_date"):
                continue
                
            birth_date = datetime.strptime(member["birth_date"], '%Y-%m-%d').date()
            this_year_birthday = birth_date.replace(year=today.year)
            
            # Find birthday event if exists
            event = await db.care_events.find_one(
                {"member_id": member["id"], "event_type": "birthday"},
                {"_id": 0}
            )
            
            if not event:
                continue
            
            if this_year_birthday == today:
                # Birthday today
                birthdays_today.append({
                    **event,
                    "member_name": member["name"],
                    "member_phone": member["phone"],
                    "member_photo_url": member.get("photo_url"),
                    "member_age": member.get("age")
                })
            elif this_year_birthday < today and not event.get("completed") and not event.get("ignored"):
                # Overdue birthday (past but not completed and not ignored)
                days_overdue = (today - this_year_birthday).days
                # Only include if within writeoff threshold (0 = never writeoff)
                birthday_writeoff = writeoff_settings.get("birthday", 7)
                if birthday_writeoff == 0 or days_overdue <= birthday_writeoff:
                    overdue_birthdays.append({
                        **event,
                        "member_name": member["name"],
                        "member_phone": member["phone"],
                        "member_photo_url": member.get("photo_url"),
                        "member_age": member.get("age"),
                        "days_overdue": days_overdue
                    })
            elif tomorrow <= this_year_birthday <= week_ahead and not event.get("completed") and not event.get("ignored"):
                # Upcoming birthday (1-7 days ahead) - exclude completed and ignored
                days_until = (this_year_birthday - today).days
                upcoming_tasks.append({
                    "type": "birthday",
                    "date": this_year_birthday.isoformat(),
                    "member_id": member["id"],
                    "member_name": member["name"],
                    "member_phone": member["phone"],
                    "member_photo_url": member.get("photo_url"),
                    "member_age": member.get("age"),
                    "details": "Birthday celebration",
                    "data": event
                })
                upcoming_birthdays.append({
                    **event,
                    "member_name": member["name"],
                    "member_phone": member["phone"],
                    "member_photo_url": member.get("photo_url")
                })
        
        # Today's grief stages (not overdue, exactly today)
        grief_today = []
        for stage in grief_stages:
            sched_date = datetime.strptime(stage["scheduled_date"], '%Y-%m-%d').date()
            days_overdue = (today - sched_date).days
            
            # Apply writeoff threshold
            grief_writeoff = writeoff_settings.get("grief_support", 14)
            
            if sched_date == today:
                # Due TODAY - add to today_tasks
                today_tasks.append({
                    "type": "grief_support",
                    "date": stage["scheduled_date"],
                    "member_id": stage["member_id"],
                    "member_name": member_map.get(stage["member_id"], {}).get("name"),
                    "member_phone": member_map.get(stage["member_id"], {}).get("phone"),
                    "member_photo_url": member_map.get(stage["member_id"], {}).get("photo_url"),
                    "member_age": member_map.get(stage["member_id"], {}).get("age"),
                    "days_since_last_contact": member_map.get(stage["member_id"], {}).get("days_since_last_contact"),
                    "details": f"{stage['stage'].replace('_', ' ')} stage",
                    "data": stage
                })
            elif sched_date < today:
                # OVERDUE - check writeoff threshold for Follow-up tab
                if grief_writeoff == 0 or days_overdue <= grief_writeoff:
                    grief_today.append({
                        **stage,
                        "member_name": member_map.get(stage["member_id"], {}).get("name"),
                        "member_phone": member_map.get(stage["member_id"], {}).get("phone"),
                        "member_photo_url": member_map.get(stage["member_id"], {}).get("photo_url"),
                        "days_overdue": days_overdue
                    })
            elif tomorrow <= sched_date <= week_ahead:
                upcoming_tasks.append({
                    "type": "grief_support",
                    "date": stage["scheduled_date"],
                    "member_id": stage["member_id"],
                    "member_name": member_map.get(stage["member_id"], {}).get("name"),
                    "member_phone": member_map.get(stage["member_id"], {}).get("phone"),
                    "member_photo_url": member_map.get(stage["member_id"], {}).get("photo_url"),
                    "details": f"{stage['stage'].replace('_', ' ')} stage",
                    "data": stage
                })
        
        # Sort all upcoming tasks by date
        upcoming_tasks.sort(key=lambda x: x["date"])
        
        return {
            "birthdays_today": birthdays_today,
            "overdue_birthdays": overdue_birthdays,
            "upcoming_birthdays": upcoming_birthdays,
            "today_tasks": today_tasks,
            "grief_today": grief_today,
            "accident_followup": accident_today,
            "at_risk_members": at_risk,
            "disconnected_members": disconnected,
            "financial_aid_due": aid_due,
            "ai_suggestions": suggestions_list,
            "upcoming_tasks": upcoming_tasks,
            "total_tasks": len(birthdays_today) + len(grief_today) + len(accident_today) + len(at_risk) + len(disconnected)
        }
        
    except Exception as e:
        logger.error(f"Error calculating dashboard reminders: {str(e)}")
        raise

async def get_campus_timezone(campus_id: str) -> str:
    """Get campus timezone setting"""
    try:
        campus = await db.campuses.find_one({"id": campus_id}, {"_id": 0, "timezone": 1})
        return campus.get("timezone", "Asia/Jakarta") if campus else "Asia/Jakarta"
    except:
        return "Asia/Jakarta"

def get_date_in_timezone(timezone_str: str) -> str:
    """Get current date in specified timezone as YYYY-MM-DD string"""
    try:
        tz = ZoneInfo(timezone_str)
        return datetime.now(tz).strftime('%Y-%m-%d')
    except:
        return datetime.now(ZoneInfo("Asia/Jakarta")).strftime('%Y-%m-%d')


@api_router.post("/care-events/{event_id}/ignore")
async def ignore_care_event(event_id: str, user: dict = Depends(get_current_user)):
    """Mark a care event as ignored/dismissed"""
    try:
        event = await db.care_events.find_one({"id": event_id}, {"_id": 0})
        if not event:
            raise HTTPException(status_code=404, detail="Care event not found")
        
        # Get member name for logging
        member = await db.members.find_one({"id": event["member_id"]}, {"_id": 0})
        member_name = member["name"] if member else "Unknown"
        
        # Update event to mark as ignored
        await db.care_events.update_one(
            {"id": event_id},
            {"$set": {
                "ignored": True,
                "ignored_at": datetime.now(timezone.utc).isoformat(),
                "ignored_by": user.get("id"),
                "ignored_by_name": user.get("name"),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        # Log activity
        await log_activity(
            campus_id=event["campus_id"],
            user_id=user["id"],
            user_name=user["name"],
            action_type=ActivityActionType.IGNORE_TASK,
            member_id=event["member_id"],
            member_name=member_name,
            care_event_id=event_id,
            event_type=EventType(event["event_type"]),
            notes=f"Ignored {event['event_type']} task",
            user_photo_url=user.get("photo_url")
        )
        
        # Invalidate dashboard cache
        await invalidate_dashboard_cache(event["campus_id"])
        
        return {"success": True, "message": "Care event ignored"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ignoring care event: {str(e)}")
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
            
            if status in [EngagementStatus.AT_RISK, EngagementStatus.DISCONNECTED]:
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
        
        # Normalize phone number if provided
        if 'phone' in update_data and update_data['phone']:
            update_data['phone'] = normalize_phone_number(update_data['phone'])
        
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

@api_router.delete("/care-events/{event_id}")
async def delete_care_event(event_id: str):
    """Delete care event and recalculate member engagement"""
    try:
        # Get the care event first to know which member and type
        event = await db.care_events.find_one({"id": event_id}, {"_id": 0})
        if not event:
            raise HTTPException(status_code=404, detail="Care event not found")
        
        member_id = event["member_id"]
        event_type = event.get("event_type")
        
        # If deleting a timeline event created from followup completion, reset the stage
        if event_type in ["grief_loss", "accident_illness"]:
            # Check if this timeline event is linked to a grief stage
            if event.get("grief_stage_id"):
                await db.grief_support.update_one(
                    {"id": event["grief_stage_id"]},
                    {"$set": {
                        "completed": False,
                        "completed_at": None,
                        "ignored": False,
                        "ignored_at": None
                    }}
                )
            
            # Check if this timeline event is linked to an accident stage
            elif event.get("accident_stage_id"):
                await db.accident_followup.update_one(
                    {"id": event["accident_stage_id"]},
                    {"$set": {
                        "completed": False,
                        "completed_at": None,
                        "ignored": False,
                        "ignored_at": None
                    }}
                )
        
        # If deleting a birthday completion timeline event, reset the birthday event
        if event_type == "regular_contact" and "Birthday" in event.get("title", ""):
            # Find the birthday event for this member
            birthday_event = await db.care_events.find_one(
                {"member_id": member_id, "event_type": "birthday"},
                {"_id": 0}
            )
            if birthday_event:
                await db.care_events.update_one(
                    {"id": birthday_event["id"]},
                    {"$set": {"completed": False, "updated_at": datetime.now(timezone.utc).isoformat()}}
                )
        
        # Delete the care event
        result = await db.care_events.delete_one({"id": event_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Care event not found")
        
        # Delete activity logs related to this care event
        await db.activity_logs.delete_many({"care_event_id": event_id})
        
        # If deleting grief/accident parent event, also delete followup stages
        if event_type == "grief_loss":
            # Get all grief stages
            grief_stages = await db.grief_support.find(
                {"care_event_id": event_id},
                {"_id": 0, "id": 1, "member_id": 1, "stage": 1}
            ).to_list(None)
            
            # Delete timeline entries created from these stages
            stage_ids = [s["id"] for s in grief_stages]
            if stage_ids:
                await db.care_events.delete_many({"grief_stage_id": {"$in": stage_ids}})
            
            # Delete activity logs for each grief stage
            for stage in grief_stages:
                await db.activity_logs.delete_many({
                    "member_id": stage["member_id"],
                    "notes": {"$regex": f"{stage['stage'].replace('_', ' ')}", "$options": "i"}
                })
            
            # Delete grief support stages
            await db.grief_support.delete_many({"care_event_id": event_id})
            
        elif event_type == "accident_illness":
            # Get all accident stages
            accident_stages = await db.accident_followup.find(
                {"care_event_id": event_id},
                {"_id": 0, "id": 1, "member_id": 1, "stage": 1}
            ).to_list(None)
            
            # Delete timeline entries created from these stages
            stage_ids = [s["id"] for s in accident_stages]
            if stage_ids:
                await db.care_events.delete_many({"accident_stage_id": {"$in": stage_ids}})
            
            # Delete activity logs for each accident stage
            for stage in accident_stages:
                await db.activity_logs.delete_many({
                    "member_id": stage["member_id"],
                    "notes": {"$regex": f"{stage['stage'].replace('_', ' ')}", "$options": "i"}
                })
            
            # Delete accident followup stages
            await db.accident_followup.delete_many({"care_event_id": event_id})
        
        # Recalculate member's last contact date from remaining NON-BIRTHDAY events
        # Birthday events don't count as contact unless completed (marked as contacted)
        remaining_events = await db.care_events.find(
            {
                "member_id": member_id,
                "$or": [
                    {"event_type": {"$ne": "birthday"}},  # Non-birthday events
                    {"event_type": "birthday", "completed": True}  # Completed birthday events
                ]
            },
            {"_id": 0, "created_at": 1}
        ).sort("created_at", -1).limit(1).to_list(1)
        
        if remaining_events:
            # Update to most recent remaining event
            last_event = remaining_events[0]
            new_last_contact = last_event["created_at"]
            
            # Calculate new engagement status
            if isinstance(new_last_contact, str):
                last_contact_dt = datetime.fromisoformat(new_last_contact)
            else:
                last_contact_dt = new_last_contact
                
            if last_contact_dt.tzinfo is None:
                last_contact_dt = last_contact_dt.replace(tzinfo=timezone.utc)
            
            days_since = (datetime.now(timezone.utc) - last_contact_dt).days
            
            if days_since < 60:
                engagement_status = "active"
            elif days_since < 90:
                engagement_status = "at_risk"
            else:
                engagement_status = "disconnected"
                
            await db.members.update_one(
                {"id": member_id},
                {"$set": {
                    "last_contact_date": new_last_contact,
                    "days_since_last_contact": days_since,
                    "engagement_status": engagement_status,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }}
            )
        else:
            # No remaining events - reset to never contacted
            await db.members.update_one(
                {"id": member_id},
                {"$set": {
                    "last_contact_date": None,
                    "days_since_last_contact": 999,
                    "engagement_status": "disconnected",
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }}
            )
        
        # Also delete related grief support stages and accident followup stages
        await db.grief_support.delete_many({"care_event_id": event_id})
        await db.accident_followup.delete_many({"care_event_id": event_id})
        
        # Invalidate dashboard cache
        await invalidate_dashboard_cache(event["campus_id"])
        
        return {"success": True, "message": "Care event deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting care event: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/members/{member_id}/photo")
async def upload_member_photo(member_id: str, file: UploadFile = File(...)):
    """Upload member profile photo with optimization"""
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
        
        # Optimize image: resize and compress
        image = image.convert('RGB')
        
        # Resize to multiple sizes for different contexts
        sizes = {
            'thumbnail': (100, 100),  # For lists and small avatars
            'medium': (300, 300),     # For profile views
            'large': (600, 600)       # For detailed views
        }
        
        base_filename = f"{member_id}"
        photo_urls = {}
        
        for size_name, (width, height) in sizes.items():
            # Create optimized version
            resized = image.copy()
            resized.thumbnail((width, height), Image.Resampling.LANCZOS)
            
            # Save with optimization
            filename = f"{base_filename}_{size_name}.jpg"
            filepath = Path(ROOT_DIR) / "uploads" / filename
            resized.save(filepath, "JPEG", quality=85, optimize=True)
            
            photo_urls[size_name] = f"/uploads/{filename}"
        
        # Update member record with optimized photo URLs
        await db.members.update_one(
            {"id": member_id},
            {"$set": {
                "photo_url": photo_urls['medium'],  # Default medium size
                "photo_urls": photo_urls,  # All sizes available
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        return {
            "success": True, 
            "photo_urls": photo_urls,
            "default_url": photo_urls['medium']
        }
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
        
        # Get member name for logging
        member = await db.members.find_one({"id": event.member_id}, {"_id": 0, "name": 1})
        member_name = member["name"] if member else "Unknown"
        
        # Determine if this is a one-time event that should be auto-completed
        one_time_events = [
            EventType.REGULAR_CONTACT,
            EventType.CHILDBIRTH,
            EventType.NEW_HOUSE
        ]
        
        # Check if financial aid is one-time
        is_one_time_financial_aid = (
            event.event_type == EventType.FINANCIAL_AID and 
            event.aid_type and 
            not event.aid_notes  # No recurring schedule means one-time
        )
        
        is_one_time = event.event_type in one_time_events or is_one_time_financial_aid
        
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
            aid_notes=event.aid_notes,
            created_by_user_id=current_user["id"],
            created_by_user_name=current_user["name"],
            # Auto-complete one-time events
            completed=is_one_time,
            completed_at=datetime.now(timezone.utc) if is_one_time else None,
            completed_by_user_id=current_user["id"] if is_one_time else None,
            completed_by_user_name=current_user["name"] if is_one_time else None
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
        
        # Log activity for creating the care event
        # For one-time events, log as COMPLETE_TASK since they're auto-completed
        action_type = ActivityActionType.COMPLETE_TASK if is_one_time else ActivityActionType.CREATE_CARE_EVENT
        action_note = f"{'Completed' if is_one_time else 'Created'} {event.event_type.value.replace('_', ' ')} event: {event.title}"
        
        await log_activity(
            campus_id=campus_id,
            user_id=current_user["id"],
            user_name=current_user["name"],
            action_type=action_type,
            member_id=event.member_id,
            member_name=member_name,
            care_event_id=care_event.id,
            event_type=event.event_type,
            notes=action_note,
            user_photo_url=current_user.get("photo_url")
        )
        
        # Update member's last contact date for completed one-time events or non-birthday events
        if is_one_time or (event.event_type != EventType.BIRTHDAY):
            now = datetime.now(timezone.utc)
            await db.members.update_one(
                {"id": event.member_id},
                {"$set": {
                    "last_contact_date": now.isoformat(),
                    "days_since_last_contact": 0,  # Reset to 0 for fresh contact
                    "engagement_status": "active",  # Set to active after contact
                    "updated_at": now.isoformat()
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
        
        # Invalidate dashboard cache after creating care event
        await invalidate_dashboard_cache(campus_id)
        
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
        
        # Enrich events with member names
        for event in events:
            if event.get("member_id"):
                member = await db.members.find_one(
                    {"member_id": event["member_id"]}, 
                    {"_id": 0, "name": 1}
                )
                if member:
                    event["member_name"] = member.get("name")
                else:
                    # Extract name from title if member not found
                    # Title format: "Bantuan Keuangan - MEMBER_NAME" or similar
                    title = event.get("title", "")
                    if " - " in title:
                        event["member_name"] = title.split(" - ", 1)[1].strip()
        
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

@api_router.post("/care-events/{event_id}/complete")
async def complete_care_event(event_id: str, current_user: dict = Depends(get_current_user)):
    """Mark care event as completed and update member engagement"""
    try:
        # Get the care event first
        event = await db.care_events.find_one({"id": event_id}, {"_id": 0})
        if not event:
            raise HTTPException(status_code=404, detail="Care event not found")
        
        # Get member name for logging
        member = await db.members.find_one({"id": event["member_id"]}, {"_id": 0})
        member_name = member["name"] if member else "Unknown"
        
        # Mark event as completed
        result = await db.care_events.update_one(
            {"id": event_id},
            {"$set": {
                "completed": True,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "completed_by_user_id": current_user["id"],
                "completed_by_user_name": current_user["name"],
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Care event not found")
        
        # Log activity
        await log_activity(
            campus_id=event["campus_id"],
            user_id=current_user["id"],
            user_name=current_user["name"],
            action_type=ActivityActionType.COMPLETE_TASK,
            member_id=event["member_id"],
            member_name=member_name,
            care_event_id=event_id,
            event_type=EventType(event["event_type"]),
            notes=f"Completed {event['event_type']} task",
            user_photo_url=current_user.get("photo_url")
        )
        
        # Update member engagement status (since this event now counts as contact)
        now = datetime.now(timezone.utc)
        await db.members.update_one(
            {"id": event["member_id"]},
            {"$set": {
                "last_contact_date": now.isoformat(),
                "days_since_last_contact": 0,
                "engagement_status": "active",
                "updated_at": now.isoformat()
            }}
        )
        
        # For birthday completions, also create a regular contact event for timeline
        if event["event_type"] == "birthday":
            # Get campus timezone for correct date
            campus_tz = await get_campus_timezone(event["campus_id"])
            today_date = get_date_in_timezone(campus_tz)
            
            contact_event = {
                "id": str(uuid.uuid4()),
                "member_id": event["member_id"],
                "campus_id": event["campus_id"],
                "event_type": "regular_contact",
                "event_date": today_date,  # Use campus timezone date
                "title": "Birthday Contact",
                "description": f"Contacted {member_name} for their birthday celebration",
                "completed": True,
                "completed_at": now.isoformat(),
                "completed_by_user_id": current_user["id"],
                "completed_by_user_name": current_user["name"],
                "reminder_sent": False,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat()
            }
            
            await db.care_events.insert_one(contact_event)
        
        # Invalidate dashboard cache after completing event
        await invalidate_dashboard_cache(event["campus_id"])
        
        return {"success": True, "message": "Care event marked as completed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing care event: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/care-events/{event_id}/send-reminder")
async def send_care_event_reminder(event_id: str, current_user: dict = Depends(get_current_user)):
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
                    "reminder_sent_at": datetime.now(timezone.utc).isoformat(),
                    "reminder_sent_by_user_id": current_user["id"],
                    "reminder_sent_by_user_name": current_user["name"]
                }}
            )
            
            # Log activity
            await log_activity(
                campus_id=event["campus_id"],
                user_id=current_user["id"],
                user_name=current_user["name"],
                action_type=ActivityActionType.SEND_REMINDER,
                member_id=event["member_id"],
                member_name=member["name"],
                care_event_id=event_id,
                event_type=EventType(event["event_type"]),
                notes=f"Sent WhatsApp reminder for {event['event_type']}",
                user_photo_url=current_user.get("photo_url")
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
async def complete_grief_stage(stage_id: str, notes: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Mark grief stage as completed with notes"""
    try:
        # Get stage first
        stage = await db.grief_support.find_one({"id": stage_id}, {"_id": 0})
        if not stage:
            raise HTTPException(status_code=404, detail="Grief stage not found")
        
        # Get member name for logging
        member = await db.members.find_one({"id": stage["member_id"]}, {"_id": 0, "name": 1})
        member_name = member["name"] if member else "Unknown"
        
        update_data = {
            "completed": True,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "completed_by_user_id": current_user["id"],
            "completed_by_user_name": current_user["name"],
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
        
        # Create timeline entry (will show in Timeline tab, NOT in Grief tab)
        # This entry does NOT have care_event_id, so it won't appear in Grief tab filter
        campus_tz = await get_campus_timezone(stage["campus_id"])
        today_date = get_date_in_timezone(campus_tz)
        
        timeline_event_id = str(uuid.uuid4())
        await db.care_events.insert_one({
            "id": timeline_event_id,
            "member_id": stage["member_id"],
            "campus_id": stage["campus_id"],
            "event_type": "grief_loss",
            "event_date": today_date,
            "title": f"Grief Support: {stage['stage'].replace('_', ' ')}",
            "description": "Completed grief follow-up stage" + (f"\n\nNotes: {notes}" if notes else ""),
            "grief_stage_id": stage_id,  # Link for undo (but NOT care_event_id)
            "completed": True,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "completed_by_user_id": current_user["id"],
            "completed_by_user_name": current_user["name"],
            "created_by_user_id": current_user["id"],
            "created_by_user_name": current_user["name"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Log activity
        await log_activity(
            campus_id=stage["campus_id"],
            user_id=current_user["id"],
            user_name=current_user["name"],
            action_type=ActivityActionType.COMPLETE_TASK,
            member_id=stage["member_id"],
            member_name=member_name,
            care_event_id=timeline_event_id,
            event_type=EventType.GRIEF_LOSS,
            notes=f"Completed grief support stage: {stage['stage'].replace('_', ' ')}",
            user_photo_url=current_user.get("photo_url")
        )
        
        # Update member's last contact date
        await db.members.update_one(
            {"id": stage["member_id"]},
            {"$set": {"last_contact_date": datetime.now(timezone.utc).isoformat()}}
        )
        
        # Invalidate dashboard cache
        await invalidate_dashboard_cache(stage["campus_id"])
        
        return {"success": True, "message": "Grief stage marked as completed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing grief stage: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/grief-support/{stage_id}/ignore")
async def ignore_grief_stage(stage_id: str, user: dict = Depends(get_current_user)):
    """Mark a grief support stage as ignored/dismissed"""
    try:
        stage = await db.grief_support.find_one({"id": stage_id}, {"_id": 0})
        if not stage:
            raise HTTPException(status_code=404, detail="Grief stage not found")
        
        # Get member name for logging
        member = await db.members.find_one({"id": stage["member_id"]}, {"_id": 0, "name": 1})
        member_name = member["name"] if member else "Unknown"
        
        await db.grief_support.update_one(
            {"id": stage_id},
            {"$set": {
                "ignored": True,
                "ignored_at": datetime.now(timezone.utc).isoformat(),
                "ignored_by": user.get("id"),
                "ignored_by_name": user.get("name")
            }}
        )
        
        # Create timeline entry (will show in Timeline tab, NOT in Grief tab)
        campus_tz = await get_campus_timezone(stage["campus_id"])
        today_date = get_date_in_timezone(campus_tz)
        
        timeline_event_id = str(uuid.uuid4())
        await db.care_events.insert_one({
            "id": timeline_event_id,
            "member_id": stage["member_id"],
            "campus_id": stage["campus_id"],
            "event_type": "grief_loss",
            "event_date": today_date,
            "title": f"Grief Support: {stage['stage'].replace('_', ' ')} (Ignored)",
            "description": "Stage was marked as ignored/not applicable",
            "grief_stage_id": stage_id,  # Link for undo (but NOT care_event_id)
            "ignored": True,
            "ignored_at": datetime.now(timezone.utc).isoformat(),
            "ignored_by": user.get("id"),
            "ignored_by_name": user.get("name"),
            "created_by_user_id": user.get("id"),
            "created_by_user_name": user.get("name"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Log activity
        await log_activity(
            campus_id=stage["campus_id"],
            user_id=user["id"],
            user_name=user["name"],
            action_type=ActivityActionType.IGNORE_TASK,
            member_id=stage["member_id"],
            member_name=member_name,
            care_event_id=timeline_event_id,
            event_type=EventType.GRIEF_LOSS,
            notes=f"Ignored grief support stage: {stage['stage'].replace('_', ' ')}",
            user_photo_url=user.get("photo_url")
        )
        
        # Invalidate dashboard cache
        await invalidate_dashboard_cache(stage["campus_id"])
        
        return {"success": True, "message": "Grief stage ignored"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/grief-support/{stage_id}/undo")
async def undo_grief_stage(stage_id: str, user: dict = Depends(get_current_user)):
    """Undo completion or ignore of grief support stage"""
    try:
        stage = await db.grief_support.find_one({"id": stage_id}, {"_id": 0})
        if not stage:
            raise HTTPException(status_code=404, detail="Grief stage not found")
        
        # Delete timeline entries created for this stage (linked by grief_stage_id)
        await db.care_events.delete_many({"grief_stage_id": stage_id})
        
        # Delete activity logs related to this grief stage
        await db.activity_logs.delete_many({
            "member_id": stage["member_id"],
            "notes": {"$regex": f"{stage['stage'].replace('_', ' ')}", "$options": "i"}
        })
        
        # Reset the grief stage
        await db.grief_support.update_one(
            {"id": stage_id},
            {"$set": {
                "completed": False,
                "completed_at": None,
                "completed_by_user_id": None,
                "completed_by_user_name": None,
                "ignored": False,
                "ignored_at": None,
                "ignored_by": None,
                "ignored_by_name": None
            }}
        )
        
        # Invalidate dashboard cache
        await invalidate_dashboard_cache(stage["campus_id"])
        
        return {"success": True, "message": "Grief support stage reset"}
    except HTTPException:
        raise
    except Exception as e:
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

@api_router.get("/accident-followup")
async def list_accident_followup(completed: Optional[bool] = None, current_user: dict = Depends(get_current_user)):
    """List all accident follow-up stages"""
    try:
        query = get_campus_filter(current_user)
        if completed is not None:
            query["completed"] = completed
        
        stages = await db.accident_followup.find(query, {"_id": 0}).sort("scheduled_date", 1).to_list(1000)
        return stages
    except Exception as e:
        logger.error(f"Error listing accident follow-up: {str(e)}")
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
async def complete_accident_stage(stage_id: str, notes: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Mark accident follow-up stage as completed"""
    try:
        # Get stage first
        stage = await db.accident_followup.find_one({"id": stage_id}, {"_id": 0})
        if not stage:
            raise HTTPException(status_code=404, detail="Accident follow-up stage not found")
        
        # Get member name for logging
        member = await db.members.find_one({"id": stage["member_id"]}, {"_id": 0, "name": 1})
        member_name = member["name"] if member else "Unknown"
        
        update_data = {
            "completed": True,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "completed_by_user_id": current_user["id"],
            "completed_by_user_name": current_user["name"],
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
        
        # Create timeline entry (will show in Timeline tab, NOT in Accident tab)
        campus_tz = await get_campus_timezone(stage["campus_id"])
        today_date = get_date_in_timezone(campus_tz)
        
        timeline_event_id = str(uuid.uuid4())
        await db.care_events.insert_one({
            "id": timeline_event_id,
            "member_id": stage["member_id"],
            "campus_id": stage["campus_id"],
            "event_type": "accident_illness",
            "event_date": today_date,
            "title": f"Accident Follow-up: {stage['stage'].replace('_', ' ')}",
            "description": "Completed accident/illness follow-up" + (f"\n\nNotes: {notes}" if notes else ""),
            "accident_stage_id": stage_id,  # Link for undo
            "completed": True,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "completed_by_user_id": current_user["id"],
            "completed_by_user_name": current_user["name"],
            "created_by_user_id": current_user["id"],
            "created_by_user_name": current_user["name"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Log activity
        await log_activity(
            campus_id=stage["campus_id"],
            user_id=current_user["id"],
            user_name=current_user["name"],
            action_type=ActivityActionType.COMPLETE_TASK,
            member_id=stage["member_id"],
            member_name=member_name,
            care_event_id=timeline_event_id,
            event_type=EventType.ACCIDENT_ILLNESS,
            notes=f"Completed accident/illness follow-up: {stage['stage'].replace('_', ' ')}",
            user_photo_url=current_user.get("photo_url")
        )
        
        # Update member's last contact date
        await db.members.update_one(
            {"id": stage["member_id"]},
            {"$set": {"last_contact_date": datetime.now(timezone.utc).isoformat()}}
        )
        
        # Invalidate dashboard cache
        await invalidate_dashboard_cache(stage["campus_id"])
        
        return {"success": True, "message": "Accident follow-up stage completed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing accident stage: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/accident-followup/{stage_id}/undo")
async def undo_accident_stage(stage_id: str, user: dict = Depends(get_current_user)):
    """Undo completion or ignore of accident followup stage"""
    try:
        stage = await db.accident_followup.find_one({"id": stage_id}, {"_id": 0})
        if not stage:
            raise HTTPException(status_code=404, detail="Accident followup not found")
        
        # Delete timeline entries created for this stage (linked by accident_stage_id)
        await db.care_events.delete_many({"accident_stage_id": stage_id})
        
        # Delete activity logs related to this accident stage
        await db.activity_logs.delete_many({
            "member_id": stage["member_id"],
            "notes": {"$regex": f"{stage['stage'].replace('_', ' ')}", "$options": "i"}
        })
        
        # Reset the accident stage
        await db.accident_followup.update_one(
            {"id": stage_id},
            {"$set": {
                "completed": False,
                "completed_at": None,
                "completed_by_user_id": None,
                "completed_by_user_name": None,
                "ignored": False,
                "ignored_at": None,
                "ignored_by": None,
                "ignored_by_name": None
            }}
        )
        
        # Invalidate dashboard cache
        await invalidate_dashboard_cache(stage["campus_id"])
        
        return {"success": True, "message": "Accident followup stage reset"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== FINANCIAL AID SCHEDULE ENDPOINTS ====================

@api_router.post("/financial-aid-schedules", response_model=FinancialAidSchedule)
async def create_aid_schedule(schedule: dict, current_user: dict = Depends(get_current_user)):
    """Create a financial aid schedule"""
    try:
        # Calculate next occurrence based on frequency
        today = date.today()
        start_date = date.fromisoformat(schedule['start_date']) if isinstance(schedule['start_date'], str) else schedule['start_date']
        next_occurrence = start_date
        
        if schedule['frequency'] == 'weekly' and schedule.get('day_of_week'):
            # For weekly: Find next occurrence of specified weekday from TODAY
            days_ahead = {'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6}
            target_weekday = days_ahead[schedule['day_of_week']]
            current_weekday = today.weekday()
            
            if target_weekday >= current_weekday:
                # This week
                days_to_add = target_weekday - current_weekday
            else:
                # Next week
                days_to_add = 7 - current_weekday + target_weekday
            
            next_occurrence = today + timedelta(days=days_to_add)
            
        elif schedule['frequency'] == 'monthly' and schedule.get('day_of_month'):
            # For monthly: Use start_date (supports backdating)
            day_of_month = schedule['day_of_month']
            start_month = start_date.month
            start_year = start_date.year
            
            # Validate day exists in the specified month
            try:
                first_occurrence = date(start_year, start_month, day_of_month)
                
                # Use the actual start date (even if in past - will show as overdue)
                next_occurrence = first_occurrence
                        
            except ValueError:
                # Day doesn't exist in this month (e.g., Feb 31, Nov 31)
                raise HTTPException(
                    status_code=400, 
                    detail=f"Day {day_of_month} does not exist in the specified month"
                )
            
        elif schedule['frequency'] == 'monthly' and schedule.get('day_of_month'):
            # Find next occurrence of this day of month from today onward
            day_of_month = schedule['day_of_month']
            
            # Try this month first
            try:
                next_occurrence = today.replace(day=day_of_month)
                if next_occurrence < today:
                    # This month's day has passed, go to next month
                    if today.month == 12:
                        next_occurrence = next_occurrence.replace(year=today.year + 1, month=1)
                    else:
                        next_occurrence = next_occurrence.replace(month=today.month + 1)
            except ValueError:
                # Day doesn't exist in this month (e.g., Feb 31), go to next month
                if today.month == 12:
                    next_occurrence = date(today.year + 1, 1, min(day_of_month, 31))
                else:
                    next_occurrence = date(today.year, today.month + 1, min(day_of_month, 31))
                    
        elif schedule['frequency'] == 'annually' and schedule.get('month_of_year'):
            # Find next occurrence of this month/day from today onward
            month_of_year = schedule['month_of_year']
            day_of_month = schedule.get('day_of_month', 1)  # Default to 1st if not specified
            
            # Try this year first
            try:
                next_occurrence = date(today.year, month_of_year, day_of_month)
                if next_occurrence < today:
                    # This year's date has passed, go to next year
                    next_occurrence = date(today.year + 1, month_of_year, day_of_month)
            except ValueError:
                # Day doesn't exist in month (e.g., Feb 31), use last day of month
                if month_of_year == 2:
                    # February - check leap year
                    if (today.year % 4 == 0 and today.year % 100 != 0) or (today.year % 400 == 0):
                        day_of_month = min(day_of_month, 29)
                    else:
                        day_of_month = min(day_of_month, 28)
                elif month_of_year in [4, 6, 9, 11]:
                    day_of_month = min(day_of_month, 30)
                else:
                    day_of_month = min(day_of_month, 31)
                
                next_occurrence = date(today.year, month_of_year, day_of_month)
                if next_occurrence < today:
                    next_occurrence = date(today.year + 1, month_of_year, day_of_month)
        
        aid_schedule = FinancialAidSchedule(
            member_id=schedule['member_id'],
            campus_id=schedule['campus_id'],
            title=schedule['title'],
            aid_type=schedule['aid_type'],
            aid_amount=schedule['aid_amount'],
            frequency=schedule['frequency'],
            start_date=start_date,
            end_date=schedule.get('end_date'),
            day_of_week=schedule.get('day_of_week'),
            day_of_month=schedule.get('day_of_month'),
            month_of_year=schedule.get('month_of_year'),
            next_occurrence=next_occurrence,
            created_by=current_user['id'],
            notes=schedule.get('notes')
        )
        
        # Serialize dates for MongoDB
        schedule_dict = aid_schedule.model_dump()
        schedule_dict['start_date'] = schedule_dict['start_date'].isoformat()
        if schedule_dict.get('end_date'):
            schedule_dict['end_date'] = schedule_dict['end_date'].isoformat()
        schedule_dict['next_occurrence'] = schedule_dict['next_occurrence'].isoformat()
        
        await db.financial_aid_schedules.insert_one(schedule_dict)
        
        # Invalidate dashboard cache
        await invalidate_dashboard_cache(schedule['campus_id'])
        
        return aid_schedule
    except Exception as e:
        logger.error(f"Error creating aid schedule: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/financial-aid-schedules")
async def list_aid_schedules(
    member_id: Optional[str] = None,
    active_only: bool = True,
    current_user: dict = Depends(get_current_user)
):
    """List financial aid schedules"""
    try:
        query = get_campus_filter(current_user)
        
        if member_id:
            query['member_id'] = member_id
        
        if active_only:
            query['is_active'] = True
        
        schedules = await db.financial_aid_schedules.find(query, {"_id": 0}).to_list(1000)
        return schedules
    except Exception as e:
        logger.error(f"Error listing aid schedules: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.delete("/financial-aid-schedules/{schedule_id}/ignored-occurrence/{date}")
async def remove_ignored_occurrence(schedule_id: str, date: str, current_user: dict = Depends(get_current_user)):
    """Remove a specific ignored occurrence from a schedule"""
    try:
        schedule = await db.financial_aid_schedules.find_one({"id": schedule_id}, {"_id": 0})
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")
        
        ignored_list = schedule.get("ignored_occurrences", [])
        if date in ignored_list:
            ignored_list.remove(date)
        
        await db.financial_aid_schedules.update_one(
            {"id": schedule_id},
            {"$set": {
                "ignored_occurrences": ignored_list,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        # Invalidate dashboard cache
        await invalidate_dashboard_cache(schedule["campus_id"])
        
        return {"success": True, "message": "Ignored occurrence removed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing ignored occurrence: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.delete("/financial-aid-schedules/{schedule_id}/ignored-occurrence/{occurrence_date}")
async def remove_ignored_occurrence(schedule_id: str, occurrence_date: str):
    """Remove a specific ignored occurrence from the schedule"""
    try:
        schedule = await db.financial_aid_schedules.find_one({"id": schedule_id}, {"_id": 0, "ignored_occurrences": 1, "campus_id": 1})
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")
        
        # Remove the occurrence from ignored list
        ignored_list = schedule.get("ignored_occurrences", [])
        if occurrence_date in ignored_list:
            ignored_list.remove(occurrence_date)
        
        await db.financial_aid_schedules.update_one(
            {"id": schedule_id},
            {"$set": {
                "ignored_occurrences": ignored_list,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        # Invalidate dashboard cache
        await invalidate_dashboard_cache(schedule["campus_id"])
        
        return {"success": True, "message": "Ignored occurrence removed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing ignored occurrence: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/financial-aid-schedules/{schedule_id}/clear-ignored")
async def clear_all_ignored_occurrences(schedule_id: str, current_user: dict = Depends(get_current_user)):
    """Clear all ignored occurrences for a schedule"""
    try:
        schedule = await db.financial_aid_schedules.find_one({"id": schedule_id}, {"_id": 0})
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")
        
        # Get member name for logging
        member = await db.members.find_one({"id": schedule["member_id"]}, {"_id": 0})
        member_name = member["name"] if member else "Unknown"
        
        await db.financial_aid_schedules.update_one(
            {"id": schedule_id},
            {"$set": {
                "ignored_occurrences": [],
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        # Log activity
        await log_activity(
            campus_id=schedule["campus_id"],
            user_id=current_user["id"],
            user_name=current_user["name"],
            action_type=ActivityActionType.CLEAR_IGNORED,
            member_id=schedule["member_id"],
            member_name=member_name,
            notes=f"Cleared all ignored occurrences for {schedule.get('aid_type', 'financial aid')} schedule",
            user_photo_url=current_user.get("photo_url")
        )
        
        # Invalidate dashboard cache
        await invalidate_dashboard_cache(schedule["campus_id"])
        
        return {"success": True, "message": "All ignored occurrences cleared"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing ignored occurrences: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.delete("/financial-aid-schedules/{schedule_id}")
async def delete_aid_schedule(schedule_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a financial aid schedule"""
    try:
        # Get schedule first to get campus_id
        schedule = await db.financial_aid_schedules.find_one({"id": schedule_id}, {"_id": 0, "campus_id": 1})
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")
        
        result = await db.financial_aid_schedules.delete_one({"id": schedule_id})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Schedule not found")
        
        # Invalidate dashboard cache
        await invalidate_dashboard_cache(schedule["campus_id"])
        
        return {"success": True, "message": "Financial aid schedule deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting aid schedule: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/financial-aid-schedules/{schedule_id}/stop")
async def stop_aid_schedule(schedule_id: str, current_user: dict = Depends(get_current_user)):
    """Manually stop a financial aid schedule"""
    try:
        # Get schedule first
        schedule = await db.financial_aid_schedules.find_one({"id": schedule_id}, {"_id": 0})
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")
        
        # Get member name for logging
        member = await db.members.find_one({"id": schedule["member_id"]}, {"_id": 0})
        member_name = member["name"] if member else "Unknown"
        
        result = await db.financial_aid_schedules.update_one(
            {"id": schedule_id},
            {"$set": {
                "is_active": False,
                "stopped_by_user_id": current_user["id"],
                "stopped_by_user_name": current_user["name"],
                "stopped_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Schedule not found")
        
        # Log activity
        await log_activity(
            campus_id=schedule["campus_id"],
            user_id=current_user["id"],
            user_name=current_user["name"],
            action_type=ActivityActionType.STOP_SCHEDULE,
            member_id=schedule["member_id"],
            member_name=member_name,
            notes=f"Stopped {schedule.get('aid_type', 'financial aid')} schedule",
            user_photo_url=current_user.get("photo_url")
        )
        
        # Invalidate dashboard cache
        await invalidate_dashboard_cache(schedule["campus_id"])
        
        return {"success": True, "message": "Financial aid schedule stopped"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping aid schedule: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/financial-aid-schedules/member/{member_id}")
async def get_member_aid_schedules(member_id: str, current_user: dict = Depends(get_current_user)):
    """Get financial aid schedules for specific member (active + stopped with history)"""
    try:
        logger.info(f"[GET AID SCHEDULES] Querying for member_id={member_id}")
        
        # Get ALL schedules for this member (don't limit to 20)
        schedules = await db.financial_aid_schedules.find(
            {"member_id": member_id},
            {"_id": 0}
        ).sort("next_occurrence", 1).to_list(None)  # None = no limit
        
        # Log all schedule IDs found
        logger.info(f"[GET AID SCHEDULES] Found {len(schedules)} schedule IDs for member")
        
        # Filter: active schedules OR stopped schedules with ignored history
        filtered = [
            s for s in schedules 
            if s.get("is_active") or (s.get("ignored_occurrences") and len(s.get("ignored_occurrences", [])) > 0)
        ]
        
        # Enhanced logging for debugging
        logger.info(f"Total schedules: {len(schedules)}, Active+WithHistory: {len(filtered)}")
        if len(filtered) == 0 and len(schedules) > 0:
            # Debug why filter returned nothing
            for s in schedules[:3]:  # Check first 3
                logger.info(f"  Debug schedule: id={s.get('id')[:8]}, is_active={s.get('is_active')} (type={type(s.get('is_active'))}), ignored_occ={s.get('ignored_occurrences')} (type={type(s.get('ignored_occurrences'))}), member_id={s.get('member_id')[:8] if s.get('member_id') else 'None'}")
        
        return filtered
    except Exception as e:
        logger.error(f"Error getting member aid schedules: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/financial-aid-schedules/due-today")
async def get_aid_due_today(current_user: dict = Depends(get_current_user)):
    """Get financial aid schedules due today and overdue"""
    try:
        today = date.today().isoformat()
        query = get_campus_filter(current_user)
        query.update({
            "next_occurrence": {"$lte": today},  # Today and overdue
            "is_active": True
        })
        
        schedules = await db.financial_aid_schedules.find(query, {"_id": 0}).to_list(100)
        
        # Add member info and calculate overdue days
        for schedule in schedules:
            member = await db.members.find_one({"id": schedule["member_id"]}, {"_id": 0, "name": 1, "phone": 1, "photo_url": 1})
            if member:
                schedule["member_name"] = member["name"]
                schedule["member_phone"] = member["phone"]
                schedule["member_photo_url"] = member.get("photo_url")
                
                # Calculate how many days overdue
                next_date = date.fromisoformat(schedule["next_occurrence"])
                days_overdue = (date.today() - next_date).days
                schedule["days_overdue"] = max(0, days_overdue)
                schedule["status"] = "overdue" if days_overdue > 0 else "due_today"
        
        return schedules
    except Exception as e:
        logger.error(f"Error getting aid due today: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/financial-aid-schedules/{schedule_id}/mark-distributed")
async def mark_aid_distributed(schedule_id: str, current_user: dict = Depends(get_current_user)):
    """Mark scheduled aid as distributed and advance to next occurrence"""
    try:
        # Get the schedule
        schedule = await db.financial_aid_schedules.find_one({"id": schedule_id}, {"_id": 0})
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")
        
        # Get member name for logging
        member = await db.members.find_one({"id": schedule["member_id"]}, {"_id": 0, "name": 1})
        member_name = member["name"] if member else "Unknown"
        
        # Create care event for this payment
        payment_event_id = str(uuid.uuid4())
        await db.care_events.insert_one({
            "id": payment_event_id,
            "member_id": schedule["member_id"],
            "campus_id": schedule["campus_id"],
            "event_type": "financial_aid",
            "event_date": schedule["next_occurrence"],
            "title": f"{schedule['title']} - Scheduled Payment",
            "aid_type": schedule["aid_type"],
            "aid_amount": schedule["aid_amount"],
            "aid_notes": f"From {schedule['frequency']} schedule",
            "completed": True,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "completed_by_user_id": current_user["id"],
            "completed_by_user_name": current_user["name"],
            "created_by_user_id": current_user["id"],
            "created_by_user_name": current_user["name"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Log activity
        await log_activity(
            campus_id=schedule["campus_id"],
            user_id=current_user["id"],
            user_name=current_user["name"],
            action_type=ActivityActionType.COMPLETE_TASK,
            member_id=schedule["member_id"],
            member_name=member_name,
            care_event_id=payment_event_id,
            event_type=EventType.FINANCIAL_AID,
            notes=f"Marked {schedule.get('aid_type', 'financial aid')} as distributed - Rp {schedule.get('aid_amount', 0):,.0f}",
            user_photo_url=current_user.get("photo_url")
        )
        
        # Update member's last contact date and engagement status
        settings = await get_engagement_settings()
        status, days = calculate_engagement_status(datetime.now(timezone.utc), settings.get("atRiskDays", 60), settings.get("disconnectedDays", 90))
        
        await db.members.update_one(
            {"id": schedule["member_id"]},
            {"$set": {
                "last_contact_date": datetime.now(timezone.utc).isoformat(),
                "engagement_status": status,
                "days_since_last_contact": days,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        # Calculate next occurrence
        current_date = date.fromisoformat(schedule["next_occurrence"])
        today = date.today()
        
        if schedule["frequency"] == "weekly":
            next_date = current_date + timedelta(weeks=1)
        elif schedule["frequency"] == "monthly":
            # Safely advance to next month, handling day-of-month edge cases
            day_of_month = schedule.get("day_of_month", current_date.day)
            
            if current_date.month == 12:
                # December → January next year
                next_year = current_date.year + 1
                next_month = 1
            else:
                next_year = current_date.year
                next_month = current_date.month + 1
            
            # Handle months with fewer days (e.g., Jan 31 → Feb 28/29)
            try:
                next_date = date(next_year, next_month, day_of_month)
            except ValueError:
                # Day doesn't exist in next month, use last valid day
                if next_month == 2:
                    # February
                    if (next_year % 4 == 0 and next_year % 100 != 0) or (next_year % 400 == 0):
                        next_date = date(next_year, next_month, min(day_of_month, 29))
                    else:
                        next_date = date(next_year, next_month, min(day_of_month, 28))
                elif next_month in [4, 6, 9, 11]:
                    next_date = date(next_year, next_month, min(day_of_month, 30))
                else:
                    next_date = date(next_year, next_month, min(day_of_month, 31))
        elif schedule["frequency"] == "annually":
            next_date = current_date.replace(year=current_date.year + 1)
        else:
            next_date = current_date
        
        # Update schedule with new next occurrence
        # Log before update for debugging
        logger.info(f"[DISTRIBUTE] Before update - Schedule {schedule_id}: is_active={schedule.get('is_active')}, ignored_occurrences={schedule.get('ignored_occurrences')}, next_occurrence={schedule.get('next_occurrence')}")
        
        await db.financial_aid_schedules.update_one(
            {"id": schedule_id},
            {"$set": {
                "next_occurrence": next_date.isoformat(),
                "occurrences_completed": (schedule.get("occurrences_completed", 0) + 1),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        # Log after update for debugging
        updated_schedule = await db.financial_aid_schedules.find_one({"id": schedule_id}, {"_id": 0})
        logger.info(f"[DISTRIBUTE] After update - Schedule {schedule_id}: is_active={updated_schedule.get('is_active')}, ignored_occurrences={updated_schedule.get('ignored_occurrences')}, next_occurrence={updated_schedule.get('next_occurrence')}")
        
        # Invalidate dashboard cache
        await invalidate_dashboard_cache(schedule["campus_id"])
        
        return {
            "success": True,
            "message": "Payment marked as distributed and schedule advanced",
            "next_occurrence": next_date.isoformat()
        }
    except Exception as e:
        logger.error(f"Error marking aid distributed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/financial-aid-schedules/{schedule_id}/ignore")
async def ignore_financial_aid_schedule(schedule_id: str, user: dict = Depends(get_current_user)):
    """Mark a specific financial aid occurrence as ignored (not the entire schedule)"""
    try:
        schedule = await db.financial_aid_schedules.find_one({"id": schedule_id}, {"_id": 0})
        if not schedule:
            raise HTTPException(status_code=404, detail="Financial aid schedule not found")
        
        # Get member name for logging
        member = await db.members.find_one({"id": schedule["member_id"]}, {"_id": 0, "name": 1})
        member_name = member["name"] if member else "Unknown"
        
        current_occurrence = schedule.get("next_occurrence")
        if not current_occurrence:
            raise HTTPException(status_code=400, detail="No next occurrence to ignore")
        
        # Add current occurrence to ignored list
        ignored_list = schedule.get("ignored_occurrences", [])
        if current_occurrence not in ignored_list:
            ignored_list.append(current_occurrence)
        
        # Calculate next occurrence (skip ignored dates)
        current_date = date.fromisoformat(current_occurrence) if isinstance(current_occurrence, str) else current_occurrence
        
        # Log before update for debugging
        logger.info(f"[IGNORE] Before update - Schedule {schedule_id}: member_id={schedule.get('member_id')}, is_active={schedule.get('is_active')}, ignored_occurrences={schedule.get('ignored_occurrences')}, next_occurrence={schedule.get('next_occurrence')}")
        
        if schedule["frequency"] == "weekly":
            next_date = current_date + timedelta(weeks=1)
        elif schedule["frequency"] == "monthly":
            # Safely advance to next month, handling day-of-month edge cases
            day_of_month = schedule.get("day_of_month", current_date.day)
            
            if current_date.month == 12:
                # December → January next year
                next_year = current_date.year + 1
                next_month = 1
            else:
                next_year = current_date.year
                next_month = current_date.month + 1
            
            # Handle months with fewer days (e.g., Jan 31 → Feb 28/29)
            try:
                next_date = date(next_year, next_month, day_of_month)
            except ValueError:
                # Day doesn't exist in next month, use last valid day
                if next_month == 2:
                    # February
                    if (next_year % 4 == 0 and next_year % 100 != 0) or (next_year % 400 == 0):
                        next_date = date(next_year, next_month, min(day_of_month, 29))
                    else:
                        next_date = date(next_year, next_month, min(day_of_month, 28))
                elif next_month in [4, 6, 9, 11]:
                    next_date = date(next_year, next_month, min(day_of_month, 30))
                else:
                    next_date = date(next_year, next_month, min(day_of_month, 31))
        elif schedule["frequency"] == "annually":
            next_date = current_date.replace(year=current_date.year + 1)
        else:
            next_date = current_date
        
        await db.financial_aid_schedules.update_one(
            {"id": schedule_id},
            {"$set": {
                "ignored_occurrences": ignored_list,
                "next_occurrence": next_date.isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        # Log after update for debugging
        updated_schedule = await db.financial_aid_schedules.find_one({"id": schedule_id}, {"_id": 0})
        logger.info(f"[IGNORE] After update - Schedule {schedule_id}: is_active={updated_schedule.get('is_active')}, ignored_occurrences={updated_schedule.get('ignored_occurrences')}, next_occurrence={updated_schedule.get('next_occurrence')}")
        
        # CRITICAL DEBUG: Check if update actually persisted
        verify_schedule = await db.financial_aid_schedules.find_one({"id": schedule_id}, {"_id": 0})
        logger.info(f"[IGNORE] VERIFY - Schedule {schedule_id} from DB: is_active={verify_schedule.get('is_active')}, ignored={verify_schedule.get('ignored_occurrences')}")
        
        # Log activity
        await log_activity(
            campus_id=schedule["campus_id"],
            user_id=user["id"],
            user_name=user["name"],
            action_type=ActivityActionType.IGNORE_TASK,
            member_id=schedule["member_id"],
            member_name=member_name,
            notes=f"Ignored {schedule.get('aid_type', 'financial aid')} payment on {current_occurrence}",
            user_photo_url=user.get("photo_url")
        )
        
        # Invalidate dashboard cache
        await invalidate_dashboard_cache(schedule["campus_id"])
        
        return {
            "success": True, 
            "message": f"Occurrence on {current_occurrence} ignored. Next payment: {next_date.isoformat()}",
            "ignored_date": current_occurrence,
            "next_occurrence": next_date.isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== FINANCIAL AID ENDPOINTS ====================

@api_router.post("/accident-followup/{stage_id}/ignore")
async def ignore_accident_stage(stage_id: str, user: dict = Depends(get_current_user)):
    """Mark an accident followup stage as ignored/dismissed"""
    try:
        stage = await db.accident_followup.find_one({"id": stage_id}, {"_id": 0})
        if not stage:
            raise HTTPException(status_code=404, detail="Accident followup not found")
        
        # Get member name for logging
        member = await db.members.find_one({"id": stage["member_id"]}, {"_id": 0, "name": 1})
        member_name = member["name"] if member else "Unknown"
        
        await db.accident_followup.update_one(
            {"id": stage_id},
            {"$set": {
                "ignored": True,
                "ignored_at": datetime.now(timezone.utc).isoformat(),
                "ignored_by": user.get("id"),
                "ignored_by_name": user.get("name")
            }}
        )
        
        # Create timeline entry (will show in Timeline tab, NOT in Accident tab)
        campus_tz = await get_campus_timezone(stage["campus_id"])
        today_date = get_date_in_timezone(campus_tz)
        
        timeline_event_id = str(uuid.uuid4())
        await db.care_events.insert_one({
            "id": timeline_event_id,
            "member_id": stage["member_id"],
            "campus_id": stage["campus_id"],
            "event_type": "accident_illness",
            "event_date": today_date,
            "title": f"Accident Follow-up: {stage['stage'].replace('_', ' ')} (Ignored)",
            "description": "Stage was marked as ignored/not applicable",
            "accident_stage_id": stage_id,  # Link for undo
            "ignored": True,
            "ignored_at": datetime.now(timezone.utc).isoformat(),
            "ignored_by": user.get("id"),
            "ignored_by_name": user.get("name"),
            "created_by_user_id": user.get("id"),
            "created_by_user_name": user.get("name"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Log activity
        await log_activity(
            campus_id=stage["campus_id"],
            user_id=user["id"],
            user_name=user["name"],
            action_type=ActivityActionType.IGNORE_TASK,
            member_id=stage["member_id"],
            member_name=member_name,
            care_event_id=timeline_event_id,
            event_type=EventType.ACCIDENT_ILLNESS,
            notes=f"Ignored accident/illness follow-up: {stage['stage'].replace('_', ' ')}",
            user_photo_url=user.get("photo_url")
        )
        
        # Invalidate dashboard cache
        await invalidate_dashboard_cache(stage["campus_id"])
        
        return {"success": True, "message": "Accident followup ignored"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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

@api_router.get("/financial-aid/recipients")
async def get_financial_aid_recipients():
    """Get list of all financial aid recipients with totals"""
    try:
        # Aggregate financial aid by member
        pipeline = [
            {"$match": {"event_type": EventType.FINANCIAL_AID}},
            {"$group": {
                "_id": "$member_id",
                "total_amount": {"$sum": "$aid_amount"},
                "aid_count": {"$sum": 1}
            }},
            {"$sort": {"total_amount": -1}}
        ]
        
        recipients_data = await db.care_events.aggregate(pipeline).to_list(1000)
        
        # Fetch member names and photos
        recipients = []
        for data in recipients_data:
            member_id = data["_id"]
            if member_id:
                member = await db.members.find_one({"id": member_id}, {"_id": 0, "name": 1, "photo_url": 1})
                member_name = "Unknown"
                photo_url = None
                
                if member:
                    member_name = member.get("name", "Unknown")
                    photo_url = member.get("photo_url")
                else:
                    # Try to get name from the first event's title
                    event = await db.care_events.find_one(
                        {"member_id": member_id, "event_type": EventType.FINANCIAL_AID},
                        {"_id": 0, "title": 1}
                    )
                    if event and event.get("title"):
                        title = event["title"]
                        if " - " in title:
                            member_name = title.split(" - ", 1)[1].strip()
                
                recipients.append({
                    "member_id": member_id,
                    "member_name": member_name,
                    "photo_url": photo_url,
                    "total_amount": data["total_amount"],
                    "aid_count": data["aid_count"]
                })
        
        return recipients
    except Exception as e:
        logger.error(f"Error getting financial aid recipients: {str(e)}")
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
            if status in [EngagementStatus.AT_RISK, EngagementStatus.DISCONNECTED]:
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
    campus_id: Optional[str] = None,
    current_admin: dict = Depends(get_current_admin)
):
    """Continuously sync members from external API with archiving"""
    try:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(api_url, headers=headers)
            external_members = response.json()
        
        sync_campus_id = campus_id or current_admin.get('campus_id')
        synced_count = 0
        updated_count = 0
        archived_count = 0
        errors = []
        
        # Track external IDs from API
        external_ids = set()
        
        for ext_member in external_members:
            try:
                ext_id = str(ext_member.get('id'))
                external_ids.add(ext_id)
                
                # Check if member exists by external_member_id
                existing = await db.members.find_one(
                    {"external_member_id": ext_id},
                    {"_id": 0}
                )
                
                if existing:
                    # Update existing member with latest data
                    update_data = {
                        "name": ext_member.get('name'),
                        "phone": ext_member.get('phone'),
                        "email": ext_member.get('email'),
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }
                    
                    # If member was archived, un-archive them
                    if existing.get("is_archived"):
                        update_data["is_archived"] = False
                        update_data["archived_at"] = None
                        update_data["archived_reason"] = None
                    
                    # Update other fields if provided
                    if ext_member.get('birth_date'):
                        update_data["birth_date"] = ext_member.get('birth_date')
                    if ext_member.get('address'):
                        update_data["address"] = ext_member.get('address')
                    if ext_member.get('membership_status'):
                        update_data["membership_status"] = ext_member.get('membership_status')
                    if ext_member.get('category'):
                        update_data["category"] = ext_member.get('category')
                    if ext_member.get('gender'):
                        update_data["gender"] = ext_member.get('gender')
                    
                    await db.members.update_one(
                        {"id": existing["id"]},
                        {"$set": update_data}
                    )
                    updated_count += 1
                else:
                    # Create new member
                    member = Member(
                        name=ext_member.get('name'),
                        phone=ext_member.get('phone'),
                        campus_id=sync_campus_id,
                        external_member_id=ext_id,
                        email=ext_member.get('email'),
                        birth_date=ext_member.get('birth_date'),
                        address=ext_member.get('address'),
                        membership_status=ext_member.get('membership_status'),
                        category=ext_member.get('category'),
                        gender=ext_member.get('gender')
                    )
                    member_dict = member.model_dump()
                    if member_dict.get('birth_date'):
                        member_dict['birth_date'] = member_dict['birth_date'].isoformat()
                    await db.members.insert_one(member_dict)
                
                synced_count += 1
            except Exception as e:
                errors.append(f"Error syncing {ext_member.get('name')}: {str(e)}")
        
        # Archive members that exist in our DB but not in external API source
        # (Only for members with external_member_id from this source)
        existing_external_members = await db.members.find(
            {
                "campus_id": sync_campus_id,
                "external_member_id": {"$exists": True, "$ne": None},
                "is_archived": {"$ne": True}
            },
            {"_id": 0, "id": 1, "name": 1, "external_member_id": 1}
        ).to_list(None)
        
        for member in existing_external_members:
            if member["external_member_id"] not in external_ids:
                # Member no longer in external source - archive them
                await db.members.update_one(
                    {"id": member["id"]},
                    {"$set": {
                        "is_archived": True,
                        "archived_at": datetime.now(timezone.utc).isoformat(),
                        "archived_reason": "Removed from external API source",
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }}
                )
                archived_count += 1
                logger.info(f"Archived member {member['name']} - no longer in external source")
        
        return {
            "success": True,
            "synced_count": synced_count,
            "updated_count": updated_count,
            "archived_count": archived_count,
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

# ==================== AUTO-SUGGESTIONS ENDPOINTS ====================

@api_router.get("/suggestions/follow-up")
async def get_intelligent_suggestions(current_user: dict = Depends(get_current_user)):
    """Generate intelligent follow-up recommendations"""
    try:
        campus_filter = get_campus_filter(current_user)
        today = date.today()
        
        # Get members and their recent activities
        members = await db.members.find(campus_filter, {"_id": 0}).to_list(1000)
        recent_events = await db.care_events.find({**campus_filter}, {"_id": 0}).to_list(2000)
        
        suggestions = []
        
        for member in members:
            member_events = [e for e in recent_events if e['member_id'] == member['id']]
            last_contact = member.get('last_contact_date')
            days_since = member.get('days_since_last_contact', 999)
            
            # Skip members contacted in last 48 hours (recently contacted)
            if last_contact:
                if isinstance(last_contact, str):
                    last_contact_date = datetime.fromisoformat(last_contact)
                else:
                    last_contact_date = last_contact
                
                # Ensure both dates are timezone-aware for comparison
                if last_contact_date.tzinfo is None:
                    last_contact_date = last_contact_date.replace(tzinfo=timezone.utc)
                
                now_utc = datetime.now(timezone.utc)
                
                # If contacted in last 2 days, don't suggest
                if (now_utc - last_contact_date).days <= 2:
                    continue
            
            # AI-powered suggestions based on patterns
            if days_since > 90:
                suggestions.append({
                    "member_id": member['id'],
                    "member_name": member['name'],
                    "member_phone": member['phone'],
                    "member_photo_url": member.get('photo_url'),
                    "priority": "high",
                    "suggestion": "Urgent reconnection needed",
                    "reason": f"No contact for {days_since} days - risk of disconnection",
                    "recommended_action": "Personal visit or phone call",
                    "urgency_score": min(100, days_since)
                })
            elif member.get('age', 0) > 65 and days_since > 30:
                suggestions.append({
                    "member_id": member['id'],
                    "member_name": member['name'],
                    "member_phone": member['phone'],
                    "member_photo_url": member.get('photo_url'),
                    "priority": "medium",
                    "suggestion": "Senior care check-in",
                    "reason": f"Senior member, {days_since} days since contact",
                    "recommended_action": "Health and wellness check",
                    "urgency_score": days_since + 20  # Boost for seniors
                })
            elif member.get('membership_status') == 'Visitor' and days_since > 14:
                suggestions.append({
                    "member_id": member['id'],
                    "member_name": member['name'],
                    "member_phone": member['phone'],
                    "member_photo_url": member.get('photo_url'),
                    "priority": "medium",
                    "suggestion": "Visitor follow-up",
                    "reason": "New visitor needs welcoming contact",
                    "recommended_action": "Welcome visit or invitation to activities",
                    "urgency_score": days_since + 10
                })
            elif len([e for e in member_events if e.get('event_type') == 'financial_aid']) > 0 and days_since > 60:
                suggestions.append({
                    "member_id": member['id'],
                    "member_name": member['name'],
                    "member_phone": member['phone'],
                    "member_photo_url": member.get('photo_url'),
                    "priority": "medium",
                    "suggestion": "Financial aid follow-up",
                    "reason": "Previous aid recipient, check on progress",
                    "recommended_action": "Follow-up on aid effectiveness",
                    "urgency_score": days_since + 15
                })
            elif member.get('marital_status') == 'Single' and member.get('age', 0) > 25 and days_since > 45:
                suggestions.append({
                    "member_id": member['id'],
                    "member_name": member['name'],
                    "member_phone": member['phone'],
                    "member_photo_url": member.get('photo_url'),
                    "priority": "low",
                    "suggestion": "Single adult engagement",
                    "reason": "Single adult may need community connection",
                    "recommended_action": "Invite to small groups or social activities",
                    "urgency_score": days_since
                })
        
        # Sort by urgency score and return top suggestions
        suggestions.sort(key=lambda x: x['urgency_score'], reverse=True)
        return suggestions[:20]  # Top 20 suggestions
        
    except Exception as e:
        logger.error(f"Error generating suggestions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/analytics/demographic-trends")
async def get_demographic_trends(current_user: dict = Depends(get_current_user)):
    """Analyze demographic trends and population shifts"""
    try:
        campus_filter = get_campus_filter(current_user)
        members = await db.members.find(campus_filter, {"_id": 0}).to_list(1000)
        events = await db.care_events.find({**campus_filter}, {"_id": 0}).to_list(2000)
        
        # Age group analysis
        age_groups = {
            'Children (0-12)': {'count': 0, 'care_events': 0},
            'Teenagers (13-17)': {'count': 0, 'care_events': 0},
            'Young Adults (18-30)': {'count': 0, 'care_events': 0},
            'Adults (31-60)': {'count': 0, 'care_events': 0},
            'Seniors (60+)': {'count': 0, 'care_events': 0}
        }
        
        # Membership trends
        membership_trends = {
            'Member': {'count': 0, 'engagement_score': 0},
            'Non Member': {'count': 0, 'engagement_score': 0},
            'Visitor': {'count': 0, 'engagement_score': 0},
            'Sympathizer': {'count': 0, 'engagement_score': 0}
        }
        
        # Care needs by demographics
        care_needs = {
            'Financial aid by age': {},
            'Grief support by age': {},
            'Medical needs by age': {},
            'Engagement by membership': {}
        }
        
        for member in members:
            age = member.get('age', 0)
            membership = member.get('membership_status', 'Unknown')
            days_since_contact = member.get('days_since_last_contact', 999)
            
            # Age group classification
            if age <= 12:
                age_group = 'Children (0-12)'
            elif age <= 17:
                age_group = 'Teenagers (13-17)'
            elif age <= 30:
                age_group = 'Young Adults (18-30)'
            elif age <= 60:
                age_group = 'Adults (31-60)'
            else:
                age_group = 'Seniors (60+)'
            
            age_groups[age_group]['count'] += 1
            
            # Engagement scoring (inverse of days since contact)
            engagement_score = max(0, 100 - days_since_contact)
            
            if membership in membership_trends:
                membership_trends[membership]['count'] += 1
                membership_trends[membership]['engagement_score'] += engagement_score
            
            # Care event analysis for this member
            member_events = [e for e in events if e['member_id'] == member['id']]
            age_groups[age_group]['care_events'] += len(member_events)
            
            # Care needs analysis
            financial_events = len([e for e in member_events if e.get('event_type') == 'financial_aid'])
            grief_events = len([e for e in member_events if e.get('event_type') == 'grief_loss'])
            medical_events = len([e for e in member_events if e.get('event_type') == 'accident_illness'])
            
            age_key = f"{age//10*10}s"  # 20s, 30s, 40s, etc.
            care_needs['Financial aid by age'][age_key] = care_needs['Financial aid by age'].get(age_key, 0) + financial_events
            care_needs['Grief support by age'][age_key] = care_needs['Grief support by age'].get(age_key, 0) + grief_events
            care_needs['Medical needs by age'][age_key] = care_needs['Medical needs by age'].get(age_key, 0) + medical_events
        
        # Calculate averages for membership engagement
        for status, data in membership_trends.items():
            if data['count'] > 0:
                data['avg_engagement'] = round(data['engagement_score'] / data['count'])
            else:
                data['avg_engagement'] = 0
        
        # Generate insights
        insights = []
        
        # Age-based insights
        highest_count_group = max(age_groups.items(), key=lambda x: x[1]['count'])
        highest_care_group = max(age_groups.items(), key=lambda x: x[1]['care_events'])
        
        insights.append(f"Largest demographic: {highest_count_group[0]} ({highest_count_group[1]['count']} members)")
        insights.append(f"Most care needed: {highest_care_group[0]} ({highest_care_group[1]['care_events']} events)")
        
        # Membership insights
        lowest_engagement = min(membership_trends.items(), key=lambda x: x[1]['avg_engagement'])
        insights.append(f"Lowest engagement: {lowest_engagement[0]} (avg score: {lowest_engagement[1]['avg_engagement']})")
        
        return {
            "age_groups": [{"name": k, **v} for k, v in age_groups.items()],
            "membership_trends": [{"status": k, **v} for k, v in membership_trends.items()],
            "care_needs": care_needs,
            "insights": insights,
            "total_members": len(members),
            "analysis_date": today.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error analyzing demographic trends: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== CONFIGURATION ENDPOINTS (For Mobile App) ====================

@api_router.get("/config/aid-types")
async def get_aid_types():
    """Get all financial aid types"""
    return [
        {"value": "education", "label": "Education Support", "icon": "🎓"},
        {"value": "medical", "label": "Medical Bills", "icon": "🏥"},
        {"value": "emergency", "label": "Emergency Relief", "icon": "🚨"},
        {"value": "housing", "label": "Housing Assistance", "icon": "🏠"},
        {"value": "food", "label": "Food Support", "icon": "🍞"},
        {"value": "funeral_costs", "label": "Funeral Costs", "icon": "⚱️"},
        {"value": "other", "label": "Other", "icon": "📋"}
    ]

@api_router.get("/config/event-types")
async def get_event_types():
    """Get all care event types"""
    return [
        {"value": "birthday", "label": "Birthday", "icon": "🎂"},
        {"value": "childbirth", "label": "Childbirth", "icon": "👶"},
        {"value": "grief_loss", "label": "Grief/Loss", "icon": "💔"},
        {"value": "new_house", "label": "New House", "icon": "🏠"},
        {"value": "accident_illness", "label": "Accident/Illness", "icon": "🚑"},
        {"value": "financial_aid", "label": "Financial Aid", "icon": "💰"},
        {"value": "regular_contact", "label": "Regular Contact", "icon": "📞"}
    ]

@api_router.get("/config/relationship-types")
async def get_relationship_types():
    """Get grief relationship types"""
    return [
        {"value": "spouse", "label": "Spouse"},
        {"value": "parent", "label": "Parent"},
        {"value": "child", "label": "Child"},
        {"value": "sibling", "label": "Sibling"},
        {"value": "friend", "label": "Friend"},
        {"value": "other", "label": "Other"}
    ]

@api_router.get("/config/user-roles")
async def get_user_roles():
    """Get user role types"""
    return [
        {"value": "full_admin", "label": "Full Administrator", "description": "Access all campuses"},
        {"value": "campus_admin", "label": "Campus Administrator", "description": "Manage one campus"},
        {"value": "pastor", "label": "Pastor", "description": "Pastoral care staff"}
    ]

@api_router.get("/config/engagement-statuses")
async def get_engagement_statuses():
    """Get engagement status types"""
    return [
        {"value": "active", "label": "Active", "color": "green", "description": "Recent contact"},
        {"value": "at_risk", "label": "At Risk", "color": "amber", "description": "30-59 days no contact"},
        {"value": "disconnected", "label": "Disconnected", "color": "red", "description": "90+ days no contact"}
    ]

@api_router.get("/config/weekdays")
async def get_weekdays():
    """Get weekday options"""
    return [
        {"value": "monday", "label": "Monday", "short": "Mon"},
        {"value": "tuesday", "label": "Tuesday", "short": "Tue"},
        {"value": "wednesday", "label": "Wednesday", "short": "Wed"},
        {"value": "thursday", "label": "Thursday", "short": "Thu"},
        {"value": "friday", "label": "Friday", "short": "Fri"},
        {"value": "saturday", "label": "Saturday", "short": "Sat"},
        {"value": "sunday", "label": "Sunday", "short": "Sun"}
    ]

@api_router.get("/config/months")
async def get_months():
    """Get month options"""
    return [
        {"value": 1, "label": "January", "short": "Jan"},
        {"value": 2, "label": "February", "short": "Feb"},
        {"value": 3, "label": "March", "short": "Mar"},
        {"value": 4, "label": "April", "short": "Apr"},
        {"value": 5, "label": "May", "short": "May"},
        {"value": 6, "label": "June", "short": "Jun"},
        {"value": 7, "label": "July", "short": "Jul"},
        {"value": 8, "label": "August", "short": "Aug"},
        {"value": 9, "label": "September", "short": "Sep"},
        {"value": 10, "label": "October", "short": "Oct"},
        {"value": 11, "label": "November", "short": "Nov"},
        {"value": 12, "label": "December", "short": "Dec"}
    ]

@api_router.get("/config/frequency-types")
async def get_frequency_types():
    """Get financial aid frequency types"""
    return [
        {"value": "one_time", "label": "One-time Payment", "description": "Single payment (already given)"},
        {"value": "weekly", "label": "Weekly Schedule", "description": "Future weekly payments"},
        {"value": "monthly", "label": "Monthly Schedule", "description": "Future monthly payments"},
        {"value": "annually", "label": "Annual Schedule", "description": "Future annual payments"}
    ]

@api_router.get("/config/membership-statuses")
async def get_membership_statuses():
    """Get membership status types"""
    return [
        {"value": "Member", "label": "Member", "active": True},
        {"value": "Non Member", "label": "Non Member", "active": False},
        {"value": "Visitor", "label": "Visitor", "active": False},
        {"value": "Sympathizer", "label": "Sympathizer", "active": False},
        {"value": "Member (Inactive)", "label": "Member (Inactive)", "active": False}
    ]

@api_router.get("/config/all")
async def get_all_config():
    """Get all configuration data for mobile app"""
    try:
        return {
            "aid_types": await get_aid_types(),
            "event_types": await get_event_types(),
            "relationship_types": await get_relationship_types(),
            "user_roles": await get_user_roles(),
            "engagement_statuses": await get_engagement_statuses(),
            "weekdays": await get_weekdays(),
            "months": await get_months(),
            "frequency_types": await get_frequency_types(),
            "membership_statuses": await get_membership_statuses(),
            "settings": {
                "engagement": await get_engagement_settings(),
                "grief_stages": await get_grief_stages(),
                "accident_followup": await get_accident_followup()
            }
        }
    except Exception as e:
        logger.error(f"Error getting all config: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== SETTINGS CONFIGURATION ENDPOINTS ====================

@api_router.post("/admin/recalculate-engagement")
async def recalculate_all_engagement_status(user: dict = Depends(get_current_user)):
    """Recalculate engagement status for all members (admin only)"""
    try:
        if user.get("role") not in [UserRole.FULL_ADMIN, UserRole.CAMPUS_ADMIN]:
            raise HTTPException(status_code=403, detail="Only admins can recalculate engagement")
        
        # Get engagement settings
        settings = await get_engagement_settings()
        at_risk_days = settings.get("atRiskDays", 60)
        disconnected_days = settings.get("disconnectedDays", 90)
        
        # Get all members
        members = await db.members.find({}, {"_id": 0, "id": 1, "last_contact_date": 1}).to_list(None)
        
        updated_count = 0
        stats = {"active": 0, "at_risk": 0, "disconnected": 0}
        
        for member in members:
            status, days = calculate_engagement_status(
                member.get("last_contact_date"),
                at_risk_days,
                disconnected_days
            )
            
            await db.members.update_one(
                {"id": member["id"]},
                {"$set": {
                    "engagement_status": status,
                    "days_since_last_contact": days,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            
            stats[status] = stats.get(status, 0) + 1
            updated_count += 1
        
        # Clear dashboard cache for all campuses
        await db.dashboard_cache.delete_many({})
        
        logger.info(f"Recalculated engagement for {updated_count} members")
        
        return {
            "success": True,
            "updated_count": updated_count,
            "stats": stats,
            "thresholds": {
                "at_risk_days": at_risk_days,
                "disconnected_days": disconnected_days
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recalculating engagement: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/settings/engagement")
async def get_engagement_settings():
    """Get engagement threshold settings"""
    try:
        settings = await db.settings.find_one({"type": "engagement"}, {"_id": 0})
        if not settings:
            # Return defaults
            return {
                "atRiskDays": 60,
                "inactiveDays": 90
            }
        return settings.get("data", {"atRiskDays": 60, "inactiveDays": 90})
    except Exception as e:
        logger.error(f"Error getting engagement settings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.put("/settings/engagement")
async def update_engagement_settings(settings: dict, current_admin: dict = Depends(get_current_admin)):
    """Update engagement threshold settings"""
    try:
        await db.settings.update_one(
            {"type": "engagement"},
            {"$set": {
                "type": "engagement",
                "data": settings,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "updated_by": current_admin["id"]
            }},
            upsert=True
        )
        return {"success": True, "message": "Engagement settings updated"}
    except Exception as e:
        logger.error(f"Error updating engagement settings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/settings/overdue_writeoff")
async def get_overdue_writeoff_settings(user: dict = Depends(get_current_user)):
    """Get overdue write-off threshold settings"""
    try:
        settings = await db.settings.find_one({"key": "overdue_writeoff"}, {"_id": 0})
        return settings if settings else {
            "key": "overdue_writeoff", 
            "data": {
                "birthday": 7,
                "financial_aid": 0,
                "accident_illness": 14,
                "grief_support": 14
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.put("/settings/overdue_writeoff")
async def update_overdue_writeoff_settings(settings_data: dict, user: dict = Depends(get_current_user)):
    """Update overdue write-off threshold settings"""
    try:
        if user.get("role") not in [UserRole.FULL_ADMIN, UserRole.CAMPUS_ADMIN]:
            raise HTTPException(status_code=403, detail="Only admins can update settings")
        
        await db.settings.update_one(
            {"key": "overdue_writeoff"},
            {"$set": {
                "key": "overdue_writeoff",
                "data": settings_data.get("data", {}),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }},
            upsert=True
        )
        return {"success": True, "message": "Write-off settings updated"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/settings/grief-stages")
async def get_grief_stages():
    """Get grief support stage configuration"""
    try:
        settings = await db.settings.find_one({"type": "grief_stages"}, {"_id": 0})
        if not settings:
            # Return defaults
            return [
                {"stage": "1_week", "days": 7, "name": "1 Week After"},
                {"stage": "2_weeks", "days": 14, "name": "2 Weeks After"},
                {"stage": "1_month", "days": 30, "name": "1 Month After"},
                {"stage": "3_months", "days": 90, "name": "3 Months After"},
                {"stage": "6_months", "days": 180, "name": "6 Months After"},
                {"stage": "1_year", "days": 365, "name": "1 Year After"}
            ]
        return settings.get("data", [])
    except Exception as e:
        logger.error(f"Error getting grief stages: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.put("/settings/grief-stages")
async def update_grief_stages(stages: list, current_admin: dict = Depends(get_current_admin)):
    """Update grief support stage configuration"""
    try:
        await db.settings.update_one(
            {"type": "grief_stages"},
            {"$set": {
                "type": "grief_stages",
                "data": stages,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "updated_by": current_admin["id"]
            }},
            upsert=True
        )
        return {"success": True, "message": "Grief stages configuration updated"}
    except Exception as e:
        logger.error(f"Error updating grief stages: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/settings/accident-followup")
async def get_accident_followup():
    """Get accident follow-up configuration"""
    try:
        settings = await db.settings.find_one({"type": "accident_followup"}, {"_id": 0})
        if not settings:
            # Return defaults
            return [
                {"stage": "first_followup", "days": 3, "name": "First Follow-up"},
                {"stage": "second_followup", "days": 7, "name": "Second Follow-up"},
                {"stage": "final_followup", "days": 14, "name": "Final Follow-up"}
            ]
        return settings.get("data", [])
    except Exception as e:
        logger.error(f"Error getting accident followup settings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.put("/settings/accident-followup")
async def update_accident_followup(config: list, current_admin: dict = Depends(get_current_admin)):
    """Update accident follow-up configuration"""
    try:
        await db.settings.update_one(
            {"type": "accident_followup"},
            {"$set": {
                "type": "accident_followup",
                "data": config,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "updated_by": current_admin["id"]
            }},
            upsert=True
        )
        return {"success": True, "message": "Accident follow-up configuration updated"}
    except Exception as e:
        logger.error(f"Error updating accident followup settings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/settings/user-preferences/{user_id}")
async def get_user_preferences(user_id: str):
    """Get user preferences (language, etc.)"""
    try:
        prefs = await db.user_preferences.find_one({"user_id": user_id}, {"_id": 0})
        if not prefs:
            return {"language": "id"}  # Default Indonesian
        return prefs.get("data", {"language": "id"})
    except Exception as e:
        logger.error(f"Error getting user preferences: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.put("/settings/user-preferences/{user_id}")
async def update_user_preferences(user_id: str, preferences: dict):
    """Update user preferences"""
    try:
        await db.user_preferences.update_one(
            {"user_id": user_id},
            {"$set": {
                "user_id": user_id,
                "data": preferences,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }},
            upsert=True
        )
        return {"success": True, "message": "User preferences updated"}
    except Exception as e:
        logger.error(f"Error updating user preferences: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

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


# ==================== SYNC ENDPOINTS ====================

@api_router.post("/sync/config")
async def save_sync_config(config: SyncConfigCreate, current_user: dict = Depends(get_current_user)):
    """Save sync configuration for campus"""
    if current_user["role"] not in [UserRole.FULL_ADMIN, UserRole.CAMPUS_ADMIN]:
        raise HTTPException(status_code=403, detail="Only administrators can configure sync")
    
    try:
        campus_id = current_user.get("campus_id")
        if not campus_id and current_user["role"] == UserRole.FULL_ADMIN:
            raise HTTPException(status_code=400, detail="Please select a campus first")
        
        # Check if config exists
        existing = await db.sync_configs.find_one({"campus_id": campus_id}, {"_id": 0})
        
        # Get core church_id by logging in to core API
        core_church_id = None
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                login_response = await client.post(
                    f"{config.api_base_url.rstrip('/')}/api/auth/login",
                    json={"email": config.api_email, "password": config.api_password}
                )
                if login_response.status_code == 200:
                    login_data = login_response.json()
                    core_church_id = login_data.get("user", {}).get("church_id") or login_data.get("church", {}).get("id")
        except:
            pass  # If we can't get church_id, continue without it
        
        sync_config_data = {
            "campus_id": campus_id,
            "core_church_id": core_church_id,
            "sync_method": config.sync_method,
            "api_base_url": config.api_base_url.rstrip('/'),
            "api_email": config.api_email,
            "api_password": config.api_password,
            "polling_interval_hours": config.polling_interval_hours,
            "reconciliation_enabled": config.reconciliation_enabled,
            "reconciliation_time": config.reconciliation_time,
            "filter_mode": config.filter_mode,
            "filter_rules": config.filter_rules or [],
            "is_enabled": config.is_enabled,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        if existing:
            # Preserve existing webhook_secret
            sync_config_data["webhook_secret"] = existing.get("webhook_secret", secrets.token_urlsafe(32))
            sync_config_data["id"] = existing["id"]
            
            # Update existing
            await db.sync_configs.update_one(
                {"campus_id": campus_id},
                {"$set": sync_config_data}
            )
        else:
            # Create new with generated webhook secret
            sync_config = SyncConfig(
                campus_id=campus_id,
                sync_method=config.sync_method,
                api_base_url=config.api_base_url.rstrip('/'),
                api_email=config.api_email,
                api_password=config.api_password,
                polling_interval_hours=config.polling_interval_hours,
                reconciliation_enabled=config.reconciliation_enabled,
                reconciliation_time=config.reconciliation_time,
                filter_mode=config.filter_mode,
                filter_rules=config.filter_rules or [],
                is_enabled=config.is_enabled
            )
            await db.sync_configs.insert_one(sync_config.model_dump())
        
        return {"success": True, "message": "Sync configuration saved"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving sync config: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/sync/regenerate-secret")
async def regenerate_webhook_secret(current_user: dict = Depends(get_current_user)):
    """Regenerate webhook secret for security rotation"""
    if current_user["role"] not in [UserRole.FULL_ADMIN, UserRole.CAMPUS_ADMIN]:
        raise HTTPException(status_code=403, detail="Only administrators can regenerate webhook secret")
    
    try:
        campus_id = current_user.get("campus_id")
        if not campus_id:
            raise HTTPException(status_code=400, detail="Please select a campus first")
        
        # Generate new secret
        new_secret = secrets.token_urlsafe(32)
        
        # Update config
        result = await db.sync_configs.update_one(
            {"campus_id": campus_id},
            {"$set": {
                "webhook_secret": new_secret,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Sync configuration not found")
        
        return {
            "success": True,
            "message": "Webhook secret regenerated successfully",
            "new_secret": new_secret
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error regenerating webhook secret: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/sync/discover-fields")
async def discover_fields_from_core(config_test: SyncConfigCreate, current_user: dict = Depends(get_current_user)):
    """
    Analyze sample members from core API to discover available fields and their values
    Returns field metadata for building dynamic filters
    """
    if current_user["role"] not in [UserRole.FULL_ADMIN, UserRole.CAMPUS_ADMIN]:
        raise HTTPException(status_code=403, detail="Only administrators can discover fields")
    
    try:
        import httpx
        
        # Login to core API
        async with httpx.AsyncClient(timeout=30.0) as client:
            login_response = await client.post(
                f"{config_test.api_base_url.rstrip('/')}/api/auth/login",
                json={"email": config_test.api_email, "password": config_test.api_password}
            )
            
            if login_response.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to authenticate with core API")
            
            token = login_response.json().get("access_token")
            
            # Fetch members (limit to 100 for analysis)
            members_response = await client.get(
                f"{config_test.api_base_url.rstrip('/')}/api/members/",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if members_response.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to fetch members from core API")
            
            members = members_response.json()[:100]  # Analyze first 100 members
            
            if len(members) == 0:
                return {"fields": [], "message": "No members found in core system"}
            
            # Analyze fields
            field_metadata = {}
            
            for member in members:
                for field_name, field_value in member.items():
                    if field_name in ["id", "church_id", "campus_id", "_id"]:
                        continue  # Skip system fields
                    
                    if field_name not in field_metadata:
                        field_metadata[field_name] = {
                            "name": field_name,
                            "type": None,
                            "distinct_values": set(),
                            "has_null": False,
                            "sample_value": field_value
                        }
                    
                    # Determine field type
                    if field_value is None:
                        field_metadata[field_name]["has_null"] = True
                    elif isinstance(field_value, bool):
                        field_metadata[field_name]["type"] = "boolean"
                        field_metadata[field_name]["distinct_values"].add(field_value)
                    elif isinstance(field_value, (int, float)):
                        field_metadata[field_name]["type"] = "number"
                    elif isinstance(field_value, str):
                        # Check if it's a date
                        if "date" in field_name.lower() or "birth" in field_name.lower():
                            field_metadata[field_name]["type"] = "date"
                        else:
                            field_metadata[field_name]["type"] = "string"
                            # Collect distinct values for string fields (max 50 unique values)
                            if len(field_metadata[field_name]["distinct_values"]) < 50:
                                field_metadata[field_name]["distinct_values"].add(field_value)
            
            # Convert to list and process distinct values
            fields = []
            for field_name, metadata in field_metadata.items():
                field_info = {
                    "name": field_name,
                    "label": field_name.replace("_", " ").title(),
                    "type": metadata["type"],
                    "sample_value": metadata["sample_value"],
                    "has_null": metadata["has_null"]
                }
                
                # Convert distinct values to list
                if metadata["type"] in ["string", "boolean"]:
                    distinct_list = sorted(list(metadata["distinct_values"]))
                    if len(distinct_list) > 0 and len(distinct_list) <= 20:  # Only if reasonable number
                        field_info["distinct_values"] = distinct_list
                
                fields.append(field_info)
            
            # Sort fields by name
            fields.sort(key=lambda x: x["name"])
            
            return {
                "fields": fields,
                "sample_count": len(members),
                "message": f"Discovered {len(fields)} fields from {len(members)} sample members"
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error discovering fields: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/sync/config")
async def get_sync_config(current_user: dict = Depends(get_current_user)):
    """Get sync configuration for campus"""
    try:
        campus_id = current_user.get("campus_id")
        if not campus_id:
            return None
        
        config = await db.sync_configs.find_one({"campus_id": campus_id}, {"_id": 0})
        if config:
            # Don't return actual password to frontend, but keep webhook_secret
            config["api_password"] = "********" if config.get("api_password") else ""
            # Keep webhook_secret for display (user needs to configure it in core system)
        
        return config
    
    except Exception as e:
        logger.error(f"Error getting sync config: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/sync/test-connection")
async def test_sync_connection(config: SyncConfigCreate, current_user: dict = Depends(get_current_user)):
    """Test connection to core API"""
    if current_user["role"] not in [UserRole.FULL_ADMIN, UserRole.CAMPUS_ADMIN]:
        raise HTTPException(status_code=403, detail="Only administrators can test sync")
    
    try:
        import httpx
        
        # Test login - send as 'email' key even if it's not email format (core API requirement)
        login_url = f"{config.api_base_url.rstrip('/')}/api/auth/login"
        async with httpx.AsyncClient(timeout=30.0) as client:
            login_response = await client.post(
                login_url,
                json={"email": config.api_email, "password": config.api_password}
            )
            
            if login_response.status_code != 200:
                error_detail = login_response.text
                try:
                    error_json = login_response.json()
                    error_detail = error_json.get("detail", error_detail)
                except:
                    pass
                
                return {
                    "success": False,
                    "message": f"Login failed: {error_detail}"
                }
            
            token = login_response.json().get("access_token")
            if not token:
                return {
                    "success": False,
                    "message": "No access token received"
                }
            
            # Test members endpoint - fetch with pagination to get actual total
            members_url = f"{config.api_base_url.rstrip('/')}/api/members/"
            
            # Try to get total count by fetching with pagination
            total_members = 0
            offset = 0
            page_size = 100
            
            while True:
                members_response = await client.get(
                    f"{members_url}?limit={page_size}&skip={offset}",
                    headers={"Authorization": f"Bearer {token}"}
                )
                
                if members_response.status_code != 200:
                    return {
                        "success": False,
                        "message": f"Members API failed: {members_response.text}"
                    }
                
                batch = members_response.json()
                
                # Handle both response formats
                if isinstance(batch, dict):
                    if 'pagination' in batch and 'total' in batch['pagination']:
                        # Has pagination metadata - use total
                        total_members = batch['pagination']['total']
                        break
                    elif 'data' in batch:
                        # Paginated but count ourselves
                        batch_members = batch['data']
                        total_members += len(batch_members)
                        if len(batch_members) < page_size:
                            break
                    else:
                        break
                elif isinstance(batch, list):
                    total_members += len(batch)
                    if len(batch) < page_size:
                        break
                else:
                    break
                
                offset += page_size
                
                # Safety limit
                if offset > 10000:
                    total_members = f"{total_members}+ (stopped at 10,000)"
                    break
            
            return {
                "success": True,
                "message": f"Connection successful! Core system has {total_members} total members. Sync will fetch all.",
                "member_count": total_members
            }
    
    except httpx.TimeoutException:
        return {
            "success": False,
            "message": "Connection timeout. Please check the API URL."
        }
    except Exception as e:
        logger.error(f"Error testing sync connection: {str(e)}")
        return {
            "success": False,
            "message": f"Connection error: {str(e)}"
        }

@api_router.post("/sync/members/pull")
async def sync_members_from_core(current_user: dict = Depends(get_current_user)):
    """Pull members from core API and sync"""
    if current_user["role"] not in [UserRole.FULL_ADMIN, UserRole.CAMPUS_ADMIN]:
        raise HTTPException(status_code=403, detail="Only administrators can sync members")
    
    try:
        import httpx
        from io import BytesIO
        import base64
        
        campus_id = current_user.get("campus_id")
        if not campus_id:
            raise HTTPException(status_code=400, detail="Please select a campus first")
        
        # Get sync config
        config = await db.sync_configs.find_one({"campus_id": campus_id}, {"_id": 0})
        if not config or not config.get("is_enabled"):
            raise HTTPException(status_code=400, detail="Sync is not configured or enabled for this campus")
        
        # Create sync log
        sync_log = SyncLog(
            campus_id=campus_id,
            sync_type="manual",
            status="in_progress"
        )
        sync_log_dict = sync_log.model_dump()
        await db.sync_logs.insert_one(sync_log_dict)
        sync_log_id = sync_log.id
        
        start_time = datetime.now(timezone.utc)
        
        try:
            # Login to core API
            async with httpx.AsyncClient(timeout=60.0) as client:
                login_response = await client.post(
                    f"{config['api_base_url']}/api/auth/login",
                    json={"email": config["api_email"], "password": config["api_password"]}
                )
                
                if login_response.status_code != 200:
                    raise Exception(f"Login failed: {login_response.text}")
                
                token = login_response.json().get("access_token")
                
                # Fetch ALL members using pagination
                all_members = []
                page_size = 100
                offset = 0
                
                while True:
                    members_response = await client.get(
                        f"{config['api_base_url']}/api/members/?limit={page_size}&skip={offset}",
                        headers={"Authorization": f"Bearer {token}"}
                    )
                    
                    if members_response.status_code != 200:
                        raise Exception(f"Failed to fetch members: {members_response.text}")
                    
                    batch = members_response.json()
                    
                    # Handle both array response and paginated response
                    if isinstance(batch, dict) and 'data' in batch:
                        # Paginated response: {"data": [...], "pagination": {...}}
                        batch_members = batch['data']
                        all_members.extend(batch_members)
                        
                        # Check if there are more pages
                        pagination = batch.get('pagination', {})
                        if not pagination.get('has_more', False):
                            break
                    elif isinstance(batch, list):
                        # Direct array response
                        all_members.extend(batch)
                        
                        # If batch size is less than page_size, we've reached the end
                        if len(batch) < page_size:
                            break
                    else:
                        break
                    
                    offset += page_size
                    
                    # Safety limit to prevent infinite loop
                    if offset > 10000:
                        logger.warning(f"Reached safety limit of 10000 members")
                        break
                
                core_members = all_members
                logger.info(f"Fetched {len(core_members)} total members from core API using pagination")
                
                # Stats
                stats = {
                    "fetched": len(core_members),
                    "created": 0,
                    "updated": 0,
                    "archived": 0,
                    "unarchived": 0
                }
                
                # Get existing members
                existing_members = await db.members.find({"campus_id": campus_id}, {"_id": 0}).to_list(None)
                existing_map = {m.get("external_member_id"): m for m in existing_members if m.get("external_member_id")}
                
                # Apply dynamic filters
                filter_mode = config.get("filter_mode", "include")
                filter_rules = config.get("filter_rules", [])
                filtered_members = []
                
                for core_member in core_members:
                    # Check if member matches filter rules
                    if not filter_rules or len(filter_rules) == 0:
                        # No filters, include all
                        filtered_members.append(core_member)
                        continue
                    
                    matches_all_rules = True
                    
                    for rule in filter_rules:
                        field_name = rule.get("field")
                        operator = rule.get("operator")
                        filter_value = rule.get("value")
                        
                        member_value = core_member.get(field_name)
                        
                        # Apply operator
                        rule_matches = False
                        
                        if operator == "equals":
                            rule_matches = str(member_value) == str(filter_value)
                        
                        elif operator == "not_equals":
                            rule_matches = str(member_value) != str(filter_value)
                        
                        elif operator == "contains":
                            if member_value and filter_value:
                                rule_matches = str(filter_value).lower() in str(member_value).lower()
                        
                        elif operator == "in":
                            if isinstance(filter_value, list):
                                rule_matches = member_value in filter_value
                        
                        elif operator == "not_in":
                            if isinstance(filter_value, list):
                                rule_matches = member_value not in filter_value
                        
                        elif operator in ["greater_than", "less_than", "between"]:
                            # Numeric or age comparison
                            try:
                                if "date_of_birth" in field_name or "birth" in field_name:
                                    # Calculate age
                                    if member_value:
                                        birth_date = date.fromisoformat(member_value) if isinstance(member_value, str) else member_value
                                        age = (date.today() - birth_date).days // 365
                                        member_value = age
                                
                                if operator == "greater_than":
                                    rule_matches = float(member_value) > float(filter_value)
                                elif operator == "less_than":
                                    rule_matches = float(member_value) < float(filter_value)
                                elif operator == "between":
                                    if isinstance(filter_value, list) and len(filter_value) == 2:
                                        rule_matches = float(filter_value[0]) <= float(member_value) <= float(filter_value[1])
                            except:
                                rule_matches = False
                        
                        elif operator == "is_true":
                            rule_matches = member_value == True or member_value == "true"
                        
                        elif operator == "is_false":
                            rule_matches = member_value == False or member_value == "false"
                        
                        # If any rule doesn't match, mark as not matching all
                        if not rule_matches:
                            matches_all_rules = False
                            break
                    
                    # Apply include/exclude logic
                    if filter_mode == "include":
                        if matches_all_rules:
                            filtered_members.append(core_member)
                    else:  # exclude
                        if not matches_all_rules:
                            filtered_members.append(core_member)
                
                logger.info(f"Filter mode: {filter_mode}. Filtered {len(core_members)} members to {len(filtered_members)} using {len(filter_rules)} rules")
                
                # Update stats
                stats["fetched"] = len(filtered_members)
                
                # Process each filtered core member
                for core_member in filtered_members:
                    core_id = core_member.get("id")
                    existing = existing_map.get(core_id)
                    
                    # Prepare member data
                    member_data = {
                        "external_member_id": core_id,
                        "name": core_member.get("full_name"),
                        "phone": normalize_phone_number(core_member.get("phone_whatsapp", "")) if core_member.get("phone_whatsapp") else None,
                        "birth_date": core_member.get("date_of_birth"),
                        "gender": core_member.get("gender"),
                        "category": core_member.get("member_status"),
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }
                    
                    # Calculate age if birth_date exists
                    if core_member.get("date_of_birth"):
                        try:
                            dob = core_member["date_of_birth"]
                            birth_date = date.fromisoformat(dob) if isinstance(dob, str) else dob
                            age = (date.today() - birth_date).days // 365
                            member_data["age"] = age
                        except:
                            member_data["age"] = None
                    else:
                        member_data["age"] = None
                    
                    # Handle photo if exists
                    photo_base64 = core_member.get("photo_base64")
                    if photo_base64 and photo_base64.startswith("data:image"):
                        try:
                            # Extract base64 data
                            image_data = photo_base64.split(",")[1] if "," in photo_base64 else photo_base64
                            image_bytes = base64.b64decode(image_data)
                            
                            # Save photo
                            upload_dir = Path(ROOT_DIR) / "uploads"
                            upload_dir.mkdir(exist_ok=True)
                            
                            ext = "jpg"
                            if "png" in photo_base64:
                                ext = "png"
                            filename = f"JEMAAT-{core_id[:5]}.{ext}"
                            filepath = upload_dir / filename
                            
                            # Resize and save
                            img = Image.open(BytesIO(image_bytes))
                            img = img.convert('RGB')
                            img.thumbnail((800, 800), Image.Resampling.LANCZOS)
                            img.save(filepath, 'JPEG', quality=85)
                            
                            member_data["photo_url"] = f"/uploads/{filename}"
                        except Exception as e:
                            logger.error(f"Error processing photo for {core_id}: {str(e)}")
                    
                    # Check if member is active
                    is_active = core_member.get("is_active", True)
                    
                    if existing:
                        # Update existing member
                        if not is_active and not existing.get("is_archived"):
                            # Archive member
                            member_data["is_archived"] = True
                            member_data["archived_at"] = datetime.now(timezone.utc).isoformat()
                            member_data["archived_reason"] = "Deactivated in core system"
                            stats["archived"] += 1
                        elif is_active and existing.get("is_archived"):
                            # Unarchive member
                            member_data["is_archived"] = False
                            member_data["archived_at"] = None
                            member_data["archived_reason"] = None
                            stats["unarchived"] += 1
                        else:
                            stats["updated"] += 1
                        
                        await db.members.update_one(
                            {"id": existing["id"]},
                            {"$set": member_data}
                        )
                    else:
                        # Create new member
                        new_member = {
                            "id": str(uuid.uuid4()),
                            "campus_id": campus_id,
                            **member_data,
                            "is_archived": not is_active,
                            "engagement_status": "active",
                            "days_since_last_contact": 999,
                            "created_at": datetime.now(timezone.utc).isoformat()
                        }
                        
                        await db.members.insert_one(new_member)
                        stats["created"] += 1
                

                # Archive members that no longer match filter (Option A)
                # Get all core member IDs that passed filter
                filtered_core_ids = set(m.get("id") for m in filtered_members)
                
                # Find existing synced members that are NOT in filtered list
                for existing_member in existing_members:
                    external_id = existing_member.get("external_member_id")
                    if external_id and external_id not in filtered_core_ids and not existing_member.get("is_archived"):
                        # This member was synced before but doesn't match new filter
                        await db.members.update_one(
                            {"id": existing_member["id"]},
                            {"$set": {
                                "is_archived": True,
                                "archived_at": datetime.now(timezone.utc).isoformat(),
                                "archived_reason": "No longer matches sync filter rules",
                                "updated_at": datetime.now(timezone.utc).isoformat()
                            }}
                        )
                        stats["archived"] += 1
                        logger.info(f"Archived member {existing_member['name']} (no longer matches filter)")

                # Update sync config
                end_time = datetime.now(timezone.utc)
                duration = (end_time - start_time).total_seconds()
                
                await db.sync_configs.update_one(
                    {"campus_id": campus_id},
                    {"$set": {
                        "last_sync_at": end_time.isoformat(),
                        "last_sync_status": "success",
                        "last_sync_message": f"Synced {stats['fetched']} members successfully"
                    }}
                )
                
                # Update sync log
                await db.sync_logs.update_one(
                    {"id": sync_log_id},
                    {"$set": {
                        "status": "success",
                        "members_fetched": stats["fetched"],
                        "members_created": stats["created"],
                        "members_updated": stats["updated"],
                        "members_archived": stats["archived"],
                        "members_unarchived": stats["unarchived"],
                        "completed_at": end_time.isoformat(),
                        "duration_seconds": duration
                    }}
                )
                
                return {
                    "success": True,
                    "message": "Sync completed successfully",
                    "stats": stats,
                    "duration_seconds": duration
                }
        
        except Exception as sync_error:
            # Log sync failure
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            
            await db.sync_configs.update_one(
                {"campus_id": campus_id},
                {"$set": {
                    "last_sync_at": end_time.isoformat(),
                    "last_sync_status": "error",
                    "last_sync_message": str(sync_error)
                }}
            )
            
            await db.sync_logs.update_one(
                {"id": sync_log_id},
                {"$set": {
                    "status": "error",
                    "error_message": str(sync_error),
                    "completed_at": end_time.isoformat(),
                    "duration_seconds": duration
                }}
            )
            
            raise HTTPException(status_code=500, detail=str(sync_error))
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in sync members: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/sync/logs")
async def get_sync_logs(current_user: dict = Depends(get_current_user), limit: int = 20):
    """Get sync history logs"""
    try:
        campus_id = current_user.get("campus_id")
        if not campus_id:
            return []
        
        logs = await db.sync_logs.find(
            {"campus_id": campus_id},
            {"_id": 0}
        ).sort("started_at", -1).limit(limit).to_list(limit)
        
        return logs
    
    except Exception as e:
        logger.error(f"Error getting sync logs: {str(e)}")


@api_router.post("/sync/webhook")
async def receive_sync_webhook(request: Request):
    """
    Webhook receiver for real-time member sync from core system
    Validates HMAC signature for security
    """
    try:
        # Get raw body for signature verification
        body = await request.body()
        
        # Get signature from header
        signature = request.headers.get("X-Webhook-Signature")
        if not signature:
            raise HTTPException(status_code=401, detail="Missing webhook signature")
        
        # Parse JSON body
        try:
            payload = await request.json()
        except:
            raise HTTPException(status_code=400, detail="Invalid JSON payload")
        
        # Get campus_id from payload
        campus_id = payload.get("church_id") or payload.get("campus_id")
        if not campus_id:
            raise HTTPException(status_code=400, detail="Missing campus_id in payload")
        
        # Get sync config for this campus by core church_id or campus_id
        config = await db.sync_configs.find_one({
            "$or": [
                {"core_church_id": campus_id},
                {"campus_id": campus_id}
            ]
        }, {"_id": 0})
        if not config:
            logger.warning(f"Webhook received for campus {campus_id} with no sync config")
            raise HTTPException(status_code=404, detail="Sync not configured for this campus")
        
        if not config.get("is_enabled"):
            logger.warning(f"Webhook received for campus {campus_id} but sync is disabled")
            raise HTTPException(status_code=403, detail="Sync is disabled for this campus")
        
        # Verify webhook signature using HMAC
        webhook_secret = config.get("webhook_secret", "")
        expected_signature = hmac.new(
            webhook_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_signature):
            logger.error(f"Invalid webhook signature for campus {campus_id}")
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
        
        # Log webhook delivery
        await db.webhook_logs.insert_one({
            "id": str(uuid.uuid4()),
            "campus_id": campus_id,
            "event_type": payload.get("event_type"),
            "member_id": payload.get("member_id"),
            "payload": payload,
            "signature_valid": True,
            "received_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Process webhook based on event type
        event_type = payload.get("event_type")
        member_id = payload.get("member_id")
        
        if event_type in ["member.created", "member.updated", "member.deleted"]:
            # Trigger a sync for this specific member (or full sync)
            # For simplicity, we'll trigger a full sync
            # In production, you could optimize to sync just this member
            
            logger.info(f"Webhook {event_type} received for campus {campus_id}, triggering sync")
            
            # Trigger sync in background (don't wait)
            # Note: For production, use background task or queue
            # For now, we'll just log and let scheduled sync handle it
            
            return {
                "success": True,
                "message": f"Webhook received: {event_type}",
                "will_sync": "Sync will occur on next scheduled run or manual trigger"
            }
        else:
            return {
                "success": True,
                "message": f"Webhook received but event type {event_type} not handled"
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

        raise HTTPException(status_code=500, detail=str(e))

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

@api_router.get("/user-photos/{filename}")
async def get_user_photo(filename: str):
    """Serve user profile photos"""
    filepath = Path(ROOT_DIR) / "user_photos" / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Photo not found")
    return FileResponse(filepath)

# ==================== SEARCH ENDPOINT ====================

@api_router.get("/search")
async def global_search(q: str, current_user: dict = Depends(get_current_user)):
    """
    Global search across members and care events
    Returns members matching name, phone, email and care events matching title, description
    """
    try:
        if not q or len(q) < 2:
            return {"members": [], "care_events": []}
        
        # Get user's campus
        campus_id = current_user.get("campus_id")
        
        # For full admin, search across all campuses they have access to
        search_filter = {}
        if current_user["role"] in [UserRole.CAMPUS_ADMIN, UserRole.PASTOR]:
            search_filter["campus_id"] = campus_id
        
        # Search members
        member_query = {
            **search_filter,
            "$or": [
                {"name": {"$regex": q, "$options": "i"}},
                {"phone": {"$regex": q, "$options": "i"}}
            ]
        }
        
        members = await db.members.find(member_query, {"_id": 0}).limit(10).to_list(10)
        
        # Search care events
        care_event_query = {
            **search_filter,
            "$or": [
                {"title": {"$regex": q, "$options": "i"}},
                {"description": {"$regex": q, "$options": "i"}}
            ]
        }
        
        care_events = await db.care_events.find(care_event_query, {"_id": 0}).limit(10).to_list(10)
        
        # Enrich care events with member names
        for event in care_events:
            if event.get("member_id"):
                member = await db.members.find_one({"id": event["member_id"]}, {"_id": 0, "name": 1})
                event["member_name"] = member["name"] if member else "Unknown"
        
        return {
            "members": members,
            "care_events": care_events
        }
    
    except Exception as e:
        logger.error(f"Error in global search: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== ACTIVITY LOG ENDPOINTS ====================

@api_router.get("/activity-logs", response_model=List[ActivityLogResponse])
async def get_activity_logs(
    current_user: dict = Depends(get_current_user),
    user_id: Optional[str] = None,
    action_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100
):
    """
    Get activity logs with optional filters
    Default: last 30 days
    """
    try:
        # Get user's campus
        campus_id = current_user.get("campus_id")
        
        # Build query
        query = {}
        if current_user["role"] in [UserRole.CAMPUS_ADMIN, UserRole.PASTOR]:
            query["campus_id"] = campus_id
        
        # Filter by user
        if user_id:
            query["user_id"] = user_id
        
        # Filter by action type
        if action_type:
            query["action_type"] = action_type
        
        # Date range filter (default: last 30 days)
        if not start_date:
            start_datetime = datetime.now(timezone.utc) - timedelta(days=30)
        else:
            start_datetime = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        
        if not end_date:
            end_datetime = datetime.now(timezone.utc)
        else:
            end_datetime = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        query["created_at"] = {
            "$gte": start_datetime,
            "$lte": end_datetime
        }
        
        # Get logs
        logs = await db.activity_logs.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
        
        return logs
    
    except Exception as e:
        logger.error(f"Error fetching activity logs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/activity-logs/summary")
async def get_activity_summary(current_user: dict = Depends(get_current_user)):
    """
    Get summary statistics for activity logs
    """
    try:
        campus_id = current_user.get("campus_id")
        
        query = {}
        if current_user["role"] in [UserRole.CAMPUS_ADMIN, UserRole.PASTOR]:
            query["campus_id"] = campus_id
        
        # Last 30 days
        start_datetime = datetime.now(timezone.utc) - timedelta(days=30)
        query["created_at"] = {"$gte": start_datetime}
        
        # Total activities
        total = await db.activity_logs.count_documents(query)
        
        # Get unique users
        users_pipeline = [
            {"$match": query},
            {"$group": {"_id": "$user_id", "name": {"$first": "$user_name"}, "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        
        users = await db.activity_logs.aggregate(users_pipeline).to_list(None)
        
        # Count by action type
        actions_pipeline = [
            {"$match": query},
            {"$group": {"_id": "$action_type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        
        actions = await db.activity_logs.aggregate(actions_pipeline).to_list(None)
        
        return {
            "total_activities": total,
            "active_users": len(users),
            "top_users": users[:5],
            "action_breakdown": actions
        }
    
    except Exception as e:
        logger.error(f"Error fetching activity summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

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