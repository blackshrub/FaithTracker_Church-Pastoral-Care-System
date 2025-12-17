"""
FaithTracker Constants - Centralized configuration values

All magic numbers and configuration constants used throughout the application.
These can be overridden by settings stored in the database.
"""

# ==================== ENGAGEMENT STATUS THRESHOLDS ====================
# (defaults - can be overridden by church settings)
ENGAGEMENT_AT_RISK_DAYS_DEFAULT = 60
ENGAGEMENT_DISCONNECTED_DAYS_DEFAULT = 90
ENGAGEMENT_NO_CONTACT_DAYS = 999  # Used when member has never been contacted

# ==================== GRIEF SUPPORT TIMELINE ====================
# Days after mourning date for each follow-up stage
GRIEF_ONE_WEEK_DAYS = 7
GRIEF_TWO_WEEKS_DAYS = 14
GRIEF_ONE_MONTH_DAYS = 30
GRIEF_THREE_MONTHS_DAYS = 90
GRIEF_SIX_MONTHS_DAYS = 180
GRIEF_ONE_YEAR_DAYS = 365

# ==================== ACCIDENT/ILLNESS FOLLOW-UP TIMELINE ====================
# Days after event for follow-up visits
ACCIDENT_FIRST_FOLLOWUP_DAYS = 3
ACCIDENT_SECOND_FOLLOWUP_DAYS = 7
ACCIDENT_FINAL_FOLLOWUP_DAYS = 14

# ==================== REMINDER SETTINGS ====================
# Default days before event to send reminder
DEFAULT_REMINDER_DAYS_BIRTHDAY = 7
DEFAULT_REMINDER_DAYS_CHILDBIRTH = 14
DEFAULT_REMINDER_DAYS_FINANCIAL_AID = 0
DEFAULT_REMINDER_DAYS_ACCIDENT_ILLNESS = 14
DEFAULT_REMINDER_DAYS_GRIEF_SUPPORT = 14

# ==================== JWT TOKEN SETTINGS ====================
JWT_TOKEN_EXPIRE_HOURS = 4  # Reduced from 24h for better security

# ==================== PAGINATION ====================
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 1000
MAX_PAGE_NUMBER = 10000
MAX_LIMIT = 2000

# ==================== DASHBOARD/ANALYTICS ====================
DEFAULT_ANALYTICS_DAYS = 30
DEFAULT_UPCOMING_DAYS = 7

# ==================== FILE UPLOAD LIMITS ====================
# Size limits in bytes
MAX_IMAGE_SIZE = 10 * 1024 * 1024      # 10 MB for images
MAX_CSV_SIZE = 5 * 1024 * 1024         # 5 MB for CSV imports
MAX_REQUEST_BODY_SIZE = 15 * 1024 * 1024  # 15 MB max request body

# ==================== IMAGE VALIDATION ====================
# Magic bytes for allowed image types (security: validate file content, not just Content-Type)
IMAGE_MAGIC_BYTES = {
    b'\xff\xd8\xff': 'image/jpeg',           # JPEG
    b'\x89PNG\r\n\x1a\n': 'image/png',       # PNG
    b'GIF87a': 'image/gif',                   # GIF87a
    b'GIF89a': 'image/gif',                   # GIF89a
    b'RIFF': 'image/webp',                    # WebP (partial check)
}
