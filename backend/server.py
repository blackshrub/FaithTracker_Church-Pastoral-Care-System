"""
FaithTracker Pastoral Care System - Main Backend API
Multi-tenant pastoral care management with complete accountability
Handles all API endpoints, authentication, database operations, and business logic

Framework: Litestar + msgspec (migrated from FastAPI + Pydantic)
"""

from litestar import Litestar, Router, get, post, put, patch, delete, Request, Response
from litestar.di import Provide
from litestar.exceptions import HTTPException, NotAuthorizedException, PermissionDeniedException
from litestar.status_codes import HTTP_200_OK, HTTP_201_CREATED, HTTP_204_NO_CONTENT, HTTP_400_BAD_REQUEST, HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN, HTTP_404_NOT_FOUND, HTTP_413_REQUEST_ENTITY_TOO_LARGE, HTTP_500_INTERNAL_SERVER_ERROR
from litestar.datastructures import UploadFile, State
from litestar.params import Parameter
from litestar.response import Response as LitestarResponse, File as LitestarFile, Stream
from litestar.middleware.base import AbstractMiddleware, DefineMiddleware
from litestar.middleware.compression import CompressionMiddleware
from litestar.middleware.rate_limit import RateLimitConfig
from litestar.config.cors import CORSConfig
from litestar.openapi import OpenAPIConfig
from litestar.connection import ASGIConnection
from litestar.handlers.base import BaseRouteHandler
import msgspec
import msgspec.json
from msgspec import Struct, field, UNSET, UnsetType
from typing import Annotated
from bson import ObjectId, Decimal128, Binary, Regex
from bson.errors import InvalidId
import base64
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import secrets
import hmac
import hashlib
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
from enum import Enum
import uuid
from datetime import datetime, timezone, timedelta, date
from zoneinfo import ZoneInfo
import asyncio
import re


# Custom msgspec response class for proper BSON/MongoDB type serialization
def msgspec_enc_hook(obj):
    """Custom encoder hook for msgspec to handle BSON/MongoDB types.

    Handles:
    - datetime/date: ISO 8601 format
    - ObjectId: string representation (24-char hex)
    - Decimal128: float (or string for precision-critical)
    - Binary: base64-encoded string
    - Regex: pattern string
    - UUID: string representation
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, Decimal128):
        # Convert to float for JSON; use str(obj.to_decimal()) if precision is critical
        return float(obj.to_decimal())
    if isinstance(obj, Binary):
        return base64.b64encode(obj).decode('utf-8')
    if isinstance(obj, Regex):
        return obj.pattern
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, bytes):
        return base64.b64encode(obj).decode('utf-8')
    raise NotImplementedError(f"Object of type {type(obj)} is not JSON serializable")


# Create a reusable encoder instance (more efficient than creating per-request)
_msgspec_encoder = msgspec.json.Encoder(enc_hook=msgspec_enc_hook)


class CustomMsgspecResponse(Response):
    """Custom Response using msgspec for fast JSON serialization with BSON type support."""
    media_type = "application/json"

    def render(self, content) -> bytes:
        return _msgspec_encoder.encode(content)


# Jakarta timezone (UTC+7)
JAKARTA_TZ = ZoneInfo("Asia/Jakarta")

# PDF report generation (lazy import to avoid startup issues)
def get_pdf_generator():
    from pdf_report import generate_monthly_report_pdf
    return generate_monthly_report_pdf

# Configure logging - structured JSON in production, human-readable in development
import sys

class JSONFormatter(logging.Formatter):
    """JSON log formatter for production - easier to parse and search"""
    def format(self, record):
        import json
        log_obj = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)

# Configure logging based on environment
log_level = logging.INFO
log_handler = logging.StreamHandler(sys.stdout)

if os.environ.get('ENVIRONMENT', 'development') == 'production':
    # Structured JSON logging for production (easier to parse, search, aggregate)
    log_handler.setFormatter(JSONFormatter())
else:
    # Human-readable format for development
    log_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))

logging.basicConfig(level=log_level, handlers=[log_handler])
logger = logging.getLogger(__name__)

# Credential encryption for security
from cryptography.fernet import Fernet
import base64

# Get encryption key from environment (REQUIRED in production)
ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY')
if not ENCRYPTION_KEY:
    if os.environ.get('ENVIRONMENT', 'development') == 'production':
        raise RuntimeError(
            "ENCRYPTION_KEY environment variable is required in production. "
            "Generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    else:
        # Generate a key for development only
        ENCRYPTION_KEY = Fernet.generate_key().decode()
        logger.warning("ENCRYPTION_KEY not set - using temporary key. Set ENCRYPTION_KEY for production!")

cipher_suite = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)

def encrypt_password(password: str) -> str:
    """Encrypt password for storage"""
    return cipher_suite.encrypt(password.encode()).decode()

def decrypt_password(encrypted: str) -> str:
    """Decrypt password for use"""
    try:
        return cipher_suite.decrypt(encrypted.encode()).decode()
    except Exception:
        # If decryption fails, assume it's already plain text (backward compatibility)
        return encrypted

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

# Validate configuration on startup
from config import validate_config
validate_config(exit_on_error=False)  # Show warnings but don't exit

# MongoDB connection with optimized pooling for production
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(
    mongo_url,
    maxPoolSize=50,  # Maximum number of connections in the pool
    minPoolSize=10,  # Minimum number of connections to keep open
    maxIdleTimeMS=45000,  # Close idle connections after 45 seconds
    serverSelectionTimeoutMS=5000,  # Timeout for server selection
    connectTimeoutMS=10000,  # Timeout for new connections
    socketTimeoutMS=45000,  # Timeout for socket operations
)
db = client[os.environ.get('DB_NAME', 'pastoral_care_db')]

# NOTE: Litestar app will be created at the end of the file after all routes are defined
# Middleware and app configuration will be done there

# Request size limit middleware for Litestar
class RequestSizeLimitMiddleware(AbstractMiddleware):
    """Limit request body size to prevent memory exhaustion attacks"""
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            content_length = headers.get(b"content-length")
            if content_length:
                if int(content_length) > MAX_REQUEST_BODY_SIZE:
                    response = LitestarResponse(
                        content={"detail": "Request body too large"},
                        status_code=HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        media_type="application/json"
                    )
                    await response(scope, receive, send)
                    return
        await self.app(scope, receive, send)

# ==================== SAFE ERROR HANDLING ====================

# Generic error messages for production (don't expose internal details)
GENERIC_ERROR_MESSAGES = {
    400: "Invalid request",
    401: "Authentication required",
    403: "Access denied",
    404: "Resource not found",
    500: "An internal error occurred. Please try again later.",
}

def safe_error_detail(e: Exception, status_code: int = 500) -> str:
    """
    Return a safe error message for production.
    In development, returns the full error for debugging.
    """
    if os.environ.get('ENVIRONMENT', 'development') == 'production':
        return GENERIC_ERROR_MESSAGES.get(status_code, "An error occurred")
    else:
        # In development, include the error message for debugging
        return str(e)

# Global exception handler for Litestar (will be registered with app)
def global_exception_handler(request: Request, exc: Exception) -> LitestarResponse:
    """
    Global exception handler that logs full errors but returns safe messages.
    This catches any unhandled exceptions not caught by endpoint-level handlers.
    """
    import json

    # Handle HTTP exceptions properly - return their status code and message
    if isinstance(exc, HTTPException):
        content = json.dumps({"detail": exc.detail})
        return LitestarResponse(
            content=content,
            status_code=exc.status_code,
            media_type="application/json"
        )

    # Log the full error for debugging
    logger.error(f"Unhandled exception: {type(exc).__name__}: {str(exc)}")

    # Return a safe error message
    if os.environ.get('ENVIRONMENT', 'development') == 'production':
        content = json.dumps({"detail": "An internal error occurred. Please try again later."})
    else:
        # In development, include more details
        content = json.dumps({"detail": str(exc), "type": type(exc).__name__})

    return LitestarResponse(
        content=content,
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        media_type="application/json"
    )

# Route handlers list (will be collected and passed to Litestar app)
route_handlers: List[Any] = []

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

# ==================== CONSTANTS ====================

# Engagement Status Thresholds (defaults - can be overridden by settings)
ENGAGEMENT_AT_RISK_DAYS_DEFAULT = 60
ENGAGEMENT_DISCONNECTED_DAYS_DEFAULT = 90
ENGAGEMENT_NO_CONTACT_DAYS = 999  # Used when member has never been contacted

# Grief Support Timeline (days after mourning date)
GRIEF_ONE_WEEK_DAYS = 7
GRIEF_TWO_WEEKS_DAYS = 14
GRIEF_ONE_MONTH_DAYS = 30
GRIEF_THREE_MONTHS_DAYS = 90
GRIEF_SIX_MONTHS_DAYS = 180
GRIEF_ONE_YEAR_DAYS = 365

# Accident/Illness Follow-up Timeline (days after event)
ACCIDENT_FIRST_FOLLOWUP_DAYS = 3
ACCIDENT_SECOND_FOLLOWUP_DAYS = 7
ACCIDENT_FINAL_FOLLOWUP_DAYS = 14

# Reminder Settings (days before event)
DEFAULT_REMINDER_DAYS_BIRTHDAY = 7
DEFAULT_REMINDER_DAYS_CHILDBIRTH = 14
DEFAULT_REMINDER_DAYS_FINANCIAL_AID = 0
DEFAULT_REMINDER_DAYS_ACCIDENT_ILLNESS = 14
DEFAULT_REMINDER_DAYS_GRIEF_SUPPORT = 14

# JWT Token Settings
JWT_TOKEN_EXPIRE_HOURS = 24

# Pagination Defaults
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 1000

# Dashboard Lookback (days)
DEFAULT_ANALYTICS_DAYS = 30
DEFAULT_UPCOMING_DAYS = 7

# File Upload Limits (bytes)
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB for images
MAX_CSV_SIZE = 5 * 1024 * 1024      # 5 MB for CSV imports

# Request Body Size Limits
MAX_REQUEST_BODY_SIZE = 15 * 1024 * 1024  # 15 MB max request body

# Pagination Bounds (for query parameter validation)
MAX_PAGE_NUMBER = 10000
MAX_LIMIT = 2000

# ==================== IMAGE VALIDATION ====================

# Magic bytes for allowed image types (security: validate file content, not just Content-Type)
IMAGE_MAGIC_BYTES = {
    b'\xff\xd8\xff': 'image/jpeg',           # JPEG
    b'\x89PNG\r\n\x1a\n': 'image/png',       # PNG
    b'GIF87a': 'image/gif',                   # GIF87a
    b'GIF89a': 'image/gif',                   # GIF89a
    b'RIFF': 'image/webp',                    # WebP (partial check)
}

def validate_image_magic_bytes(content: bytes) -> tuple[bool, str]:
    """
    Validate image file by checking magic bytes (file signature).
    Returns (is_valid, detected_mime_type or error_message)
    """
    if len(content) < 8:
        return False, "File too small to be a valid image"

    for magic, mime_type in IMAGE_MAGIC_BYTES.items():
        if content.startswith(magic):
            return True, mime_type

    # Special check for WebP (RIFF....WEBP)
    if content[:4] == b'RIFF' and content[8:12] == b'WEBP':
        return True, 'image/webp'

    return False, "Invalid image format. Allowed: JPEG, PNG, GIF, WebP"

# ==================== UUID VALIDATION & REGEX UTILITIES ====================

import re

def escape_regex(text: str) -> str:
    """
    Escape special regex characters to prevent NoSQL injection.
    This makes the text safe to use in MongoDB $regex queries.
    """
    # Escape all regex special characters
    special_chars = r'\.^$*+?{}[]|()'
    for char in special_chars:
        text = text.replace(char, '\\' + char)
    return text

# UUID v4 pattern for validation
UUID_PATTERN = re.compile(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$', re.IGNORECASE)

def is_valid_uuid(value: str) -> bool:
    """Check if a string is a valid UUID format."""
    if not isinstance(value, str):
        return False
    return bool(UUID_PATTERN.match(value))

def generate_uuid() -> str:
    """Generate a valid UUID string with validation."""
    new_uuid = str(uuid.uuid4())
    # Double-check the generated UUID is valid (defensive programming)
    if not is_valid_uuid(new_uuid):
        logger.error(f"Generated invalid UUID: {new_uuid}")
        # Retry once
        new_uuid = str(uuid.uuid4())
    return new_uuid

# ==================== AUTH CONFIGURATION ====================

# JWT Secret Key (REQUIRED - no default for security)
SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or os.environ.get('JWT_SECRET')
if not SECRET_KEY:
    if os.environ.get('ENVIRONMENT', 'development') == 'production':
        raise RuntimeError(
            "JWT_SECRET_KEY environment variable is required. "
            "Generate with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    else:
        # Generate a key for development only - will change on restart
        SECRET_KEY = secrets.token_hex(32)
        logger.warning("JWT_SECRET_KEY not set - using temporary key. Set JWT_SECRET_KEY for production!")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = JWT_TOKEN_EXPIRE_HOURS * 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

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

async def get_current_user(request: Request) -> dict:
    """Extract and validate JWT token from Authorization header.

    This is a Litestar dependency that will be provided via Provide().
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            extra={"headers": {"WWW-Authenticate": "Bearer"}},
        )

    token = auth_header[7:]  # Remove "Bearer " prefix
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            )
    except JWTError:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if user is None:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    return user

async def get_current_admin(request: Request) -> dict:
    """Get current user and verify admin role."""
    current_user = await get_current_user(request)
    if current_user.get("role") not in [UserRole.FULL_ADMIN.value, UserRole.CAMPUS_ADMIN.value, "full_admin", "campus_admin"]:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user

async def get_full_admin(request: Request) -> dict:
    """Get current user and verify full admin role."""
    current_user = await get_current_user(request)
    if current_user.get("role") not in [UserRole.FULL_ADMIN.value, "full_admin"]:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
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
# Using msgspec.Struct instead of Pydantic BaseModel for faster serialization

class CampusCreate(Struct):
    campus_name: Annotated[str, msgspec.Meta(min_length=1, max_length=200)]
    location: str | None = None  # msgspec doesn't support max_length on union types
    timezone: str = "Asia/Jakarta"  # Default to UTC+7

class Campus(Struct):
    campus_name: str
    id: str = field(default_factory=generate_uuid)
    location: str | None = None
    timezone: str = "Asia/Jakarta"  # Campus timezone (default UTC+7)
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

class MemberCreate(Struct):
    name: Annotated[str, msgspec.Meta(min_length=1, max_length=200)]
    campus_id: str
    phone: str | None = None
    external_member_id: str | None = None
    notes: str | None = None
    birth_date: date | None = None
    address: str | None = None
    category: str | None = None
    gender: str | None = None
    blood_type: str | None = None
    marital_status: str | None = None
    membership_status: str | None = None
    age: int | None = None

class MemberUpdate(Struct):
    name: str | None = None
    phone: str | None = None
    external_member_id: str | None = None
    notes: str | None = None
    birth_date: date | None = None
    address: str | None = None
    category: str | None = None
    gender: str | None = None
    blood_type: str | None = None
    marital_status: str | None = None
    membership_status: str | None = None

class Member(Struct):
    name: str
    campus_id: str
    id: str = field(default_factory=generate_uuid)
    phone: str | None = None  # Some members may not have phone numbers
    photo_url: str | None = None
    last_contact_date: datetime | None = None
    engagement_status: EngagementStatus = EngagementStatus.ACTIVE
    days_since_last_contact: int = 0
    is_archived: bool = False
    archived_at: datetime | None = None
    archived_reason: str | None = None
    external_member_id: str | None = None
    notes: str | None = None
    birth_date: date | None = None
    address: str | None = None
    category: str | None = None
    gender: str | None = None
    blood_type: str | None = None
    marital_status: str | None = None
    membership_status: str | None = None
    age: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

class VisitationLogEntry(Struct):
    visitor_name: Annotated[str, msgspec.Meta(min_length=1, max_length=200)]
    visit_date: date
    notes: Annotated[str, msgspec.Meta(max_length=2000)]
    prayer_offered: bool = False

class CareEventCreate(Struct):
    member_id: str
    campus_id: str
    event_type: EventType
    event_date: date
    title: Annotated[str, msgspec.Meta(min_length=1, max_length=300)]
    description: str | None = None
    # Grief support fields
    grief_relationship: str | None = None
    # Accident/illness fields (merged from hospital)
    hospital_name: str | None = None
    initial_visitation: VisitationLogEntry | None = None
    # Financial aid fields
    aid_type: AidType | None = None
    aid_amount: float | None = None
    aid_notes: str | None = None

class CareEventUpdate(Struct):
    event_type: EventType | None = None
    event_date: date | None = None
    title: str | None = None
    description: str | None = None
    completed: bool | None = None
    # Hospital fields
    discharge_date: date | None = None

class CareEvent(Struct):
    member_id: str
    campus_id: str
    event_type: EventType
    event_date: date
    title: str
    id: str = field(default_factory=generate_uuid)
    care_event_id: str | None = None  # Parent event ID (for linking child events)
    description: str | None = None
    completed: bool = False
    completed_at: datetime | None = None
    completed_by_user_id: str | None = None
    completed_by_user_name: str | None = None
    ignored: bool = False
    ignored_at: datetime | None = None
    ignored_by: str | None = None
    ignored_by_name: str | None = None
    created_by_user_id: str | None = None
    created_by_user_name: str | None = None
    # Member information (enriched from members collection)
    member_name: str | None = None
    member_phone: str | None = None
    member_photo_url: str | None = None
    # Grief support fields (only relationship, use event_date as mourning date)
    grief_relationship: str | None = None
    grief_stage: GriefStage | None = None
    grief_stage_id: str | None = None  # Link to grief_support stage (for timeline entries)
    # Accident/illness fields (merged from hospital, only hospital_name, use event_date as admission)
    hospital_name: str | None = None
    accident_stage_id: str | None = None  # Link to accident_followup stage (for timeline entries)
    visitation_log: List[Dict[str, Any]] = field(default_factory=list)
    # Follow-up type marker
    followup_type: str | None = None  # "scheduled" or "additional" (for grief/accident follow-ups)
    # Financial aid fields
    aid_type: AidType | None = None
    aid_amount: float | None = None
    aid_notes: str | None = None
    reminder_sent: bool = False
    reminder_sent_at: datetime | None = None
    reminder_sent_by_user_id: str | None = None
    reminder_sent_by_user_name: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SetupAdminRequest(Struct):
    email: str  # Email validation handled at route level
    password: str
    name: str
    phone: str  # Required for WhatsApp notifications

class SetupCampusRequest(Struct):
    campus_name: str
    location: str
    timezone: str


class AdditionalVisitRequest(Struct):
    visit_date: str
    visit_type: str
    notes: str


class GriefSupport(Struct):
    care_event_id: str
    member_id: str
    campus_id: str
    stage: GriefStage
    scheduled_date: date
    id: str = field(default_factory=generate_uuid)
    completed: bool = False
    completed_at: datetime | None = None
    ignored: bool = False
    ignored_at: datetime | None = None
    ignored_by: str | None = None
    notes: str | None = None
    reminder_sent: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

class AccidentFollowup(Struct):
    care_event_id: str
    member_id: str
    campus_id: str
    stage: str  # "first_followup", "second_followup", "final_followup"
    scheduled_date: date
    id: str = field(default_factory=generate_uuid)
    completed: bool = False
    completed_at: datetime | None = None
    ignored: bool = False
    ignored_at: datetime | None = None
    ignored_by: str | None = None
    notes: str | None = None
    reminder_sent: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

class NotificationLog(Struct):
    channel: NotificationChannel
    recipient: str
    message: str
    status: NotificationStatus
    id: str = field(default_factory=generate_uuid)
    care_event_id: str | None = None
    grief_support_id: str | None = None
    member_id: str | None = None
    campus_id: str | None = None
    pastoral_team_user_id: str | None = None  # If sent to pastoral team
    response_data: Dict[str, Any] | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

class FinancialAidSchedule(Struct):
    member_id: str
    campus_id: str
    title: str
    aid_type: AidType
    aid_amount: float
    frequency: ScheduleFrequency
    start_date: date
    next_occurrence: date
    created_by: str  # User ID who created the schedule
    id: str = field(default_factory=generate_uuid)
    end_date: date | None = None  # None means no end
    # Weekly specific
    day_of_week: WeekDay | None = None
    # Monthly specific
    day_of_month: int | None = None  # 1-31
    # Annual specific
    month_of_year: int | None = None  # 1-12
    # Tracking
    is_active: bool = True
    ignored_occurrences: List[str] = field(default_factory=list)  # List of dates (YYYY-MM-DD) that were ignored
    occurrences_completed: int = 0
    notes: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

# User Authentication Models
class UserCreate(Struct):
    email: str  # Email validation handled at route level
    password: Annotated[str, msgspec.Meta(min_length=8, max_length=128)]
    name: Annotated[str, msgspec.Meta(min_length=1, max_length=200)]
    phone: Annotated[str, msgspec.Meta(max_length=20)]  # Pastoral team member's phone for receiving reminders
    role: UserRole = UserRole.PASTOR
    campus_id: str | None = None  # Required for campus_admin and pastor, null for full_admin

class UserUpdate(Struct):
    name: str | None = None
    phone: str | None = None
    password: str | None = None
    role: UserRole | None = None
    campus_id: str | None = None

class UserLogin(Struct):
    email: str  # Email validation handled at route level
    password: str
    campus_id: str | None = None  # Campus selection at login

class User(Struct):
    email: str  # Email validation handled at route level
    name: str
    role: UserRole
    hashed_password: str
    id: str = field(default_factory=generate_uuid)
    campus_id: str | None = None
    phone: str | None = None  # For receiving pastoral care task reminders
    photo_url: str | None = None
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

class UserResponse(Struct):
    id: str
    email: str  # Email validation handled at route level
    name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    campus_id: str | None = None
    campus_name: str | None = None
    phone: str | None = None
    photo_url: str | None = None

class TokenResponse(Struct):
    access_token: str
    token_type: str
    user: UserResponse


class ActivityLog(Struct):
    campus_id: str
    user_id: str
    user_name: str
    action_type: ActivityActionType
    id: str = field(default_factory=generate_uuid)
    user_photo_url: str | None = None
    member_id: str | None = None
    member_name: str | None = None
    care_event_id: str | None = None
    event_type: EventType | None = None
    notes: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

class ActivityLogResponse(Struct):
    id: str
    campus_id: str
    user_id: str
    user_name: str
    action_type: str
    created_at: datetime
    user_photo_url: str | None = None
    member_id: str | None = None
    member_name: str | None = None
    care_event_id: str | None = None
    event_type: str | None = None
    notes: str | None = None


