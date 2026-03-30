"""FaithTracker Routes Package"""

from .accident_followup import init_accident_followup_routes
from .accident_followup import route_handlers as accident_followup_handlers
from .auth import route_handlers as auth_handlers
from .campus import route_handlers as campus_handlers
from .care_events import init_care_event_routes
from .care_events import route_handlers as care_event_handlers
from .dashboard import init_dashboard_routes
from .dashboard import route_handlers as dashboard_handlers
from .financial_aid import init_financial_aid_routes
from .financial_aid import route_handlers as financial_aid_handlers
from .grief_support import init_grief_support_routes
from .grief_support import route_handlers as grief_support_handlers
from .members import init_member_routes
from .members import route_handlers as member_handlers

__all__ = [
    "accident_followup_handlers",
    "auth_handlers",
    "campus_handlers",
    "care_event_handlers",
    "dashboard_handlers",
    "financial_aid_handlers",
    "grief_support_handlers",
    "init_accident_followup_routes",
    "init_care_event_routes",
    "init_dashboard_routes",
    "init_financial_aid_routes",
    "init_grief_support_routes",
    "init_member_routes",
    "member_handlers",
]
