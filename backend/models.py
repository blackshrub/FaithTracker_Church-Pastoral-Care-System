"""
FaithTracker Models - msgspec Struct definitions

All data models used throughout the application.
Using msgspec.Struct instead of Pydantic BaseModel for faster serialization.
"""

import re
import uuid
import secrets
import logging
from datetime import datetime, date, timezone
from typing import Annotated, List, Dict, Any, Optional

import msgspec
from msgspec import Struct, field, UNSET, UnsetType

from enums import (
    EngagementStatus, EventType, GriefStage, AidType,
    NotificationChannel, NotificationStatus, UserRole,
    ScheduleFrequency, WeekDay, ActivityActionType, NoteCategory
)

logger = logging.getLogger(__name__)

# ==================== UUID UTILITIES ====================

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


# ==================== CAMPUS MODELS ====================

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


# ==================== MEMBER MODELS ====================

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


# ==================== CARE EVENT MODELS ====================

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


# ==================== SETUP MODELS ====================

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


# ==================== GRIEF SUPPORT MODELS ====================

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


# ==================== NOTIFICATION MODELS ====================

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


# ==================== FINANCIAL AID MODELS ====================

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


class FinancialAidScheduleCreate(Struct):
    """Create a financial aid schedule"""
    member_id: str
    title: str
    aid_type: str  # AidType enum value as string
    aid_amount: float
    frequency: str  # ScheduleFrequency enum value as string
    start_date: str  # ISO date string
    end_date: str | None = None
    day_of_week: str | None = None  # WeekDay enum value
    day_of_month: int | None = None
    month_of_year: int | None = None
    notes: str | None = None


# ==================== SETTINGS MODELS ====================

class AutomationSettingsUpdate(Struct):
    """Automation settings (daily digest time, WhatsApp gateway)"""
    digestTime: str = "08:00"
    whatsappGateway: str = ""
    enabled: bool = True


class OverdueWriteoffSettingsUpdate(Struct):
    """Overdue task writeoff settings"""
    days: int = 30
    enabled: bool = False


class EngagementSettingsUpdate(Struct):
    """Engagement threshold settings"""
    active_days: int = 60
    at_risk_days: int = 90


class UserPreferencesUpdate(Struct):
    """User preferences for notifications, etc."""
    email_notifications: bool = True
    whatsapp_notifications: bool = True


# ==================== PASTORAL NOTES MODELS ====================

class PastoralNoteCreate(Struct):
    member_id: str
    title: Annotated[str, msgspec.Meta(min_length=1, max_length=200)]
    content: Annotated[str, msgspec.Meta(min_length=1, max_length=10000)]
    category: str | None = None
    is_private: bool = False
    follow_up_date: str | None = None
    follow_up_notes: str | None = None


class PastoralNoteUpdate(Struct):
    title: Annotated[str, msgspec.Meta(min_length=1, max_length=200)] | None = None
    content: Annotated[str, msgspec.Meta(min_length=1, max_length=10000)] | None = None
    category: str | None = None
    is_private: bool | None = None
    follow_up_date: str | None = None
    follow_up_notes: str | None = None
    follow_up_completed: bool | None = None


# ==================== USER MODELS ====================

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


# ==================== ACTIVITY LOG MODELS ====================

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
    webhook_secret: str = field(default_factory=lambda: secrets.token_hex(32))  # Full 256-bit entropy for HMAC-SHA256
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