# ==================== SYNC MODELS ====================

class SyncConfig(Struct):
    campus_id: str  # FaithTracker campus ID
    api_base_url: str  # e.g., https://faithflow.yourdomain.com
    api_email: str
    api_password: str  # Encrypted in database
    id: str = field(default_factory=generate_uuid)
    core_church_id: str | None = None  # Core system's church_id (for webhook matching)
    sync_method: str = "polling"  # "polling" or "webhook"
    api_path_prefix: str = "/api"  # API path prefix (e.g., "/api" or "" for no prefix)
    api_login_endpoint: str = "/auth/login"  # Login endpoint path (e.g., "/auth/login" or "/login")
    api_members_endpoint: str = "/members/"  # Members endpoint path
    webhook_secret: str = field(default_factory=lambda: secrets.token_urlsafe(32))  # For signature verification
    is_enabled: bool = False
    polling_interval_hours: int = 6  # For polling method
    reconciliation_enabled: bool = False  # Daily 3 AM reconciliation (recommended for webhook mode)
    reconciliation_time: str = "03:00"  # Time for daily reconciliation (HH:MM format)
    # Sync filters (optional - empty means sync all)
    filter_mode: str = "include"  # "include" or "exclude"
    filter_rules: List[Dict[str, Any]] | None = None  # Dynamic filter rules
    # Example: [{"field": "gender", "operator": "equals", "value": "Female"}, {"field": "age", "operator": "between", "value": [18, 35]}]
    last_sync_at: datetime | None = None
    last_sync_status: str | None = None  # success, error
    last_sync_message: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

class SyncConfigCreate(Struct):
    api_base_url: str
    api_email: str
    api_password: str
    sync_method: str = "polling"
    api_path_prefix: str = "/api"  # API path prefix (e.g., "/api" or "" for no prefix)
    api_login_endpoint: str = "/auth/login"  # Login endpoint path (e.g., "/auth/login" or "/login")
    api_members_endpoint: str = "/members/"  # Members endpoint path
    polling_interval_hours: int = 6
    reconciliation_enabled: bool = False
    reconciliation_time: str = "03:00"
    filter_mode: str = "include"
    filter_rules: List[Dict[str, Any]] | None = None
    is_enabled: bool = False

class SyncLog(Struct):
    campus_id: str
    sync_type: str  # manual, scheduled, webhook
    status: str  # success, error, partial
    id: str = field(default_factory=generate_uuid)
    members_fetched: int = 0
    members_created: int = 0
    members_updated: int = 0
    members_archived: int = 0
    members_unarchived: int = 0
    error_message: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    duration_seconds: float | None = None


# ==================== UTILITY FUNCTIONS ====================

# Simple in-memory cache for static data
_cache = {}
_cache_timestamps = {}

def get_from_cache(key: str, ttl_seconds: int = 300) -> Optional[Any]:
    """
    Get value from cache if not expired

    Args:
        key: Cache key
        ttl_seconds: Time to live in seconds (default 5 minutes)

    Returns:
        Cached value or None if expired/not found
    """
    if key in _cache:
        age = (datetime.now(timezone.utc) - _cache_timestamps[key]).total_seconds()
        if age < ttl_seconds:
            return _cache[key]
        else:
            # Expired, remove from cache
            del _cache[key]
            del _cache_timestamps[key]
    return None

def set_in_cache(key: str, value: Any) -> None:
    """
    Store value in cache with current timestamp

    Args:
        key: Cache key
        value: Value to cache
    """
    _cache[key] = value
    _cache_timestamps[key] = datetime.now(timezone.utc)

def invalidate_cache(pattern: Optional[str] = None) -> None:
    """
    Invalidate cache entries

    Args:
        pattern: If provided, only invalidate keys containing this pattern.
                If None, clear entire cache.
    """
    global _cache, _cache_timestamps
    if pattern is None:
        _cache.clear()
        _cache_timestamps.clear()
    else:
        keys_to_delete = [k for k in _cache.keys() if pattern in k]
        for key in keys_to_delete:
            del _cache[key]
            del _cache_timestamps[key]

async def get_engagement_settings():
    """Get engagement threshold settings from database (cached for 10 minutes)"""
    cache_key = "engagement_settings"
    cached = get_from_cache(cache_key, ttl_seconds=600)
    if cached is not None:
        return cached

    try:
        settings = await db.settings.find_one({"key": "engagement_thresholds"}, {"_id": 0})
        if settings:
            result = settings.get("data", {"atRiskDays": ENGAGEMENT_AT_RISK_DAYS_DEFAULT, "disconnectedDays": ENGAGEMENT_DISCONNECTED_DAYS_DEFAULT})
        else:
            result = {"atRiskDays": ENGAGEMENT_AT_RISK_DAYS_DEFAULT, "disconnectedDays": ENGAGEMENT_DISCONNECTED_DAYS_DEFAULT}

        set_in_cache(cache_key, result)
        return result
    except Exception:
        return {"atRiskDays": ENGAGEMENT_AT_RISK_DAYS_DEFAULT, "disconnectedDays": ENGAGEMENT_DISCONNECTED_DAYS_DEFAULT}

async def get_writeoff_settings():
    """Get overdue write-off threshold settings from database (cached for 10 minutes)"""
    cache_key = "writeoff_settings"
    cached = get_from_cache(cache_key, ttl_seconds=600)
    if cached is not None:
        return cached

    default_settings = {
        "birthday": DEFAULT_REMINDER_DAYS_BIRTHDAY,
        "financial_aid": DEFAULT_REMINDER_DAYS_FINANCIAL_AID,
        "accident_illness": DEFAULT_REMINDER_DAYS_ACCIDENT_ILLNESS,
        "grief_support": DEFAULT_REMINDER_DAYS_GRIEF_SUPPORT
    }

    try:
        settings = await db.settings.find_one({"key": "overdue_writeoff"}, {"_id": 0})
        if settings:
            result = settings.get("data", default_settings)
        else:
            result = default_settings

        set_in_cache(cache_key, result)
        return result
    except Exception:
        return default_settings

async def calculate_engagement_status_async(last_contact: Optional[datetime]) -> tuple[EngagementStatus, int]:
    """Calculate engagement status using configurable thresholds"""
    settings = await get_engagement_settings()
    at_risk_days = settings.get("atRiskDays", ENGAGEMENT_AT_RISK_DAYS_DEFAULT)
    disconnected_days = settings.get("disconnectedDays", ENGAGEMENT_DISCONNECTED_DAYS_DEFAULT)

    if not last_contact:
        return EngagementStatus.DISCONNECTED, ENGAGEMENT_NO_CONTACT_DAYS
    
    # Handle string dates
    if isinstance(last_contact, str):
        try:
            last_contact = datetime.fromisoformat(last_contact)
        except ValueError:
            return EngagementStatus.DISCONNECTED, ENGAGEMENT_NO_CONTACT_DAYS

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

def calculate_engagement_status(last_contact: Optional[datetime], at_risk_days: int = ENGAGEMENT_AT_RISK_DAYS_DEFAULT, disconnected_days: int = ENGAGEMENT_DISCONNECTED_DAYS_DEFAULT) -> tuple[EngagementStatus, int]:
    """Calculate engagement status and days since last contact (with configurable thresholds)"""
    if not last_contact:
        return EngagementStatus.DISCONNECTED, ENGAGEMENT_NO_CONTACT_DAYS

    # Handle string dates
    if isinstance(last_contact, str):
        try:
            last_contact = datetime.fromisoformat(last_contact)
        except ValueError:
            return EngagementStatus.DISCONNECTED, ENGAGEMENT_NO_CONTACT_DAYS
    
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
        await db.activity_logs.insert_one(msgspec.to_builtins(activity))
        logger.info(f"Activity logged: {user_name} - {action_type} - {member_name}")
    except Exception as e:
        logger.error(f"Error logging activity: {str(e)}")
        # Don't fail the main operation if logging fails
        pass

# ==================== HELPER FUNCTIONS ====================

async def get_member_or_404(member_id: str, projection: Optional[dict] = None) -> dict:
    """
    Get member by ID or raise 404 HTTPException

    Args:
        member_id: The member's ID
        projection: Optional MongoDB projection dict to limit fields returned

    Returns:
        Member document

    Raises:
        HTTPException: 404 if member not found
    """
    projection_dict = projection if projection else {"_id": 0}
    member = await db.members.find_one({"id": member_id}, projection_dict)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    return member

async def get_care_event_or_404(event_id: str, projection: Optional[dict] = None) -> dict:
    """
    Get care event by ID or raise 404 HTTPException

    Args:
        event_id: The event's ID
        projection: Optional MongoDB projection dict to limit fields returned

    Returns:
        Care event document

    Raises:
        HTTPException: 404 if care event not found
    """
    projection_dict = projection if projection else {"_id": 0}
    event = await db.care_events.find_one({"id": event_id}, projection_dict)
    if not event:
        raise HTTPException(status_code=404, detail="Care event not found")
    return event

async def get_campus_or_404(campus_id: str) -> dict:
    """
    Get campus by ID or raise 404 HTTPException

    Args:
        campus_id: The campus's ID

    Returns:
        Campus document

    Raises:
        HTTPException: 404 if campus not found
    """
    campus = await db.campuses.find_one({"id": campus_id}, {"_id": 0})
    if not campus:
        raise HTTPException(status_code=404, detail="Campus not found")
    return campus

