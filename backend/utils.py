"""
FaithTracker Utils - Pure utility functions

Validation, caching, and helper functions that don't depend on database.
"""

import re
from datetime import datetime, timezone
from typing import Optional, Any

from enums import EngagementStatus
from constants import (
    ENGAGEMENT_AT_RISK_DAYS_DEFAULT,
    ENGAGEMENT_DISCONNECTED_DAYS_DEFAULT,
    ENGAGEMENT_NO_CONTACT_DAYS
)

# ==================== REGEX PATTERNS ====================

# Email validation pattern (RFC 5322 simplified)
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

# Phone validation: digits only after stripping, reasonable length
PHONE_PATTERN = re.compile(r'^\+?[0-9]{7,15}$')


# ==================== PASSWORD CONSTANTS ====================

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128


# ==================== VALIDATION FUNCTIONS ====================

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


def validate_email(email: str) -> bool:
    """Validate email format with additional security checks"""
    if not email:
        return False
    # RFC 5321 length limit
    if len(email) > 254:
        return False
    # Check for consecutive dots (invalid per RFC)
    if ".." in email:
        return False
    # Check for leading/trailing dots in local part
    local_part = email.split("@")[0] if "@" in email else ""
    if local_part.startswith(".") or local_part.endswith("."):
        return False
    return bool(EMAIL_PATTERN.match(email))


def validate_phone(phone: str) -> bool:
    """Validate phone number format"""
    if not phone:
        return True  # Empty phone is allowed (optional field)
    # Strip common separators for validation
    cleaned = phone.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    return bool(PHONE_PATTERN.match(cleaned))


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validate password with basic length requirements.

    Requirements:
    - Minimum 8 characters
    - Maximum 128 characters (prevent DoS via bcrypt)

    Returns:
        (is_valid, error_message)
    """
    if not password:
        return False, "Password is required"

    if len(password) < PASSWORD_MIN_LENGTH:
        return False, f"Password must be at least {PASSWORD_MIN_LENGTH} characters"

    if len(password) > PASSWORD_MAX_LENGTH:
        return False, f"Password must be at most {PASSWORD_MAX_LENGTH} characters"

    return True, ""


# ==================== PHONE NORMALIZATION ====================

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


# ==================== ENGAGEMENT STATUS ====================

def calculate_engagement_status(
    last_contact: Optional[datetime],
    at_risk_days: int = ENGAGEMENT_AT_RISK_DAYS_DEFAULT,
    disconnected_days: int = ENGAGEMENT_DISCONNECTED_DAYS_DEFAULT
) -> tuple[EngagementStatus, int]:
    """
    Calculate engagement status and days since last contact.
    
    Args:
        last_contact: Last contact datetime (can be None or string)
        at_risk_days: Days threshold for at-risk status (default from constants)
        disconnected_days: Days threshold for disconnected status (default from constants)
    
    Returns:
        Tuple of (EngagementStatus, days_since_last_contact)
    """
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


# ==================== CACHE ====================

# Simple in-memory cache for static data
_cache: dict = {}
_cache_timestamps: dict = {}


def get_from_cache(key: str, ttl_seconds: int = 300) -> Optional[Any]:
    """
    Get value from cache if not expired.

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
    Store value in cache with current timestamp.

    Args:
        key: Cache key
        value: Value to cache
    """
    _cache[key] = value
    _cache_timestamps[key] = datetime.now(timezone.utc)


def invalidate_cache(pattern: Optional[str] = None) -> None:
    """
    Invalidate cache entries.

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
