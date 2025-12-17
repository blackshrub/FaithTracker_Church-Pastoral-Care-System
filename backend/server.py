"""
FaithTracker Pastoral Care System - Main Backend API
Multi-tenant pastoral care management with complete accountability
Handles all API endpoints, authentication, database operations, and business logic

Framework: Litestar + msgspec (migrated from FastAPI + Pydantic)
"""

from litestar import Litestar, Router, get, post, put, patch, delete, Request, Response
from litestar.di import Provide
from litestar.exceptions import HTTPException, NotAuthorizedException, PermissionDeniedException
from litestar.status_codes import HTTP_200_OK, HTTP_201_CREATED, HTTP_204_NO_CONTENT, HTTP_400_BAD_REQUEST, HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN, HTTP_404_NOT_FOUND, HTTP_413_REQUEST_ENTITY_TOO_LARGE, HTTP_429_TOO_MANY_REQUESTS, HTTP_500_INTERNAL_SERVER_ERROR
from litestar.datastructures import UploadFile, State
from litestar.params import Parameter, Body
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

# Import extracted enums and constants
from enums import (
    EngagementStatus, EventType, GriefStage, AidType,
    NotificationChannel, NotificationStatus, UserRole,
    ScheduleFrequency, WeekDay, ActivityActionType, NoteCategory
)
from constants import (
    ENGAGEMENT_AT_RISK_DAYS_DEFAULT, ENGAGEMENT_DISCONNECTED_DAYS_DEFAULT,
    ENGAGEMENT_NO_CONTACT_DAYS, GRIEF_ONE_WEEK_DAYS, GRIEF_TWO_WEEKS_DAYS,
    GRIEF_ONE_MONTH_DAYS, GRIEF_THREE_MONTHS_DAYS, GRIEF_SIX_MONTHS_DAYS,
    GRIEF_ONE_YEAR_DAYS, ACCIDENT_FIRST_FOLLOWUP_DAYS, ACCIDENT_SECOND_FOLLOWUP_DAYS,
    ACCIDENT_FINAL_FOLLOWUP_DAYS, DEFAULT_REMINDER_DAYS_BIRTHDAY,
    DEFAULT_REMINDER_DAYS_CHILDBIRTH, DEFAULT_REMINDER_DAYS_FINANCIAL_AID,
    DEFAULT_REMINDER_DAYS_ACCIDENT_ILLNESS, DEFAULT_REMINDER_DAYS_GRIEF_SUPPORT,
    JWT_TOKEN_EXPIRE_HOURS, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, MAX_PAGE_NUMBER,
    MAX_LIMIT, DEFAULT_ANALYTICS_DAYS, DEFAULT_UPCOMING_DAYS, MAX_IMAGE_SIZE,
    MAX_CSV_SIZE, MAX_REQUEST_BODY_SIZE, IMAGE_MAGIC_BYTES
)
from models import (
    # UUID utilities
    is_valid_uuid, generate_uuid, UUID_PATTERN,
    # Campus models
    CampusCreate, Campus,
    # Member models
    MemberCreate, MemberUpdate, Member,
    # Care event models
    VisitationLogEntry, CareEventCreate, CareEventUpdate, CareEvent,
    # Setup models
    SetupAdminRequest, SetupCampusRequest, AdditionalVisitRequest,
    # Grief/accident models
    GriefSupport, AccidentFollowup,
    # Notification models
    NotificationLog,
    # Financial aid models
    FinancialAidSchedule, FinancialAidScheduleCreate,
    # Settings models
    AutomationSettingsUpdate, OverdueWriteoffSettingsUpdate,
    EngagementSettingsUpdate, UserPreferencesUpdate,
    # Pastoral notes models
    PastoralNoteCreate, PastoralNoteUpdate,
    # User models
    UserCreate, UserUpdate, UserLogin, User, UserResponse, TokenResponse,
    # Activity log models
    ActivityLog, ActivityLogResponse,
    # Sync models
    SyncConfig, SyncConfigCreate, SyncLog,
)
from utils import (
    # Validation
    EMAIL_PATTERN, PHONE_PATTERN,
    PASSWORD_MIN_LENGTH, PASSWORD_MAX_LENGTH,
    escape_regex, validate_email, validate_phone, validate_password_strength,
    # Phone normalization
    normalize_phone_number,
    # Engagement calculation
    calculate_engagement_status,
    # Cache
    get_from_cache, set_in_cache, invalidate_cache,
)
from dependencies import init_dependencies
from routes.campus import route_handlers as campus_route_handlers
from routes.auth import route_handlers as auth_route_handlers
from routes.members import route_handlers as member_route_handlers, init_member_routes
from routes.care_events import route_handlers as care_event_route_handlers, init_care_event_routes
from routes.grief_support import route_handlers as grief_support_route_handlers, init_grief_support_routes
from routes.accident_followup import route_handlers as accident_followup_route_handlers, init_accident_followup_routes
from routes.financial_aid import route_handlers as financial_aid_route_handlers, init_financial_aid_routes
from routes.dashboard import route_handlers as dashboard_route_handlers, init_dashboard_routes


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
    - Enum: value (msgspec handles str Enums, but this catches others)
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
    if isinstance(obj, Enum):
        return obj.value
    raise NotImplementedError(f"Object of type {type(obj)} is not JSON serializable")


# Create a reusable encoder instance (more efficient than creating per-request)
_msgspec_encoder = msgspec.json.Encoder(enc_hook=msgspec_enc_hook)


def to_mongo_doc(obj, _original_obj=None) -> dict:
    """Convert msgspec Struct to MongoDB-ready dict preserving datetime as native types.

    This helper ensures datetime fields are stored as native MongoDB Date types (ISODate)
    for proper sorting and querying. Use this instead of raw msgspec.to_builtins().

    Args:
        obj: A msgspec Struct instance or dict
        _original_obj: Internal use - original Struct for datetime field extraction

    Returns:
        Dict with datetime preserved as native types, UNSET values excluded,
        and Enum values converted to their underlying values.
    """
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            if v is UNSET:
                continue  # Skip UNSET values
            elif isinstance(v, datetime):
                result[k] = v  # Keep as datetime for MongoDB ISODate storage
            elif isinstance(v, date) and not isinstance(v, datetime):
                result[k] = v.isoformat()  # date (not datetime) -> string YYYY-MM-DD
            elif isinstance(v, str) and _original_obj is not None:
                # Check if this was originally a datetime that msgspec converted to string
                orig_val = getattr(_original_obj, k, None)
                if isinstance(orig_val, datetime):
                    result[k] = orig_val  # Restore original datetime
                else:
                    result[k] = v
            elif isinstance(v, Enum):
                result[k] = v.value
            elif isinstance(v, dict):
                result[k] = to_mongo_doc(v)
            elif isinstance(v, list):
                result[k] = [to_mongo_doc(item) if isinstance(item, (dict, Struct)) else
                            item if isinstance(item, datetime) else
                            item.isoformat() if isinstance(item, date) else
                            item.value if isinstance(item, Enum) else item
                            for item in v]
            else:
                result[k] = v
        return result

    # Convert Struct to dict first using msgspec.to_builtins with str_keys for MongoDB compatibility
    # Pass original object to restore datetime fields that msgspec converts to strings
    raw = msgspec.to_builtins(obj, str_keys=True)
    return to_mongo_doc(raw, _original_obj=obj)


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
            "timestamp": datetime.now(timezone.utc),
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

def decrypt_password(encrypted: str) -> str | None:
    """Decrypt password for use. Returns None if decryption fails."""
    try:
        return cipher_suite.decrypt(encrypted.encode()).decode()
    except Exception:
        # Return None instead of plaintext to prevent accidental exposure
        logger.warning("Failed to decrypt password - may be corrupted or using wrong key")
        return None

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
import jwt
from jwt.exceptions import InvalidTokenError as JWTError  # PyJWT (no ecdsa vulnerability)
import bcrypt
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

# Security headers middleware - prevents XSS, clickjacking, MIME sniffing attacks
class SecurityHeadersMiddleware(AbstractMiddleware):
    """Add security headers to all responses"""
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            async def send_with_security_headers(message):
                if message["type"] == "http.response.start":
                    headers = dict(message.get("headers", []))
                    # Add security headers
                    security_headers = [
                        (b"x-content-type-options", b"nosniff"),
                        (b"x-frame-options", b"DENY"),
                        (b"x-xss-protection", b"1; mode=block"),
                        (b"referrer-policy", b"strict-origin-when-cross-origin"),
                        (b"permissions-policy", b"geolocation=(), microphone=(), camera=()"),
                    ]
                    existing_headers = list(message.get("headers", []))
                    existing_headers.extend(security_headers)
                    message = {**message, "headers": existing_headers}
                await send(message)
            await self.app(scope, receive, send_with_security_headers)
        else:
            await self.app(scope, receive, send)

# ==================== LOGIN RATE LIMITING & ACCOUNT LOCKOUT ====================

# In-memory storage for login attempts (per IP and per account)
# Format: {"ip:email": {"attempts": int, "last_attempt": datetime, "locked_until": datetime | None}}
_login_attempts: Dict[str, Dict[str, Any]] = {}

# Security constants for brute force protection
LOGIN_MAX_ATTEMPTS = 5  # Max failed attempts before lockout
LOGIN_LOCKOUT_MINUTES = 15  # Account lockout duration
LOGIN_ATTEMPT_WINDOW_MINUTES = 5  # Time window to count attempts

