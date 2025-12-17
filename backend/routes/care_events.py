"""
FaithTracker Care Event Routes
Handles care event CRUD, bulk operations, reminders, and visitation logs
"""

from litestar import get, post, put, delete, Request
from litestar.exceptions import HTTPException
from litestar.params import Parameter
import msgspec
import logging
import os
from datetime import datetime, timezone, date
from typing import Optional, List, Callable, Awaitable, Any, Dict

from enums import EventType, UserRole, ActivityActionType
from constants import MAX_PAGE_NUMBER, MAX_LIMIT
from models import (
    CareEvent, CareEventCreate, CareEventUpdate,
    VisitationLogEntry, AdditionalVisitRequest,
    to_mongo_doc, generate_uuid
)
from dependencies import (
    get_db, get_current_user, get_campus_filter, safe_error_detail
)

logger = logging.getLogger(__name__)

# Callbacks to server.py functions (set via init_care_event_routes)
_invalidate_dashboard_cache: Optional[Callable[[str], Awaitable[None]]] = None
_log_activity: Optional[Callable[..., Awaitable[None]]] = None
_send_whatsapp_message: Optional[Callable[..., Awaitable[dict]]] = None
_generate_grief_timeline: Optional[Callable[[date, str, str], List[Dict[str, Any]]]] = None
_generate_accident_followup_timeline: Optional[Callable[[date, str, str, str], List[Dict[str, Any]]]] = None
_get_campus_timezone: Optional[Callable[[str], Awaitable[str]]] = None
_get_date_in_timezone: Optional[Callable[[str], str]] = None


def init_care_event_routes(
    invalidate_dashboard_cache: Callable[[str], Awaitable[None]],
    log_activity: Callable[..., Awaitable[None]],
    send_whatsapp_message: Callable[..., Awaitable[dict]],
    generate_grief_timeline: Callable[[date, str, str], List[Dict[str, Any]]],
    generate_accident_followup_timeline: Callable[[date, str, str, str], List[Dict[str, Any]]],
    get_campus_timezone: Callable[[str], Awaitable[str]],
    get_date_in_timezone: Callable[[str], str],
):
    """Initialize care event routes with callbacks to server.py functions"""
    global _invalidate_dashboard_cache, _log_activity, _send_whatsapp_message
    global _generate_grief_timeline, _generate_accident_followup_timeline
    global _get_campus_timezone, _get_date_in_timezone
    
    _invalidate_dashboard_cache = invalidate_dashboard_cache
    _log_activity = log_activity
    _send_whatsapp_message = send_whatsapp_message
    _generate_grief_timeline = generate_grief_timeline
    _generate_accident_followup_timeline = generate_accident_followup_timeline
    _get_campus_timezone = get_campus_timezone
    _get_date_in_timezone = get_date_in_timezone


# ==================== BULK EVENT IDS MODEL ====================

class BulkEventIds(msgspec.Struct):
    """Request body for bulk operations"""
    event_ids: List[str]


# ==================== CARE EVENT ENDPOINTS ====================

