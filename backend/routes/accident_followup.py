"""
Accident Followup Routes for FaithTracker Backend
Extracted from server.py for better modularity
"""
from datetime import datetime, timezone
from typing import Optional, Callable, Any, List

from litestar import get, post
from litestar.params import Parameter
from litestar.exceptions import HTTPException
from litestar.connection import Request

from dependencies import (
    get_db, get_current_user, get_campus_filter,
    safe_error_detail, logger
)
from constants import MAX_PAGE_NUMBER, MAX_LIMIT
from models import generate_uuid
from enums import ActivityActionType, EventType

# Callbacks to be injected from server.py
_invalidate_dashboard_cache: Optional[Callable] = None
_log_activity: Optional[Callable] = None
_get_campus_timezone: Optional[Callable] = None
_get_date_in_timezone: Optional[Callable] = None


def init_accident_followup_routes(
    invalidate_dashboard_cache: Callable,
    log_activity: Callable,
    get_campus_timezone: Callable,
    get_date_in_timezone: Callable
):
    """Initialize callbacks for accident followup routes"""
    global _invalidate_dashboard_cache, _log_activity
    global _get_campus_timezone, _get_date_in_timezone
    _invalidate_dashboard_cache = invalidate_dashboard_cache
    _log_activity = log_activity
    _get_campus_timezone = get_campus_timezone
    _get_date_in_timezone = get_date_in_timezone


@get("/accident-followup")
async def list_accident_followup(
    request: Request,
    completed: Optional[bool] = None,
    page: int = Parameter(default=1, ge=1, le=MAX_PAGE_NUMBER),
    limit: int = Parameter(default=50, ge=1, le=MAX_LIMIT),
) -> dict:
    """List all accident follow-up stages with pagination"""
    current_user = await get_current_user(request)
    db = get_db()
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
    db = get_db()
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
    db = get_db()
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
            "completed_at": datetime.now(timezone.utc),
            "completed_by_user_id": current_user["id"],
            "completed_by_user_name": current_user["name"],
            "updated_at": datetime.now(timezone.utc)
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
        campus_tz = await _get_campus_timezone(stage["campus_id"])
        today_date = _get_date_in_timezone(campus_tz)
        
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
            "completed_at": datetime.now(timezone.utc),
            "completed_by_user_id": current_user["id"],
            "completed_by_user_name": current_user["name"],
            "created_by_user_id": current_user["id"],
            "created_by_user_name": current_user["name"],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        })
        
        # Log activity
        await _log_activity(
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
            {"$set": {"last_contact_date": datetime.now(timezone.utc)}}
        )
        
        # Invalidate dashboard cache
        await _invalidate_dashboard_cache(stage["campus_id"])
        
        return {"success": True, "message": "Accident follow-up stage completed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing accident stage: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@post("/accident-followup/{stage_id:str}/undo")
async def undo_accident_stage(stage_id: str, request: Request) -> dict:
    """Undo completion or ignore of accident followup stage"""
    db = get_db()
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
        await _invalidate_dashboard_cache(stage["campus_id"])
        
        return {"success": True, "message": "Accident followup stage reset"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@post("/accident-followup/{stage_id:str}/ignore")
async def ignore_accident_stage(stage_id: str, request: Request) -> dict:
    """Mark an accident followup stage as ignored/dismissed"""
    current_user = await get_current_user(request)
    db = get_db()
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
                "ignored_at": datetime.now(timezone.utc),
                "ignored_by": current_user.get("id"),
                "ignored_by_name": current_user.get("name")
            }}
        )
        
        # Create timeline entry (will show in Timeline tab, NOT in Accident tab)
        campus_tz = await _get_campus_timezone(stage["campus_id"])
        today_date = _get_date_in_timezone(campus_tz)
        
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
            "ignored_at": datetime.now(timezone.utc),
            "ignored_by": current_user.get("id"),
            "ignored_by_name": current_user.get("name"),
            "created_by_user_id": current_user.get("id"),
            "created_by_user_name": current_user.get("name"),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        })
        
        # Log activity
        await _log_activity(
            campus_id=stage["campus_id"],
            user_id=current_user["id"],
            user_name=current_user["name"],
            action_type=ActivityActionType.IGNORE_TASK,
            member_id=stage["member_id"],
            member_name=member_name,
            care_event_id=timeline_event_id,
            event_type=EventType.ACCIDENT_ILLNESS,
            notes=f"Ignored accident/illness follow-up: {stage['stage'].replace('_', ' ')}",
            user_photo_url=current_user.get("photo_url")
        )
        
        # Invalidate dashboard cache
        await _invalidate_dashboard_cache(stage["campus_id"])
        
        return {"success": True, "message": "Accident followup ignored"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


# Export route handlers
route_handlers = [
    list_accident_followup,
    get_member_accident_timeline,
    complete_accident_stage,
    undo_accident_stage,
    ignore_accident_stage,
]