def _get_client_ip(request: Request) -> str:
    """Extract client IP from request, handling proxied requests"""
    # Check X-Forwarded-For header (from Angie/reverse proxy)
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        # Take the first IP (original client)
        return forwarded_for.split(",")[0].strip()
    # Check X-Real-IP header
    real_ip = request.headers.get("x-real-ip", "")
    if real_ip:
        return real_ip.strip()
    # Fallback to direct connection IP
    client = request.scope.get("client")
    return client[0] if client else "unknown"

def _check_login_rate_limit(ip: str, email: str) -> tuple[bool, str | None]:
    """
    Check if login attempt is allowed.
    Returns (is_allowed, error_message).
    """
    key = f"{ip}:{email.lower()}"
    now = datetime.now(timezone.utc)

    if key in _login_attempts:
        record = _login_attempts[key]

        # Check if account is locked
        if record.get("locked_until"):
            if now < record["locked_until"]:
                remaining = int((record["locked_until"] - now).total_seconds() // 60) + 1
                return False, f"Account temporarily locked. Try again in {remaining} minutes."
            else:
                # Lockout expired, reset
                del _login_attempts[key]
                return True, None

        # Check if within attempt window
        window_start = now - timedelta(minutes=LOGIN_ATTEMPT_WINDOW_MINUTES)
        if record["last_attempt"] > window_start:
            if record["attempts"] >= LOGIN_MAX_ATTEMPTS:
                # Lock the account
                record["locked_until"] = now + timedelta(minutes=LOGIN_LOCKOUT_MINUTES)
                logger.warning(f"Account locked due to too many failed attempts: {email} from {ip}")
                return False, f"Too many failed attempts. Account locked for {LOGIN_LOCKOUT_MINUTES} minutes."

    return True, None

def _record_failed_login(ip: str, email: str) -> None:
    """Record a failed login attempt"""
    key = f"{ip}:{email.lower()}"
    now = datetime.now(timezone.utc)

    if key in _login_attempts:
        record = _login_attempts[key]
        window_start = now - timedelta(minutes=LOGIN_ATTEMPT_WINDOW_MINUTES)

        if record["last_attempt"] > window_start:
            record["attempts"] += 1
        else:
            # Outside window, reset counter
            record["attempts"] = 1
        record["last_attempt"] = now
    else:
        _login_attempts[key] = {
            "attempts": 1,
            "last_attempt": now,
            "locked_until": None
        }

    # Log failed attempt
    attempts = _login_attempts[key]["attempts"]
    logger.warning(f"Failed login attempt {attempts}/{LOGIN_MAX_ATTEMPTS} for {email} from {ip}")

def _clear_login_attempts(ip: str, email: str) -> None:
    """Clear login attempts after successful login"""
    key = f"{ip}:{email.lower()}"
    if key in _login_attempts:
        del _login_attempts[key]

# Cleanup old entries periodically (called on each login attempt)
def _cleanup_old_login_attempts() -> None:
    """Remove expired login attempt records to prevent memory growth"""
    now = datetime.now(timezone.utc)
    expiry = now - timedelta(minutes=LOGIN_LOCKOUT_MINUTES + LOGIN_ATTEMPT_WINDOW_MINUTES)

    keys_to_delete = []
    for key, record in _login_attempts.items():
        # Remove if last attempt was long ago and not locked
        if record["last_attempt"] < expiry and not record.get("locked_until"):
            keys_to_delete.append(key)
        # Remove if lockout has expired
        elif record.get("locked_until") and record["locked_until"] < now:
            keys_to_delete.append(key)

    for key in keys_to_delete:
        del _login_attempts[key]

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
    from litestar.exceptions import ValidationException

    # Log request details for validation errors (to debug 400 errors)
    if isinstance(exc, ValidationException):
        # Log the validation error details
        detail_str = str(exc.detail) if hasattr(exc, 'detail') else str(exc)
        logger.warning(f"[VALIDATION] {request.method} {request.url.path} failed: {detail_str}")

        # Try to get additional info from the exception
        if hasattr(exc, 'extra') and exc.extra:
            logger.warning(f"[VALIDATION] Extra info: {exc.extra}")

        content = json.dumps({"detail": f"Validation failed for {request.method} {request.url.path}"})
        return LitestarResponse(
            content=content,
            status_code=HTTP_400_BAD_REQUEST,
            media_type="application/json"
        )

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

# ==================== IMAGE VALIDATION ====================
# (Enums and constants now imported from enums.py and constants.py)

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

# ==================== VALIDATION UTILITIES ====================
# (Validation functions now imported from utils.py)

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

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a bcrypt hash."""
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )

def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(
        password.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')

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

    # Validate token is not empty (security: prevents auth bypass with "Bearer " header)
    if not token or not token.strip():
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Token is empty or invalid",
            extra={"headers": {"WWW-Authenticate": "Bearer"}},
        )

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
    role = current_user.get("role")
    # Handle both enum and string values for role comparison
    if role == UserRole.FULL_ADMIN.value or role == "full_admin":
        return {}  # Full admin sees all campuses
    elif current_user.get("campus_id"):
        return {"campus_id": current_user["campus_id"]}  # Campus-specific user
    else:
        # User has no campus - return impossible filter to prevent data leaks
        return {"campus_id": {"$exists": False, "$eq": "IMPOSSIBLE_VALUE"}}

# ==================== MODELS ====================
# (All models now imported from models.py)

# ==================== UTILITY FUNCTIONS ====================
# (Cache functions now imported from utils.py)

async def _get_engagement_settings_cached():
    """Get engagement threshold settings from database (cached for 10 minutes) - internal helper"""
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
    except Exception as e:
        logger.warning(f"Failed to get engagement settings: {str(e)}, using defaults")
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
    except Exception as e:
        logger.warning(f"Failed to get writeoff settings: {str(e)}, using defaults")
        return default_settings

async def calculate_engagement_status_async(last_contact: Optional[datetime]) -> tuple[EngagementStatus, int]:
    """Calculate engagement status using configurable thresholds"""
    settings = await _get_engagement_settings_cached()
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

# calculate_engagement_status (sync) and normalize_phone_number now imported from utils.py

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
    """Log user activity for accountability tracking and broadcast to SSE subscribers"""
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
        await db.activity_logs.insert_one(to_mongo_doc(activity))
        logger.info(f"Activity logged: {user_name} - {action_type} - {member_name}")

        # Broadcast to SSE subscribers for real-time updates
        # Import here to avoid circular import at module level
        try:
            activity_data = {
                "id": activity.id,
                "campus_id": campus_id,
                "user_id": user_id,
                "user_name": user_name,
                "user_photo_url": user_photo_url,
                "action_type": action_type.value if hasattr(action_type, 'value') else action_type,
                "member_id": member_id,
                "member_name": member_name,
                "care_event_id": care_event_id,
                "event_type": event_type.value if event_type and hasattr(event_type, 'value') else event_type,
                "notes": notes,
                "timestamp": activity.created_at.isoformat() if activity.created_at else datetime.now(JAKARTA_TZ).isoformat()
            }
            # Schedule broadcast without blocking (fire and forget)
            import asyncio
            asyncio.create_task(_broadcast_activity_safe(campus_id, activity_data))
        except Exception as broadcast_err:
            logger.debug(f"SSE broadcast skipped: {str(broadcast_err)}")

    except Exception as e:
        logger.error(f"Error logging activity: {str(e)}")
        # Don't fail the main operation if logging fails
        pass

async def _broadcast_activity_safe(campus_id: str, activity_data: dict):
    """Safe wrapper for broadcasting that won't fail if broadcast_activity isn't defined yet"""
    try:
        await broadcast_activity(campus_id, activity_data)
    except NameError:
        pass  # broadcast_activity not yet defined during module load
    except Exception as e:
        logger.debug(f"SSE broadcast error: {str(e)}")

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
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
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
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        timeline.append(grief_support)
    
    return timeline

async def send_whatsapp_message(phone: str, message: str, care_event_id: Optional[str] = None,
                                grief_support_id: Optional[str] = None, member_id: str = None) -> Dict[str, Any]:
    """Send WhatsApp message via gateway"""
    try:
        # Read from database settings first, fall back to environment variable
        settings = await db.settings.find_one({"type": "automation"}, {"_id": 0})
        whatsapp_url = None
        if settings and settings.get("data", {}).get("whatsappGateway"):
            whatsapp_url = settings["data"]["whatsappGateway"]
        if not whatsapp_url:
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
            
            await db.notification_logs.insert_one(to_mongo_doc(log_entry))
            
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
            await db.notification_logs.insert_one(to_mongo_doc(log_entry))
        
        return {
            "success": False,
            "error": str(e)
        }

# ==================== CAMPUS ENDPOINTS ====================
# (Moved to routes/campus.py)

# ==================== AUTHENTICATION ENDPOINTS ====================
# (Moved to routes/auth.py)

# ==================== MEMBER ENDPOINTS ====================
# (Moved to routes/members.py)

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


# Timezone cache to avoid repeated DB lookups
_timezone_cache: dict[str, tuple[str, float]] = {}
TIMEZONE_CACHE_TTL = 600  # 10 minutes

# Valid timezones set for validation
try:
    from zoneinfo import available_timezones
    VALID_TIMEZONES = available_timezones()
except ImportError:
    VALID_TIMEZONES = {"Asia/Jakarta", "UTC", "America/New_York", "Europe/London"}

def is_valid_timezone(tz_str: str) -> bool:
    """Validate timezone string"""
    return tz_str in VALID_TIMEZONES

async def get_campus_timezone(campus_id: str) -> str:
    """Get campus timezone setting (cached for 10 minutes)"""
    import time

    # Check cache first
    if campus_id in _timezone_cache:
        cached_tz, cached_time = _timezone_cache[campus_id]
        if time.time() - cached_time < TIMEZONE_CACHE_TTL:
            return cached_tz

    try:
        campus = await db.campuses.find_one({"id": campus_id}, {"_id": 0, "timezone": 1})
        tz = campus.get("timezone", "Asia/Jakarta") if campus else "Asia/Jakarta"
        # Validate timezone before caching
        if not is_valid_timezone(tz):
            logger.warning(f"Invalid timezone '{tz}' for campus {campus_id}, using default")
            tz = "Asia/Jakarta"
        _timezone_cache[campus_id] = (tz, time.time())
        return tz
    except Exception as e:
        logger.warning(f"Failed to get campus timezone: {str(e)}, using default")
        return "Asia/Jakarta"

def get_date_in_timezone(timezone_str: str) -> str:
    """Get current date in specified timezone as YYYY-MM-DD string"""
    try:
        # Validate timezone before use
        if not is_valid_timezone(timezone_str):
            logger.warning(f"Invalid timezone '{timezone_str}', using Asia/Jakarta")
            timezone_str = "Asia/Jakarta"
        tz = ZoneInfo(timezone_str)
        return datetime.now(tz).strftime('%Y-%m-%d')
    except Exception as e:
        logger.warning(f"Failed to get date in timezone: {str(e)}, using Jakarta")
        return datetime.now(ZoneInfo("Asia/Jakarta")).strftime('%Y-%m-%d')


@post("/care-events/{event_id:str}/ignore")
async def ignore_care_event(event_id: str, request: Request) -> dict:
    """Mark a care event as ignored/dismissed"""
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

        # Update event to mark as ignored
        await db.care_events.update_one(
            {"id": event_id},
            {"$set": {
                "ignored": True,
                "ignored_at": datetime.now(timezone.utc),
                "ignored_by": current_user.get("id"),
                "ignored_by_name": current_user.get("name"),
                "updated_at": datetime.now(timezone.utc)
            }}
        )

        # Log activity
        await log_activity(
            campus_id=event["campus_id"],
            user_id=current_user["id"],
            user_name=current_user["name"],
            action_type=ActivityActionType.IGNORE_TASK,
            member_id=event["member_id"],
            member_name=member_name,
            care_event_id=event_id,
            event_type=EventType(event["event_type"]),
            notes=f"Ignored {event['event_type']} task",
            user_photo_url=current_user.get("photo_url")
        )
        
        # Invalidate dashboard cache
        await invalidate_dashboard_cache(event["campus_id"])
        
        return {"success": True, "message": "Care event ignored"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ignoring care event: {str(e)}")
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
                    {"$set": {"completed": False, "updated_at": datetime.now(timezone.utc)}}
                )
                # Also delete the activity log associated with the original birthday event completion
                await db.activity_logs.delete_many({"care_event_id": birthday_event["id"]})
        
        # Delete the care event
        result = await db.care_events.delete_one({"id": event_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Care event not found")

        # Delete activity logs related to this care event
        activity_delete_result = await db.activity_logs.delete_many({"care_event_id": event_id})
        logger.info(f"[DELETE EVENT] Deleted {activity_delete_result.deleted_count} activity logs for care_event_id={event_id}")

        # Delete notification logs related to this care event
        await db.notification_logs.delete_many({"care_event_id": event_id})

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

                # Delete activity logs and notification logs for these timeline entries
                if timeline_entry_ids:
                    await db.activity_logs.delete_many({"care_event_id": {"$in": timeline_entry_ids}})
                    await db.notification_logs.delete_many({"care_event_id": {"$in": timeline_entry_ids}})

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

                # Delete activity logs and notification logs for these timeline entries
                if timeline_entry_ids:
                    await db.activity_logs.delete_many({"care_event_id": {"$in": timeline_entry_ids}})
                    await db.notification_logs.delete_many({"care_event_id": {"$in": timeline_entry_ids}})

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
                    "updated_at": datetime.now(timezone.utc)
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
                    "updated_at": datetime.now(timezone.utc)
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

# NOTE: Financial aid endpoints moved to routes/financial_aid.py

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
                        "updated_at": datetime.now(timezone.utc)
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
                        birth_date=ext_member.get('birth_date'),
                        address=ext_member.get('address'),
                        membership_status=ext_member.get('membership_status'),
                        category=ext_member.get('category'),
                        gender=ext_member.get('gender')
                    )
                    await db.members.insert_one(to_mongo_doc(member))
                
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
                        "archived_at": datetime.now(timezone.utc),
                        "archived_reason": "Removed from external API source",
                        "updated_at": datetime.now(timezone.utc)
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
                    campus_id=campus_id
                )

                await db.members.insert_one(to_mongo_doc(member))
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
async def import_members_json(data: List[Dict[str, Any]] = Body(), request: Request = None) -> dict:
    """Import members from JSON array"""
    current_user = await get_current_user(request)
    try:
        # Get campus_id from current user for multi-tenancy
        campus_id = current_user.get("campus_id")
        if not campus_id:
            raise HTTPException(status_code=400, detail="No campus assigned to your account")

        imported_count = 0
        errors = []

        for member_data in data:
            try:
                member = Member(
                    name=member_data.get('name', ''),
                    phone=member_data.get('phone', ''),
                    external_member_id=member_data.get('external_member_id'),
                    notes=member_data.get('notes'),
                    campus_id=campus_id
                )

                await db.members.insert_one(to_mongo_doc(member))
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
        csv_content = output.getvalue()
        return Response(
            content=csv_content,
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
        csv_content = output.getvalue()
        return Response(
            content=csv_content,
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
async def test_whatsapp_integration(data: WhatsAppTestRequest) -> dict:
    """Test WhatsApp gateway integration by sending a test message"""
    try:
        result = await send_whatsapp_message(data.phone, data.message, member_id="test")

        if result['success']:
            return WhatsAppTestResponse(
                success=True,
                message=f"✅ WhatsApp message sent successfully to {data.phone}!",
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

        # Build event lookup maps ONCE (O(n) instead of O(n*m) nested loops)
        events_by_member = {}  # member_id -> list of events
        financial_aid_members = set()  # members with financial aid events
        for event in recent_events:
            mid = event.get('member_id')
            if mid:
                if mid not in events_by_member:
                    events_by_member[mid] = []
                events_by_member[mid].append(event)
                if event.get('event_type') == 'financial_aid':
                    financial_aid_members.add(mid)

        suggestions = []
        now_utc = datetime.now(timezone.utc)

        for member in members:
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
            elif member['id'] in financial_aid_members and days_since > 60:
                # O(1) lookup instead of O(n) array scan
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
            age = member.get('age') or 0  # Handle None explicitly
            # Use membership_status, fallback to category if empty (external sync pattern)
            membership = member.get('membership_status') or member.get('category') or 'Unknown'
            days_since_contact = member.get('days_since_last_contact') or 999

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
                    # Ensure timezone-aware (MongoDB stores as UTC)
                    if created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=timezone.utc)
                    return created_at
                if isinstance(created_at, str) and created_at:
                    try:
                        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        return dt
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
    year: Optional[int] = None,
    month: Optional[int] = None,
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
    year: Optional[int] = None,
    month: Optional[int] = None,
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
    year: Optional[int] = None,
    month: Optional[int] = None,
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

        # Note: Staff performance is derived from activity_logs (which use ISODate),
        # not care_events (which store completed_at as strings). This ensures accurate data.

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


def static_config_response(data: list, request: Request = None) -> LitestarResponse:
    """Return static config data with E-Tag and aggressive HTTP cache headers (1 hour)

    E-Tag enables 304 Not Modified responses, saving bandwidth on repeated requests.
    """
    import json
    # Generate E-Tag from content hash
    content_str = json.dumps(data, sort_keys=True, default=str)
    etag = f'"{hashlib.md5(content_str.encode()).hexdigest()}"'

    # Check If-None-Match header for conditional request
    if request:
        if_none_match = request.headers.get("if-none-match")
        if if_none_match and if_none_match == etag:
            return LitestarResponse(
                content=None,
                status_code=304,
                headers={"ETag": etag}
            )

    return LitestarResponse(
        content=data,
        headers={
            "Cache-Control": "public, max-age=3600, stale-while-revalidate=86400",
            "Vary": "Accept-Encoding",
            "ETag": etag
        }
    )


@get("/config/aid-types")
async def get_aid_types(request: Request) -> dict:
    """Get all financial aid types (cached with E-Tag + HTTP cache headers)"""
    return static_config_response(_CACHED_AID_TYPES, request)

@get("/config/event-types")
async def get_event_types(request: Request) -> dict:
    """Get all care event types (cached with E-Tag + HTTP cache headers)"""
    return static_config_response(_CACHED_EVENT_TYPES, request)

@get("/config/relationship-types")
async def get_relationship_types(request: Request) -> dict:
    """Get grief relationship types (cached with E-Tag + HTTP cache headers)"""
    return static_config_response(_CACHED_RELATIONSHIP_TYPES, request)

@get("/config/user-roles")
async def get_user_roles(request: Request) -> dict:
    """Get user role types (cached with E-Tag + HTTP cache headers)"""
    return static_config_response(_CACHED_USER_ROLES, request)

@get("/config/engagement-statuses")
async def get_engagement_statuses(request: Request) -> dict:
    """Get engagement status types (cached with E-Tag + HTTP cache headers)"""
    return static_config_response(_CACHED_ENGAGEMENT_STATUSES, request)

@get("/config/weekdays")
async def get_weekdays(request: Request) -> dict:
    """Get weekday options (cached with E-Tag + HTTP cache headers)"""
    return static_config_response([
        {"value": "monday", "label": "Monday", "short": "Mon"},
        {"value": "tuesday", "label": "Tuesday", "short": "Tue"},
        {"value": "wednesday", "label": "Wednesday", "short": "Wed"},
        {"value": "thursday", "label": "Thursday", "short": "Thu"},
        {"value": "friday", "label": "Friday", "short": "Fri"},
        {"value": "saturday", "label": "Saturday", "short": "Sat"},
        {"value": "sunday", "label": "Sunday", "short": "Sun"}
    ], request)

@get("/config/months")
async def get_months(request: Request) -> dict:
    """Get month options (cached with E-Tag + HTTP cache headers)"""
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
    ], request)

@get("/config/frequency-types")
async def get_frequency_types(request: Request) -> dict:
    """Get financial aid frequency types (cached with E-Tag + HTTP cache headers)"""
    return static_config_response([
        {"value": "one_time", "label": "One-time Payment", "description": "Single payment (already given)"},
        {"value": "weekly", "label": "Weekly Schedule", "description": "Future weekly payments"},
        {"value": "monthly", "label": "Monthly Schedule", "description": "Future monthly payments"},
        {"value": "annually", "label": "Annual Schedule", "description": "Future annual payments"}
    ], request)

@get("/config/membership-statuses")
async def get_membership_statuses(request: Request) -> dict:
    """Get membership status types (cached with E-Tag + HTTP cache headers)"""
    return static_config_response([
        {"value": "Member", "label": "Member", "active": True},
        {"value": "Non Member", "label": "Non Member", "active": False},
        {"value": "Visitor", "label": "Visitor", "active": False},
        {"value": "Sympathizer", "label": "Sympathizer", "active": False},
        {"value": "Member (Inactive)", "label": "Member (Inactive)", "active": False}
    ], request)

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
        if user.get("role") not in [UserRole.FULL_ADMIN.value, UserRole.CAMPUS_ADMIN.value]:
            raise HTTPException(status_code=403, detail="Only admins can recalculate engagement")
        
        # Get engagement settings
        settings = await _get_engagement_settings_cached()
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
                    "updated_at": datetime.now(timezone.utc)
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
async def update_engagement_settings(data: EngagementSettingsUpdate, request: Request) -> dict:
    """Update engagement threshold settings"""
    current_admin = await get_current_admin(request)
    try:
        await db.settings.update_one(
            {"type": "engagement"},
            {"$set": {
                "type": "engagement",
                "data": to_mongo_doc(data),
                "updated_at": datetime.now(timezone.utc),
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
async def update_automation_settings(data: AutomationSettingsUpdate, request: Request) -> dict:
    """Update automation settings (daily digest time, WhatsApp gateway)"""
    current_admin = await get_current_admin(request)
    try:
        # Validate digestTime format (HH:MM)
        digest_time = data.digestTime
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
                    "whatsappGateway": data.whatsappGateway,
                    "enabled": data.enabled
                },
                "updated_at": datetime.now(timezone.utc),
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
async def update_overdue_writeoff_settings(data: OverdueWriteoffSettingsUpdate, request: Request) -> dict:
    """Update overdue write-off threshold settings"""
    current_admin = await get_current_admin(request)
    try:
        await db.settings.update_one(
            {"key": "overdue_writeoff"},
            {"$set": {
                "key": "overdue_writeoff",
                "data": {"days": data.days, "enabled": data.enabled},
                "updated_at": datetime.now(timezone.utc),
                "updated_by": current_admin["id"]
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
async def update_grief_stages(data: list = Body(), request: Request = None) -> dict:
    """Update grief support stage configuration"""
    current_admin = await get_current_admin(request)
    try:
        await db.settings.update_one(
            {"type": "grief_stages"},
            {"$set": {
                "type": "grief_stages",
                "data": data,
                "updated_at": datetime.now(timezone.utc),
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
async def update_accident_followup(data: list = Body(), request: Request = None) -> dict:
    """Update accident follow-up configuration"""
    current_admin = await get_current_admin(request)
    try:
        await db.settings.update_one(
            {"type": "accident_followup"},
            {"$set": {
                "type": "accident_followup",
                "data": data,
                "updated_at": datetime.now(timezone.utc),
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
async def update_user_preferences(user_id: str, data: UserPreferencesUpdate) -> dict:
    """Update user preferences"""
    try:
        await db.user_preferences.update_one(
            {"user_id": user_id},
            {"$set": {
                "user_id": user_id,
                "data": to_mongo_doc(data),
                "updated_at": datetime.now(timezone.utc)
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
async def save_sync_config(data: SyncConfigCreate, request: Request) -> dict:
    """Save sync configuration for campus"""
    current_user = await get_current_user(request)
    if current_user["role"] not in [UserRole.FULL_ADMIN.value, UserRole.CAMPUS_ADMIN.value]:
        raise HTTPException(status_code=403, detail="Only administrators can configure sync")
    
    try:
        campus_id = current_user.get("campus_id")
        if not campus_id and current_user["role"] == UserRole.FULL_ADMIN.value:
            raise HTTPException(status_code=400, detail="Please select a campus first")
        
        # Check if config exists
        existing = await db.sync_configs.find_one({"campus_id": campus_id}, {"_id": 0})
        
        # Normalize api_path_prefix (ensure it starts with / if not empty, no trailing /)
        api_path_prefix = data.api_path_prefix.strip()
        if api_path_prefix and not api_path_prefix.startswith('/'):
            api_path_prefix = '/' + api_path_prefix
        api_path_prefix = api_path_prefix.rstrip('/')

        # Handle password: if masked (********), use existing; otherwise use new plaintext
        if data.api_password == "********":
            if existing and existing.get("api_password"):
                password_to_store = existing["api_password"]  # Keep existing encrypted password
                password_for_login = decrypt_password(existing["api_password"])
            else:
                raise HTTPException(status_code=400, detail="No stored password found. Please enter your password.")
        else:
            password_to_store = encrypt_password(data.api_password)  # Encrypt new password
            password_for_login = data.api_password

        # Get core church_id by logging in to core API
        core_church_id = None
        try:
            import httpx
            base_url = data.api_base_url.rstrip('/')
            async with httpx.AsyncClient(timeout=10.0) as client:
                if password_for_login:
                    login_response = await client.post(
                        f"{base_url}{api_path_prefix}/auth/login",
                        json={"email": data.api_email, "password": password_for_login}
                    )
                    if login_response.status_code == 200:
                        login_data = login_response.json()
                        core_church_id = login_data.get("user", {}).get("church_id") or login_data.get("church", {}).get("id")
        except Exception:
            pass  # If we can't get church_id, continue without it

        sync_config_data = {
            "campus_id": campus_id,
            "core_church_id": core_church_id,
            "sync_method": data.sync_method,
            "api_base_url": data.api_base_url.rstrip('/'),
            "api_path_prefix": api_path_prefix,
            "api_email": data.api_email,
            "api_password": password_to_store,  # Use determined password
            "polling_interval_hours": data.polling_interval_hours,
            "reconciliation_enabled": data.reconciliation_enabled,
            "reconciliation_time": data.reconciliation_time,
            "filter_mode": data.filter_mode,
            "filter_rules": data.filter_rules or [],
            "is_enabled": data.is_enabled,
            "updated_at": datetime.now(timezone.utc)
        }
        
        if existing:
            # Preserve existing webhook_secret
            sync_config_data["webhook_secret"] = existing.get("webhook_secret", secrets.token_hex(32))
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
            await db.sync_configs.insert_one(to_mongo_doc(sync_config))

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
    if current_user["role"] not in [UserRole.FULL_ADMIN.value, UserRole.CAMPUS_ADMIN.value]:
        raise HTTPException(status_code=403, detail="Only administrators can regenerate webhook secret")
    
    try:
        campus_id = current_user.get("campus_id")
        if not campus_id:
            raise HTTPException(status_code=400, detail="Please select a campus first")
        
        # Generate new secret
        new_secret = secrets.token_hex(32)
        
        # Update config
        result = await db.sync_configs.update_one(
            {"campus_id": campus_id},
            {"$set": {
                "webhook_secret": new_secret,
                "updated_at": datetime.now(timezone.utc)
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
async def discover_fields_from_core(data: SyncConfigCreate, request: Request) -> dict:
    """
    Analyze sample members from core API to discover available fields and their values
    Returns field metadata for building dynamic filters
    """
    current_user = await get_current_user(request)
    if current_user["role"] not in [UserRole.FULL_ADMIN.value, UserRole.CAMPUS_ADMIN.value]:
        raise HTTPException(status_code=403, detail="Only administrators can discover fields")

    try:
        import httpx

        # Normalize api_path_prefix
        api_path_prefix = data.api_path_prefix.strip()
        if api_path_prefix and not api_path_prefix.startswith('/'):
            api_path_prefix = '/' + api_path_prefix
        api_path_prefix = api_path_prefix.rstrip('/')
        base_url = data.api_base_url.rstrip('/')

        # Handle password: if masked (********), fetch from database; otherwise use plaintext
        if data.api_password == "********":
            campus_id = current_user.get("campus_id")
            stored_config = await db.sync_configs.find_one({"campus_id": campus_id})
            if not stored_config or not stored_config.get("api_password"):
                raise HTTPException(status_code=400, detail="No stored password found. Please enter your password.")
            password_to_use = decrypt_password(stored_config["api_password"])
            if not password_to_use:
                raise HTTPException(status_code=400, detail="Failed to decrypt stored password. Please re-enter it.")
        else:
            password_to_use = data.api_password

        # Login to core API
        async with httpx.AsyncClient(timeout=30.0) as client:
            login_response = await client.post(
                f"{base_url}{api_path_prefix}/auth/login",
                json={"email": data.api_email, "password": password_to_use}
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
async def test_sync_connection(data: SyncConfigCreate, request: Request) -> dict:
    """Test connection to core API"""
    current_user = await get_current_user(request)
    if current_user["role"] not in [UserRole.FULL_ADMIN.value, UserRole.CAMPUS_ADMIN.value]:
        raise HTTPException(status_code=403, detail="Only administrators can test sync")

    try:
        import httpx

        # Normalize paths
        api_path_prefix = data.api_path_prefix.strip()
        if api_path_prefix and not api_path_prefix.startswith('/'):
            api_path_prefix = '/' + api_path_prefix
        api_path_prefix = api_path_prefix.rstrip('/')
        base_url = data.api_base_url.rstrip('/')

        # Normalize login endpoint
        login_endpoint = getattr(data, 'api_login_endpoint', '/auth/login').strip()
        if login_endpoint and not login_endpoint.startswith('/'):
            login_endpoint = '/' + login_endpoint

        # Normalize members endpoint
        members_endpoint = getattr(data, 'api_members_endpoint', '/members/').strip()
        if members_endpoint and not members_endpoint.startswith('/'):
            members_endpoint = '/' + members_endpoint

        # Test login - send as 'email' key even if it's not email format (core API requirement)
        login_url = f"{base_url}{api_path_prefix}{login_endpoint}"

        # Handle password: if masked (********), fetch from database; otherwise use plaintext
        if data.api_password == "********":
            # Fetch stored encrypted password from database
            campus_id = current_user.get("campus_id")
            stored_config = await db.sync_configs.find_one({"campus_id": campus_id})
            if not stored_config or not stored_config.get("api_password"):
                raise HTTPException(status_code=400, detail="No stored password found. Please enter your password.")
            password_to_use = decrypt_password(stored_config["api_password"])
            if not password_to_use:
                raise HTTPException(status_code=400, detail="Failed to decrypt stored password. Please re-enter it.")
        else:
            # Password is plaintext from frontend
            password_to_use = data.api_password
        async with httpx.AsyncClient(timeout=30.0) as client:
            login_response = await client.post(
                login_url,
                json={"email": data.api_email, "password": password_to_use}
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

async def perform_member_sync_for_campus(campus_id: str, sync_type: str = "manual") -> dict:
    """
    Core member sync logic - can be called from API endpoint or scheduler.

    Args:
        campus_id: The campus to sync members for
        sync_type: Type of sync ("manual", "polling", "reconciliation")

    Returns:
        dict with success status, stats, and duration
    """
    import httpx

    # Get sync config
    config = await db.sync_configs.find_one({"campus_id": campus_id}, {"_id": 0})
    if not config or not config.get("is_enabled"):
        return {"success": False, "error": "Sync is not configured or enabled for this campus"}

    # Create sync log
    sync_log = SyncLog(
        campus_id=campus_id,
        sync_type=sync_type,
        status="in_progress"
    )
    await db.sync_logs.insert_one(to_mongo_doc(sync_log))
    sync_log_id = sync_log.id

    start_time = datetime.now(timezone.utc)

    try:
        # Get api_path_prefix with fallback for existing configs
        api_path_prefix = config.get('api_path_prefix', '/api')
        base_url = config['api_base_url'].rstrip('/')

        # Login to core API
        decrypted_pwd = decrypt_password(config["api_password"])
        if not decrypted_pwd:
            raise Exception("Failed to decrypt API password")

        async with httpx.AsyncClient(timeout=60.0) as client:
            login_response = await client.post(
                f"{base_url}{api_path_prefix}/auth/login",
                json={"email": config["api_email"], "password": decrypted_pwd}
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
                        raise Exception(f"External API server error (500). The FaithFlow server ({base_url}) is experiencing issues.")
                    elif members_response.status_code == 401:
                        raise Exception("Authentication expired. Please check your API credentials.")
                    elif members_response.status_code == 403:
                        raise Exception("Access denied. Your API account may not have permission to access member data.")
                    else:
                        raise Exception(f"Failed to fetch members (HTTP {members_response.status_code}): {members_response.text}")

                batch = members_response.json()

                # Handle both array response and paginated response
                if isinstance(batch, dict) and 'data' in batch:
                    batch_members = batch['data']
                    all_members.extend(batch_members)
                    pagination = batch.get('pagination', {})
                    if not pagination.get('has_more', False):
                        break
                elif isinstance(batch, list):
                    all_members.extend(batch)
                    if len(batch) < page_size:
                        break
                else:
                    break

                offset += page_size
                if offset > 10000:
                    logger.warning(f"Reached safety limit of 10000 members")
                    break

            core_members = all_members
            logger.info(f"Fetched {len(core_members)} total members from core API")

            # Stats
            stats = {
                "fetched": len(core_members),
                "created": 0,
                "updated": 0,
                "archived": 0,
                "unarchived": 0,
                "matched_by_id": 0,
                "matched_by_name_phone": 0,
                "matched_by_name_only": 0
            }

            # Get existing members
            existing_members = await db.members.find({"campus_id": campus_id}, {"_id": 0}).to_list(None)
            existing_map = {m.get("external_member_id"): m for m in existing_members if m.get("external_member_id")}

            # Build additional lookup maps for name-based matching
            def normalize_name(name: str) -> str:
                if not name:
                    return ""
                return " ".join(name.lower().strip().split())

            name_map = {}
            name_phone_map = {}

            for m in existing_members:
                norm_name = normalize_name(m.get("name", ""))
                if norm_name:
                    if norm_name not in name_map or m.get("is_archived"):
                        name_map[norm_name] = m
                    phone = m.get("phone", "")
                    if phone:
                        norm_phone = normalize_phone_number(phone) if phone else ""
                        key = (norm_name, norm_phone)
                        if key not in name_phone_map or m.get("is_archived"):
                            name_phone_map[key] = m

            # Apply dynamic filters
            filter_mode = config.get("filter_mode", "include")
            filter_rules = config.get("filter_rules", [])
            filtered_members = []

            for core_member in core_members:
                if not filter_rules or len(filter_rules) == 0:
                    filtered_members.append(core_member)
                    continue

                matches_all_rules = True
                for rule in filter_rules:
                    field_name = rule.get("field")
                    operator = rule.get("operator")
                    filter_value = rule.get("value")
                    member_value = core_member.get(field_name)
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
                        try:
                            if "date_of_birth" in field_name or "birth" in field_name:
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

                    if not rule_matches:
                        matches_all_rules = False
                        break

                if filter_mode == "include":
                    if matches_all_rules:
                        filtered_members.append(core_member)
                else:
                    if not matches_all_rules:
                        filtered_members.append(core_member)

            logger.info(f"Filter mode: {filter_mode}. Filtered {len(core_members)} to {len(filtered_members)}")
            stats["fetched"] = len(filtered_members)

            # Process each filtered core member
            for core_member in filtered_members:
                core_id = core_member.get("id")
                match_method = None

                # Try matching in order of preference
                existing = existing_map.get(core_id)
                if existing:
                    match_method = "id"
                    stats["matched_by_id"] += 1
                else:
                    core_name = core_member.get("full_name") or core_member.get("name")
                    core_phone = core_member.get("phone_whatsapp") or core_member.get("phone")
                    norm_core_name = normalize_name(core_name) if core_name else ""
                    norm_core_phone = normalize_phone_number(core_phone) if core_phone else ""

                    if norm_core_name and norm_core_phone:
                        key = (norm_core_name, norm_core_phone)
                        existing = name_phone_map.get(key)
                        if existing:
                            match_method = "name_phone"
                            stats["matched_by_name_phone"] += 1
                            logger.info(f"Matched '{core_name}' by name+phone (new ID: {core_id})")

                    if not existing and norm_core_name:
                        existing = name_map.get(norm_core_name)
                        if existing:
                            match_method = "name_only"
                            stats["matched_by_name_only"] += 1
                            logger.info(f"Matched '{core_name}' by name only (new ID: {core_id})")

                # Prepare member data
                membership_status = (
                    core_member.get("membership_status") or
                    core_member.get("membershipStatus") or
                    core_member.get("member_type") or
                    core_member.get("memberType") or
                    core_member.get("type") or
                    core_member.get("status")
                )
                category = (
                    core_member.get("member_status") or
                    core_member.get("memberStatus") or
                    core_member.get("category") or
                    core_member.get("group") or
                    core_member.get("classification")
                )

                member_data = {
                    "external_member_id": core_id,
                    "name": core_member.get("full_name") or core_member.get("name"),
                    "phone": normalize_phone_number(core_member.get("phone_whatsapp", "")) if core_member.get("phone_whatsapp") else (normalize_phone_number(core_member.get("phone", "")) if core_member.get("phone") else None),
                    "birth_date": core_member.get("date_of_birth") or core_member.get("birthDate") or core_member.get("birth_date"),
                    "gender": core_member.get("gender"),
                    "membership_status": membership_status,
                    "category": category,
                    "updated_at": datetime.now(timezone.utc)
                }

                # Calculate age
                if core_member.get("date_of_birth"):
                    try:
                        dob = core_member["date_of_birth"]
                        birth_date_obj = date.fromisoformat(dob) if isinstance(dob, str) else dob
                        age = (date.today() - birth_date_obj).days // 365
                        member_data["age"] = age
                    except (ValueError, TypeError):
                        member_data["age"] = None
                else:
                    member_data["age"] = None

                # Handle photo URL
                external_photo_url = (
                    core_member.get("photo_url") or
                    core_member.get("photo") or
                    core_member.get("image_url") or
                    core_member.get("avatar_url") or
                    core_member.get("profile_photo")
                )
                if external_photo_url and isinstance(external_photo_url, str) and external_photo_url.startswith("http"):
                    member_data["photo_url"] = external_photo_url

                is_active = core_member.get("is_active", True)

                if existing:
                    if not is_active and not existing.get("is_archived"):
                        member_data["is_archived"] = True
                        member_data["archived_at"] = datetime.now(timezone.utc)
                        member_data["archived_reason"] = "Deactivated in core system"
                        stats["archived"] += 1
                    elif is_active and existing.get("is_archived"):
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
                    new_member = {
                        "id": generate_uuid(),
                        "campus_id": campus_id,
                        "church_id": campus_id,  # Use campus_id as church_id for multi-tenancy
                        **member_data,
                        "is_archived": not is_active,
                        "is_active": is_active,
                        "engagement_status": "active",
                        "days_since_last_contact": 999,
                        "created_at": datetime.now(timezone.utc)
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
                            "created_at": datetime.now(timezone.utc),
                            "updated_at": datetime.now(timezone.utc)
                        }
                        await db.care_events.insert_one(birthday_event)

            # Archive members not in filtered list
            filtered_core_ids = set(m.get("id") for m in filtered_members)
            for existing_member in existing_members:
                external_id = existing_member.get("external_member_id")
                if external_id and external_id not in filtered_core_ids and not existing_member.get("is_archived"):
                    await db.members.update_one(
                        {"id": existing_member["id"]},
                        {"$set": {
                            "is_archived": True,
                            "archived_at": datetime.now(timezone.utc),
                            "archived_reason": "No longer matches sync filter rules",
                            "updated_at": datetime.now(timezone.utc)
                        }}
                    )
                    stats["archived"] += 1
                    logger.info(f"Archived member {existing_member['name']} (no longer matches filter)")

            # Log matching summary
            logger.info(
                f"Sync matching summary: by_id={stats.get('matched_by_id', 0)}, "
                f"by_name_phone={stats.get('matched_by_name_phone', 0)}, "
                f"by_name_only={stats.get('matched_by_name_only', 0)}, new={stats['created']}"
            )

            # Update sync config
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()

            match_details = []
            if stats.get("matched_by_name_phone", 0) > 0:
                match_details.append(f"{stats['matched_by_name_phone']} matched by name+phone")
            if stats.get("matched_by_name_only", 0) > 0:
                match_details.append(f"{stats['matched_by_name_only']} matched by name")

            sync_message = f"Synced {stats['fetched']} members successfully"
            if match_details:
                sync_message += f" ({', '.join(match_details)})"

            await db.sync_configs.update_one(
                {"campus_id": campus_id},
                {"$set": {
                    "last_sync_at": end_time,
                    "last_sync_status": "success",
                    "last_sync_message": sync_message
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
                    "matched_by_id": stats.get("matched_by_id", 0),
                    "matched_by_name_phone": stats.get("matched_by_name_phone", 0),
                    "matched_by_name_only": stats.get("matched_by_name_only", 0),
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
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()

        await db.sync_configs.update_one(
            {"campus_id": campus_id},
            {"$set": {
                "last_sync_at": end_time,
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

        logger.error(f"Sync error for campus {campus_id}: {str(sync_error)}")
        return {"success": False, "error": str(sync_error), "duration_seconds": duration}


@post("/sync/members/pull")
async def sync_members_from_core(request: Request) -> dict:
    """Pull members from core API and sync"""
    current_user = await get_current_user(request)
    if current_user["role"] not in [UserRole.FULL_ADMIN.value, UserRole.CAMPUS_ADMIN.value]:
        raise HTTPException(status_code=403, detail="Only administrators can sync members")

    campus_id = current_user.get("campus_id")
    if not campus_id:
        raise HTTPException(status_code=400, detail="Please select a campus first")

    result = await perform_member_sync_for_campus(campus_id, sync_type="manual")

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Sync failed"))

    return result


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
        
        await db.users.insert_one(to_mongo_doc(admin_user))
        
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

        await db.campuses.insert_one(to_mongo_doc(campus))

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
            "received_at": datetime.now(timezone.utc)
        })
        
        # Process webhook based on event type
        event_type = payload.get("event_type")
        member_id = payload.get("member_id")
        
        if event_type == "test" or event_type == "ping":
            # Test webhook - just confirm it works
            return {
                "success": True,
                "message": "Webhook test successful! FaithTracker is ready to receive member updates.",
                "timestamp": datetime.now(timezone.utc)
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
                decrypted_pwd = decrypt_password(config["api_password"])
                if not decrypted_pwd:
                    raise Exception("Failed to decrypt API password")
                async with httpx.AsyncClient(timeout=30.0) as client:
                    login_response = await client.post(
                        f"{base_url}{api_path_prefix}/auth/login",
                        json={"email": config["api_email"], "password": decrypted_pwd}
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
                                "archived_at": datetime.now(timezone.utc),
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
                            "updated_at": datetime.now(timezone.utc)
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
                                "created_at": datetime.now(timezone.utc)
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
        if current_user["role"] in [UserRole.CAMPUS_ADMIN.value, UserRole.PASTOR.value]:
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
        if current_user["role"] in [UserRole.CAMPUS_ADMIN.value, UserRole.PASTOR.value]:
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
        if current_user["role"] in [UserRole.CAMPUS_ADMIN.value, UserRole.PASTOR.value]:
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

# ==================== SSE REAL-TIME ACTIVITY STREAM ====================

# In-memory event subscribers (keyed by campus_id)
# Each subscriber is an asyncio.Queue that receives activity events
from asyncio import Queue
from typing import Dict, Set
import asyncio

_activity_subscribers: Dict[str, Set[Queue]] = {}
_subscriber_lock = asyncio.Lock()

async def broadcast_activity(campus_id: str, activity: dict):
    """Broadcast an activity event to all subscribers for a campus"""
    async with _subscriber_lock:
        if campus_id in _activity_subscribers:
            for queue in _activity_subscribers[campus_id]:
                try:
                    queue.put_nowait(activity)
                except asyncio.QueueFull:
                    # Drop oldest message if queue is full
                    try:
                        queue.get_nowait()
                        queue.put_nowait(activity)
                    except:
                        pass

async def subscribe_to_activities(campus_id: str) -> Queue:
    """Subscribe to activity events for a campus"""
    queue: Queue = Queue(maxsize=100)
    async with _subscriber_lock:
        if campus_id not in _activity_subscribers:
            _activity_subscribers[campus_id] = set()
        _activity_subscribers[campus_id].add(queue)
    return queue

async def unsubscribe_from_activities(campus_id: str, queue: Queue):
    """Unsubscribe from activity events"""
    async with _subscriber_lock:
        if campus_id in _activity_subscribers:
            _activity_subscribers[campus_id].discard(queue)
            if not _activity_subscribers[campus_id]:
                del _activity_subscribers[campus_id]

def activity_event_generator(campus_id: str, user_id: str, queue: Queue):
    """Generate SSE events for activity stream - sync generator wrapper"""
    import json

    async def _inner():
        try:
            # Send initial connection event
            yield f"event: connected\ndata: {json.dumps({'status': 'connected', 'campus_id': campus_id})}\n\n"

            # Send heartbeat every 30 seconds to keep connection alive
            heartbeat_interval = 30

            while True:
                try:
                    # Wait for event with timeout for heartbeat
                    try:
                        activity = await asyncio.wait_for(queue.get(), timeout=heartbeat_interval)

                        # Don't send user's own activities back to them
                        if activity.get("user_id") != user_id:
                            event_data = json.dumps(activity, default=str)
                            yield f"event: activity\ndata: {event_data}\n\n"

                    except asyncio.TimeoutError:
                        # Send heartbeat
                        yield f"event: heartbeat\ndata: {json.dumps({'timestamp': datetime.now(JAKARTA_TZ).isoformat()})}\n\n"

                except asyncio.CancelledError:
                    break

        finally:
            await unsubscribe_from_activities(campus_id, queue)

    return _inner()

@get("/stream/activity")
async def stream_activity(request: Request, token: Optional[str] = None) -> Stream:
    """
    Server-Sent Events endpoint for real-time activity updates.

    Streams activity events (task completions, new events, etc.) to connected clients.
    Events are scoped by campus_id for multi-tenant isolation.

    Supports authentication via:
    - Authorization header (Bearer token)
    - Query parameter (?token=xxx) - for EventSource which doesn't support headers

    Usage (JavaScript):
    ```js
    const eventSource = new EventSource('/api/stream/activity?token=' + authToken);

    eventSource.addEventListener('activity', (e) => {
      const activity = JSON.parse(e.data);
      console.log('New activity:', activity);
    });
    ```
    """
    # Try to get user from header first, then from query param
    current_user = None

    # First try Authorization header
    try:
        current_user = await get_current_user(request)
    except HTTPException:
        pass  # Header auth not available, will try query param
    except Exception:
        pass

    # If no user from header, try query param token
    if not current_user and token:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = payload.get("sub")
            if user_id:
                user_doc = await db.users.find_one({"id": user_id}, {"_id": 0})
                if user_doc:
                    current_user = user_doc
        except JWTError as e:
            logger.warning(f"[SSE] Token decode error: {str(e)}")
            detail = "Token expired" if "expired" in str(e).lower() else "Invalid token"
            raise HTTPException(status_code=401, detail=detail)

    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    campus_id = current_user.get("campus_id") or "global"
    user_id = current_user.get("id", "")

    # Subscribe BEFORE creating Stream to avoid async issues in generator
    queue = await subscribe_to_activities(campus_id)

    return Stream(
        activity_event_generator(campus_id, user_id, queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )

# ==================== SSE TEST ENDPOINT ====================

async def simple_sse_generator():
    """Simple SSE generator for testing"""
    import json
    yield f"event: connected\ndata: {json.dumps({'status': 'connected'})}\n\n"

    for i in range(10):
        await asyncio.sleep(2)
        yield f"event: heartbeat\ndata: {json.dumps({'count': i, 'timestamp': datetime.now(JAKARTA_TZ).isoformat()})}\n\n"

@get("/stream/test")
async def stream_test() -> Stream:
    """Simple SSE test endpoint - no auth required"""
    return Stream(
        simple_sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

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
            "timestamp": datetime.now(timezone.utc)
        }
    except Exception as e:
        logger.error(f"Health check failed - database unreachable: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "service": "faithtracker-api",
                "database": "disconnected",
                "timestamp": datetime.now(timezone.utc)
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
            "timestamp": datetime.now(timezone.utc)
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
    """Initialize dependencies and create default admin if needed"""
    # Initialize shared dependencies for route modules
    init_dependencies(db, SECRET_KEY)
    init_member_routes(invalidate_dashboard_cache, log_activity, msgspec_enc_hook, ROOT_DIR)
    init_care_event_routes(
        invalidate_dashboard_cache, log_activity, send_whatsapp_message,
        generate_grief_timeline, generate_accident_followup_timeline,
        get_campus_timezone, get_date_in_timezone
    )
    init_grief_support_routes(
        invalidate_dashboard_cache, log_activity, send_whatsapp_message,
        get_campus_timezone, get_date_in_timezone
    )
    init_accident_followup_routes(
        invalidate_dashboard_cache, log_activity,
        get_campus_timezone, get_date_in_timezone
    )
    init_financial_aid_routes(
        invalidate_dashboard_cache, log_activity,
        _get_engagement_settings_cached
    )
    init_dashboard_routes(
        get_campus_timezone, get_date_in_timezone,
        get_writeoff_settings
    )
    
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
                    default_admin = User(
                        email=admin_email,
                        name="Full Administrator",
                        role=UserRole.FULL_ADMIN,
                        campus_id=None,
                        phone=admin_phone,
                        hashed_password=get_password_hash(admin_password),
                        is_active=True
                    )
                    await db.users.insert_one(to_mongo_doc(default_admin))
                    logger.info(f"Default full admin user created: {admin_email}")

        start_scheduler()
    except Exception as e:
        logger.error(f"Error in startup: {str(e)}")


async def on_shutdown() -> None:
    """Cleanup on shutdown"""
    stop_scheduler()
    client.close()



# ==================== PASTORAL NOTES ENDPOINTS ====================

@post("/pastoral-notes")
async def create_pastoral_note(data: PastoralNoteCreate, request: Request) -> dict:
    """Create a new pastoral note for a member"""
    current_user = await get_current_user(request)

    # Verify member exists
    member = await get_member_or_404(data.member_id)

    # Check campus access
    if current_user["role"] != "full_admin" and current_user.get("campus_id") != member.get("campus_id"):
        raise PermissionDeniedException("You don't have access to this member's records")

    # Validate category if provided
    if data.category and data.category not in [c.value for c in NoteCategory]:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=f"Invalid category. Must be one of: {[c.value for c in NoteCategory]}")

    # Validate follow_up_date format if provided
    if data.follow_up_date:
        try:
            datetime.strptime(data.follow_up_date, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="Invalid follow_up_date format. Use YYYY-MM-DD")

    now = datetime.now(timezone.utc)
    note_id = generate_uuid()

    note_doc = {
        "id": note_id,
        "member_id": data.member_id,
        "campus_id": member.get("campus_id"),
        "title": data.title,
        "content": data.content,
        "category": data.category,
        "is_private": data.is_private,
        "created_by": current_user["id"],
        "created_by_name": current_user["name"],
        "created_at": now,
        "updated_at": None,
        "follow_up_date": data.follow_up_date,
        "follow_up_notes": data.follow_up_notes,
        "follow_up_completed": False,
        "edit_history": []
    }

    await db.pastoral_notes.insert_one(note_doc)

    # Log activity
    await log_activity(
        campus_id=member.get("campus_id"),
        user_id=current_user["id"],
        user_name=current_user["name"],
        action_type=ActivityActionType.CREATE_PASTORAL_NOTE,
        member_id=data.member_id,
        member_name=member["name"],
        notes=f"Created pastoral note: {data.title}"
    )

    note_doc.pop("_id", None)
    return note_doc


@get("/pastoral-notes")
async def list_pastoral_notes(
    request: Request,
    member_id: str | None = None,
    category: str | None = None,
    include_private: bool = False,
    follow_up_due: bool = False,
    page: int = 1,
    limit: int = 50
) -> dict:
    """List pastoral notes with filtering options"""
    current_user = await get_current_user(request)

    # Build query
    query: Dict[str, Any] = {}

    # Campus filtering
    if current_user["role"] != "full_admin":
        query["campus_id"] = current_user.get("campus_id")

    # Member filtering
    if member_id:
        query["member_id"] = member_id

    # Category filtering
    if category:
        query["category"] = category

    # Privacy filtering - only show private notes to their creators
    if not include_private:
        query["$or"] = [
            {"is_private": False},
            {"is_private": {"$exists": False}},
            {"created_by": current_user["id"]}  # Creator can always see their own
        ]
    else:
        # Even with include_private=True, non-creators can't see others' private notes
        query["$or"] = [
            {"is_private": False},
            {"is_private": {"$exists": False}},
            {"created_by": current_user["id"]}
        ]

    # Follow-up due filtering (overdue or due today)
    if follow_up_due:
        today = get_jakarta_date_str()
        query["follow_up_date"] = {"$lte": today}
        query["follow_up_completed"] = False

    # Pagination
    skip = (page - 1) * limit

    # Get total count
    total = await db.pastoral_notes.count_documents(query)

    # Get notes
    notes = await db.pastoral_notes.find(
        query,
        {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

    # Enrich with member names
    for note in notes:
        member = await db.members.find_one({"id": note["member_id"]}, {"_id": 0, "name": 1})
        note["member_name"] = member["name"] if member else "Unknown"

    return {
        "items": notes,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit
    }


@get("/pastoral-notes/{note_id:str}")
async def get_pastoral_note(note_id: str, request: Request) -> dict:
    """Get a single pastoral note with full details including edit history"""
    current_user = await get_current_user(request)

    note = await db.pastoral_notes.find_one({"id": note_id}, {"_id": 0})
    if not note:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="Pastoral note not found")

    # Check campus access
    if current_user["role"] != "full_admin" and current_user.get("campus_id") != note.get("campus_id"):
        raise PermissionDeniedException("You don't have access to this note")

    # Check private note access
    if note.get("is_private") and note.get("created_by") != current_user["id"]:
        raise PermissionDeniedException("This is a private note")

    # Enrich with member name
    member = await db.members.find_one({"id": note["member_id"]}, {"_id": 0, "name": 1})
    note["member_name"] = member["name"] if member else "Unknown"

    return note


@put("/pastoral-notes/{note_id:str}")
async def update_pastoral_note(note_id: str, data: PastoralNoteUpdate, request: Request) -> dict:
    """Update a pastoral note (saves edit history)"""
    current_user = await get_current_user(request)

    note = await db.pastoral_notes.find_one({"id": note_id}, {"_id": 0})
    if not note:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="Pastoral note not found")

    # Check campus access
    if current_user["role"] != "full_admin" and current_user.get("campus_id") != note.get("campus_id"):
        raise PermissionDeniedException("You don't have access to this note")

    # Check private note access - only creator can edit private notes
    if note.get("is_private") and note.get("created_by") != current_user["id"]:
        raise PermissionDeniedException("Only the creator can edit a private note")

    # Validate category if provided
    if data.category is not None and data.category not in [c.value for c in NoteCategory] and data.category != "":
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=f"Invalid category")

    # Validate follow_up_date format if provided
    if data.follow_up_date:
        try:
            datetime.strptime(data.follow_up_date, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="Invalid follow_up_date format. Use YYYY-MM-DD")

    now = datetime.now(timezone.utc)

    # Create history entry before updating
    history_entry = {
        "edited_at": now,
        "edited_by": current_user["id"],
        "edited_by_name": current_user["name"],
        "previous_title": note.get("title"),
        "previous_content": note.get("content"),
        "previous_category": note.get("category"),
        "previous_is_private": note.get("is_private", False),
        "previous_follow_up_date": note.get("follow_up_date"),
        "previous_follow_up_notes": note.get("follow_up_notes")
    }

    # Build update
    update_fields = {"updated_at": now}

    if data.title is not None:
        update_fields["title"] = data.title
    if data.content is not None:
        update_fields["content"] = data.content
    if data.category is not None:
        update_fields["category"] = data.category if data.category else None
    if data.is_private is not None:
        update_fields["is_private"] = data.is_private
    if data.follow_up_date is not None:
        update_fields["follow_up_date"] = data.follow_up_date if data.follow_up_date else None
    if data.follow_up_notes is not None:
        update_fields["follow_up_notes"] = data.follow_up_notes if data.follow_up_notes else None
    if data.follow_up_completed is not None:
        update_fields["follow_up_completed"] = data.follow_up_completed

    # Update with history
    await db.pastoral_notes.update_one(
        {"id": note_id},
        {
            "$set": update_fields,
            "$push": {"edit_history": history_entry}
        }
    )

    # Get updated note
    updated_note = await db.pastoral_notes.find_one({"id": note_id}, {"_id": 0})

    # Log activity
    member = await db.members.find_one({"id": note["member_id"]}, {"_id": 0, "name": 1})
    await log_activity(
        campus_id=note.get("campus_id"),
        user_id=current_user["id"],
        user_name=current_user["name"],
        action_type=ActivityActionType.UPDATE_PASTORAL_NOTE,
        member_id=note["member_id"],
        member_name=member["name"] if member else "Unknown",
        notes=f"Updated pastoral note: {updated_note.get('title')}"
    )

    return updated_note


@delete("/pastoral-notes/{note_id:str}", status_code=200)
async def delete_pastoral_note(note_id: str, request: Request) -> dict:
    """Delete a pastoral note"""
    current_user = await get_current_user(request)

    note = await db.pastoral_notes.find_one({"id": note_id}, {"_id": 0})
    if not note:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="Pastoral note not found")

    # Check campus access
    if current_user["role"] != "full_admin" and current_user.get("campus_id") != note.get("campus_id"):
        raise PermissionDeniedException("You don't have access to this note")

    # Check private note access - only creator or admin can delete
    if note.get("is_private") and note.get("created_by") != current_user["id"] and current_user["role"] not in ["full_admin", "campus_admin"]:
        raise PermissionDeniedException("Only the creator or admin can delete a private note")

    await db.pastoral_notes.delete_one({"id": note_id})

    # Log activity
    member = await db.members.find_one({"id": note["member_id"]}, {"_id": 0, "name": 1})
    await log_activity(
        campus_id=note.get("campus_id"),
        user_id=current_user["id"],
        user_name=current_user["name"],
        action_type=ActivityActionType.DELETE_PASTORAL_NOTE,
        member_id=note["member_id"],
        member_name=member["name"] if member else "Unknown",
        notes=f"Deleted pastoral note: {note.get('title')}"
    )

    return {"message": "Pastoral note deleted successfully"}


@post("/pastoral-notes/{note_id:str}/complete-followup")
async def complete_note_followup(note_id: str, request: Request) -> dict:
    """Mark a pastoral note's follow-up as completed"""
    current_user = await get_current_user(request)

    note = await db.pastoral_notes.find_one({"id": note_id}, {"_id": 0})
    if not note:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="Pastoral note not found")

    # Check campus access
    if current_user["role"] != "full_admin" and current_user.get("campus_id") != note.get("campus_id"):
        raise PermissionDeniedException("You don't have access to this note")

    if not note.get("follow_up_date"):
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="This note has no follow-up scheduled")

    await db.pastoral_notes.update_one(
        {"id": note_id},
        {"$set": {"follow_up_completed": True, "updated_at": datetime.now(timezone.utc)}}
    )

    return {"message": "Follow-up marked as completed"}


