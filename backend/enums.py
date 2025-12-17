"""
FaithTracker Enums - Centralized enum definitions

All enum types used throughout the application for type safety and consistency.
"""

from enum import Enum


class EngagementStatus(str, Enum):
    """Member engagement status based on days since last contact."""
    ACTIVE = "active"
    AT_RISK = "at_risk"
    DISCONNECTED = "disconnected"


class EventType(str, Enum):
    """Types of pastoral care events."""
    BIRTHDAY = "birthday"
    CHILDBIRTH = "childbirth"
    GRIEF_LOSS = "grief_loss"
    NEW_HOUSE = "new_house"
    ACCIDENT_ILLNESS = "accident_illness"  # Merged hospital_visit into this
    FINANCIAL_AID = "financial_aid"
    REGULAR_CONTACT = "regular_contact"


class GriefStage(str, Enum):
    """Grief support timeline stages."""
    MOURNING = "mourning"
    ONE_WEEK = "1_week"
    TWO_WEEKS = "2_weeks"
    ONE_MONTH = "1_month"
    THREE_MONTHS = "3_months"
    SIX_MONTHS = "6_months"
    ONE_YEAR = "1_year"


class AidType(str, Enum):
    """Types of financial aid."""
    EDUCATION = "education"
    MEDICAL = "medical"
    EMERGENCY = "emergency"
    HOUSING = "housing"
    FOOD = "food"
    FUNERAL_COSTS = "funeral_costs"
    OTHER = "other"


class NotificationChannel(str, Enum):
    """Communication channels for notifications."""
    WHATSAPP = "whatsapp"
    EMAIL = "email"


class NotificationStatus(str, Enum):
    """Status of notification delivery."""
    SENT = "sent"
    FAILED = "failed"
    PENDING = "pending"


class UserRole(str, Enum):
    """User roles with different access levels."""
    FULL_ADMIN = "full_admin"      # Can access all campuses
    CAMPUS_ADMIN = "campus_admin"  # Can manage their campus only
    PASTOR = "pastor"              # Regular pastoral care staff


class ScheduleFrequency(str, Enum):
    """Frequency options for scheduled events."""
    ONE_TIME = "one_time"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ANNUALLY = "annually"


class WeekDay(str, Enum):
    """Days of the week."""
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class ActivityActionType(str, Enum):
    """Types of actions logged in activity stream."""
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
    CREATE_PASTORAL_NOTE = "create_pastoral_note"
    UPDATE_PASTORAL_NOTE = "update_pastoral_note"
    DELETE_PASTORAL_NOTE = "delete_pastoral_note"


class NoteCategory(str, Enum):
    """Categories for pastoral notes."""
    SPECIAL_NEEDS = "special_needs"
    HEALTH = "health"
    FINANCIAL = "financial"
    SPIRITUAL = "spiritual"
    FAMILY = "family"
    WORK = "work"
    OTHER = "other"
