"""
FaithTracker Dependencies - Shared dependencies for route modules
"""

import json
import logging
import os
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from litestar import Request
from litestar.exceptions import HTTPException
from litestar.status_codes import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from constants import JWT_TOKEN_EXPIRE_HOURS
from enums import UserRole

logger = logging.getLogger(__name__)

# Shared state (set by server.py on startup)
_db = None
_secret_key = None
_algorithm = "HS256"

# Generic error messages for production (don't expose internal details)
GENERIC_ERROR_MESSAGES = {
    400: "Invalid request",
    401: "Authentication required",
    403: "Access denied",
    404: "Resource not found",
    500: "An internal error occurred. Please try again later.",
}


def init_dependencies(database, secret_key: str):
    """Initialize dependencies (called from server.py on startup)"""
    global _db, _secret_key
    _db = database
    _secret_key = secret_key


def get_db():
    """Get database reference"""
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_dependencies first.")
    return _db


async def get_current_user(request: Request) -> dict:
    """Extract and validate JWT token from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")

    token = auth_header[7:]
    if not token or not token.strip():
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Token is empty or invalid")

    try:
        payload = jwt.decode(token, _secret_key, algorithms=[_algorithm])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
    except jwt.PyJWTError:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")

    db = get_db()
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if user is None:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
    return user


async def get_current_admin(request: Request) -> dict:
    """Get current user and verify admin role."""
    current_user = await get_current_user(request)
    if current_user.get("role") not in [UserRole.FULL_ADMIN.value, UserRole.CAMPUS_ADMIN.value]:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return current_user


async def get_full_admin(request: Request) -> dict:
    """Get current user and verify full admin role."""
    current_user = await get_current_user(request)
    if current_user.get("role") != UserRole.FULL_ADMIN.value:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Full admin privileges required")
    return current_user


def get_campus_filter(current_user: dict) -> dict:
    """Get campus filter for queries based on user role"""
    role = current_user.get("role")
    if role == UserRole.FULL_ADMIN.value:
        return {}
    elif current_user.get("campus_id"):
        return {"campus_id": current_user["campus_id"]}
    return {"campus_id": {"$exists": False, "$eq": "IMPOSSIBLE_VALUE"}}


# ==================== AUTH HELPERS ====================


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(hours=JWT_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, _secret_key, algorithm=_algorithm)
    return encoded_jwt


def safe_error_detail(e: Exception, status_code: int = 500) -> str:
    """
    Return a safe error message for production.
    In development, returns the full error for debugging.
    """
    if os.environ.get("ENVIRONMENT", "development") == "production":
        return GENERIC_ERROR_MESSAGES.get(status_code, "An error occurred")
    else:
        return str(e)


# ==================== BRUTE FORCE PROTECTION (DragonflyDB-backed) ====================

# Redis client reference (set by server.py on startup via init_redis)
_redis = None

# Security constants for brute force protection
LOGIN_MAX_ATTEMPTS = 5  # Max failed attempts before lockout
LOGIN_LOCKOUT_MINUTES = 15  # Account lockout duration
LOGIN_ATTEMPT_WINDOW_MINUTES = 5  # Time window to count attempts
_LOGIN_KEY_TTL_SECONDS = int((LOGIN_LOCKOUT_MINUTES + LOGIN_ATTEMPT_WINDOW_MINUTES) * 60)


def init_redis(redis_client):
    """Initialize redis client for brute force protection (called from server.py on startup)"""
    global _redis
    _redis = redis_client


def get_client_ip(request: Request) -> str:
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


async def check_login_rate_limit(ip: str, email: str) -> tuple[bool, str | None]:
    """
    Check if login attempt is allowed (DragonflyDB-backed, works across workers).
    Returns (is_allowed, error_message).
    """
    if _redis is None:
        return True, None  # Fail open if redis unavailable

    key = f"ft:login:{ip}:{email.lower()}"
    try:
        data = await _redis.get(key)
        if data:
            record = json.loads(data)
            now = datetime.now(UTC)

            # Check if account is locked
            if record.get("locked_until"):
                locked_until = datetime.fromisoformat(record["locked_until"])
                if now < locked_until:
                    remaining = int((locked_until - now).total_seconds() // 60) + 1
                    return False, f"Account temporarily locked. Try again in {remaining} minutes."
                else:
                    # Lockout expired, remove key
                    await _redis.delete(key)
                    return True, None

            # Check if attempts exceed max within window
            if record["attempts"] >= LOGIN_MAX_ATTEMPTS:
                last_attempt = datetime.fromisoformat(record["last_attempt"])
                window_start = now - timedelta(minutes=LOGIN_ATTEMPT_WINDOW_MINUTES)
                if last_attempt > window_start:
                    # Lock the account
                    record["locked_until"] = (now + timedelta(minutes=LOGIN_LOCKOUT_MINUTES)).isoformat()
                    await _redis.set(key, json.dumps(record), ex=_LOGIN_KEY_TTL_SECONDS)
                    logger.warning(f"Account locked due to too many failed attempts: {email} from {ip}")
                    return False, f"Too many failed attempts. Account locked for {LOGIN_LOCKOUT_MINUTES} minutes."
    except Exception:
        return True, None  # Fail open if redis errors

    return True, None


async def record_failed_login(ip: str, email: str) -> None:
    """Record a failed login attempt in DragonflyDB"""
    if _redis is None:
        return

    key = f"ft:login:{ip}:{email.lower()}"
    now = datetime.now(UTC)

    try:
        data = await _redis.get(key)
        if data:
            record = json.loads(data)
            last_attempt = datetime.fromisoformat(record["last_attempt"])
            window_start = now - timedelta(minutes=LOGIN_ATTEMPT_WINDOW_MINUTES)

            if last_attempt > window_start:
                record["attempts"] += 1
            else:
                # Outside window, reset counter
                record["attempts"] = 1
            record["last_attempt"] = now.isoformat()
        else:
            record = {"attempts": 1, "last_attempt": now.isoformat(), "locked_until": None}

        await _redis.set(key, json.dumps(record), ex=_LOGIN_KEY_TTL_SECONDS)

        # Log failed attempt
        logger.warning(f"Failed login attempt {record['attempts']}/{LOGIN_MAX_ATTEMPTS} for {email} from {ip}")
    except Exception as e:
        logger.warning(f"Failed to record login attempt in redis: {e}")


async def clear_login_attempts(ip: str, email: str) -> None:
    """Clear login attempts after successful login"""
    if _redis is None:
        return

    key = f"ft:login:{ip}:{email.lower()}"
    try:
        await _redis.delete(key)
    except Exception as e:
        logger.warning(f"Failed to clear login attempts in redis: {e}")