@get("/pastoral-notes/member/{member_id:str}")
async def get_member_pastoral_notes(member_id: str, request: Request) -> list:
    """Get all pastoral notes for a specific member"""
    current_user = await get_current_user(request)

    # Verify member exists
    member = await get_member_or_404(member_id)

    # Check campus access
    if current_user["role"] != "full_admin" and current_user.get("campus_id") != member.get("campus_id"):
        raise PermissionDeniedException("You don't have access to this member's records")

    # Query notes - filter private notes
    query = {
        "member_id": member_id,
        "$or": [
            {"is_private": False},
            {"is_private": {"$exists": False}},
            {"created_by": current_user["id"]}
        ]
    }

    notes = await db.pastoral_notes.find(
        query,
        {"_id": 0}
    ).sort("created_at", -1).to_list(500)

    return notes


@get("/pastoral-notes/followup-due")
async def get_notes_with_followup_due(request: Request) -> list:
    """Get all notes with overdue or due today follow-ups"""
    current_user = await get_current_user(request)

    today = get_jakarta_date_str()

    query = {
        "follow_up_date": {"$lte": today},
        "follow_up_completed": False,
        "$or": [
            {"is_private": False},
            {"is_private": {"$exists": False}},
            {"created_by": current_user["id"]}
        ]
    }

    # Campus filtering
    if current_user["role"] != "full_admin":
        query["campus_id"] = current_user.get("campus_id")

    notes = await db.pastoral_notes.find(query, {"_id": 0}).sort("follow_up_date", 1).to_list(200)

    # Enrich with member names
    for note in notes:
        member = await db.members.find_one({"id": note["member_id"]}, {"_id": 0, "name": 1, "phone": 1})
        if member:
            note["member_name"] = member["name"]
            note["member_phone"] = member.get("phone")

    return notes