def generate_accident_followup_timeline(event_date: date, care_event_id: str, member_id: str, campus_id: str) -> List[Dict[str, Any]]:
    """Generate 3-stage accident/illness follow-up timeline"""
    # Get settings from localStorage or use defaults
    stages = [
        ("first_followup", ACCIDENT_FIRST_FOLLOWUP_DAYS),
        ("second_followup", ACCIDENT_SECOND_FOLLOWUP_DAYS),
        ("final_followup", ACCIDENT_FINAL_FOLLOWUP_DAYS),
    ]
    
    timeline = []
    for stage, days_offset in stages:
        scheduled_date = event_date + timedelta(days=days_offset)
        followup_stage = {
            "id": generate_uuid(),
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
        (GriefStage.ONE_WEEK, GRIEF_ONE_WEEK_DAYS),
        (GriefStage.TWO_WEEKS, GRIEF_TWO_WEEKS_DAYS),
        (GriefStage.ONE_MONTH, GRIEF_ONE_MONTH_DAYS),
        (GriefStage.THREE_MONTHS, GRIEF_THREE_MONTHS_DAYS),
        (GriefStage.SIX_MONTHS, GRIEF_SIX_MONTHS_DAYS),
        (GriefStage.ONE_YEAR, GRIEF_ONE_YEAR_DAYS),
    ]
    
    timeline = []
    for stage, days_offset in stages:
        scheduled_date = mourning_date + timedelta(days=days_offset)
        grief_support = {
            "id": generate_uuid(),
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
            
            await db.notification_logs.insert_one(msgspec.to_builtins(log_entry))
            
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
            await db.notification_logs.insert_one(msgspec.to_builtins(log_entry))
        
        return {
            "success": False,
            "error": str(e)
        }

# ==================== CAMPUS ENDPOINTS ====================

@post("/campuses")
async def create_campus(data: CampusCreate, request: Request) -> dict:
    """Create a new campus (full admin only)"""
    try:
        campus_obj = Campus(
            campus_name=campus.campus_name,
            location=campus.location
        )
        await db.campuses.insert_one(msgspec.to_builtins(campus_obj))

        # Invalidate campus cache
        invalidate_cache("campuses:")

        return campus_obj
    except Exception as e:
        logger.error(f"Error creating campus: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@get("/campuses")
async def list_campuses() -> list:
    """List all campuses (public for login selection) - cached for 10 minutes"""
    cache_key = "campuses:all"
    cached = get_from_cache(cache_key, ttl_seconds=600)

    # HTTP Cache headers for client-side caching (5 minutes public cache)
    cache_headers = {
        "Cache-Control": "public, max-age=300, stale-while-revalidate=600",
        "Vary": "Accept-Encoding"
    }

    if cached is not None:
        return LitestarResponse(content=cached, headers=cache_headers)

    try:
        campuses = await db.campuses.find({"is_active": True}, {"_id": 0}).to_list(100)

        # Serialize datetime fields for JSON response
        serialized_campuses = []
        for campus in campuses:
            campus_copy = dict(campus)
            if isinstance(campus_copy.get('created_at'), datetime):
                campus_copy['created_at'] = campus_copy['created_at'].isoformat()
            if isinstance(campus_copy.get('updated_at'), datetime):
                campus_copy['updated_at'] = campus_copy['updated_at'].isoformat()
            serialized_campuses.append(campus_copy)

        set_in_cache(cache_key, serialized_campuses)
        return LitestarResponse(content=serialized_campuses, headers=cache_headers)
    except Exception as e:
        logger.error(f"Error listing campuses: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@get("/campuses/{campus_id:str}")
async def get_campus(campus_id: str) -> dict:
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@put("/campuses/{campus_id:str}")
async def update_campus(campus_id: str, data: CampusCreate, request: Request) -> dict:
    """Update campus (full admin only)"""
    try:
        result = await db.campuses.update_one(
            {"id": campus_id},
            {"$set": {
                **msgspec.to_builtins(update),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Campus not found")

        # Invalidate campus cache
        invalidate_cache("campuses:")

        return await get_campus(campus_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating campus: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

# ==================== AUTHENTICATION ENDPOINTS ====================

@post("/auth/register")
async def register_user(data: UserCreate, request: Request) -> dict:
    """Register a new user (admin only)"""
    try:
        # Check if email already exists
        existing = await db.users.find_one({"email": data.email}, {"_id": 0})
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Validate campus_id for non-full-admin users
        if data.role != UserRole.FULL_ADMIN and not data.campus_id:
            raise HTTPException(status_code=400, detail="campus_id required for campus admin and pastor roles")
        
        user = User(
            email=data.email,
            name=data.name,
            role=data.role,
            campus_id=data.campus_id,
            phone=normalize_phone_number(data.phone),
            hashed_password=get_password_hash(data.password)
        )
        
        await db.users.insert_one(msgspec.to_builtins(user))
        
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@post("/auth/login")
async def login(data: UserLogin, request: Request) -> dict:
    """Login and get access token (rate limited: 5 attempts per minute)"""
    try:
        user = await db.users.find_one({"email": data.email}, {"_id": 0})
        if not user:
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        if not verify_password(data.password, user["hashed_password"]):
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        if not user.get("is_active", True):
            raise HTTPException(
                status_code=HTTP_403_FORBIDDEN,
                detail="User account is disabled"
            )
        
        # For campus-specific users, validate campus_id
        if user.get("role") in [UserRole.CAMPUS_ADMIN, UserRole.PASTOR]:
            if data.campus_id and user["campus_id"] != data.campus_id:
                raise HTTPException(
                    status_code=HTTP_403_FORBIDDEN,
                    detail="You don't have access to this campus"
                )
        
        # For full admins, use the selected campus_id from login
        active_campus_id = user.get("campus_id")
        if user.get("role") == UserRole.FULL_ADMIN:
            if data.campus_id:
                # Full admin selected a specific campus
                active_campus_id = data.campus_id
                # Update user's active campus
                await db.users.update_one(
                    {"id": user["id"]},
                    {"$set": {"campus_id": data.campus_id, "updated_at": datetime.now(timezone.utc).isoformat()}}
                )
            else:
                raise HTTPException(
                    status_code=HTTP_400_BAD_REQUEST,
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@get("/auth/me")
async def get_current_user_info(request: Request) -> dict:
    """Get current logged-in user info"""
    current_user = await get_current_user(request)
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

@get("/users")
async def list_users(request: Request) -> list:
    """List all users (admin only) - optimized with $lookup to avoid N+1 queries"""
    current_admin = await get_current_admin(request)
    try:
        query = {}
        # Campus admins only see users in their campus
        if current_admin.get("role") == UserRole.CAMPUS_ADMIN:
            query["campus_id"] = current_admin["campus_id"]

        # Use aggregation pipeline with $lookup for campus name (avoids N+1 queries)
        pipeline = [
            {"$match": query},
            # Only fetch required fields (exclude hashed_password for security)
            {"$project": {
                "_id": 0,
                "id": 1,
                "email": 1,
                "name": 1,
                "role": 1,
                "campus_id": 1,
                "phone": 1,
                "is_active": 1,
                "created_at": 1,
                "photo_url": 1
            }},
            # Lookup campus name
            {"$lookup": {
                "from": "campuses",
                "localField": "campus_id",
                "foreignField": "id",
                "as": "campus_info",
                "pipeline": [{"$project": {"campus_name": 1, "_id": 0}}]
            }},
            # Flatten campus_info array
            {"$addFields": {
                "campus_name": {"$arrayElemAt": ["$campus_info.campus_name", 0]}
            }},
            {"$project": {"campus_info": 0}},
            {"$limit": 100}
        ]

        users = await db.users.aggregate(pipeline).to_list(100)

        # Convert to UserResponse (is_active defaults to True if not present)
        result = [
            UserResponse(
                id=u["id"],
                email=u["email"],
                name=u["name"],
                role=u["role"],
                campus_id=u.get("campus_id"),
                campus_name=u.get("campus_name"),
                phone=u["phone"],
                is_active=u.get("is_active", True),
                created_at=u["created_at"]
            )
            for u in users
        ]

        return result
    except Exception as e:
        logger.error(f"Error listing users: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@put("/users/{user_id:str}")
async def update_user(user_id: str, data: UserUpdate, request: Request) -> dict:
    """Update a user (full admin only)"""
    current_user = await get_current_user(request)
    if current_user["role"] != "full_admin":
        raise HTTPException(status_code=403, detail="Only full administrators can update users")
    
    try:
        update_data = {k: v for k, v in msgspec.to_builtins(update).items() if v is not None}
        
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

class ProfileUpdate(Struct):
    """Model for self-profile update (excludes role and campus)"""
    name: str | None = None
    email: str | None = None
    phone: str | None = None

class PasswordChange(Struct):
    """Model for password change"""
    current_password: str
    new_password: str

@put("/auth/profile")
async def update_own_profile(update: ProfileUpdate, request: Request) -> dict:
    """Update own profile (all users can update their own name, email, phone)"""
    current_user = await get_current_user(request)
    try:
        update_data = {k: v for k, v in msgspec.to_builtins(update).items() if v is not None}

        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")

        # Normalize phone number if provided
        if 'phone' in update_data and update_data['phone']:
            update_data['phone'] = normalize_phone_number(update_data['phone'])

        # Check if email is being changed and if it's already taken
        if 'email' in update_data and update_data['email'] != current_user.get('email'):
            existing = await db.users.find_one({"email": update_data['email'], "id": {"$ne": current_user["id"]}})
            if existing:
                raise HTTPException(status_code=400, detail="Email already in use")

        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

        result = await db.users.update_one(
            {"id": current_user["id"]},
            {"$set": update_data}
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="User not found")

        updated_user = await db.users.find_one({"id": current_user["id"]}, {"_id": 0, "hashed_password": 0})

        # Get campus name if campus_id exists
        if updated_user.get("campus_id"):
            campus = await db.campuses.find_one({"id": updated_user["campus_id"]}, {"_id": 0})
            updated_user["campus_name"] = campus["campus_name"] if campus else None

        return updated_user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating profile: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@post("/auth/change-password")
async def change_password(data: PasswordChange, request: Request) -> dict:
    """Change own password (all users)"""
    current_user = await get_current_user(request)
    try:
        # Get user with hashed password
        user = await db.users.find_one({"id": current_user["id"]})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Verify current password
        if not verify_password(password_data.current_password, user["hashed_password"]):
            raise HTTPException(status_code=400, detail="Current password is incorrect")

        # Validate new password
        if len(password_data.new_password) < 6:
            raise HTTPException(status_code=400, detail="New password must be at least 6 characters")

        # Hash and update password
        new_hashed = get_password_hash(password_data.new_password)

        await db.users.update_one(
            {"id": current_user["id"]},
            {"$set": {
                "hashed_password": new_hashed,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )

        return {"message": "Password changed successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error changing password: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@post("/users/{user_id:str}/photo")
async def upload_user_photo(user_id: str, request: Request, data: UploadFile) -> dict:
    """Upload user profile photo"""
    current_user = await get_current_user(request)
    file = data  # Alias for compatibility
    # Users can upload their own photo or full admin can upload for others
    if current_user["id"] != user_id and current_user["role"] != "full_admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    try:
        # Validate file size
        contents = await file.read()
        if len(contents) > MAX_IMAGE_SIZE:
            raise HTTPException(status_code=400, detail=f"File too large. Maximum size is {MAX_IMAGE_SIZE // (1024*1024)} MB.")

        # Security: Validate image by magic bytes (not just Content-Type which can be spoofed)
        is_valid, result = validate_image_magic_bytes(contents)
        if not is_valid:
            raise HTTPException(status_code=400, detail=result)

        # Create uploads directory if not exists
        upload_dir = Path(ROOT_DIR) / "user_photos"
        upload_dir.mkdir(exist_ok=True)

        # Generate filename - always save as jpg since we convert to RGB
        filename = f"USER-{user_id[:8]}.jpg"
        filepath = upload_dir / filename

        # Resize image to 400x400 and optimize
        try:
            img = Image.open(io.BytesIO(contents))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid or corrupted image file")
        img = img.convert('RGB')
        img.thumbnail((400, 400), Image.Resampling.LANCZOS)
        img.save(filepath, 'JPEG', quality=85, optimize=True, progressive=True)
        
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@delete("/users/{user_id:str}", status_code=200)
async def delete_user(user_id: str, request: Request) -> dict:
    """Delete a user (admin only)"""
    current_admin = await get_current_admin(request)
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

# ==================== MEMBER ENDPOINTS ====================

@post("/members")
async def create_member(data: MemberCreate, request: Request) -> dict:
    """Create a new member"""
    current_user = await get_current_user(request)
    try:
        # For campus-specific users, enforce their campus
        campus_id = member.campus_id
        if current_user.get("role") in [UserRole.CAMPUS_ADMIN, UserRole.PASTOR]:
            campus_id = current_user["campus_id"]

        member_obj = Member(
            name=member.name,
            phone=normalize_phone_number(member.phone),
            campus_id=campus_id,
            external_member_id=member.external_member_id,
            notes=member.notes,
            birth_date=member.birth_date,
            address=member.address,
            category=member.category,
            gender=member.gender,
            blood_type=member.blood_type,
            marital_status=member.marital_status,
            membership_status=member.membership_status,
            age=member.age
        )

        member_dict = msgspec.to_builtins(member_obj)
        if member_dict.get('birth_date'):
            member_dict['birth_date'] = member_dict['birth_date'].isoformat() if isinstance(member_dict['birth_date'], date) else member_dict['birth_date']

        await db.members.insert_one(member_dict)
        return member_obj
    except Exception as e:
        logger.error(f"Error creating member: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@get("/members")
async def list_members(
    request: Request,
    page: int = Parameter(default=1, ge=1, le=MAX_PAGE_NUMBER),
    limit: int = Parameter(default=50, ge=1, le=MAX_LIMIT),
    engagement_status: Optional[EngagementStatus] = None,
    search: Optional[str] = None,
    show_archived: bool = False,
) -> list:
    """List all members with pagination"""
    current_user = await get_current_user(request)
    try:
        query = get_campus_filter(current_user)

        # Exclude archived members by default (unless show_archived=true)
        if not show_archived:
            query["is_archived"] = {"$ne": True}
        else:
            query["is_archived"] = True

        if engagement_status:
            query["engagement_status"] = engagement_status

        if search:
            # Security: Escape regex special characters to prevent NoSQL injection
            safe_search = escape_regex(search)
            query["$or"] = [
                {"name": {"$regex": safe_search, "$options": "i"}},  # Partial name match
                {"phone": {"$regex": safe_search, "$options": "i"}}  # Partial phone match
            ]
        
        # Calculate skip for pagination
        skip = (page - 1) * limit
        
        # Get total count for pagination metadata
        total = await db.members.count_documents(query)

        # Define projection for list view (exclude heavy fields like notes, address)
        projection = {
            "_id": 0,
            "id": 1,
            "name": 1,
            "phone": 1,
            "campus_id": 1,
            "photo_url": 1,
            "last_contact_date": 1,
            "engagement_status": 1,
            "days_since_last_contact": 1,
            "is_archived": 1,
            "external_member_id": 1,
            "age": 1,
            "gender": 1,
            "category": 1,
            "membership_status": 1,
            "marital_status": 1,
            "blood_type": 1,
            "birth_date": 1
            # Exclude: notes, address, archived_at, archived_reason, etc.
        }

        # Get paginated members with projection
        members = await db.members.find(query, projection).skip(skip).limit(limit).to_list(limit)
        
        # Update engagement status for each member
        for member in members:
            if member.get('last_contact_date'):
                if isinstance(member['last_contact_date'], str):
                    member['last_contact_date'] = datetime.fromisoformat(member['last_contact_date'])
            
            status, days = calculate_engagement_status(member.get('last_contact_date'))
            member['engagement_status'] = status
            member['days_since_last_contact'] = days
        
        # Return members array directly (frontend expects array)
        return members
        
    except Exception as e:
        logger.error(f"Error listing members: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

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


@get("/dashboard/reminders")
async def get_dashboard_reminders(request: Request) -> dict:
    """
    Get pre-calculated dashboard reminders
    Optimized for fast loading - data refreshed daily
    """
    current_user = await get_current_user(request)
    try:
        campus_id = current_user.get("campus_id")
        
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
                    "total_tasks": 0,
                    "total_members": 0
                }
        
        campus_tz = await get_campus_timezone(campus_id)
        today_date = get_date_in_timezone(campus_tz)
        
        # Check if we have cached data for today
        cache_key = f"dashboard_reminders_{current_user.get('campus_id')}_{today_date}"
        cached = await db.dashboard_cache.find_one({"cache_key": cache_key})

        if cached and cached.get("data"):
            return cached["data"]

        # If no cache, calculate now (fallback)
        data = await calculate_dashboard_reminders(current_user.get("campus_id"), campus_tz, today_date)
        
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

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
                except ValueError:
                    pass
            m["age"] = age
            member_map[m["id"]] = m
        
        # Initialize all arrays at the beginning
        birthdays_today = []
        upcoming_birthdays = []
        today_tasks = []
        overdue_birthdays = []
        upcoming_tasks = []
        
        # Grief support due (today and overdue) - with projection
        grief_stages = await db.grief_support.find(
            {"campus_id": campus_id, "completed": False, "ignored": {"$ne": True}},
            {
                "_id": 0,
                "id": 1,
                "member_id": 1,
                "campus_id": 1,
                "care_event_id": 1,
                "stage": 1,
                "scheduled_date": 1,
                "completed": 1,
                "notes": 1
            }
        ).to_list(None)
        
        logger.info(f"Found {len(grief_stages)} incomplete grief stages for campus")
        
        # Accident follow-ups due - with projection
        accident_followups = await db.accident_followup.find(
            {"campus_id": campus_id, "completed": False, "ignored": {"$ne": True}},
            {
                "_id": 0,
                "id": 1,
                "member_id": 1,
                "campus_id": 1,
                "care_event_id": 1,
                "stage": 1,
                "scheduled_date": 1,
                "completed": 1,
                "notes": 1
            }
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
        
        # Financial aid - categorize by date - with projection
        aid_schedules = await db.financial_aid_schedules.find(
            {"campus_id": campus_id, "is_active": True, "ignored": {"$ne": True}},
            {
                "_id": 0,
                "id": 1,
                "member_id": 1,
                "campus_id": 1,
                "aid_amount": 1,
                "frequency": 1,
                "next_occurrence": 1,
                "is_active": 1,
                "notes": 1
            }
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
                    "event_date": this_year_birthday.isoformat(),  # Override with this year's birthday
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
                        "event_date": this_year_birthday.isoformat(),  # Override with this year's birthday
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
                    "event_date": this_year_birthday.isoformat(),  # Override with this year's birthday
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
            "total_tasks": len(birthdays_today) + len(grief_today) + len(accident_today) + len(at_risk) + len(disconnected),
            "total_members": len(members)
        }
        
    except Exception as e:
        logger.error(f"Error calculating dashboard reminders: {str(e)}")
        raise

async def get_campus_timezone(campus_id: str) -> str:
    """Get campus timezone setting"""
    try:
        campus = await db.campuses.find_one({"id": campus_id}, {"_id": 0, "timezone": 1})
        return campus.get("timezone", "Asia/Jakarta") if campus else "Asia/Jakarta"
    except Exception:
        return "Asia/Jakarta"

def get_date_in_timezone(timezone_str: str) -> str:
    """Get current date in specified timezone as YYYY-MM-DD string"""
    try:
        tz = ZoneInfo(timezone_str)
        return datetime.now(tz).strftime('%Y-%m-%d')
    except Exception:
        return datetime.now(ZoneInfo("Asia/Jakarta")).strftime('%Y-%m-%d')


@post("/care-events/{event_id:str}/ignore")
async def ignore_care_event(event_id: str, request: Request) -> dict:
    """Mark a care event as ignored/dismissed"""
    try:
        # Get the care event with campus filter for multi-tenancy
        query = {"id": event_id}
        campus_filter = get_campus_filter(user)
        if campus_filter:
            query.update(campus_filter)
        event = await db.care_events.find_one(query, {"_id": 0})
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@get("/members/at-risk")
async def list_at_risk_members(request: Request) -> list:
    """Get members with no contact in 30+ days"""
    current_user = await get_current_user(request)
    try:
        # Apply campus filter for multi-tenancy
        query = get_campus_filter(current_user)

        # Projection for at-risk members list
        projection = {
            "_id": 0,
            "id": 1,
            "name": 1,
            "phone": 1,
            "campus_id": 1,
            "photo_url": 1,
            "last_contact_date": 1,
            "engagement_status": 1,
            "days_since_last_contact": 1,
            "external_member_id": 1
        }

        members = await db.members.find(query, projection).to_list(1000)

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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@get("/members/{member_id:str}")
async def get_member(member_id: str, request: Request) -> dict:
    """Get member by ID"""
    current_user = await get_current_user(request)
    try:
        # Build query with campus filter for multi-tenancy
        query = {"id": member_id}
        campus_filter = get_campus_filter(current_user)
        if campus_filter:
            query.update(campus_filter)

        member = await db.members.find_one(query, {"_id": 0})
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@put("/members/{member_id:str}")
async def update_member(member_id: str, data: MemberUpdate, request: Request) -> dict:
    """Update member"""
    current_user = await get_current_user(request)
    try:
        # Verify member belongs to user's campus
        query = {"id": member_id}
        campus_filter = get_campus_filter(current_user)
        if campus_filter:
            query.update(campus_filter)

        member = await db.members.find_one(query, {"_id": 0})
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")

        update_data = {k: v for k, v in msgspec.to_builtins(update).items() if v is not None}

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

        return await get_member(member_id, current_user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating member: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@delete("/members/{member_id:str}", status_code=200)
async def delete_member(member_id: str, request: Request) -> dict:
    """Delete member"""
    current_user = await get_current_user(request)
    try:
        # Verify member belongs to user's campus
        query = {"id": member_id}
        campus_filter = get_campus_filter(current_user)
        if campus_filter:
            query.update(campus_filter)

        member = await db.members.find_one(query, {"_id": 0})
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")

        result = await db.members.delete_one({"id": member_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Member not found")

        # Also delete related care events and grief support (with campus filter for defense in depth)
        member_campus_id = member.get("campus_id")
        cascade_filter = {"member_id": member_id}
        if member_campus_id:
            cascade_filter["campus_id"] = member_campus_id

        await db.care_events.delete_many(cascade_filter)
        await db.grief_support.delete_many(cascade_filter)
        await db.accident_followup.delete_many(cascade_filter)
        await db.activity_logs.delete_many({"member_id": member_id, "campus_id": member_campus_id} if member_campus_id else {"member_id": member_id})

        # Log activity
        await log_activity(
            db=db,
            user_id=current_user["id"],
            user_name=current_user["name"],
            campus_id=current_user.get("campus_id"),
            action="delete_member",
            target_type="member",
            target_id=member_id,
            target_name=member.get("name", "Unknown"),
            description=f"Deleted member {member.get('name', 'Unknown')}"
        )

        return {"success": True, "message": "Member deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting member: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@delete("/care-events/{event_id:str}", status_code=200)
async def delete_care_event(event_id: str, request: Request) -> dict:
    """Delete care event and recalculate member engagement"""
    current_user = await get_current_user(request)
    try:
        # Build query with campus filter for multi-tenancy
        query = {"id": event_id}
        campus_filter = get_campus_filter(current_user)
        if campus_filter:
            query.update(campus_filter)

        # Get the care event first to know which member and type
        event = await db.care_events.find_one(query, {"_id": 0})
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
                # Also delete the activity log associated with the original birthday event completion
                await db.activity_logs.delete_many({"care_event_id": birthday_event["id"]})
        
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

            # Get timeline entries created from these stages (to delete their activity logs)
            stage_ids = [s["id"] for s in grief_stages]
            if stage_ids:
                # Get IDs of timeline entries before deleting them
                timeline_entries = await db.care_events.find(
                    {"grief_stage_id": {"$in": stage_ids}},
                    {"_id": 0, "id": 1}
                ).to_list(None)
                timeline_entry_ids = [e["id"] for e in timeline_entries]

                # Delete activity logs for these timeline entries
                if timeline_entry_ids:
                    await db.activity_logs.delete_many({"care_event_id": {"$in": timeline_entry_ids}})

                # Delete the timeline entries
                await db.care_events.delete_many({"grief_stage_id": {"$in": stage_ids}})

            # Delete grief support stages
            await db.grief_support.delete_many({"care_event_id": event_id})
            
        elif event_type == "accident_illness":
            # Get all accident stages
            accident_stages = await db.accident_followup.find(
                {"care_event_id": event_id},
                {"_id": 0, "id": 1, "member_id": 1, "stage": 1}
            ).to_list(None)

            # Get timeline entries created from these stages (to delete their activity logs)
            stage_ids = [s["id"] for s in accident_stages]
            if stage_ids:
                # Get IDs of timeline entries before deleting them
                timeline_entries = await db.care_events.find(
                    {"accident_stage_id": {"$in": stage_ids}},
                    {"_id": 0, "id": 1}
                ).to_list(None)
                timeline_entry_ids = [e["id"] for e in timeline_entries]

                # Delete activity logs for these timeline entries
                if timeline_entry_ids:
                    await db.activity_logs.delete_many({"care_event_id": {"$in": timeline_entry_ids}})

                # Delete the timeline entries
                await db.care_events.delete_many({"accident_stage_id": {"$in": stage_ids}})

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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@post("/members/{member_id:str}/photo")
async def upload_member_photo(member_id: str, request: Request, data: UploadFile) -> dict:
    """Upload member profile photo with optimization"""
    current_user = await get_current_user(request)
    file = data  # Alias for compatibility
    try:
        # Build query with campus filter for multi-tenancy
        query = {"id": member_id}
        campus_filter = get_campus_filter(current_user)
        if campus_filter:
            query.update(campus_filter)

        # Check member exists and belongs to user's campus
        member = await db.members.find_one(query, {"_id": 0})
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")

        # Read and validate file size
        contents = await file.read()
        if len(contents) > MAX_IMAGE_SIZE:
            raise HTTPException(status_code=400, detail=f"File too large. Maximum size is {MAX_IMAGE_SIZE // (1024*1024)} MB.")

        # Security: Validate image by magic bytes (not just Content-Type which can be spoofed)
        is_valid, result = validate_image_magic_bytes(contents)
        if not is_valid:
            raise HTTPException(status_code=400, detail=result)

        # Process image
        try:
            image = Image.open(io.BytesIO(contents))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid or corrupted image file")
        
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
            
            # Save with optimization (progressive JPEG for faster loading)
            filename = f"{base_filename}_{size_name}.jpg"
            filepath = Path(ROOT_DIR) / "uploads" / filename
            resized.save(filepath, "JPEG", quality=85, optimize=True, progressive=True)
            
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

# ==================== CARE EVENT ENDPOINTS ====================

@post("/care-events")
async def create_care_event(data: CareEventCreate, request: Request) -> dict:
    """Create a new care event"""
    current_user = await get_current_user(request)
    event = data  # Alias for backward compatibility
    try:
        # For campus-specific users, enforce their campus
        campus_id = event.campus_id
        if current_user.get("role") in [UserRole.CAMPUS_ADMIN, UserRole.PASTOR]:
            campus_id = current_user["campus_id"]

        # Validate required fields for financial aid events
        if event.event_type == EventType.FINANCIAL_AID:
            logger.info(f"[FINANCIAL AID] Creating event: aid_type={repr(event.aid_type)}, aid_amount={repr(event.aid_amount)}")
            if not event.aid_type:
                logger.warning(f"[FINANCIAL AID] Rejecting: aid_type is missing or falsy: {repr(event.aid_type)}")
                raise HTTPException(status_code=400, detail="Aid type is required for financial aid events")
            if event.aid_amount is None or event.aid_amount < 0:
                logger.warning(f"[FINANCIAL AID] Rejecting: aid_amount is invalid: {repr(event.aid_amount)}")
                raise HTTPException(status_code=400, detail="Aid amount is required and must be non-negative for financial aid events")

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
            care_event.visitation_log = [msgspec.to_builtins(event.initial_visitation)]

        # Serialize for MongoDB using msgspec
        event_dict = msgspec.to_builtins(care_event)

        # Log what we're about to save for financial aid events
        if event.event_type == EventType.FINANCIAL_AID:
            logger.info(f"[FINANCIAL AID] Saving to DB: aid_type={repr(event_dict.get('aid_type'))}, aid_amount={repr(event_dict.get('aid_amount'))}")

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

        # Update member's last contact date for completed one-time events or non-birthday events
        if is_one_time or (event.event_type != EventType.BIRTHDAY):
            now = datetime.now(timezone.utc)
            await db.members.update_one(
                {"id": event.member_id},
                {"$set": {
                    "last_contact_date": now.isoformat(),
                    "days_since_last_contact": 0,
                    "engagement_status": "active",
                    "updated_at": now.isoformat()
                }}
            )
        
        # Invalidate dashboard cache
        await invalidate_dashboard_cache(campus_id)
        
        return care_event
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating care event: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))



class AdditionalVisitRequest2(Struct):
    """Second definition for additional visit (duplicate of line 714)"""
    visit_date: str
    visit_type: str
    notes: str

@post("/care-events/{parent_event_id:str}/additional-visit")
async def log_additional_visit(
    parent_event_id: str,
    data: AdditionalVisitRequest,
    request: Request,
) -> dict:
    """
    Log an additional unscheduled visit for grief or accident/illness event
    Creates a child care_event linked to parent
    """
    current_user = await get_current_user(request)
    try:
        # Get parent event
        parent = await db.care_events.find_one({"id": parent_event_id}, {"_id": 0})
        if not parent:
            raise HTTPException(status_code=404, detail="Parent event not found")
        
        # Verify it's a grief or accident event
        if parent["event_type"] not in [EventType.GRIEF_LOSS, EventType.ACCIDENT_ILLNESS]:
            raise HTTPException(status_code=400, detail="Additional visits only for grief/accident events")
        
        # Get member name
        member = await db.members.find_one({"id": parent["member_id"]}, {"_id": 0, "name": 1})
        member_name = member["name"] if member else "Unknown"
        
        # Create additional visit event
        additional_visit = {
            "id": generate_uuid(),
            "member_id": parent["member_id"],
            "campus_id": parent["campus_id"],
            "event_type": parent["event_type"],  # Same type as parent (grief_loss or accident_illness)
            "care_event_id": parent_event_id,  # Link to parent
            "followup_type": "additional",  # Marker for additional visit
            "event_date": data.visit_date,
            "title": f"Additional Visit - {data.visit_type}",
            "description": data.notes,
            "completed": True,  # Always completed (already happened)
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "completed_by_user_id": current_user["id"],
            "completed_by_user_name": current_user["name"],
            "created_by_user_id": current_user["id"],
            "created_by_user_name": current_user["name"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.care_events.insert_one(additional_visit)
        
        # Log activity
        await log_activity(
            campus_id=parent["campus_id"],
            user_id=current_user["id"],
            user_name=current_user["name"],
            action_type=ActivityActionType.COMPLETE_TASK,
            member_id=parent["member_id"],
            member_name=member_name,
            care_event_id=additional_visit["id"],
            event_type=EventType(parent["event_type"]),
            notes=f"Logged additional visit: {data.visit_type}",
            user_photo_url=current_user.get("photo_url")
        )
        
        # Update member engagement
        await db.members.update_one(
            {"id": parent["member_id"]},
            {"$set": {
                "last_contact_date": datetime.now(timezone.utc).isoformat(),
                "engagement_status": "active",
                "days_since_last_contact": 0
            }}
        )
        
        return {
            "success": True,
            "message": f"Additional visit logged: {data.visit_type}",
            "visit_id": additional_visit["id"]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error logging additional visit: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@get("/care-events")
async def list_care_events(
    request: Request,
    event_type: Optional[EventType] = None,
    member_id: Optional[str] = None,
    completed: Optional[bool] = None,
    page: int = Parameter(default=1, ge=1, le=MAX_PAGE_NUMBER),
    limit: int = Parameter(default=50, ge=1, le=MAX_LIMIT),
) -> dict:
    """List care events with optional filters and pagination - optimized with $lookup"""
    current_user = await get_current_user(request)
    try:
        # Apply campus filter for multi-tenancy
        query = get_campus_filter(current_user)

        if event_type:
            query["event_type"] = event_type

        if member_id:
            query["member_id"] = member_id

        if completed is not None:
            query["completed"] = completed

        # Calculate skip for pagination
        skip = (page - 1) * limit

        # Use aggregation with $lookup to avoid N+1 queries (50x faster)
        pipeline = [
            {"$match": query},
            {"$sort": {"event_date": -1, "created_at": -1}},  # Secondary sort by created_at for same-day events
            {"$skip": skip},
            {"$limit": limit},
            # Join with members collection to get member names, phone, and photo in single query
            {"$lookup": {
                "from": "members",
                "localField": "member_id",
                "foreignField": "id",
                "as": "member_info",
                "pipeline": [{"$project": {"_id": 0, "name": 1, "phone": 1, "photo_url": 1}}]
            }},
            # Flatten member_info array to single object
            {"$addFields": {
                "member_name": {
                    "$cond": {
                        "if": {"$gt": [{"$size": "$member_info"}, 0]},
                        "then": {"$arrayElemAt": ["$member_info.name", 0]},
                        "else": {
                            # Fallback: extract name from title if member not found
                            "$cond": {
                                "if": {"$regexMatch": {"input": "$title", "regex": " - "}},
                                "then": {"$arrayElemAt": [{"$split": ["$title", " - "]}, 1]},
                                "else": None
                            }
                        }
                    }
                },
                "member_phone": {
                    "$cond": {
                        "if": {"$gt": [{"$size": "$member_info"}, 0]},
                        "then": {"$arrayElemAt": ["$member_info.phone", 0]},
                        "else": None
                    }
                },
                "member_photo_url": {
                    "$cond": {
                        "if": {"$gt": [{"$size": "$member_info"}, 0]},
                        "then": {"$arrayElemAt": ["$member_info.photo_url", 0]},
                        "else": None
                    }
                }
            }},
            # Remove temporary lookup field and _id
            {"$project": {"member_info": 0, "_id": 0}}
        ]

        events = await db.care_events.aggregate(pipeline).to_list(limit)
        return events
    except Exception as e:
        logger.error(f"Error listing care events: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@get("/care-events/{event_id:str}")
async def get_care_event(event_id: str, request: Request) -> dict:
    """Get care event by ID"""
    current_user = await get_current_user(request)
    try:
        # Build query with campus filter for multi-tenancy
        query = {"id": event_id}
        campus_filter = get_campus_filter(current_user)
        if campus_filter:
            query.update(campus_filter)

        event = await db.care_events.find_one(query, {"_id": 0})
        if not event:
            raise HTTPException(status_code=404, detail="Care event not found")
        return event
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting care event: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@put("/care-events/{event_id:str}")
async def update_care_event(event_id: str, data: CareEventUpdate, request: Request) -> dict:
    """Update care event"""
    current_user = await get_current_user(request)
    try:
        # Build query with campus filter for multi-tenancy
        query = {"id": event_id}
        campus_filter = get_campus_filter(current_user)
        if campus_filter:
            query.update(campus_filter)

        event = await db.care_events.find_one(query, {"_id": 0})
        if not event:
            raise HTTPException(status_code=404, detail="Care event not found")

        update_data = {k: v for k, v in msgspec.to_builtins(update).items() if v is not None}
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

        result = await db.care_events.update_one(
            {"id": event_id},
            {"$set": update_data}
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Care event not found")

        return await get_care_event(event_id, current_user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating care event: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@post("/care-events/{event_id:str}/complete")
async def complete_care_event(event_id: str, request: Request) -> dict:
    """Mark care event as completed and update member engagement"""
    current_user = await get_current_user(request)
    try:
        # Get the care event with campus filter for multi-tenancy
        query = {"id": event_id}
        campus_filter = get_campus_filter(current_user)
        if campus_filter:
            query.update(campus_filter)
        event = await db.care_events.find_one(query, {"_id": 0})
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
                "id": generate_uuid(),
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@post("/care-events/{event_id:str}/send-reminder")
async def send_care_event_reminder(event_id: str, request: Request) -> dict:
    """Send WhatsApp reminder for care event"""
    current_user = await get_current_user(request)
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@post("/care-events/{event_id:str}/visitation-log")
async def add_visitation_log(event_id: str, entry: VisitationLogEntry) -> dict:
    """Add visitation log entry to hospital visit"""
    try:
        event = await db.care_events.find_one({"id": event_id}, {"_id": 0})
        if not event:
            raise HTTPException(status_code=404, detail="Care event not found")
        
        log_entry = msgspec.to_builtins(entry)
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@get("/care-events/hospital/due-followup")
async def get_hospital_followup_due() -> dict:
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

# ==================== GRIEF SUPPORT ENDPOINTS ====================

@get("/grief-support")
async def list_grief_support(
    request: Request,
    completed: Optional[bool] = None,
    page: int = Parameter(default=1, ge=1, le=MAX_PAGE_NUMBER),
    limit: int = Parameter(default=50, ge=1, le=MAX_LIMIT),
) -> dict:
    """List grief support stages with pagination"""
    current_user = await get_current_user(request)
    try:
        query = get_campus_filter(current_user)
        if completed is not None:
            query["completed"] = completed

        skip = (page - 1) * limit
        stages = await db.grief_support.find(query, {"_id": 0}).sort("scheduled_date", 1).skip(skip).limit(limit).to_list(limit)
        return stages
    except Exception as e:
        logger.error(f"Error listing grief support: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@get("/grief-support/member/{member_id:str}")
async def get_member_grief_timeline(member_id: str, request: Request) -> dict:
    """Get grief timeline for specific member"""
    current_user = await get_current_user(request)
    try:
        # Build query with campus filter
        query = {"member_id": member_id}
        campus_filter = get_campus_filter(current_user)
        query.update(campus_filter)

        timeline = await db.grief_support.find(
            query,
            {"_id": 0}
        ).sort("scheduled_date", 1).to_list(100)

        return timeline
    except Exception as e:
        logger.error(f"Error getting member grief timeline: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@post("/grief-support/{stage_id:str}/complete")
async def complete_grief_stage(stage_id: str, request: Request, notes: Optional[str] = None) -> dict:
    """Mark grief stage as completed with notes"""
    current_user = await get_current_user(request)
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
        
        timeline_event_id = generate_uuid()
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@post("/grief-support/{stage_id:str}/ignore")
async def ignore_grief_stage(stage_id: str, request: Request) -> dict:
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
        
        timeline_event_id = generate_uuid()
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@post("/grief-support/{stage_id:str}/undo")
async def undo_grief_stage(stage_id: str, request: Request) -> dict:
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@post("/grief-support/{stage_id:str}/send-reminder")
async def send_grief_reminder(stage_id: str) -> dict:
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@get("/accident-followup")
async def list_accident_followup(
    request: Request,
    completed: Optional[bool] = None,
    page: int = Parameter(default=1, ge=1, le=MAX_PAGE_NUMBER),
    limit: int = Parameter(default=50, ge=1, le=MAX_LIMIT),
) -> dict:
    """List all accident follow-up stages with pagination"""
    current_user = await get_current_user(request)
    try:
        query = get_campus_filter(current_user)
        if completed is not None:
            query["completed"] = completed

        skip = (page - 1) * limit
        stages = await db.accident_followup.find(query, {"_id": 0}).sort("scheduled_date", 1).skip(skip).limit(limit).to_list(limit)
        return stages
    except Exception as e:
        logger.error(f"Error listing accident follow-up: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@get("/accident-followup/member/{member_id:str}")
async def get_member_accident_timeline(member_id: str, request: Request) -> dict:
    """Get accident follow-up timeline for specific member"""
    current_user = await get_current_user(request)
    try:
        # Build query with campus filter
        query = {"member_id": member_id}
        campus_filter = get_campus_filter(current_user)
        query.update(campus_filter)

        timeline = await db.accident_followup.find(
            query,
            {"_id": 0}
        ).sort("scheduled_date", 1).to_list(100)

        return timeline
    except Exception as e:
        logger.error(f"Error getting member accident timeline: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@post("/accident-followup/{stage_id:str}/complete")
async def complete_accident_stage(stage_id: str, request: Request, notes: Optional[str] = None) -> dict:
    """Mark accident follow-up stage as completed"""
    current_user = await get_current_user(request)
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
        
        timeline_event_id = generate_uuid()
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@post("/accident-followup/{stage_id:str}/undo")
async def undo_accident_stage(stage_id: str, request: Request) -> dict:
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

# ==================== FINANCIAL AID SCHEDULE ENDPOINTS ====================

@post("/financial-aid-schedules")
async def create_aid_schedule(schedule: dict, request: Request) -> dict:
    """Create a financial aid schedule"""
    current_user = await get_current_user(request)
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
        
        # Serialize for MongoDB using msgspec
        schedule_dict = msgspec.to_builtins(aid_schedule)
        
        await db.financial_aid_schedules.insert_one(schedule_dict)
        
        # Invalidate dashboard cache
        await invalidate_dashboard_cache(schedule['campus_id'])
        
        return aid_schedule
    except Exception as e:
        logger.error(f"Error creating aid schedule: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@get("/financial-aid-schedules")
async def list_aid_schedules(
    request: Request,
    member_id: Optional[str] = None,
    active_only: bool = True,
    page: int = Parameter(default=1, ge=1, le=MAX_PAGE_NUMBER),
    limit: int = Parameter(default=50, ge=1, le=MAX_LIMIT),
) -> dict:
    """List financial aid schedules with pagination"""
    current_user = await get_current_user(request)
    try:
        query = get_campus_filter(current_user)

        if member_id:
            query['member_id'] = member_id

        if active_only:
            query['is_active'] = True

        skip = (page - 1) * limit
        schedules = await db.financial_aid_schedules.find(query, {"_id": 0}).skip(skip).limit(limit).to_list(limit)
        return schedules
    except Exception as e:
        logger.error(f"Error listing aid schedules: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@delete("/financial-aid-schedules/{schedule_id:str}/ignored-occurrence/{date:str}", status_code=200)
async def remove_ignored_occurrence(schedule_id: str, date: str, request: Request) -> dict:
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@delete("/financial-aid-schedules/{schedule_id:str}/ignored-occurrence/{occurrence_date:str}", status_code=200)
async def remove_ignored_occurrence(schedule_id: str, occurrence_date: str) -> dict:
    """Remove a specific ignored occurrence from the schedule and its activity log"""
    try:
        schedule = await db.financial_aid_schedules.find_one({"id": schedule_id}, {"_id": 0})
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
        
        # Delete activity log for this ignore action
        # Match activity log that has this date in the notes
        await db.activity_logs.delete_many({
            "member_id": schedule["member_id"],
            "event_type": "financial_aid",
            "action_type": "ignore_task",
            "notes": {"$regex": occurrence_date, "$options": "i"}
        })
        
        # Invalidate dashboard cache
        await invalidate_dashboard_cache(schedule["campus_id"])
        
        return {"success": True, "message": "Ignored occurrence removed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing ignored occurrence: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@post("/financial-aid-schedules/{schedule_id:str}/clear-ignored")
async def clear_all_ignored_occurrences(schedule_id: str, request: Request) -> dict:
    """Clear all ignored occurrences for a schedule"""
    current_user = await get_current_user(request)
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
            event_type=EventType.FINANCIAL_AID,
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@delete("/financial-aid-schedules/{schedule_id:str}", status_code=200)
async def delete_aid_schedule(schedule_id: str, request: Request) -> dict:
    """Delete a financial aid schedule and related activity logs"""
    try:
        # Get schedule details before deleting
        schedule = await db.financial_aid_schedules.find_one({"id": schedule_id}, {"_id": 0})
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")
        
        # Delete activity logs related to this schedule
        # Match by member_id and notes containing aid_type or "financial aid"
        await db.activity_logs.delete_many({
            "member_id": schedule["member_id"],
            "event_type": "financial_aid",
            "notes": {"$regex": schedule.get('aid_type', 'financial aid'), "$options": "i"}
        })
        
        # Delete the schedule
        result = await db.financial_aid_schedules.delete_one({"id": schedule_id})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Schedule not found")
        
        # Invalidate dashboard cache
        await invalidate_dashboard_cache(schedule["campus_id"])
        
        return {"success": True, "message": "Financial aid schedule and related logs deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting aid schedule: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@post("/financial-aid-schedules/{schedule_id:str}/stop")
async def stop_aid_schedule(schedule_id: str, request: Request) -> dict:
    """Manually stop a financial aid schedule"""
    current_user = await get_current_user(request)
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
            event_type=EventType.FINANCIAL_AID,
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@get("/financial-aid-schedules/member/{member_id:str}")
async def get_member_aid_schedules(member_id: str, request: Request) -> dict:
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@get("/financial-aid-schedules/due-today")
async def get_aid_due_today(request: Request) -> dict:
    """Get financial aid schedules due today and overdue"""
    current_user = await get_current_user(request)
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@post("/financial-aid-schedules/{schedule_id:str}/mark-distributed")
async def mark_aid_distributed(schedule_id: str, request: Request) -> dict:
    """Mark scheduled aid as distributed and advance to next occurrence"""
    current_user = await get_current_user(request)
    try:
        # Get the schedule
        schedule = await db.financial_aid_schedules.find_one({"id": schedule_id}, {"_id": 0})
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")
        
        # Get member name for logging
        member = await db.members.find_one({"id": schedule["member_id"]}, {"_id": 0, "name": 1})
        member_name = member["name"] if member else "Unknown"
        
        # Create care event for this payment
        payment_event_id = generate_uuid()
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@post("/financial-aid-schedules/{schedule_id:str}/ignore")
async def ignore_financial_aid_schedule(schedule_id: str, request: Request) -> dict:
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
        
        # Log activity
        await log_activity(
            campus_id=schedule["campus_id"],
            user_id=user["id"],
            user_name=user["name"],
            action_type=ActivityActionType.IGNORE_TASK,
            member_id=schedule["member_id"],
            member_name=member_name,
            event_type=EventType.FINANCIAL_AID,
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


# ==================== FINANCIAL AID ENDPOINTS ====================

@post("/accident-followup/{stage_id:str}/ignore")
async def ignore_accident_stage(stage_id: str, request: Request) -> dict:
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
        
        timeline_event_id = generate_uuid()
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@get("/financial-aid/summary")
async def get_financial_aid_summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> dict:
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@get("/financial-aid/recipients")
async def get_financial_aid_recipients() -> dict:
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@get("/financial-aid/member/{member_id:str}")
async def get_member_financial_aid(member_id: str) -> dict:
    """Get all financial aid given to a member"""
    try:
        aid_events = await db.care_events.find({
            "member_id": member_id,
            "event_type": EventType.FINANCIAL_AID
        }, {"_id": 0}).sort([("event_date", -1), ("created_at", -1)]).to_list(100)
        
        total_amount = sum(event.get('aid_amount', 0) or 0 for event in aid_events)
        
        return {
            "member_id": member_id,
            "total_amount": total_amount,
            "aid_count": len(aid_events),
            "aid_history": aid_events
        }
    except Exception as e:
        logger.error(f"Error getting member financial aid: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

# ==================== DASHBOARD ENDPOINTS ====================

@get("/dashboard/stats")
async def get_dashboard_stats() -> dict:
    """Get overall dashboard statistics"""
    try:
        # Optimize: Use aggregation pipeline to get member stats in single query
        member_stats_pipeline = [
            {
                "$facet": {
                    "total_count": [
                        {"$count": "count"}
                    ],
                    "at_risk_count": [
                        {"$match": {"engagement_status": {"$in": ["at_risk", "disconnected"]}}},
                        {"$count": "count"}
                    ],
                    "engagement_distribution": [
                        {"$group": {"_id": "$engagement_status", "count": {"$sum": 1}}}
                    ]
                }
            }
        ]

        member_stats_result = await db.members.aggregate(member_stats_pipeline).to_list(1)
        member_stats = member_stats_result[0] if member_stats_result else {}

        total_members = member_stats.get("total_count", [{}])[0].get("count", 0)
        at_risk_count = member_stats.get("at_risk_count", [{}])[0].get("count", 0)

        # Active grief support count (separate collection)
        active_grief = await db.grief_support.count_documents({"completed": False})

        # Optimize: Use aggregation to sum financial aid amounts directly in MongoDB
        today = date.today()
        month_start = today.replace(day=1).isoformat()

        financial_aid_pipeline = [
            {
                "$match": {
                    "event_type": EventType.FINANCIAL_AID,
                    "event_date": {"$gte": month_start}
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_aid": {"$sum": {"$ifNull": ["$aid_amount", 0]}}
                }
            }
        ]

        financial_aid_result = await db.care_events.aggregate(financial_aid_pipeline).to_list(1)
        total_aid = financial_aid_result[0]["total_aid"] if financial_aid_result else 0

        return {
            "total_members": total_members,
            "active_grief_support": active_grief,
            "members_at_risk": at_risk_count,
            "month_financial_aid": total_aid
        }
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@get("/dashboard/upcoming")
async def get_upcoming_events(days: int = 7) -> dict:
    """Get upcoming events for next N days"""
    try:
        today = date.today()
        future_date = today + timedelta(days=days)

        # Optimize: Use aggregation with $lookup to join member data in single query
        pipeline = [
            {
                "$match": {
                    "event_date": {
                        "$gte": today.isoformat(),
                        "$lte": future_date.isoformat()
                    },
                    "completed": False
                }
            },
            {
                "$lookup": {
                    "from": "members",
                    "localField": "member_id",
                    "foreignField": "id",
                    "as": "member_info"
                }
            },
            {
                "$addFields": {
                    "member_name": {"$arrayElemAt": ["$member_info.name", 0]},
                    "member_phone": {"$arrayElemAt": ["$member_info.phone", 0]}
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "member_info": 0
                }
            },
            {"$sort": {"event_date": 1}},
            {"$limit": 100}
        ]

        events = await db.care_events.aggregate(pipeline).to_list(100)
        return events
    except Exception as e:
        logger.error(f"Error getting upcoming events: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@get("/dashboard/grief-active")
async def get_active_grief_support() -> dict:
    """Get members currently in grief support timeline"""
    try:
        # Optimize: Use aggregation with $lookup and $group to join and group in single query
        pipeline = [
            {"$match": {"completed": False}},
            {"$sort": {"scheduled_date": 1}},
            {
                "$lookup": {
                    "from": "members",
                    "localField": "member_id",
                    "foreignField": "id",
                    "as": "member_info"
                }
            },
            {
                "$addFields": {
                    "member_name": {"$arrayElemAt": ["$member_info.name", 0]},
                    "member_phone": {"$arrayElemAt": ["$member_info.phone", 0]}
                }
            },
            {
                "$group": {
                    "_id": "$member_id",
                    "member_id": {"$first": "$member_id"},
                    "member_name": {"$first": {"$ifNull": ["$member_name", "Unknown"]}},
                    "stages": {
                        "$push": {
                            "$arrayToObject": {
                                "$filter": {
                                    "input": {"$objectToArray": "$$ROOT"},
                                    "cond": {"$not": [{"$in": ["$$this.k", ["_id", "member_info", "member_name", "member_phone"]]}]}
                                }
                            }
                        }
                    }
                }
            },
            {"$project": {"_id": 0}},
            {"$limit": 100}
        ]

        result = await db.grief_support.aggregate(pipeline).to_list(100)
        return result
    except Exception as e:
        logger.error(f"Error getting active grief support: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@get("/dashboard/recent-activity")
async def get_recent_activity(request: Request, limit: int = 20) -> dict:
    """Get recent care events"""
    current_user = await get_current_user(request)
    try:
        # Build campus filter for multi-tenancy
        campus_filter = get_campus_filter(current_user)
        match_stage = {"$match": campus_filter} if campus_filter else {"$match": {}}

        # Optimize: Use aggregation with $lookup to join member data in single query
        pipeline = [
            match_stage,
            {
                "$lookup": {
                    "from": "members",
                    "localField": "member_id",
                    "foreignField": "id",
                    "as": "member_info"
                }
            },
            {
                "$addFields": {
                    "member_name": {"$arrayElemAt": ["$member_info.name", 0]}
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "member_info": 0
                }
            },
            {"$sort": {"created_at": -1}},
            {"$limit": limit}
        ]

        events = await db.care_events.aggregate(pipeline).to_list(limit)
        return events
    except Exception as e:
        logger.error(f"Error getting recent activity: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

# ==================== ANALYTICS ENDPOINTS ====================

@get("/analytics/engagement-trends")
async def get_engagement_trends(request: Request, days: int = 30) -> dict:
    """Get engagement trends over time"""
    current_user = await get_current_user(request)
    try:
        start_date = date.today() - timedelta(days=days)

        # Apply campus filter for multi-tenancy
        query = {"event_date": {"$gte": start_date.isoformat()}}
        campus_filter = get_campus_filter(current_user)
        if campus_filter:
            query.update(campus_filter)

        events = await db.care_events.find(query, {"_id": 0, "event_date": 1}).to_list(1000)

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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@get("/analytics/care-events-by-type")
async def get_care_events_by_type(request: Request) -> dict:
    """Get distribution of care events by type"""
    current_user = await get_current_user(request)
    try:
        # Apply campus filter for multi-tenancy
        campus_filter = get_campus_filter(current_user)
        query = campus_filter if campus_filter else {}

        events = await db.care_events.find(query, {"_id": 0, "event_type": 1}).to_list(10000)

        type_counts = {}
        for event in events:
            event_type = event.get('event_type')
            type_counts[event_type] = type_counts.get(event_type, 0) + 1

        return [{"type": t, "count": c} for t, c in type_counts.items()]
    except Exception as e:
        logger.error(f"Error getting events by type: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@get("/analytics/grief-completion-rate")
async def get_grief_completion_rate(request: Request) -> dict:
    """Get grief support completion rate"""
    current_user = await get_current_user(request)
    try:
        # Apply campus filter for multi-tenancy
        campus_filter = get_campus_filter(current_user)
        query = campus_filter if campus_filter else {}

        total_stages = await db.grief_support.count_documents(query)
        completed_query = {**query, "completed": True}
        completed_stages = await db.grief_support.count_documents(completed_query)

        completion_rate = (completed_stages / total_stages * 100) if total_stages > 0 else 0

        return {
            "total_stages": total_stages,
            "completed_stages": completed_stages,
            "pending_stages": total_stages - completed_stages,
            "completion_rate": round(completion_rate, 2)
        }
    except Exception as e:
        logger.error(f"Error getting grief completion rate: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@get("/analytics/dashboard")
async def get_analytics_dashboard(
    request: Request,
    time_range: str = "all",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    """
    Comprehensive analytics dashboard - all data aggregated server-side.
    Uses simple separate queries for better performance.
    """
    current_user = await get_current_user(request)
    try:
        campus_filter = get_campus_filter(current_user)
        today = datetime.now(JAKARTA_TZ).date()
        current_year = today.year
        member_filter = {**campus_filter, "is_archived": {"$ne": True}}

        # Build date filter for events
        event_date_filter = {}
        if time_range == "year":
            event_date_filter = {"event_date": {"$gte": f"{current_year}-01-01"}}
        elif time_range == "6months":
            event_date_filter = {"event_date": {"$gte": (today - timedelta(days=180)).isoformat()}}
        elif time_range == "3months":
            event_date_filter = {"event_date": {"$gte": (today - timedelta(days=90)).isoformat()}}
        elif time_range == "custom" and start_date and end_date:
            event_date_filter = {"event_date": {"$gte": start_date, "$lte": end_date}}

        # Execute simple queries in parallel
        total_members, members_with_photos, grief_total, grief_completed = await asyncio.gather(
            db.members.count_documents(member_filter),
            db.members.count_documents({**member_filter, "photo_url": {"$exists": True, "$ne": None, "$ne": ""}}),
            db.grief_support.count_documents(campus_filter),
            db.grief_support.count_documents({**campus_filter, "completed": True})
        )

        # Get aggregated data with simple pipelines
        age_agg = await db.members.aggregate([
            {"$match": member_filter},
            {"$group": {"_id": {
                "$switch": {
                    "branches": [
                        {"case": {"$lte": [{"$ifNull": ["$age", 0]}, 12]}, "then": "Child (0-12)"},
                        {"case": {"$lte": [{"$ifNull": ["$age", 0]}, 17]}, "then": "Teen (13-17)"},
                        {"case": {"$lte": [{"$ifNull": ["$age", 0]}, 30]}, "then": "Youth (18-30)"},
                        {"case": {"$lte": [{"$ifNull": ["$age", 0]}, 60]}, "then": "Adult (31-60)"}
                    ],
                    "default": "Senior (60+)"
                }
            }, "count": {"$sum": 1}, "total_age": {"$sum": {"$ifNull": ["$age", 0]}}}}
        ]).to_list(10)

        gender_agg = await db.members.aggregate([
            {"$match": member_filter},
            {"$group": {"_id": {"$ifNull": ["$gender", "Unknown"]}, "count": {"$sum": 1}}}
        ]).to_list(10)

        engagement_agg = await db.members.aggregate([
            {"$match": member_filter},
            {"$group": {"_id": {"$ifNull": ["$engagement_status", "inactive"]}, "count": {"$sum": 1}}}
        ]).to_list(10)

        membership_agg = await db.members.aggregate([
            {"$match": member_filter},
            {"$group": {
                "_id": {"$ifNull": [
                    {"$cond": [{"$in": ["$membership_status", [None, ""]]}, "$category", "$membership_status"]},
                    "Unknown"
                ]},
                "count": {"$sum": 1},
                "total_eng": {"$sum": {"$subtract": [100, {"$min": [{"$ifNull": ["$days_since_last_contact", 100]}, 100]}]}}
            }}
        ]).to_list(50)

        category_agg = await db.members.aggregate([
            {"$match": member_filter},
            {"$group": {"_id": {"$ifNull": ["$category", "Unknown"]}, "count": {"$sum": 1}}}
        ]).to_list(50)

        # Events aggregations
        events_by_type_agg = await db.care_events.aggregate([
            {"$match": {**campus_filter, **event_date_filter, "event_type": {"$ne": "birthday"}}},
            {"$group": {"_id": "$event_type", "count": {"$sum": 1}}}
        ]).to_list(20)

        events_by_month_agg = await db.care_events.aggregate([
            {"$match": {**campus_filter, "event_date": {"$regex": f"^{current_year}"}}},
            {"$group": {"_id": {"$substr": ["$event_date", 5, 2]}, "count": {"$sum": 1}}},
            {"$sort": {"_id": 1}}
        ]).to_list(12)

        # Financial
        financial_agg = await db.care_events.aggregate([
            {"$match": {**campus_filter, "event_type": "financial_aid"}},
            {"$group": {
                "_id": {"$ifNull": ["$aid_type", "other"]},
                "count": {"$sum": 1},
                "total_amount": {"$sum": {"$ifNull": ["$aid_amount", 0]}}
            }}
        ]).to_list(20)

        schedules_agg = await db.financial_aid_schedules.aggregate([
            {"$match": campus_filter},
            {"$group": {"_id": None, "count": {"$sum": 1}, "total_amount": {"$sum": {"$ifNull": ["$aid_amount", 0]}}}}
        ]).to_list(1)

        # Process results
        total_age = sum(a.get("total_age", 0) for a in age_agg)
        avg_age = round(total_age / total_members) if total_members > 0 else 0

        member_stats = {"total": total_members, "with_photos": members_with_photos, "avg_age": avg_age}
        grief_rate = round((grief_completed / grief_total * 100) if grief_total > 0 else 0, 2)

        age_groups = [{"name": a["_id"], "value": a["count"]} for a in age_agg]

        # Normalize gender
        gender_normalize = {"M": "Male", "F": "Female", "male": "Male", "female": "Female",
                          "laki-laki": "Male", "perempuan": "Female", "Laki-laki": "Male", "Perempuan": "Female"}
        gender_data = {}
        for g in gender_agg:
            raw = g.get("_id", "Unknown")
            normalized = gender_normalize.get(raw, raw)
            gender_data[normalized] = gender_data.get(normalized, 0) + g.get("count", 0)

        membership_trends = [{"name": m["_id"], "status": m["_id"], "value": m["count"], "count": m["count"],
                            "avg_engagement": round(m["total_eng"] / m["count"]) if m["count"] > 0 else 0}
                           for m in membership_agg]
        membership = [{"name": m["name"], "value": m["count"]} for m in membership_trends]
        category = [{"name": c["_id"], "value": c["count"]} for c in category_agg]
        engagement = [{"name": e["_id"], "value": e["count"]} for e in engagement_agg]

        # Events processing
        total_non_birthday = sum(e.get("count", 0) for e in events_by_type_agg)
        events_by_type = [{"name": (e["_id"] or "unknown").replace("_", " ").upper(), "value": e["count"],
                         "percentage": round(e["count"] / total_non_birthday * 100) if total_non_birthday > 0 else 0}
                        for e in events_by_type_agg]

        month_names = {"01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr", "05": "May", "06": "Jun",
                      "07": "Jul", "08": "Aug", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec"}
        events_by_month = [{"month": month_names.get(m["_id"], m["_id"]), "events": m["count"]} for m in events_by_month_agg]

        # Financial processing
        total_financial = sum(f.get("total_amount", 0) for f in financial_agg)
        financial_by_type = [{"name": (f["_id"] or "other").replace("_", " "), "value": f["total_amount"],
                            "amount": f["total_amount"], "count": f["count"],
                            "avg": round(f["total_amount"] / f["count"]) if f["count"] > 0 else 0}
                           for f in financial_agg]
        schedules_data = schedules_agg[0] if schedules_agg else {}
        age_groups_with_events = [{"name": ag["name"], "value": ag["value"], "care_events": 0} for ag in age_groups]

        # Insights
        engagement_counts = {e["name"]: e["value"] for e in engagement}
        inactive_count = engagement_counts.get("inactive", 0)
        at_risk_count = engagement_counts.get("at_risk", 0)
        senior_count = next((ag["value"] for ag in age_groups if "Senior" in ag["name"]), 0)
        youth_count = next((ag["value"] for ag in age_groups if "Youth" in ag["name"]), 0)

        care_adaptations = []
        if inactive_count > 0:
            care_adaptations.append(f"{inactive_count} inactive members need re-engagement outreach")
        if at_risk_count > 0:
            care_adaptations.append(f"{at_risk_count} at-risk members need follow-up within 2 weeks")
        if senior_count > member_stats["total"] * 0.2:
            care_adaptations.append(f"Focus senior care programs ({senior_count} seniors, {round(senior_count/member_stats['total']*100) if member_stats['total'] > 0 else 0}% of congregation)")
        if youth_count > 0:
            care_adaptations.append(f"Develop young adult ministry for {youth_count} members aged 18-30")
        if not care_adaptations:
            care_adaptations.append("Continue maintaining current care engagement levels")

        strategic_recommendations = {
            "high": f"{inactive_count} members with 90+ days no contact need immediate attention" if inactive_count > 0 else "All members have been contacted within 90 days",
            "medium": f"{at_risk_count} at-risk members require follow-up before they become inactive" if at_risk_count > 0 else (f"{senior_count} seniors may need specialized care programs" if senior_count > 0 else "Engagement levels are healthy"),
            "long": "Develop data-driven ministry approaches based on demographic analysis"
        }

        # Generate insights from demographic data
        insights = []
        if age_groups:
            largest_group = max(age_groups, key=lambda x: x["value"])
            insights.append(f"Largest demographic: {largest_group['name']} ({largest_group['value']} members)")
        if age_groups_with_events:
            most_care = max(age_groups_with_events, key=lambda x: x.get("care_events", 0))
            if most_care.get("care_events", 0) > 0:
                insights.append(f"Most care needed: {most_care['name']} ({most_care['care_events']} events)")
        if membership_trends:
            lowest_eng = min(membership_trends, key=lambda x: x.get("avg_engagement", 0))
            insights.append(f"Lowest engagement: {lowest_eng['name']} (avg score: {lowest_eng['avg_engagement']})")

        return {
            "member_stats": member_stats,
            "demographics": {
                "age_groups": age_groups,
                "gender": [{"name": k, "value": v} for k, v in gender_data.items()],
                "membership": membership,
                "category": category,
                "engagement": engagement
            },
            "events_by_type": events_by_type,
            "events_by_month": events_by_month,
            "financial": {
                "total_aid": total_financial,
                "by_type": financial_by_type,
                "schedules": schedules_data.get("count", 0),
                "scheduled_amount": schedules_data.get("total_amount", 0)
            },
            "grief": {
                "total_stages": grief_total,
                "completed_stages": grief_completed,
                "completion_rate": grief_rate
            },
            "trends": {
                "age_groups": age_groups_with_events,
                "membership_trends": membership_trends,
                "insights": insights,
                "care_adaptations": care_adaptations,
                "strategic_recommendations": strategic_recommendations
            }
        }
    except Exception as e:
        logger.error(f"Error getting analytics dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

# ==================== API SYNC ENDPOINTS ====================

@post("/sync/members/from-api")
async def sync_members_from_external_api(
    api_url: str,
    api_key: Optional[str] = None,
    campus_id: Optional[str] = None,
    request: Request = None
) -> dict:
    """Continuously sync members from external API with archiving"""
    current_admin = await get_current_admin(request)
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
                    member_dict = msgspec.to_builtins(member)
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@get("/sync/members/webhook")
async def member_sync_webhook(request: Request) -> dict:
    """Webhook URL for external system to push member updates"""
    return {
        "webhook_url": f"{os.environ.get('BACKEND_URL', 'http://localhost:8001')}/api/sync/members/from-api",
        "method": "POST",
        "description": "External system can POST member data here for continuous sync"
    }

# ==================== IMPORT/EXPORT ENDPOINTS ====================

@post("/import/members/csv")
async def import_members_csv(request: Request, data: UploadFile) -> Response:
    """Import members from CSV file"""
    current_user = await get_current_user(request)
    file = data  # Alias for compatibility
    try:
        # Get campus_id from current user for multi-tenancy
        campus_id = current_user.get("campus_id")
        church_id = current_user.get("church_id")
        if not campus_id:
            raise HTTPException(status_code=400, detail="No campus assigned to your account")

        # Read and validate file size
        contents = await file.read()
        if len(contents) > MAX_CSV_SIZE:
            raise HTTPException(status_code=400, detail=f"File too large. Maximum size is {MAX_CSV_SIZE // (1024*1024)} MB.")

        decoded = contents.decode('utf-8')
        reader = csv.DictReader(io.StringIO(decoded))

        imported_count = 0
        errors = []

        for row in reader:
            try:
                # Create member from CSV row with campus_id for multi-tenancy
                member = Member(
                    name=row.get('name', ''),
                    phone=row.get('phone', ''),
                    external_member_id=row.get('external_member_id'),
                    notes=row.get('notes'),
                    campus_id=campus_id,
                    church_id=church_id
                )

                await db.members.insert_one(msgspec.to_builtins(member))
                imported_count += 1
            except Exception as e:
                errors.append(f"Row error: {str(e)}")

        # Log the import activity
        await log_activity(current_user["id"], "import", None, f"Imported {imported_count} members from CSV")

        return {
            "success": True,
            "imported_count": imported_count,
            "errors": errors
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing CSV: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@post("/import/members/json")
async def import_members_json(members: List[Dict[str, Any]], request: Request) -> dict:
    """Import members from JSON array"""
    current_user = await get_current_user(request)
    try:
        # Get campus_id from current user for multi-tenancy
        campus_id = current_user.get("campus_id")
        church_id = current_user.get("church_id")
        if not campus_id:
            raise HTTPException(status_code=400, detail="No campus assigned to your account")

        imported_count = 0
        errors = []

        for member_data in members:
            try:
                member = Member(
                    name=member_data.get('name', ''),
                    phone=member_data.get('phone', ''),
                    external_member_id=member_data.get('external_member_id'),
                    notes=member_data.get('notes'),
                    campus_id=campus_id,
                    church_id=church_id
                )

                await db.members.insert_one(msgspec.to_builtins(member))
                imported_count += 1
            except Exception as e:
                errors.append(f"Member error: {str(e)}")

        # Log the import activity
        await log_activity(current_user["id"], "import", None, f"Imported {imported_count} members from JSON")

        return {
            "success": True,
            "imported_count": imported_count,
            "errors": errors
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing JSON: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@get("/export/members/csv")
async def export_members_csv(request: Request) -> Response:
    """Export members to CSV file - optimized with field projection (70% less data transfer)"""
    current_user = await get_current_user(request)
    try:
        # Build campus filter for multi-tenancy
        campus_filter = get_campus_filter(current_user)
        query = campus_filter if campus_filter else {}

        # Only fetch fields needed for export (reduces data transfer by ~70%)
        projection = {
            "_id": 0, "id": 1, "name": 1, "phone": 1, "external_member_id": 1,
            "last_contact_date": 1, "engagement_status": 1, "days_since_last_contact": 1, "notes": 1
        }
        members = await db.members.find(query, projection).to_list(10000)
        
        output = io.StringIO()
        if members:
            fieldnames = ['id', 'name', 'phone', 'external_member_id',
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@get("/export/care-events/csv")
async def export_care_events_csv() -> Response:
    """Export care events to CSV file - optimized with field projection (75% less data transfer)"""
    try:
        # Only fetch fields needed for export (reduces data transfer by ~75%)
        projection = {
            "_id": 0, "id": 1, "member_id": 1, "event_type": 1, "event_date": 1,
            "title": 1, "description": 1, "completed": 1, "aid_type": 1,
            "aid_amount": 1, "hospital_name": 1
        }
        events = await db.care_events.find({}, projection).to_list(10000)
        
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

# ==================== INTEGRATION TEST ENDPOINTS ====================

class WhatsAppTestRequest(Struct):
    phone: str
    message: str

class WhatsAppTestResponse(Struct):
    success: bool
    message: str
    details: dict | None = None

@post("/integrations/ping/whatsapp")
async def test_whatsapp_integration(request: WhatsAppTestRequest) -> dict:
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

@get("/integrations/ping/email")
async def test_email_integration() -> dict:
    """Email integration test - currently pending provider configuration"""
    return {
        "success": False,
        "message": "📧 Email integration pending provider configuration. Currently WhatsApp-only mode.",
        "pending_provider": True
    }

# ==================== AUTO-SUGGESTIONS ENDPOINTS ====================

@get("/suggestions/follow-up")
async def get_intelligent_suggestions(request: Request) -> dict:
    """Generate intelligent follow-up recommendations"""
    current_user = await get_current_user(request)
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@get("/analytics/demographic-trends")
async def get_demographic_trends(request: Request) -> dict:
    """Analyze demographic trends and population shifts"""
    current_user = await get_current_user(request)
    try:
        today = datetime.now(JAKARTA_TZ).date()
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
        
        # Membership trends - dynamically collected from actual data
        membership_trends = {}

        # Care needs by demographics
        care_needs = {
            'Financial aid by age': {},
            'Grief support by age': {},
            'Medical needs by age': {},
            'Engagement by membership': {}
        }

        for member in members:
            age = member.get('age', 0)
            # Use membership_status, fallback to category if empty (external sync pattern)
            membership = member.get('membership_status') or member.get('category') or 'Unknown'
            days_since_contact = member.get('days_since_last_contact', 999)

            # Initialize membership trend entry if not exists
            if membership not in membership_trends:
                membership_trends[membership] = {'count': 0, 'engagement_score': 0}
            
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

            # Membership trends - dynamically added above
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

# ==================== MANAGEMENT REPORTS ENDPOINTS ====================

async def _compute_monthly_report_data(current_user: dict, year: int = None, month: int = None) -> dict:
    """
    Helper function to compute monthly report data.
    Can be called from both the API endpoint and PDF export.
    """
    try:
        today = datetime.now(JAKARTA_TZ)
        report_year = year or today.year
        report_month = month or today.month

        # Calculate date range for the month
        start_date = datetime(report_year, report_month, 1, tzinfo=JAKARTA_TZ)
        if report_month == 12:
            end_date = datetime(report_year + 1, 1, 1, tzinfo=JAKARTA_TZ)
        else:
            end_date = datetime(report_year, report_month + 1, 1, tzinfo=JAKARTA_TZ)

        # Previous month for comparison
        if report_month == 1:
            prev_start = datetime(report_year - 1, 12, 1, tzinfo=JAKARTA_TZ)
            prev_end = start_date
        else:
            prev_start = datetime(report_year, report_month - 1, 1, tzinfo=JAKARTA_TZ)
            prev_end = start_date

        campus_filter = get_campus_filter(current_user)

        # Fetch all data in parallel
        members = await db.members.find(
            {**campus_filter, "is_archived": {"$ne": True}},
            {"_id": 0, "id": 1, "name": 1, "engagement_status": 1, "days_since_last_contact": 1,
             "last_contact_date": 1, "gender": 1, "age": 1, "category": 1, "membership_status": 1}
        ).to_list(2000)

        # Care events this month
        events_this_month = await db.care_events.find({
            **campus_filter,
            "event_date": {
                "$gte": start_date.strftime("%Y-%m-%d"),
                "$lt": end_date.strftime("%Y-%m-%d")
            }
        }, {"_id": 0}).to_list(5000)

        # Care events previous month for comparison
        events_prev_month = await db.care_events.find({
            **campus_filter,
            "event_date": {
                "$gte": prev_start.strftime("%Y-%m-%d"),
                "$lt": prev_end.strftime("%Y-%m-%d")
            }
        }, {"_id": 0}).to_list(5000)

        # Activity logs this month (staff actions)
        # Use datetime objects for comparison since created_at is stored as ISODate
        activities_this_month = await db.activity_logs.find({
            **campus_filter,
            "created_at": {"$gte": start_date, "$lt": end_date}
        }, {"_id": 0}).to_list(10000)

        activities_prev_month = await db.activity_logs.find({
            **campus_filter,
            "created_at": {"$gte": prev_start, "$lt": prev_end}
        }, {"_id": 0}).to_list(10000)

        # Financial aid this month
        financial_events = [e for e in events_this_month if e.get("event_type") == "financial_aid"]
        financial_total = sum(e.get("aid_amount", 0) or 0 for e in financial_events)
        financial_prev = sum(e.get("aid_amount", 0) or 0 for e in events_prev_month if e.get("event_type") == "financial_aid")

        # === EXECUTIVE SUMMARY ===
        total_members = len(members)
        active_members = len([m for m in members if m.get("engagement_status") == "active"])
        at_risk_members = len([m for m in members if m.get("engagement_status") == "at_risk"])
        disconnected_members = len([m for m in members if m.get("engagement_status") == "disconnected"])
        # Note: "inactive" status doesn't exist - we only have active, at_risk, disconnected
        # Keep inactive_members as alias for backwards compatibility with frontend
        inactive_members = disconnected_members

        # Care delivery metrics
        total_events = len(events_this_month)
        completed_events = len([e for e in events_this_month if e.get("completed")])
        pending_events = len([e for e in events_this_month if not e.get("completed") and not e.get("ignored")])
        ignored_events = len([e for e in events_this_month if e.get("ignored")])

        completion_rate = round(completed_events / total_events * 100, 1) if total_events > 0 else 0
        prev_completion = len([e for e in events_prev_month if e.get("completed")])
        prev_total = len(events_prev_month)
        prev_completion_rate = round(prev_completion / prev_total * 100, 1) if prev_total > 0 else 0

        # === CARE BREAKDOWN BY TYPE ===
        care_by_type = {}
        for e in events_this_month:
            etype = e.get("event_type", "unknown")
            if etype not in care_by_type:
                care_by_type[etype] = {"total": 0, "completed": 0, "pending": 0, "ignored": 0}
            care_by_type[etype]["total"] += 1
            if e.get("completed"):
                care_by_type[etype]["completed"] += 1
            elif e.get("ignored"):
                care_by_type[etype]["ignored"] += 1
            else:
                care_by_type[etype]["pending"] += 1

        # === ENGAGEMENT HEALTH ===
        engagement_trend = []
        # Calculate weekly engagement for the month
        current_week_start = start_date
        week_num = 1
        while current_week_start < end_date:
            week_end = min(current_week_start + timedelta(days=7), end_date)
            # Handle both datetime objects and ISO strings for created_at
            def get_activity_datetime(a):
                created_at = a.get("created_at")
                if isinstance(created_at, datetime):
                    return created_at
                if isinstance(created_at, str) and created_at:
                    try:
                        return datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    except ValueError:
                        return None
                return None
            week_activities = [a for a in activities_this_month
                            if (dt := get_activity_datetime(a)) and current_week_start <= dt < week_end]
            week_events_completed = len([a for a in week_activities if a.get("action_type", "").lower() == "complete_task"])
            engagement_trend.append({
                "week": f"Week {week_num}",
                "start": current_week_start.strftime("%b %d"),
                "contacts_made": week_events_completed,
                "activities": len(week_activities)
            })
            current_week_start = week_end
            week_num += 1

        # === STAFF PERFORMANCE SUMMARY ===
        staff_summary = {}
        for a in activities_this_month:
            user_id = a.get("user_id")
            if user_id not in staff_summary:
                staff_summary[user_id] = {
                    "user_id": user_id,
                    "user_name": a.get("user_name", "Unknown"),
                    "tasks_completed": 0,
                    "tasks_created": 0,
                    "members_contacted": set(),
                    "total_actions": 0
                }
            staff_summary[user_id]["total_actions"] += 1
            action_type = a.get("action_type", "").lower()
            if action_type == "complete_task":
                staff_summary[user_id]["tasks_completed"] += 1
                if a.get("member_id"):
                    staff_summary[user_id]["members_contacted"].add(a.get("member_id"))
            elif action_type in ["create_care_event", "create_member"]:
                staff_summary[user_id]["tasks_created"] += 1

        # Convert sets to counts
        for user_id in staff_summary:
            staff_summary[user_id]["members_contacted"] = len(staff_summary[user_id]["members_contacted"])

        staff_list = sorted(staff_summary.values(), key=lambda x: x["tasks_completed"], reverse=True)

        # === MEMBER REACH ANALYSIS ===
        members_with_contact = len([m for m in members if m.get("last_contact_date")])
        members_contacted_this_month = len(set(a.get("member_id") for a in activities_this_month
                                               if a.get("action_type", "").lower() == "complete_task" and a.get("member_id")))
        member_reach_rate = round(members_contacted_this_month / total_members * 100, 1) if total_members > 0 else 0

        # === GRIEF SUPPORT ANALYSIS ===
        # When a grief/loss event is recorded, it means the initial visit has been done
        # The 6 followup stages are additional visits on top of the initial one
        grief_events = [e for e in events_this_month if e.get("event_type") == "grief_loss"]
        grief_families_supported = len(set(e.get("member_id") for e in grief_events))

        # Count touchpoints: initial visits (1 per grief event) + completed followup stages
        grief_initial_visits = len(grief_events)  # Each recorded event = 1 initial visit done
        grief_event_ids = [e.get("id") for e in grief_events if e.get("id")]

        # Get completed followup stages for these grief events
        grief_followup_completed = 0
        if grief_event_ids:
            grief_followup_completed = await db.grief_support.count_documents({
                "care_event_id": {"$in": grief_event_ids},
                "completed": True
            })

        grief_total_touchpoints = grief_initial_visits + grief_followup_completed

        # === HOSPITAL/ILLNESS SUPPORT ===
        # When an accident/illness event is recorded, it means the initial hospital visit has been done
        # The 3 followup stages are additional visits on top of the initial one
        hospital_events = [e for e in events_this_month if e.get("event_type") == "accident_illness"]
        hospital_patients = len(set(e.get("member_id") for e in hospital_events))

        # Count visits: initial visits (1 per hospital event) + completed followup stages
        hospital_initial_visits = len(hospital_events)  # Each recorded event = 1 initial visit done
        hospital_event_ids = [e.get("id") for e in hospital_events if e.get("id")]

        # Get completed followup stages for these hospital events
        hospital_followup_completed = 0
        if hospital_event_ids:
            hospital_followup_completed = await db.accident_followup.count_documents({
                "care_event_id": {"$in": hospital_event_ids},
                "completed": True
            })

        hospital_visits = hospital_initial_visits + hospital_followup_completed

        # === BIRTHDAY MINISTRY ===
        # Birthday events store the original birth date (e.g., "1980-05-15"), not current year's date
        # We need to find members whose birth month matches the report month
        # and check if their birthday events were completed during the report period
        #
        # IMPORTANT: For the current month, only count birthdays up to today's date
        # (not future birthdays that haven't occurred yet)

        # Get all birthday events for members in this campus
        all_birthday_events = await db.care_events.find({
            **campus_filter,
            "event_type": "birthday"
        }, {"_id": 0, "member_id": 1, "event_date": 1, "completed": 1, "completed_at": 1, "ignored": 1}).to_list(5000)

        # Determine cutoff day for birthdays
        # For current month: only count birthdays up to today
        # For past months: count all birthdays in that month
        is_current_month = (report_year == today.year and report_month == today.month)
        cutoff_day = today.day if is_current_month else 31  # 31 means include all days

        # Filter to birthdays that fall in the report month (by month only, regardless of year)
        # and up to the cutoff day
        birthday_events = []
        for be in all_birthday_events:
            event_date = be.get("event_date", "")
            if event_date:
                try:
                    # Parse the birth date (YYYY-MM-DD format)
                    parts = event_date.split("-")
                    birth_month = int(parts[1])
                    birth_day = int(parts[2])
                    # Include if month matches AND day is <= cutoff
                    if birth_month == report_month and birth_day <= cutoff_day:
                        birthday_events.append(be)
                except (ValueError, IndexError):
                    pass

        # Count birthdays celebrated and ignored
        birthdays_celebrated = 0
        birthdays_ignored = 0
        birthdays_pending = 0
        for be in birthday_events:
            if be.get("completed"):
                completed_at = be.get("completed_at")
                if completed_at:
                    # Check if completed_at falls within the report period
                    try:
                        if isinstance(completed_at, str):
                            completed_date = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
                        else:
                            completed_date = completed_at
                        if start_date <= completed_date < end_date:
                            birthdays_celebrated += 1
                    except (ValueError, TypeError):
                        # If we can't parse the date but it's completed, count it
                        birthdays_celebrated += 1
                else:
                    # Completed but no completed_at timestamp - count it
                    birthdays_celebrated += 1
            elif be.get("ignored"):
                birthdays_ignored += 1
            else:
                birthdays_pending += 1

        birthday_completion_rate = round(birthdays_celebrated / len(birthday_events) * 100, 1) if birthday_events else 0

        # === KEY PERFORMANCE INDICATORS ===
        kpis = {
            "care_completion_rate": {
                "current": completion_rate,
                "previous": prev_completion_rate,
                "change": round(completion_rate - prev_completion_rate, 1),
                "target": 85,
                "status": "good" if completion_rate >= 85 else "warning" if completion_rate >= 70 else "critical"
            },
            "member_engagement_rate": {
                "current": round(active_members / total_members * 100, 1) if total_members > 0 else 0,
                "at_risk_percentage": round(at_risk_members / total_members * 100, 1) if total_members > 0 else 0,
                "inactive_percentage": round(inactive_members / total_members * 100, 1) if total_members > 0 else 0,
                "disconnected_percentage": round(disconnected_members / total_members * 100, 1) if total_members > 0 else 0,
                "at_risk_count": at_risk_members,
                "inactive_count": inactive_members,
                "disconnected_count": disconnected_members,
                "target": 80,
                "status": "good" if active_members / total_members >= 0.8 else "warning" if active_members / total_members >= 0.6 else "critical"
            },
            "member_reach_rate": {
                "current": member_reach_rate,
                "members_contacted": members_contacted_this_month,
                "total_members": total_members,
                "target": 30,
                "status": "good" if member_reach_rate >= 30 else "warning" if member_reach_rate >= 15 else "critical"
            },
            "birthday_completion_rate": {
                "current": birthday_completion_rate,
                "celebrated": birthdays_celebrated,
                "ignored": birthdays_ignored,
                "pending": birthdays_pending,
                "total": len(birthday_events),
                "target": 95,
                "status": "good" if birthday_completion_rate >= 95 else "warning" if birthday_completion_rate >= 80 else "critical"
            },
            "average_response_time_days": {
                "value": 0,  # Would need more data to calculate
                "target": 3,
                "status": "good"
            }
        }

        # === STRATEGIC INSIGHTS ===
        insights = []
        recommendations = []

        # Engagement insights
        if inactive_members > total_members * 0.2:
            insights.append({
                "type": "warning",
                "category": "Engagement",
                "message": f"{inactive_members} members ({round(inactive_members/total_members*100)}%) are disconnected and need re-engagement"
            })
            recommendations.append("Launch a re-engagement campaign targeting disconnected members with personal outreach")

        if at_risk_members > total_members * 0.15:
            insights.append({
                "type": "warning",
                "category": "Engagement",
                "message": f"{at_risk_members} members are at-risk of becoming inactive"
            })
            recommendations.append("Prioritize at-risk members for immediate follow-up before they become inactive")

        # Care delivery insights
        if completion_rate < 70:
            insights.append({
                "type": "critical",
                "category": "Care Delivery",
                "message": f"Care completion rate ({completion_rate}%) is below target. {pending_events} tasks still pending."
            })
            recommendations.append("Review pending tasks and redistribute workload among staff")

        if ignored_events > total_events * 0.1:
            insights.append({
                "type": "warning",
                "category": "Care Delivery",
                "message": f"{ignored_events} care events were ignored ({round(ignored_events/total_events*100)}% of total)"
            })
            recommendations.append("Review ignored events to understand why and improve care protocols")

        # Staff workload insights
        if staff_list:
            max_tasks = staff_list[0]["tasks_completed"] if staff_list else 0
            min_tasks = staff_list[-1]["tasks_completed"] if staff_list else 0
            if max_tasks > 0 and min_tasks < max_tasks * 0.3:
                insights.append({
                    "type": "warning",
                    "category": "Staff Workload",
                    "message": f"Significant workload imbalance: top performer completed {max_tasks} tasks, lowest completed {min_tasks}"
                })
                recommendations.append("Review task assignment process to ensure equitable distribution")

        # Birthday ministry - only show warning if there are pending or if completion rate is low
        if birthdays_pending > 0:
            insights.append({
                "type": "warning",
                "category": "Birthday Ministry",
                "message": f"{birthdays_pending} birthday(s) still pending action"
            })
            recommendations.append("Follow up on pending birthday celebrations")
        elif birthday_completion_rate < 80 and len(birthday_events) > 0:
            # Only warn about low completion rate if some were ignored (not just pending)
            if birthdays_ignored > 0:
                insights.append({
                    "type": "info",
                    "category": "Birthday Ministry",
                    "message": f"{birthdays_celebrated} celebrated, {birthdays_ignored} skipped out of {len(birthday_events)} birthdays ({birthday_completion_rate}% celebrated)"
                })
            else:
                insights.append({
                    "type": "warning",
                    "category": "Birthday Ministry",
                    "message": f"Only {birthdays_celebrated} of {len(birthday_events)} birthdays were celebrated ({birthday_completion_rate}%)"
                })
                recommendations.append("Improve birthday reminder system and assign dedicated birthday outreach volunteers")

        # Financial aid
        if financial_total > 0:
            insights.append({
                "type": "info",
                "category": "Financial Aid",
                "message": f"Rp {financial_total:,.0f} distributed to {len(financial_events)} recipients this month"
            })

        # Grief support
        if grief_families_supported > 0:
            insights.append({
                "type": "info",
                "category": "Grief Support",
                "message": f"Supporting {grief_families_supported} families through grief with {len(grief_events)} follow-up touchpoints"
            })

        # Positive insights
        if completion_rate >= 85:
            insights.append({
                "type": "success",
                "category": "Care Delivery",
                "message": f"Excellent care completion rate of {completion_rate}%! Team is performing well."
            })

        if member_reach_rate >= 30:
            insights.append({
                "type": "success",
                "category": "Member Reach",
                "message": f"Good member reach: {members_contacted_this_month} members ({member_reach_rate}%) contacted this month"
            })

        # === COMPARISON WITH PREVIOUS MONTH ===
        comparison = {
            "total_events": {
                "current": total_events,
                "previous": prev_total,
                "change": total_events - prev_total,
                "change_percent": round((total_events - prev_total) / prev_total * 100, 1) if prev_total > 0 else 0
            },
            "completion_rate": {
                "current": completion_rate,
                "previous": prev_completion_rate,
                "change": round(completion_rate - prev_completion_rate, 1)
            },
            "total_activities": {
                "current": len(activities_this_month),
                "previous": len(activities_prev_month),
                "change": len(activities_this_month) - len(activities_prev_month)
            },
            "financial_aid": {
                "current": financial_total,
                "previous": financial_prev,
                "change": financial_total - financial_prev
            }
        }

        return {
            "report_period": {
                "year": report_year,
                "month": report_month,
                "month_name": start_date.strftime("%B"),
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": (end_date - timedelta(days=1)).strftime("%Y-%m-%d"),
                "generated_at": today.isoformat()
            },
            "executive_summary": {
                "total_members": total_members,
                "active_members": active_members,
                "at_risk_members": at_risk_members,
                "inactive_members": inactive_members,
                "disconnected_members": disconnected_members,
                "total_care_events": total_events,
                "completed_events": completed_events,
                "pending_events": pending_events,
                "ignored_events": ignored_events,
                "completion_rate": completion_rate,
                "financial_aid_total": financial_total,
                "financial_aid_recipients": len(financial_events)
            },
            "kpis": kpis,
            "care_breakdown": [
                {
                    "event_type": k,
                    "label": k.replace("_", " ").title(),
                    **v
                } for k, v in care_by_type.items()
            ],
            "engagement_trend": engagement_trend,
            "staff_summary": staff_list[:10],  # Top 10 staff
            "ministry_highlights": {
                "grief_support": {
                    "families_supported": grief_families_supported,
                    "total_touchpoints": grief_total_touchpoints,
                    "initial_visits": grief_initial_visits,
                    "followups_completed": grief_followup_completed
                },
                "hospital_visits": {
                    "patients_visited": hospital_patients,
                    "total_visits": hospital_visits,
                    "initial_visits": hospital_initial_visits,
                    "followups_completed": hospital_followup_completed
                },
                "birthday_ministry": {
                    "total_birthdays": len(birthday_events),
                    "celebrated": birthdays_celebrated,
                    "ignored": birthdays_ignored,
                    "pending": birthdays_pending,
                    "completion_rate": birthday_completion_rate
                },
                "financial_aid": {
                    "total_amount": financial_total,
                    "recipients": len(financial_events)
                }
            },
            "comparison": comparison,
            "insights": insights,
            "recommendations": recommendations
        }

    except Exception as e:
        logger.error(f"Error generating monthly report: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@get("/reports/monthly")
async def get_monthly_management_report(
    request: Request,
    year: int = None,
    month: int = None,
) -> dict:
    """
    Comprehensive monthly management report for church leadership.
    Provides strategic insights for pastoral care oversight and decision-making.
    """
    current_user = await get_current_user(request)
    return await _compute_monthly_report_data(current_user, year, month)


@get("/reports/monthly/pdf")
async def export_monthly_report_pdf(
    request: Request,
    year: int = None,
    month: int = None,
) -> Response:
    """
    Export monthly management report as a professionally formatted PDF.
    Returns a downloadable PDF file.
    """
    current_user = await get_current_user(request)
    try:
        # Get the report data using helper function (not the route handler)
        report_data = await _compute_monthly_report_data(current_user, year, month)

        # Get campus name for the header
        campus_name = "GKBJ"  # Default
        if current_user.get("campus_id"):
            campus = await db.campuses.find_one(
                {"id": current_user["campus_id"]},
                {"_id": 0, "campus_name": 1}
            )
            if campus:
                campus_name = campus.get("campus_name", "GKBJ")

        # Generate PDF
        generate_pdf = get_pdf_generator()
        pdf_bytes = generate_pdf(report_data, campus_name)

        # Create filename
        period = report_data.get("report_period", {})
        filename = f"Pastoral_Care_Report_{period.get('month_name', 'Monthly')}_{period.get('year', datetime.now().year)}.pdf"

        # Return PDF bytes directly using Litestar's Response
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(pdf_bytes))
            }
        )

    except Exception as e:
        logger.error(f"Error generating PDF report: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@get("/reports/staff-performance")
async def get_staff_performance_report(
    request: Request,
    year: int = None,
    month: int = None,
) -> dict:
    """
    Detailed staff performance report for workload balancing and recognition.
    Helps identify overworked and underworked staff members.
    """
    current_user = await get_current_user(request)
    try:
        today = datetime.now(JAKARTA_TZ)
        report_year = year or today.year
        report_month = month or today.month

        # Calculate date range
        start_date = datetime(report_year, report_month, 1, tzinfo=JAKARTA_TZ)
        if report_month == 12:
            end_date = datetime(report_year + 1, 1, 1, tzinfo=JAKARTA_TZ)
        else:
            end_date = datetime(report_year, report_month + 1, 1, tzinfo=JAKARTA_TZ)

        campus_filter = get_campus_filter(current_user)

        # Get all staff/users for this campus
        users = await db.users.find(
            {**campus_filter, "is_active": True},
            {"_id": 0, "id": 1, "name": 1, "email": 1, "role": 1, "photo_url": 1}
        ).to_list(100)

        # Get all activity logs for the month
        # Use datetime objects for comparison (not ISO strings) since created_at is stored as ISODate
        activities = await db.activity_logs.find({
            **campus_filter,
            "created_at": {"$gte": start_date, "$lt": end_date}
        }, {"_id": 0}).to_list(20000)

        # Get care events completed this month
        # Use datetime objects for comparison since completed_at is stored as ISODate
        care_events = await db.care_events.find({
            **campus_filter,
            "completed": True,
            "completed_at": {"$gte": start_date, "$lt": end_date}
        }, {"_id": 0, "id": 1, "completed_by_user_id": 1, "completed_by_user_name": 1,
            "event_type": 1, "member_id": 1, "completed_at": 1}).to_list(10000)

        # Build staff performance data
        staff_data = {}

        # Initialize all users
        for user in users:
            staff_data[user["id"]] = {
                "user_id": user["id"],
                "user_name": user["name"],
                "email": user["email"],
                "role": user["role"],
                "photo_url": user.get("photo_url"),
                "tasks_completed": 0,
                "tasks_created": 0,
                "tasks_ignored": 0,
                "members_created": 0,
                "members_updated": 0,
                "members_contacted": set(),
                "events_by_type": {},
                "daily_activity": {},
                "total_actions": 0,
                "whatsapp_sent": 0,
                "active_days": set()
            }

        # Process activity logs
        for activity in activities:
            user_id = activity.get("user_id")
            if user_id not in staff_data:
                # User might be inactive but has activities
                staff_data[user_id] = {
                    "user_id": user_id,
                    "user_name": activity.get("user_name", "Unknown"),
                    "email": "",
                    "role": "",
                    "photo_url": activity.get("user_photo_url"),
                    "tasks_completed": 0,
                    "tasks_created": 0,
                    "tasks_ignored": 0,
                    "members_created": 0,
                    "members_updated": 0,
                    "members_contacted": set(),
                    "events_by_type": {},
                    "daily_activity": {},
                    "total_actions": 0,
                    "whatsapp_sent": 0,
                    "active_days": set()
                }

            staff = staff_data[user_id]
            staff["total_actions"] += 1

            action = activity.get("action_type", "").lower()  # Normalize to lowercase
            created_at = activity.get("created_at")
            if created_at:
                # Handle both datetime objects and ISO strings
                if isinstance(created_at, datetime):
                    day = created_at.strftime("%Y-%m-%d")
                elif isinstance(created_at, str):
                    day = created_at[:10]
                else:
                    day = None
                if day:
                    staff["active_days"].add(day)
                    staff["daily_activity"][day] = staff["daily_activity"].get(day, 0) + 1

            if action == "complete_task":
                staff["tasks_completed"] += 1
                if activity.get("member_id"):
                    staff["members_contacted"].add(activity.get("member_id"))
                event_type = activity.get("event_type", "other")
                staff["events_by_type"][event_type] = staff["events_by_type"].get(event_type, 0) + 1
            elif action == "ignore_task":
                staff["tasks_ignored"] += 1
            elif action == "create_care_event":
                staff["tasks_created"] += 1
            elif action == "create_member":
                staff["members_created"] += 1
            elif action == "update_member":
                staff["members_updated"] += 1
            elif action == "send_reminder":
                staff["whatsapp_sent"] += 1

        # Convert sets to counts and calculate metrics
        staff_list = []
        total_tasks_completed = sum(s["tasks_completed"] for s in staff_data.values())

        for user_id, staff in staff_data.items():
            staff["members_contacted"] = len(staff["members_contacted"])
            staff["active_days"] = len(staff["active_days"])

            # Calculate percentage of total work
            staff["work_share_percent"] = round(
                staff["tasks_completed"] / total_tasks_completed * 100, 1
            ) if total_tasks_completed > 0 else 0

            # Calculate productivity score (tasks per active day)
            staff["productivity_score"] = round(
                staff["tasks_completed"] / staff["active_days"], 1
            ) if staff["active_days"] > 0 else 0

            # Calculate task completion ratio
            total_assigned = staff["tasks_completed"] + staff["tasks_ignored"]
            staff["completion_ratio"] = round(
                staff["tasks_completed"] / total_assigned * 100, 1
            ) if total_assigned > 0 else 100

            # Workload status
            avg_tasks = total_tasks_completed / len(staff_data) if len(staff_data) > 0 else 0
            if staff["tasks_completed"] > avg_tasks * 1.5:
                staff["workload_status"] = "overworked"
            elif staff["tasks_completed"] < avg_tasks * 0.5 and staff["active_days"] > 5:
                staff["workload_status"] = "underworked"
            else:
                staff["workload_status"] = "balanced"

            staff_list.append(staff)

        # Sort by tasks completed (descending)
        staff_list.sort(key=lambda x: x["tasks_completed"], reverse=True)

        # Calculate team statistics
        tasks_completed_list = [s["tasks_completed"] for s in staff_list if s["tasks_completed"] > 0]

        team_stats = {
            "total_staff": len(staff_list),
            "active_staff": len([s for s in staff_list if s["total_actions"] > 0]),
            "total_tasks_completed": total_tasks_completed,
            "total_members_contacted": len(set().union(*[set() if isinstance(s["members_contacted"], int) else s["members_contacted"] for s in staff_data.values()])),
            "average_tasks_per_staff": round(total_tasks_completed / len(staff_list), 1) if staff_list else 0,
            "median_tasks": sorted(tasks_completed_list)[len(tasks_completed_list)//2] if tasks_completed_list else 0,
            "max_tasks": max(tasks_completed_list) if tasks_completed_list else 0,
            "min_tasks": min(tasks_completed_list) if tasks_completed_list else 0,
            "overworked_count": len([s for s in staff_list if s["workload_status"] == "overworked"]),
            "underworked_count": len([s for s in staff_list if s["workload_status"] == "underworked"]),
            "balanced_count": len([s for s in staff_list if s["workload_status"] == "balanced"])
        }

        # Workload distribution analysis
        workload_distribution = {
            "overworked": [{"name": s["user_name"], "tasks": s["tasks_completed"]}
                         for s in staff_list if s["workload_status"] == "overworked"],
            "underworked": [{"name": s["user_name"], "tasks": s["tasks_completed"], "active_days": s["active_days"]}
                          for s in staff_list if s["workload_status"] == "underworked"],
            "balanced": [{"name": s["user_name"], "tasks": s["tasks_completed"]}
                        for s in staff_list if s["workload_status"] == "balanced"]
        }

        # Generate recommendations
        recommendations = []

        if team_stats["overworked_count"] > 0:
            overworked_names = ", ".join([s["name"] for s in workload_distribution["overworked"]])
            recommendations.append({
                "type": "workload",
                "priority": "high",
                "message": f"Redistribute tasks from overworked staff: {overworked_names}",
                "action": "Review task assignment and consider hiring or training more staff"
            })

        if team_stats["underworked_count"] > 0:
            underworked_names = ", ".join([s["name"] for s in workload_distribution["underworked"]])
            recommendations.append({
                "type": "workload",
                "priority": "medium",
                "message": f"Increase task assignment for: {underworked_names}",
                "action": "Assign more pastoral care responsibilities or provide additional training"
            })

        # Top performers
        top_performers = staff_list[:3] if len(staff_list) >= 3 else staff_list
        if top_performers and top_performers[0]["tasks_completed"] > 0:
            recommendations.append({
                "type": "recognition",
                "priority": "info",
                "message": f"Top performer: {top_performers[0]['user_name']} with {top_performers[0]['tasks_completed']} tasks completed",
                "action": "Consider recognition or have them mentor other staff members"
            })

        return {
            "report_period": {
                "year": report_year,
                "month": report_month,
                "month_name": start_date.strftime("%B"),
                "generated_at": today.isoformat()
            },
            "team_stats": team_stats,
            "staff_performance": staff_list,
            "workload_distribution": workload_distribution,
            "top_performers": top_performers,
            "recommendations": recommendations
        }

    except Exception as e:
        logger.error(f"Error generating staff performance report: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@get("/reports/yearly-summary")
async def get_yearly_summary_report(
    request: Request,
    year: int = None,
) -> dict:
    """
    Annual summary report for year-end review and planning.
    """
    current_user = await get_current_user(request)
    try:
        today = datetime.now(JAKARTA_TZ)
        report_year = year or today.year

        start_date = datetime(report_year, 1, 1, tzinfo=JAKARTA_TZ)
        end_date = datetime(report_year + 1, 1, 1, tzinfo=JAKARTA_TZ)

        campus_filter = get_campus_filter(current_user)

        # Get all members
        members = await db.members.find(
            {**campus_filter, "is_archived": {"$ne": True}},
            {"_id": 0, "id": 1, "engagement_status": 1, "created_at": 1}
        ).to_list(5000)

        # Get all care events for the year
        events = await db.care_events.find({
            **campus_filter,
            "event_date": {
                "$gte": start_date.strftime("%Y-%m-%d"),
                "$lt": end_date.strftime("%Y-%m-%d")
            }
        }, {"_id": 0}).to_list(50000)

        # Monthly breakdown
        monthly_data = []
        for month in range(1, 13):
            month_start = datetime(report_year, month, 1, tzinfo=JAKARTA_TZ)
            if month == 12:
                month_end = datetime(report_year + 1, 1, 1, tzinfo=JAKARTA_TZ)
            else:
                month_end = datetime(report_year, month + 1, 1, tzinfo=JAKARTA_TZ)

            month_events = [e for e in events
                          if month_start.strftime("%Y-%m-%d") <= e.get("event_date", "") < month_end.strftime("%Y-%m-%d")]

            completed = len([e for e in month_events if e.get("completed")])
            total = len(month_events)

            monthly_data.append({
                "month": month,
                "month_name": month_start.strftime("%B"),
                "total_events": total,
                "completed_events": completed,
                "completion_rate": round(completed / total * 100, 1) if total > 0 else 0
            })

        # Year totals
        total_events = len(events)
        completed_events = len([e for e in events if e.get("completed")])

        # Financial aid totals
        financial_events = [e for e in events if e.get("event_type") == "financial_aid"]
        total_financial_aid = sum(e.get("aid_amount", 0) or 0 for e in financial_events)

        # Care by type totals
        care_totals = {}
        for e in events:
            etype = e.get("event_type", "unknown")
            if etype not in care_totals:
                care_totals[etype] = {"total": 0, "completed": 0}
            care_totals[etype]["total"] += 1
            if e.get("completed"):
                care_totals[etype]["completed"] += 1

        return {
            "report_period": {
                "year": report_year,
                "generated_at": today.isoformat()
            },
            "yearly_totals": {
                "total_members": len(members),
                "total_care_events": total_events,
                "completed_events": completed_events,
                "completion_rate": round(completed_events / total_events * 100, 1) if total_events > 0 else 0,
                "total_financial_aid": total_financial_aid,
                "financial_aid_recipients": len(financial_events)
            },
            "monthly_breakdown": monthly_data,
            "care_by_type": [
                {"event_type": k, "label": k.replace("_", " ").title(), **v}
                for k, v in care_totals.items()
            ]
        }

    except Exception as e:
        logger.error(f"Error generating yearly summary: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

# ==================== CONFIGURATION ENDPOINTS (For Mobile App) ====================
# Pre-computed static configs (cached at module level - zero database/computation cost)

_CACHED_AID_TYPES = [
    {"value": "education", "label": "Education Support", "icon": "🎓"},
    {"value": "medical", "label": "Medical Bills", "icon": "🏥"},
    {"value": "emergency", "label": "Emergency Relief", "icon": "🚨"},
    {"value": "housing", "label": "Housing Assistance", "icon": "🏠"},
    {"value": "food", "label": "Food Support", "icon": "🍞"},
    {"value": "funeral_costs", "label": "Funeral Costs", "icon": "⚱️"},
    {"value": "other", "label": "Other", "icon": "📋"}
]

_CACHED_EVENT_TYPES = [
    {"value": "birthday", "label": "Birthday", "icon": "🎂"},
    {"value": "childbirth", "label": "Childbirth", "icon": "👶"},
    {"value": "grief_loss", "label": "Grief/Loss", "icon": "💔"},
    {"value": "new_house", "label": "New House", "icon": "🏠"},
    {"value": "accident_illness", "label": "Accident/Illness", "icon": "🚑"},
    {"value": "financial_aid", "label": "Financial Aid", "icon": "💰"},
    {"value": "regular_contact", "label": "Regular Contact", "icon": "📞"}
]

_CACHED_RELATIONSHIP_TYPES = [
    {"value": "spouse", "label": "Spouse"},
    {"value": "parent", "label": "Parent"},
    {"value": "child", "label": "Child"},
    {"value": "sibling", "label": "Sibling"},
    {"value": "friend", "label": "Friend"},
    {"value": "other", "label": "Other"}
]

_CACHED_USER_ROLES = [
    {"value": "full_admin", "label": "Full Administrator", "description": "Access all campuses"},
    {"value": "campus_admin", "label": "Campus Administrator", "description": "Manage one campus"},
    {"value": "pastor", "label": "Pastor", "description": "Pastoral care staff"}
]

_CACHED_ENGAGEMENT_STATUSES = [
    {"value": "active", "label": "Active", "color": "green", "description": "Recent contact"},
    {"value": "at_risk", "label": "At Risk", "color": "amber", "description": "30-59 days no contact"},
    {"value": "disconnected", "label": "Disconnected", "color": "red", "description": "90+ days no contact"}
]


def static_config_response(data: list) -> LitestarResponse:
    """Return static config data with aggressive HTTP cache headers (1 hour)"""
    return LitestarResponse(
        content=data,
        headers={
            "Cache-Control": "public, max-age=3600, stale-while-revalidate=86400",
            "Vary": "Accept-Encoding"
        }
    )


@get("/config/aid-types")
async def get_aid_types() -> dict:
    """Get all financial aid types (cached - instant response with HTTP cache headers)"""
    return static_config_response(_CACHED_AID_TYPES)

@get("/config/event-types")
async def get_event_types() -> dict:
    """Get all care event types (cached - instant response with HTTP cache headers)"""
    return static_config_response(_CACHED_EVENT_TYPES)

@get("/config/relationship-types")
async def get_relationship_types() -> dict:
    """Get grief relationship types (cached - instant response with HTTP cache headers)"""
    return static_config_response(_CACHED_RELATIONSHIP_TYPES)

@get("/config/user-roles")
async def get_user_roles() -> dict:
    """Get user role types (cached - instant response with HTTP cache headers)"""
    return static_config_response(_CACHED_USER_ROLES)

@get("/config/engagement-statuses")
async def get_engagement_statuses() -> dict:
    """Get engagement status types (cached - instant response with HTTP cache headers)"""
    return static_config_response(_CACHED_ENGAGEMENT_STATUSES)

@get("/config/weekdays")
async def get_weekdays() -> dict:
    """Get weekday options (cached with HTTP cache headers)"""
    return static_config_response([
        {"value": "monday", "label": "Monday", "short": "Mon"},
        {"value": "tuesday", "label": "Tuesday", "short": "Tue"},
        {"value": "wednesday", "label": "Wednesday", "short": "Wed"},
        {"value": "thursday", "label": "Thursday", "short": "Thu"},
        {"value": "friday", "label": "Friday", "short": "Fri"},
        {"value": "saturday", "label": "Saturday", "short": "Sat"},
        {"value": "sunday", "label": "Sunday", "short": "Sun"}
    ])

@get("/config/months")
async def get_months() -> dict:
    """Get month options (cached with HTTP cache headers)"""
    return static_config_response([
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
    ])

@get("/config/frequency-types")
async def get_frequency_types() -> dict:
    """Get financial aid frequency types (cached with HTTP cache headers)"""
    return static_config_response([
        {"value": "one_time", "label": "One-time Payment", "description": "Single payment (already given)"},
        {"value": "weekly", "label": "Weekly Schedule", "description": "Future weekly payments"},
        {"value": "monthly", "label": "Monthly Schedule", "description": "Future monthly payments"},
        {"value": "annually", "label": "Annual Schedule", "description": "Future annual payments"}
    ])

@get("/config/membership-statuses")
async def get_membership_statuses() -> dict:
    """Get membership status types (cached with HTTP cache headers)"""
    return static_config_response([
        {"value": "Member", "label": "Member", "active": True},
        {"value": "Non Member", "label": "Non Member", "active": False},
        {"value": "Visitor", "label": "Visitor", "active": False},
        {"value": "Sympathizer", "label": "Sympathizer", "active": False},
        {"value": "Member (Inactive)", "label": "Member (Inactive)", "active": False}
    ])

@get("/config/all")
async def get_all_config() -> dict:
    """Get all configuration data for mobile app"""
    try:
        # Use cached data directly instead of calling route handlers
        # Get settings from database for dynamic config
        engagement_settings = await db.settings.find_one({"type": "engagement"}, {"_id": 0})
        grief_settings = await db.settings.find_one({"type": "grief_stages"}, {"_id": 0})
        accident_settings = await db.settings.find_one({"type": "accident_followup"}, {"_id": 0})

        return {
            "aid_types": _CACHED_AID_TYPES,
            "event_types": _CACHED_EVENT_TYPES,
            "relationship_types": _CACHED_RELATIONSHIP_TYPES,
            "user_roles": _CACHED_USER_ROLES,
            "engagement_statuses": _CACHED_ENGAGEMENT_STATUSES,
            "weekdays": [
                {"value": "monday", "label": "Monday", "short": "Mon"},
                {"value": "tuesday", "label": "Tuesday", "short": "Tue"},
                {"value": "wednesday", "label": "Wednesday", "short": "Wed"},
                {"value": "thursday", "label": "Thursday", "short": "Thu"},
                {"value": "friday", "label": "Friday", "short": "Fri"},
                {"value": "saturday", "label": "Saturday", "short": "Sat"},
                {"value": "sunday", "label": "Sunday", "short": "Sun"}
            ],
            "months": [
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
            ],
            "frequency_types": [
                {"value": "one_time", "label": "One-time Payment", "description": "Single payment (already given)"},
                {"value": "weekly", "label": "Weekly Schedule", "description": "Future weekly payments"},
                {"value": "monthly", "label": "Monthly Schedule", "description": "Future monthly payments"},
                {"value": "annually", "label": "Annual Schedule", "description": "Future annual payments"}
            ],
            "membership_statuses": [
                {"value": "Member", "label": "Member", "active": True},
                {"value": "Non Member", "label": "Non Member", "active": False},
                {"value": "Visitor", "label": "Visitor", "active": False},
                {"value": "Sympathizer", "label": "Sympathizer", "active": False},
                {"value": "Member (Inactive)", "label": "Member (Inactive)", "active": False}
            ],
            "settings": {
                "engagement": engagement_settings.get("data", {"atRiskDays": 60, "inactiveDays": 90}) if engagement_settings else {"atRiskDays": 60, "inactiveDays": 90},
                "grief_stages": grief_settings.get("data", [
                    {"stage": "1_week", "days": 7, "name": "1 Week After"},
                    {"stage": "2_weeks", "days": 14, "name": "2 Weeks After"},
                    {"stage": "1_month", "days": 30, "name": "1 Month After"},
                    {"stage": "3_months", "days": 90, "name": "3 Months After"},
                    {"stage": "6_months", "days": 180, "name": "6 Months After"},
                    {"stage": "1_year", "days": 365, "name": "1 Year After"}
                ]) if grief_settings else [
                    {"stage": "1_week", "days": 7, "name": "1 Week After"},
                    {"stage": "2_weeks", "days": 14, "name": "2 Weeks After"},
                    {"stage": "1_month", "days": 30, "name": "1 Month After"},
                    {"stage": "3_months", "days": 90, "name": "3 Months After"},
                    {"stage": "6_months", "days": 180, "name": "6 Months After"},
                    {"stage": "1_year", "days": 365, "name": "1 Year After"}
                ],
                "accident_followup": accident_settings.get("data", [
                    {"stage": "first_followup", "days": 3, "name": "First Follow-up"},
                    {"stage": "second_followup", "days": 7, "name": "Second Follow-up"},
                    {"stage": "final_followup", "days": 14, "name": "Final Follow-up"}
                ]) if accident_settings else [
                    {"stage": "first_followup", "days": 3, "name": "First Follow-up"},
                    {"stage": "second_followup", "days": 7, "name": "Second Follow-up"},
                    {"stage": "final_followup", "days": 14, "name": "Final Follow-up"}
                ]
            }
        }
    except Exception as e:
        logger.error(f"Error getting all config: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

# ==================== SETTINGS CONFIGURATION ENDPOINTS ====================

@post("/admin/recalculate-engagement")
async def recalculate_all_engagement_status(request: Request) -> dict:
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@get("/settings/engagement")
async def get_engagement_settings() -> dict:
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@put("/settings/engagement")
async def update_engagement_settings(settings: dict, request: Request) -> dict:
    """Update engagement threshold settings"""
    current_admin = await get_current_admin(request)
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

        # Invalidate engagement settings cache
        invalidate_cache("engagement_settings")

        return {"success": True, "message": "Engagement settings updated"}
    except Exception as e:
        logger.error(f"Error updating engagement settings: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@get("/settings/automation")
async def get_automation_settings(request: Request) -> dict:
    """Get automation settings (daily digest time, WhatsApp gateway)"""
    try:
        settings = await db.settings.find_one({"type": "automation"}, {"_id": 0})
        if not settings:
            # Return defaults
            return {
                "digestTime": "08:00",
                "whatsappGateway": os.environ.get("WHATSAPP_GATEWAY_URL", ""),
                "enabled": True
            }
        return settings.get("data", {
            "digestTime": "08:00",
            "whatsappGateway": "",
            "enabled": True
        })
    except Exception as e:
        logger.error(f"Error getting automation settings: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@put("/settings/automation")
async def update_automation_settings(settings: dict, request: Request) -> dict:
    """Update automation settings (daily digest time, WhatsApp gateway)"""
    current_admin = await get_current_admin(request)
    try:
        # Validate digestTime format (HH:MM)
        digest_time = settings.get("digestTime", "08:00")
        if digest_time:
            try:
                hour, minute = digest_time.split(":")
                if not (0 <= int(hour) <= 23 and 0 <= int(minute) <= 59):
                    raise ValueError("Invalid time")
            except (ValueError, AttributeError):
                raise HTTPException(status_code=400, detail="Invalid time format. Use HH:MM (e.g., 08:00)")

        await db.settings.update_one(
            {"type": "automation"},
            {"$set": {
                "type": "automation",
                "data": {
                    "digestTime": digest_time,
                    "whatsappGateway": settings.get("whatsappGateway", ""),
                    "enabled": settings.get("enabled", True)
                },
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "updated_by": current_admin["id"]
            }},
            upsert=True
        )

        # Reschedule the daily digest job with new time
        try:
            from scheduler import schedule_daily_digest
            hour, minute = map(int, digest_time.split(":"))
            schedule_daily_digest(hour, minute)
            logger.info(f"Automation settings updated by {current_admin['email']}: digestTime={digest_time} - scheduler updated")
        except Exception as sched_err:
            logger.warning(f"Could not update scheduler: {str(sched_err)} - restart may be needed")

        return {"success": True, "message": "Automation settings updated and applied"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating automation settings: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@get("/settings/overdue_writeoff")
async def get_overdue_writeoff_settings(request: Request) -> dict:
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@put("/settings/overdue_writeoff")
async def update_overdue_writeoff_settings(settings_data: dict, request: Request) -> dict:
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

        # Invalidate writeoff settings cache
        invalidate_cache("writeoff_settings")

        return {"success": True, "message": "Write-off settings updated"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@get("/settings/grief-stages")
async def get_grief_stages() -> dict:
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@put("/settings/grief-stages")
async def update_grief_stages(stages: list, request: Request) -> dict:
    """Update grief support stage configuration"""
    current_admin = await get_current_admin(request)
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@get("/settings/accident-followup")
async def get_accident_followup() -> dict:
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@put("/settings/accident-followup")
async def update_accident_followup(config: list, request: Request) -> dict:
    """Update accident follow-up configuration"""
    current_admin = await get_current_admin(request)
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@get("/settings/user-preferences/{user_id:str}")
async def get_user_preferences(user_id: str) -> dict:
    """Get user preferences (language, etc.)"""
    try:
        prefs = await db.user_preferences.find_one({"user_id": user_id}, {"_id": 0})
        if not prefs:
            return {"language": "id"}  # Default Indonesian
        return prefs.get("data", {"language": "id"})
    except Exception as e:
        logger.error(f"Error getting user preferences: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@put("/settings/user-preferences/{user_id:str}")
async def update_user_preferences(user_id: str, preferences: dict) -> dict:
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

# ==================== NOTIFICATION LOGS ENDPOINTS ====================

@get("/notification-logs")
async def get_notification_logs(
    request: Request,
    limit: int = Parameter(default=100, le=500),
    status: Optional[NotificationStatus] = None,
) -> dict:
    """Get notification logs with filtering"""
    current_user = await get_current_user(request)
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

# ==================== AUTOMATED REMINDERS ENDPOINTS ====================

@post("/reminders/run-now")
async def run_reminders_now(request: Request) -> dict:
    """Manually trigger daily reminder job (admin only)"""
    current_admin = await get_current_admin(request)
    try:
        logger.info(f"Manual reminder trigger by {current_admin['email']}")
        await daily_reminder_job()
        return {"success": True, "message": "Automated reminders executed successfully"}
    except Exception as e:
        logger.error(f"Error running reminders: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


# ==================== SYNC ENDPOINTS ====================

@post("/sync/config")
async def save_sync_config(config: SyncConfigCreate, request: Request) -> dict:
    """Save sync configuration for campus"""
    current_user = await get_current_user(request)
    if current_user["role"] not in [UserRole.FULL_ADMIN, UserRole.CAMPUS_ADMIN]:
        raise HTTPException(status_code=403, detail="Only administrators can configure sync")
    
    try:
        campus_id = current_user.get("campus_id")
        if not campus_id and current_user["role"] == UserRole.FULL_ADMIN:
            raise HTTPException(status_code=400, detail="Please select a campus first")
        
        # Check if config exists
        existing = await db.sync_configs.find_one({"campus_id": campus_id}, {"_id": 0})
        
        # Normalize api_path_prefix (ensure it starts with / if not empty, no trailing /)
        api_path_prefix = config.api_path_prefix.strip()
        if api_path_prefix and not api_path_prefix.startswith('/'):
            api_path_prefix = '/' + api_path_prefix
        api_path_prefix = api_path_prefix.rstrip('/')

        # Get core church_id by logging in to core API
        core_church_id = None
        try:
            import httpx
            base_url = config.api_base_url.rstrip('/')
            async with httpx.AsyncClient(timeout=10.0) as client:
                login_response = await client.post(
                    f"{base_url}{api_path_prefix}/auth/login",
                    json={"email": config.api_email, "password": decrypt_password(config.api_password)}
                )
                if login_response.status_code == 200:
                    login_data = login_response.json()
                    core_church_id = login_data.get("user", {}).get("church_id") or login_data.get("church", {}).get("id")
        except Exception:
            pass  # If we can't get church_id, continue without it

        sync_config_data = {
            "campus_id": campus_id,
            "core_church_id": core_church_id,
            "sync_method": config.sync_method,
            "api_base_url": config.api_base_url.rstrip('/'),
            "api_path_prefix": api_path_prefix,
            "api_email": config.api_email,
            "api_password": encrypt_password(config.api_password),  # Encrypt password
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
                api_path_prefix=api_path_prefix,
                api_email=config.api_email,
                api_password=config.api_password,
                polling_interval_hours=config.polling_interval_hours,
                reconciliation_enabled=config.reconciliation_enabled,
                reconciliation_time=config.reconciliation_time,
                filter_mode=config.filter_mode,
                filter_rules=config.filter_rules or [],
                is_enabled=config.is_enabled
            )
            await db.sync_configs.insert_one(msgspec.to_builtins(sync_config))
        
        return {"success": True, "message": "Sync configuration saved"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving sync config: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@post("/sync/regenerate-secret")
async def regenerate_webhook_secret(request: Request) -> dict:
    """Regenerate webhook secret for security rotation"""
    current_user = await get_current_user(request)
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@post("/sync/discover-fields")
async def discover_fields_from_core(config_test: SyncConfigCreate, request: Request) -> dict:
    """
    Analyze sample members from core API to discover available fields and their values
    Returns field metadata for building dynamic filters
    """
    current_user = await get_current_user(request)
    if current_user["role"] not in [UserRole.FULL_ADMIN, UserRole.CAMPUS_ADMIN]:
        raise HTTPException(status_code=403, detail="Only administrators can discover fields")
    
    try:
        import httpx

        # Normalize api_path_prefix
        api_path_prefix = config_test.api_path_prefix.strip()
        if api_path_prefix and not api_path_prefix.startswith('/'):
            api_path_prefix = '/' + api_path_prefix
        api_path_prefix = api_path_prefix.rstrip('/')
        base_url = config_test.api_base_url.rstrip('/')

        # Login to core API
        async with httpx.AsyncClient(timeout=30.0) as client:
            login_response = await client.post(
                f"{base_url}{api_path_prefix}/auth/login",
                json={"email": config_test.api_email, "password": config_test.api_password}
            )

            if login_response.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to authenticate with core API")

            token = login_response.json().get("access_token")

            # Fetch members (limit to 100 for analysis)
            members_response = await client.get(
                f"{base_url}{api_path_prefix}/members/",
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@get("/sync/config")
async def get_sync_config(request: Request) -> dict:
    """Get sync configuration for campus"""
    try:
        current_user = await get_current_user(request)
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@post("/sync/test-connection")
async def test_sync_connection(config: SyncConfigCreate, request: Request) -> dict:
    """Test connection to core API"""
    current_user = await get_current_user(request)
    if current_user["role"] not in [UserRole.FULL_ADMIN, UserRole.CAMPUS_ADMIN]:
        raise HTTPException(status_code=403, detail="Only administrators can test sync")
    
    try:
        import httpx

        # Normalize paths
        api_path_prefix = config.api_path_prefix.strip()
        if api_path_prefix and not api_path_prefix.startswith('/'):
            api_path_prefix = '/' + api_path_prefix
        api_path_prefix = api_path_prefix.rstrip('/')
        base_url = config.api_base_url.rstrip('/')

        # Normalize login endpoint
        login_endpoint = getattr(config, 'api_login_endpoint', '/auth/login').strip()
        if login_endpoint and not login_endpoint.startswith('/'):
            login_endpoint = '/' + login_endpoint

        # Normalize members endpoint
        members_endpoint = getattr(config, 'api_members_endpoint', '/members/').strip()
        if members_endpoint and not members_endpoint.startswith('/'):
            members_endpoint = '/' + members_endpoint

        # Test login - send as 'email' key even if it's not email format (core API requirement)
        login_url = f"{base_url}{api_path_prefix}{login_endpoint}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            login_response = await client.post(
                login_url,
                json={"email": config.api_email, "password": decrypt_password(config.api_password)}
            )

            if login_response.status_code != 200:
                error_detail = login_response.text
                try:
                    error_json = login_response.json()
                    error_detail = error_json.get("detail", error_detail)
                except ValueError:
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
            members_url = f"{base_url}{api_path_prefix}{members_endpoint}"
            
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

@post("/sync/members/pull")
async def sync_members_from_core(request: Request) -> dict:
    """Pull members from core API and sync"""
    current_user = await get_current_user(request)
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
        sync_log_dict = msgspec.to_builtins(sync_log)
        # Preserve datetime as proper BSON Date for correct sorting
        sync_log_dict["started_at"] = sync_log.started_at
        await db.sync_logs.insert_one(sync_log_dict)
        sync_log_id = sync_log.id
        
        start_time = datetime.now(timezone.utc)
        
        try:
            # Get api_path_prefix with fallback for existing configs
            api_path_prefix = config.get('api_path_prefix', '/api')
            base_url = config['api_base_url'].rstrip('/')

            # Login to core API
            async with httpx.AsyncClient(timeout=60.0) as client:
                login_response = await client.post(
                    f"{base_url}{api_path_prefix}/auth/login",
                    json={"email": config["api_email"], "password": decrypt_password(config["api_password"])}
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
                        f"{base_url}{api_path_prefix}/members/?limit={page_size}&skip={offset}",
                        headers={"Authorization": f"Bearer {token}"}
                    )

                    if members_response.status_code != 200:
                        if members_response.status_code == 500:
                            raise Exception(f"External API server error (500). The FaithFlow server ({base_url}) is experiencing issues. Please try again later or contact FaithFlow support.")
                        elif members_response.status_code == 401:
                            raise Exception("Authentication expired. Please check your API credentials.")
                        elif members_response.status_code == 403:
                            raise Exception("Access denied. Your API account may not have permission to access member data.")
                        else:
                            raise Exception(f"Failed to fetch members (HTTP {members_response.status_code}): {members_response.text}")
                    
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
                            except (ValueError, TypeError):
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
                        except (ValueError, TypeError):
                            member_data["age"] = None
                    else:
                        member_data["age"] = None

                    # Handle photo URL from external API (CDN approach - no local storage)
                    # Check common field names for photo URL
                    external_photo_url = (
                        core_member.get("photo_url") or
                        core_member.get("photo") or
                        core_member.get("image_url") or
                        core_member.get("avatar_url") or
                        core_member.get("profile_photo")
                    )
                    if external_photo_url and isinstance(external_photo_url, str) and external_photo_url.startswith("http"):
                        # Store external URL directly - photos served from API provider (CDN approach)
                        member_data["photo_url"] = external_photo_url
                    
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
                            "id": generate_uuid(),
                            "campus_id": campus_id,
                            **member_data,
                            "is_archived": not is_active,
                            "engagement_status": "active",
                            "days_since_last_contact": 999,
                            "created_at": datetime.now(timezone.utc).isoformat()
                        }
                        
                        await db.members.insert_one(new_member)
                        stats["created"] += 1

                        # Create birthday event if member has birth_date
                        if new_member.get("birth_date"):
                            birthday_event = {
                                "id": generate_uuid(),
                                "member_id": new_member["id"],
                                "campus_id": campus_id,
                                "church_id": campus_id,
                                "event_type": EventType.BIRTHDAY.value,
                                "event_date": new_member["birth_date"],
                                "title": "Birthday Celebration",
                                "description": "Annual birthday reminder",
                                "completed": False,
                                "ignored": False,
                                "created_at": datetime.now(timezone.utc).isoformat(),
                                "updated_at": datetime.now(timezone.utc).isoformat()
                            }
                            await db.care_events.insert_one(birthday_event)

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
                        "completed_at": end_time,
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
                    "completed_at": end_time,
                    "duration_seconds": duration
                }}
            )
            
            raise HTTPException(status_code=500, detail=str(sync_error))
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in sync members: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@get("/sync/logs")
async def get_sync_logs(
    request: Request,
    limit: int = 5,
    skip: int = 0
) -> dict:
    """Get sync history logs with pagination"""
    try:
        current_user = await get_current_user(request)
        campus_id = current_user.get("campus_id")
        if not campus_id:
            return {"logs": [], "total": 0, "has_more": False}

        # Get total count
        total = await db.sync_logs.count_documents({"campus_id": campus_id})

        # Get paginated logs
        logs = await db.sync_logs.find(
            {"campus_id": campus_id},
            {"_id": 0}
        ).sort("started_at", -1).skip(skip).limit(limit).to_list(limit)

        return {
            "logs": logs,
            "total": total,
            "has_more": skip + len(logs) < total
        }

    except Exception as e:
        logger.error(f"Error getting sync logs: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


# ==================== SETUP WIZARD ENDPOINTS ====================

@post("/setup/admin")
async def setup_first_admin(request: SetupAdminRequest) -> dict:
    """Create church admin account (allows one church admin even if default system admin exists)"""
    try:
        # Default system admin email (auto-created at startup for system provider)
        DEFAULT_SYSTEM_ADMIN_EMAIL = "admin@gkbj.church"

        # Check if a non-default (church) admin already exists
        church_admin_count = await db.users.count_documents({
            "role": UserRole.FULL_ADMIN,
            "email": {"$ne": DEFAULT_SYSTEM_ADMIN_EMAIL}
        })

        if church_admin_count > 0:
            raise HTTPException(status_code=400, detail="Church admin already exists")

        # Prevent creating another account with the default system admin email
        if request.email.lower() == DEFAULT_SYSTEM_ADMIN_EMAIL.lower():
            raise HTTPException(status_code=400, detail="Cannot use system admin email. Please use a different email.")
        
        # Create first admin
        admin_user = User(
            email=request.email,
            name=request.name,
            role=UserRole.FULL_ADMIN,
            campus_id=None,
            phone=normalize_phone_number(request.phone) if request.phone else None,
            hashed_password=get_password_hash(request.password)
        )
        
        # Convert to dict and ensure proper serialization
        user_dict = msgspec.to_builtins(admin_user)
        user_dict['created_at'] = user_dict['created_at'].isoformat() if isinstance(user_dict['created_at'], datetime) else user_dict['created_at']
        user_dict['updated_at'] = user_dict['updated_at'].isoformat() if isinstance(user_dict['updated_at'], datetime) else user_dict['updated_at']
        
        await db.users.insert_one(user_dict)
        
        return {"success": True, "message": "Admin account created"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating first admin: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@post("/setup/campus")
async def setup_first_campus(request: SetupCampusRequest) -> dict:
    """Create first campus (setup wizard)"""
    try:
        campus = Campus(
            campus_name=request.campus_name,
            location=request.location,
            timezone=request.timezone
        )

        # Convert to dict and ensure proper datetime serialization
        campus_dict = msgspec.to_builtins(campus)
        campus_dict['created_at'] = campus_dict['created_at'].isoformat() if isinstance(campus_dict['created_at'], datetime) else campus_dict['created_at']
        campus_dict['updated_at'] = campus_dict['updated_at'].isoformat() if isinstance(campus_dict['updated_at'], datetime) else campus_dict['updated_at']

        await db.campuses.insert_one(campus_dict)

        # Invalidate campuses cache so new campus appears immediately
        invalidate_cache("campuses")

        return {"success": True, "message": "Campus created", "campus_id": campus.id}

    except Exception as e:
        logger.error(f"Error creating first campus: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@get("/setup/status")
async def check_setup_status() -> dict:
    """Check if initial setup is needed"""
    try:
        # Default system admin email (auto-created at startup for system provider)
        DEFAULT_SYSTEM_ADMIN_EMAIL = "admin@gkbj.church"

        # Check for church admin (non-default admin)
        church_admin_count = await db.users.count_documents({
            "role": UserRole.FULL_ADMIN,
            "email": {"$ne": DEFAULT_SYSTEM_ADMIN_EMAIL}
        })
        campus_count = await db.campuses.count_documents({})

        return {
            "needs_setup": church_admin_count == 0 or campus_count == 0,
            "has_admin": church_admin_count > 0,
            "has_campus": campus_count > 0
        }

    except Exception as e:
        logger.error(f"Error checking setup status: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@post("/sync/webhook")
async def receive_sync_webhook(request: Request) -> dict:
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
        except Exception:
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
            "id": generate_uuid(),
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
        
        if event_type == "test" or event_type == "ping":
            # Test webhook - just confirm it works
            return {
                "success": True,
                "message": "Webhook test successful! FaithTracker is ready to receive member updates.",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        elif event_type in ["member.created", "member.updated", "member.deleted"]:
            # Sync this specific member immediately
            if not member_id:
                return {
                    "success": False,
                    "message": "member_id required in webhook payload for member events"
                }
            
            logger.info(f"Webhook {event_type} received for member {member_id}, syncing...")
            
            try:
                import httpx
                from io import BytesIO
                import base64

                # Get api_path_prefix with fallback for existing configs
                api_path_prefix = config.get('api_path_prefix', '/api')
                base_url = config['api_base_url'].rstrip('/')

                # Login to core API
                async with httpx.AsyncClient(timeout=30.0) as client:
                    login_response = await client.post(
                        f"{base_url}{api_path_prefix}/auth/login",
                        json={"email": config["api_email"], "password": decrypt_password(config["api_password"])}
                    )

                    if login_response.status_code != 200:
                        raise Exception("Login failed")

                    token = login_response.json().get("access_token")

                    if event_type == "member.deleted":
                        # Archive the member
                        await db.members.update_one(
                            {"external_member_id": member_id},
                            {"$set": {
                                "is_archived": True,
                                "archived_at": datetime.now(timezone.utc).isoformat(),
                                "archived_reason": "Deleted in core system"
                            }}
                        )
                        logger.info(f"Archived member {member_id}")
                        return {
                            "success": True,
                            "message": f"Member archived: {member_id}"
                        }
                    else:
                        # Fetch specific member directly from core
                        member_response = await client.get(
                            f"{base_url}{api_path_prefix}/members/{member_id}",
                            headers={"Authorization": f"Bearer {token}"}
                        )
                        
                        if member_response.status_code != 200:
                            return {
                                "success": False,
                                "message": f"Member {member_id} not found in core system (status: {member_response.status_code})"
                            }
                        
                        core_member = member_response.json()
                        
                        # Prepare member data
                        member_data = {
                            "external_member_id": member_id,
                            "name": core_member.get("full_name"),
                            "phone": normalize_phone_number(core_member.get("phone_whatsapp", "")) if core_member.get("phone_whatsapp") else None,
                            "birth_date": core_member.get("date_of_birth"),
                            "gender": core_member.get("gender"),
                            "category": core_member.get("member_status"),
                            "updated_at": datetime.now(timezone.utc).isoformat()
                        }
                        
                        # Calculate age
                        if core_member.get("date_of_birth"):
                            try:
                                dob = core_member["date_of_birth"]
                                birth_date = date.fromisoformat(dob) if isinstance(dob, str) else dob
                                age = (date.today() - birth_date).days // 365
                                member_data["age"] = age
                            except (ValueError, TypeError):
                                member_data["age"] = None

                        # Handle photo if exists
                        photo_base64 = core_member.get("photo_base64")
                        if photo_base64 and photo_base64.startswith("data:image"):
                            try:
                                image_data = photo_base64.split(",")[1] if "," in photo_base64 else photo_base64
                                image_bytes = base64.b64decode(image_data)
                                
                                upload_dir = Path(ROOT_DIR) / "uploads"
                                upload_dir.mkdir(exist_ok=True)
                                
                                ext = "jpg"
                                if "png" in photo_base64: ext = "png"
                                filename = f"JEMAAT-{member_id[:5]}.{ext}"
                                filepath = upload_dir / filename
                                
                                img = Image.open(BytesIO(image_bytes))
                                img = img.convert('RGB')
                                img.thumbnail((800, 800), Image.Resampling.LANCZOS)
                                img.save(filepath, 'JPEG', quality=85)
                                
                                member_data["photo_url"] = f"/uploads/{filename}"
                            except Exception as e:
                                logger.error(f"Error processing photo: {str(e)}")
                        
                        # Check if member exists
                        existing = await db.members.find_one({"external_member_id": member_id}, {"_id": 0})
                        
                        if existing:
                            # Update existing
                            await db.members.update_one(
                                {"id": existing["id"]},
                                {"$set": member_data}
                            )
                            logger.info(f"Updated member {core_member.get('full_name')} via webhook")
                            action = "updated"
                        else:
                            # Create new
                            new_member = {
                                "id": generate_uuid(),
                                "campus_id": config["campus_id"],
                                **member_data,
                                "is_archived": not core_member.get("is_active", True),
                                "engagement_status": "active",
                                "days_since_last_contact": 999,
                                "created_at": datetime.now(timezone.utc).isoformat()
                            }
                            await db.members.insert_one(new_member)
                            logger.info(f"Created member {core_member.get('full_name')} via webhook")
                            action = "created"
                        
                        return {
                            "success": True,
                            "message": f"Member {action}: {core_member.get('full_name')}",
                            "member_id": member_id
                        }
            
            except Exception as sync_error:
                logger.error(f"Error syncing member from webhook: {str(sync_error)}")
                return {
                    "success": False,
                    "message": f"Failed to sync member: {str(sync_error)}"
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@get("/reminders/stats")
async def get_reminder_stats() -> dict:
    """Get reminder statistics for today"""
    try:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Count notifications sent today
        # Use datetime object for comparison since created_at is stored as ISODate
        logs = await db.notification_logs.find({
            "created_at": {"$gte": today_start}
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

# ==================== STATIC FILES ====================

@get("/uploads/{filename:str}")
async def get_uploaded_file(filename: str) -> dict:
    """Serve uploaded files with path traversal protection"""
    # Validate filename - reject any path traversal attempts
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    uploads_dir = (Path(ROOT_DIR) / "uploads").resolve()
    filepath = (uploads_dir / filename).resolve()

    # Security: Ensure resolved path is within uploads directory
    if not filepath.is_relative_to(uploads_dir):
        raise HTTPException(status_code=403, detail="Access denied")

    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(filepath)

@get("/user-photos/{filename:str}")
async def get_user_photo(filename: str) -> dict:
    """Serve user profile photos with path traversal protection"""
    # Validate filename - reject any path traversal attempts
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    photos_dir = (Path(ROOT_DIR) / "user_photos").resolve()
    filepath = (photos_dir / filename).resolve()

    # Security: Ensure resolved path is within user_photos directory
    if not filepath.is_relative_to(photos_dir):
        raise HTTPException(status_code=403, detail="Access denied")

    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Photo not found")
    return FileResponse(filepath)

# ==================== SEARCH ENDPOINT ====================

@get("/search")
async def global_search(q: str, request: Request) -> dict:
    """
    Global search across members and care events
    Returns members matching name, phone, email and care events matching title, description
    """
    try:
        current_user = await get_current_user(request)
        if not q or len(q) < 2:
            return {"members": [], "care_events": []}

        # Security: Escape regex special characters to prevent NoSQL injection
        safe_query = escape_regex(q)

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
                {"name": {"$regex": safe_query, "$options": "i"}},
                {"phone": {"$regex": safe_query, "$options": "i"}}
            ]
        }
        
        members = await db.members.find(member_query, {"_id": 0}).limit(10).to_list(10)
        
        # Search care events
        care_event_query = {
            **search_filter,
            "$or": [
                {"title": {"$regex": safe_query, "$options": "i"}},
                {"description": {"$regex": safe_query, "$options": "i"}}
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

# ==================== ACTIVITY LOG ENDPOINTS ====================

@get("/activity-logs")
async def get_activity_logs(
    request: Request,
    user_id: Optional[str] = None,
    action_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100
) -> dict:
    """
    Get activity logs with optional filters
    Default: last 30 days
    """
    try:
        current_user = await get_current_user(request)
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

@get("/activity-logs/summary")
async def get_activity_summary(request: Request) -> dict:
    """
    Get summary statistics for activity logs
    """
    try:
        current_user = await get_current_user(request)
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
        raise HTTPException(status_code=500, detail=safe_error_detail(e))
# ==================== HEALTH CHECK ENDPOINTS ====================

@get("/health")
async def health_check() -> dict:
    """
    Health check endpoint - verifies API and database are operational.
    Used by Docker health checks and load balancers.
    """
    try:
        # Verify database connectivity
        await client.admin.command('ping')
        return {
            "status": "healthy",
            "service": "faithtracker-api",
            "database": "connected",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed - database unreachable: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "service": "faithtracker-api",
                "database": "disconnected",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )

@get("/ready")
async def readiness_check() -> dict:
    """Readiness probe - can the API handle requests? Checks database connectivity."""
    try:
        # Verify database connectivity with ping
        await client.admin.command('ping')
        return {
            "status": "ready",
            "database": "connected",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Readiness check failed: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail={"status": "not_ready", "database": "disconnected", "error": str(e)}
        )

# ==================== LITESTAR APP CONFIGURATION ====================

# CORS Configuration for subdomain architecture
cors_origins = os.environ.get('ALLOWED_ORIGINS', os.environ.get('FRONTEND_URL', ''))
cors_origins_list = [origin.strip() for origin in cors_origins.split(',') if origin.strip()]

# Security: Don't allow wildcard with credentials - this is a security risk
if not cors_origins_list or cors_origins_list[0] == '*':
    if os.environ.get('ENVIRONMENT', 'development') == 'production':
        logger.error(
            "ALLOWED_ORIGINS or FRONTEND_URL must be set in production. "
            "Wildcard CORS with credentials is a security risk."
        )
        cors_origins_list = []
    else:
        cors_origins_list = [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8001",
            "http://127.0.0.1:8001"
        ]
        logger.warning("CORS: Using development origins. Set ALLOWED_ORIGINS for production.")

cors_config = CORSConfig(
    allow_credentials=True,
    allow_origins=cors_origins_list,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With", "Cache-Control", "Pragma"],
    expose_headers=["X-Total-Count"],
)


# Lifecycle functions
async def on_startup() -> None:
    """Create default full admin user if none exists (using environment variables)"""
    try:
        admin_count = await db.users.count_documents({"role": UserRole.FULL_ADMIN.value})
        if admin_count == 0:
            admin_email = os.environ.get('ADMIN_EMAIL')
            admin_password = os.environ.get('ADMIN_PASSWORD')
            admin_phone = os.environ.get('ADMIN_PHONE', '')

            if not admin_email or not admin_password:
                logger.warning(
                    "No full admin user exists. Set ADMIN_EMAIL and ADMIN_PASSWORD "
                    "environment variables to create initial admin, or use init_db.py script."
                )
            else:
                if len(admin_password) < 12:
                    logger.warning(
                        "ADMIN_PASSWORD should be at least 12 characters for security. "
                        "Admin user not created."
                    )
                else:
                    # Convert msgspec Struct to dict for MongoDB
                    default_admin = User(
                        email=admin_email,
                        name="Full Administrator",
                        role=UserRole.FULL_ADMIN,
                        campus_id=None,
                        phone=admin_phone,
                        hashed_password=get_password_hash(admin_password),
                        is_active=True
                    )
                    # msgspec Struct to dict conversion
                    admin_dict = msgspec.to_builtins(default_admin)
                    await db.users.insert_one(admin_dict)
                    logger.info(f"Default full admin user created: {admin_email}")

        start_scheduler()
    except Exception as e:
        logger.error(f"Error in startup: {str(e)}")


async def on_shutdown() -> None:
    """Cleanup on shutdown"""
    stop_scheduler()
    client.close()


# All route handlers - must be explicitly listed for Litestar
route_handlers = [
    # Health checks
    health_check,
    readiness_check,
    # Campus endpoints
    create_campus,
    list_campuses,
    get_campus,
    update_campus,
    # Auth endpoints
    register_user,
    login,
    get_current_user_info,
    list_users,
    update_user,
    update_own_profile,
    change_password,
    upload_user_photo,
    delete_user,
    # Member endpoints
    create_member,
    list_members,
    get_member,
    update_member,
    delete_member,
    upload_member_photo,
    list_at_risk_members,
    # Dashboard endpoints
    get_dashboard_reminders,
    get_dashboard_stats,
    get_upcoming_events,
    get_active_grief_support,
    get_recent_activity,
    # Care event endpoints
    create_care_event,
    list_care_events,
    get_care_event,
    update_care_event,
    complete_care_event,
    ignore_care_event,
    delete_care_event,
    send_care_event_reminder,
    add_visitation_log,
    log_additional_visit,
    get_hospital_followup_due,
    # Grief support endpoints
    list_grief_support,
    get_member_grief_timeline,
    complete_grief_stage,
    ignore_grief_stage,
    undo_grief_stage,
    send_grief_reminder,
    # Accident followup endpoints
    list_accident_followup,
    get_member_accident_timeline,
    complete_accident_stage,
    undo_accident_stage,
    ignore_accident_stage,
    # Financial aid endpoints
    create_aid_schedule,
    list_aid_schedules,
    remove_ignored_occurrence,
    clear_all_ignored_occurrences,
    delete_aid_schedule,
    stop_aid_schedule,
    get_member_aid_schedules,
    get_aid_due_today,
    mark_aid_distributed,
    ignore_financial_aid_schedule,
    get_financial_aid_summary,
    get_financial_aid_recipients,
    get_member_financial_aid,
    # Analytics endpoints
    get_engagement_trends,
    get_care_events_by_type,
    get_grief_completion_rate,
    get_analytics_dashboard,
    get_demographic_trends,
    # Sync endpoints
    sync_members_from_external_api,
    member_sync_webhook,
    save_sync_config,
    regenerate_webhook_secret,
    discover_fields_from_core,
    get_sync_config,
    test_sync_connection,
    sync_members_from_core,
    get_sync_logs,
    receive_sync_webhook,
    # Import/Export endpoints
    import_members_csv,
    import_members_json,
    export_members_csv,
    export_care_events_csv,
    # Integration endpoints
    test_whatsapp_integration,
    test_email_integration,
    # Suggestions endpoint
    get_intelligent_suggestions,
    # Reports endpoints
    get_monthly_management_report,
    export_monthly_report_pdf,
    get_staff_performance_report,
    get_yearly_summary_report,
    # Config endpoints
    get_aid_types,
    get_event_types,
    get_relationship_types,
    get_user_roles,
    get_engagement_statuses,
    get_weekdays,
    get_months,
    get_frequency_types,
    get_membership_statuses,
    get_all_config,
    # Admin endpoints
    recalculate_all_engagement_status,
    # Settings endpoints
    get_engagement_settings,
    update_engagement_settings,
    get_automation_settings,
    update_automation_settings,
    get_overdue_writeoff_settings,
    update_overdue_writeoff_settings,
    get_grief_stages,
    update_grief_stages,
    get_accident_followup,
    update_accident_followup,
    get_user_preferences,
    update_user_preferences,
    # Notification endpoints
    get_notification_logs,
    run_reminders_now,
    get_reminder_stats,
    # Setup endpoints
    setup_first_admin,
    setup_first_campus,
    check_setup_status,
    # File serving endpoints
    get_uploaded_file,
    get_user_photo,
    # Search endpoint
    global_search,
    # Activity log endpoints
    get_activity_logs,
    get_activity_summary,
]

# Create Litestar application
app = Litestar(
    route_handlers=route_handlers,
    cors_config=cors_config,
    on_startup=[on_startup],
    on_shutdown=[on_shutdown],
    openapi_config=OpenAPIConfig(
        title="FaithTracker API",
        version="1.0.0",
        description="Pastoral Care Management System API",
    ),
    type_encoders={
        datetime: lambda dt: dt.isoformat(),
        date: lambda d: d.isoformat(),
        ObjectId: str,
        Decimal128: lambda d: float(d.to_decimal()),
    },
    exception_handlers={Exception: global_exception_handler},
)