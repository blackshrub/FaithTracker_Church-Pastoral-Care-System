"""FaithTracker Routes Package"""
from .campus import route_handlers as campus_handlers
from .auth import route_handlers as auth_handlers
from .members import route_handlers as member_handlers, init_member_routes
from .care_events import route_handlers as care_event_handlers, init_care_event_routes
from .grief_support import route_handlers as grief_support_handlers, init_grief_support_routes
from .accident_followup import route_handlers as accident_followup_handlers, init_accident_followup_routes
from .financial_aid import route_handlers as financial_aid_handlers, init_financial_aid_routes

__all__ = [
    'campus_handlers', 'auth_handlers', 
    'member_handlers', 'init_member_routes',
    'care_event_handlers', 'init_care_event_routes',
    'grief_support_handlers', 'init_grief_support_routes',
    'accident_followup_handlers', 'init_accident_followup_routes',
    'financial_aid_handlers', 'init_financial_aid_routes'
]