@get("/config/note-categories")
async def get_note_categories() -> list:
    """Get available pastoral note categories"""
    return [
        {"value": "special_needs", "label": "Kebutuhan Khusus", "label_en": "Special Needs"},
        {"value": "health", "label": "Kesehatan", "label_en": "Health"},
        {"value": "financial", "label": "Keuangan", "label_en": "Financial"},
        {"value": "spiritual", "label": "Rohani", "label_en": "Spiritual"},
        {"value": "family", "label": "Keluarga", "label_en": "Family"},
        {"value": "work", "label": "Pekerjaan", "label_en": "Work"},
        {"value": "other", "label": "Lainnya", "label_en": "Other"},
    ]



# All route handlers - must be explicitly listed for Litestar
route_handlers = [
    # Health checks
    health_check,
    readiness_check,
    # Campus endpoints (from routes/campus.py)
    *campus_route_handlers,
    # Auth endpoints (from routes/auth.py)
    *auth_route_handlers,
    # Member endpoints (from routes/members.py)
    *member_route_handlers,
    # Dashboard & Analytics endpoints (from routes/dashboard.py)
    *dashboard_route_handlers,
    # Care event endpoints (from routes/care_events.py)
    *care_event_route_handlers,
    # Care event endpoints staying in server.py (complex interdependencies)
    ignore_care_event,
    delete_care_event,
    # Grief support endpoints (from routes/grief_support.py)
    *grief_support_route_handlers,
    # Accident followup endpoints (from routes/accident_followup.py)
    *accident_followup_route_handlers,
    # Financial aid endpoints (from routes/financial_aid.py)
    *financial_aid_route_handlers,
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
    # Pastoral notes endpoints
    create_pastoral_note,
    list_pastoral_notes,
    get_pastoral_note,
    update_pastoral_note,
    delete_pastoral_note,
    complete_note_followup,
    get_member_pastoral_notes,
    get_notes_with_followup_due,
    get_note_categories,

    # Real-time SSE stream
    stream_activity,
    stream_test,
]

# Rate limiting configuration
rate_limit_config = RateLimitConfig(
    rate_limit=("minute", 100),  # 100 requests per minute for general endpoints
    exclude=["/health", "/docs", "/schema"],  # Exclude health check and docs
)

# Create Litestar application
app = Litestar(
    route_handlers=route_handlers,
    cors_config=cors_config,
    on_startup=[on_startup],
    on_shutdown=[on_shutdown],
    middleware=[
        DefineMiddleware(SecurityHeadersMiddleware),  # Security headers (XSS, clickjacking protection)
        # Note: Compression handled by Angie at edge (Brotli/gzip)
        DefineMiddleware(RequestSizeLimitMiddleware),  # Limit request body size
        rate_limit_config.middleware,  # Rate limiting
    ],
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