@post("/care-events")
async def create_care_event(data: CareEventCreate, request: Request) -> dict:
    """Create a new care event"""
    current_user = await get_current_user(request)
    db = get_db()
    event = data  # Alias for backward compatibility
    try:
        # For campus-specific users, enforce their campus
        campus_id = event.campus_id
        if current_user.get("role") in [UserRole.CAMPUS_ADMIN.value, UserRole.PASTOR.value]:
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
            care_event.visitation_log = [to_mongo_doc(event.initial_visitation)]

        # Serialize for MongoDB using to_mongo_doc (handles all dates automatically)
        event_dict = to_mongo_doc(care_event)

        # Log what we're about to save for financial aid events
        if event.event_type == EventType.FINANCIAL_AID:
            logger.info(f"[FINANCIAL AID] Saving to DB: aid_type={repr(event_dict.get('aid_type'))}, aid_amount={repr(event_dict.get('aid_amount'))}")

        await db.care_events.insert_one(event_dict)
        
        # Log activity for creating the care event
        # For one-time events, log as COMPLETE_TASK since they're auto-completed
        action_type = ActivityActionType.COMPLETE_TASK if is_one_time else ActivityActionType.CREATE_CARE_EVENT
        action_note = f"{'Completed' if is_one_time else 'Created'} {event.event_type.value.replace('_', ' ')} event: {event.title}"
        
        if _log_activity:
            await _log_activity(
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
        if event.event_type == EventType.GRIEF_LOSS and _generate_grief_timeline:
            timeline = _generate_grief_timeline(
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
        if event.event_type == EventType.ACCIDENT_ILLNESS and _generate_accident_followup_timeline:
            timeline = _generate_accident_followup_timeline(
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
                    "last_contact_date": now,
                    "days_since_last_contact": 0,
                    "engagement_status": "active",
                    "updated_at": now
                }}
            )
        
        # Invalidate dashboard cache
        if _invalidate_dashboard_cache:
            await _invalidate_dashboard_cache(campus_id)
        
        return care_event
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating care event: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@get("/care-events")
async def list_care_events(
    request: Request,
    event_type: Optional[EventType] = None,
    member_id: Optional[str] = None,
    completed: Optional[bool] = None,
    page: int = Parameter(default=1, ge=1, le=MAX_PAGE_NUMBER),
    limit: int = Parameter(default=50, ge=1, le=MAX_LIMIT),
) -> list:
    """List care events with optional filters and pagination - optimized with $lookup"""
    current_user = await get_current_user(request)
    db = get_db()
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
    db = get_db()
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
    db = get_db()
    try:
        # Build query with campus filter for multi-tenancy
        query = {"id": event_id}
        campus_filter = get_campus_filter(current_user)
        if campus_filter:
            query.update(campus_filter)

        event = await db.care_events.find_one(query, {"_id": 0})
        if not event:
            raise HTTPException(status_code=404, detail="Care event not found")

        update_data = {k: v for k, v in to_mongo_doc(data).items() if v is not None}
        update_data["updated_at"] = datetime.now(timezone.utc)

        result = await db.care_events.update_one(
            {"id": event_id},
            {"$set": update_data}
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Care event not found")

        # Return updated event
        updated_event = await db.care_events.find_one({"id": event_id}, {"_id": 0})
        return updated_event
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating care event: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@post("/care-events/{event_id:str}/complete")
async def complete_care_event(event_id: str, request: Request) -> dict:
    """Mark care event as completed and update member engagement"""
    current_user = await get_current_user(request)
    db = get_db()
    try:
        # Get the care event with campus filter for multi-tenancy
        query = {"id": event_id}
        campus_filter = get_campus_filter(current_user)
        if campus_filter:
            query.update(campus_filter)
        event = await db.care_events.find_one(query, {"_id": 0})
        if not event:
            raise HTTPException(status_code=404, detail="Care event not found")

        # Idempotency check: if already completed, return success without re-processing
        # This prevents duplicate activity logs and "Birthday Contact" events on double-clicks
        if event.get("completed"):
            return {"success": True, "message": "Care event already completed"}

        # Get member name for logging
        member = await db.members.find_one({"id": event["member_id"]}, {"_id": 0})
        member_name = member["name"] if member else "Unknown"
        
        # Mark event as completed
        result = await db.care_events.update_one(
            {"id": event_id},
            {"$set": {
                "completed": True,
                "completed_at": datetime.now(timezone.utc),
                "completed_by_user_id": current_user["id"],
                "completed_by_user_name": current_user["name"],
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Care event not found")
        
        # Log activity
        if _log_activity:
            await _log_activity(
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
                "last_contact_date": now,
                "days_since_last_contact": 0,
                "engagement_status": "active",
                "updated_at": now
            }}
        )
        
        # For birthday completions, also create a regular contact event for timeline
        if event["event_type"] == "birthday" and _get_campus_timezone and _get_date_in_timezone:
            # Get campus timezone for correct date
            campus_tz = await _get_campus_timezone(event["campus_id"])
            today_date = _get_date_in_timezone(campus_tz)
            
            contact_event = {
                "id": generate_uuid(),
                "member_id": event["member_id"],
                "campus_id": event["campus_id"],
                "event_type": "regular_contact",
                "event_date": today_date,  # Use campus timezone date
                "title": "Birthday Contact",
                "description": f"Contacted {member_name} for their birthday celebration",
                "completed": True,
                "completed_at": now,
                "completed_by_user_id": current_user["id"],
                "completed_by_user_name": current_user["name"],
                "reminder_sent": False,
                "created_at": now,
                "updated_at": now
            }
            
            await db.care_events.insert_one(contact_event)
        
        # Invalidate dashboard cache after completing event
        if _invalidate_dashboard_cache:
            await _invalidate_dashboard_cache(event["campus_id"])
        
        return {"success": True, "message": "Care event marked as completed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing care event: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))

# NOTE: ignore_care_event and delete_care_event remain in server.py
# due to complex interdependencies with grief/accident stages


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
    db = get_db()
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
            "completed_at": datetime.now(timezone.utc),
            "completed_by_user_id": current_user["id"],
            "completed_by_user_name": current_user["name"],
            "created_by_user_id": current_user["id"],
            "created_by_user_name": current_user["name"],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        await db.care_events.insert_one(additional_visit)
        
        # Log activity
        if _log_activity:
            await _log_activity(
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
                "last_contact_date": datetime.now(timezone.utc),
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


@post("/care-events/{event_id:str}/send-reminder")
async def send_care_event_reminder(event_id: str, request: Request) -> dict:
    """Send WhatsApp reminder for care event"""
    current_user = await get_current_user(request)
    db = get_db()
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
        
        if not _send_whatsapp_message:
            raise HTTPException(status_code=500, detail="WhatsApp service not configured")
        
        result = await _send_whatsapp_message(
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
                    "reminder_sent_at": datetime.now(timezone.utc),
                    "reminder_sent_by_user_id": current_user["id"],
                    "reminder_sent_by_user_name": current_user["name"]
                }}
            )
            
            # Log activity
            if _log_activity:
                await _log_activity(
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
    db = get_db()
    try:
        event = await db.care_events.find_one({"id": event_id}, {"_id": 0})
        if not event:
            raise HTTPException(status_code=404, detail="Care event not found")
        
        log_entry = to_mongo_doc(entry)
        
        await db.care_events.update_one(
            {"id": event_id},
            {
                "$push": {"visitation_log": log_entry},
                "$set": {"updated_at": datetime.now(timezone.utc)}
            }
        )
        
        return {"success": True, "message": "Visitation log added"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding visitation log: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@get("/care-events/hospital/due-followup")
async def get_hospital_followup_due() -> list:
    """Get accident/illness events needing follow-up"""
    db = get_db()
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
            event_date_val = event.get('event_date')
            if isinstance(event_date_val, str):
                event_date_val = date.fromisoformat(event_date_val)
            
            days_since_event = (today - event_date_val).days
            
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


# ==================== BULK CARE EVENT OPERATIONS ====================

@post("/care-events/bulk-complete")
async def bulk_complete_care_events(request: Request, data: BulkEventIds) -> dict:
    """
    Mark multiple care events as completed in a single operation.

    Significantly faster than individual completions for batch processing.
    Returns count of successfully completed events.
    """
    current_user = await get_current_user(request)
    db = get_db()
    try:
        event_ids = data.event_ids
        if not event_ids:
            raise HTTPException(status_code=400, detail="No event IDs provided")

        if len(event_ids) > 100:
            raise HTTPException(status_code=400, detail="Maximum 100 events per bulk operation")

        # Build query with campus filter for multi-tenancy
        query = {"id": {"$in": event_ids}, "completed": {"$ne": True}}
        campus_filter = get_campus_filter(current_user)
        if campus_filter:
            query.update(campus_filter)

        # Get events to process (for logging)
        events = await db.care_events.find(query, {"_id": 0}).to_list(None)
        if not events:
            return {"success": True, "completed_count": 0, "message": "No pending events found"}

        # Bulk update
        now = datetime.now(timezone.utc)
        result = await db.care_events.update_many(
            query,
            {"$set": {
                "completed": True,
                "completed_at": now,
                "completed_by_user_id": current_user["id"],
                "completed_by_user_name": current_user["name"],
                "updated_at": now
            }}
        )

        # Log activity for each completed event (batch)
        if _log_activity:
            for event in events:
                member = await db.members.find_one({"id": event["member_id"]}, {"name": 1, "_id": 0})
                member_name = member["name"] if member else "Unknown"
                await _log_activity(
                    campus_id=event["campus_id"],
                    user_id=current_user["id"],
                    user_name=current_user["name"],
                    action_type=ActivityActionType.COMPLETE_TASK,
                    member_id=event["member_id"],
                    member_name=member_name,
                    care_event_id=event["id"],
                    event_type=EventType(event["event_type"]) if event.get("event_type") else None,
                    notes=f"Bulk completed {event.get('event_type', 'care')} task",
                    user_photo_url=current_user.get("photo_url")
                )

        # Update engagement status for affected members
        member_ids = list(set(e["member_id"] for e in events))
        for member_id in member_ids:
            await db.members.update_one(
                {"id": member_id},
                {"$set": {
                    "last_contact_date": now,
                    "updated_at": now
                }}
            )

        logger.info(f"Bulk completed {result.modified_count} care events by {current_user['name']}")
        return {
            "success": True,
            "completed_count": result.modified_count,
            "message": f"Successfully completed {result.modified_count} care events"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk complete: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@post("/care-events/bulk-ignore")
async def bulk_ignore_care_events(request: Request, data: BulkEventIds) -> dict:
    """
    Mark multiple care events as ignored in a single operation.

    Useful for batch dismissing irrelevant or outdated events.
    Returns count of successfully ignored events.
    """
    current_user = await get_current_user(request)
    db = get_db()
    try:
        event_ids = data.event_ids
        if not event_ids:
            raise HTTPException(status_code=400, detail="No event IDs provided")

        if len(event_ids) > 100:
            raise HTTPException(status_code=400, detail="Maximum 100 events per bulk operation")

        # Build query with campus filter
        query = {"id": {"$in": event_ids}, "ignored": {"$ne": True}}
        campus_filter = get_campus_filter(current_user)
        if campus_filter:
            query.update(campus_filter)

        # Get events to process (for logging)
        events = await db.care_events.find(query, {"_id": 0}).to_list(None)
        if not events:
            return {"success": True, "ignored_count": 0, "message": "No pending events found"}

        # Bulk update
        now = datetime.now(timezone.utc)
        result = await db.care_events.update_many(
            query,
            {"$set": {
                "ignored": True,
                "ignored_at": now,
                "ignored_by_user_id": current_user["id"],
                "ignored_by_user_name": current_user["name"],
                "updated_at": now
            }}
        )

        # Log activity for each ignored event
        if _log_activity:
            for event in events:
                member = await db.members.find_one({"id": event["member_id"]}, {"name": 1, "_id": 0})
                member_name = member["name"] if member else "Unknown"
                await _log_activity(
                    campus_id=event["campus_id"],
                    user_id=current_user["id"],
                    user_name=current_user["name"],
                    action_type=ActivityActionType.IGNORE_TASK,
                    member_id=event["member_id"],
                    member_name=member_name,
                    care_event_id=event["id"],
                    event_type=EventType(event["event_type"]) if event.get("event_type") else None,
                    notes=f"Bulk ignored {event.get('event_type', 'care')} task",
                    user_photo_url=current_user.get("photo_url")
                )

        logger.info(f"Bulk ignored {result.modified_count} care events by {current_user['name']}")
        return {
            "success": True,
            "ignored_count": result.modified_count,
            "message": f"Successfully ignored {result.modified_count} care events"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk ignore: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@post("/care-events/bulk-delete")
async def bulk_delete_care_events(request: Request, data: BulkEventIds) -> dict:
    """
    Delete multiple care events in a single operation.

    WARNING: This is a destructive operation. Events cannot be recovered.
    Returns count of successfully deleted events.
    """
    current_user = await get_current_user(request)
    db = get_db()
    try:
        event_ids = data.event_ids
        if not event_ids:
            raise HTTPException(status_code=400, detail="No event IDs provided")

        if len(event_ids) > 50:
            raise HTTPException(status_code=400, detail="Maximum 50 events per bulk delete")

        # Build query with campus filter
        query = {"id": {"$in": event_ids}}
        campus_filter = get_campus_filter(current_user)
        if campus_filter:
            query.update(campus_filter)

        # Get events to process (for logging and cleanup)
        events = await db.care_events.find(query, {"_id": 0}).to_list(None)
        if not events:
            return {"success": True, "deleted_count": 0, "message": "No events found"}

        # Delete the events
        result = await db.care_events.delete_many(query)

        # Clean up related data and log activity
        if _log_activity:
            for event in events:
                # Delete related activity logs
                await db.activity_logs.delete_many({"care_event_id": event["id"]})

                # Log the deletion
                member = await db.members.find_one({"id": event["member_id"]}, {"name": 1, "_id": 0})
                member_name = member["name"] if member else "Unknown"
                await _log_activity(
                    campus_id=event["campus_id"],
                    user_id=current_user["id"],
                    user_name=current_user["name"],
                    action_type=ActivityActionType.DELETE_EVENT,
                    member_id=event["member_id"],
                    member_name=member_name,
                    care_event_id=event["id"],
                    event_type=EventType(event["event_type"]) if event.get("event_type") else None,
                    notes=f"Bulk deleted {event.get('event_type', 'care')} event",
                    user_photo_url=current_user.get("photo_url")
                )

        logger.info(f"Bulk deleted {result.deleted_count} care events by {current_user['name']}")
        return {
            "success": True,
            "deleted_count": result.deleted_count,
            "message": f"Successfully deleted {result.deleted_count} care events"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk delete: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


# Route handlers list for server.py to include
# Note: ignore_care_event and delete_care_event remain in server.py
# due to complex interdependencies with grief/accident stages
route_handlers = [
    create_care_event,
    list_care_events,
    get_care_event,
    update_care_event,
    complete_care_event,
    log_additional_visit,
    send_care_event_reminder,
    add_visitation_log,
    get_hospital_followup_due,
    bulk_complete_care_events,
    bulk_ignore_care_events,
    bulk_delete_care_events,
]
