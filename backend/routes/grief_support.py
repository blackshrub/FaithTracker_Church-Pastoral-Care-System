"""
FaithTracker Grief Support Routes
Handles grief support timeline management, stage completion, and reminders
"""

import logging
import os
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from litestar import Request, get, post
from litestar.exceptions import HTTPException
from litestar.params import Parameter

from constants import MAX_LIMIT, MAX_PAGE_NUMBER
from dependencies import get_campus_filter, get_current_user, get_db, safe_error_detail
from enums import ActivityActionType, EventType
from models import generate_uuid

logger = logging.getLogger(__name__)

# Callbacks to server.py functions (set via init_grief_support_routes)
_invalidate_dashboard_cache: Callable[[str], Awaitable[None]] | None = None
_log_activity: Callable[..., Awaitable[None]] | None = None
_send_whatsapp_message: Callable[..., Awaitable[dict]] | None = None
_get_campus_timezone: Callable[[str], Awaitable[str]] | None = None
_get_date_in_timezone: Callable[[str], str] | None = None


def _assert_initialized():
    """Verify all callbacks have been set. Call at the start of mutating handlers."""
    missing = [
        name
        for name, val in [
            ("_invalidate_dashboard_cache", _invalidate_dashboard_cache),
            ("_log_activity", _log_activity),
            ("_send_whatsapp_message", _send_whatsapp_message),
            ("_get_campus_timezone", _get_campus_timezone),
            ("_get_date_in_timezone", _get_date_in_timezone),
        ]
        if val is None
    ]
    if missing:
        raise RuntimeError(
            f"Grief support routes not initialized. Missing callbacks: {', '.join(missing)}. "
            "Call init_grief_support_routes() during app startup."
        )


def init_grief_support_routes(
    invalidate_dashboard_cache: Callable[[str], Awaitable[None]],
    log_activity: Callable[..., Awaitable[None]],
    send_whatsapp_message: Callable[..., Awaitable[dict]],
    get_campus_timezone: Callable[[str], Awaitable[str]],
    get_date_in_timezone: Callable[[str], str],
):
    """Initialize grief support routes with callbacks to server.py functions"""
    global _invalidate_dashboard_cache, _log_activity, _send_whatsapp_message
    global _get_campus_timezone, _get_date_in_timezone

    _invalidate_dashboard_cache = invalidate_dashboard_cache
    _log_activity = log_activity
    _send_whatsapp_message = send_whatsapp_message
    _get_campus_timezone = get_campus_timezone
    _get_date_in_timezone = get_date_in_timezone


# ==================== GRIEF SUPPORT ENDPOINTS ====================


@get("/grief-support")
async def list_grief_support(
    request: Request,
    completed: bool | None = None,
    page: int = Parameter(default=1, ge=1, le=MAX_PAGE_NUMBER),
    limit: int = Parameter(default=50, ge=1, le=MAX_LIMIT),
) -> dict:
    """List grief support stages with pagination"""
    current_user = await get_current_user(request)
    db = get_db()
    try:
        query = get_campus_filter(current_user)
        if completed is not None:
            query["completed"] = completed

        skip = (page - 1) * limit
        stages = (
            await db.grief_support.find(query, {"_id": 0})
            .sort("scheduled_date", 1)
            .skip(skip)
            .limit(limit)
            .to_list(limit)
        )
        return stages
    except Exception as e:
        logger.error(f"Error listing grief support: {e!s}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@get("/grief-support/member/{member_id:str}")
async def get_member_grief_timeline(member_id: str, request: Request) -> dict:
    """Get grief timeline for specific member"""
    current_user = await get_current_user(request)
    db = get_db()
    try:
        # Build query with campus filter
        query = {"member_id": member_id}
        campus_filter = get_campus_filter(current_user)
        query.update(campus_filter)

        timeline = await db.grief_support.find(query, {"_id": 0}).sort("scheduled_date", 1).to_list(100)

        return timeline
    except Exception as e:
        logger.error(f"Error getting member grief timeline: {e!s}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@post("/grief-support/{stage_id:str}/complete")
async def complete_grief_stage(stage_id: str, request: Request, notes: str | None = None) -> dict:
    """Mark grief stage as completed with notes"""
    _assert_initialized()
    current_user = await get_current_user(request)
    db = get_db()
    try:
        # Scope by campus so a user from one campus cannot complete a stage
        # belonging to another by guessing/enumerating stage IDs.
        campus_filter = get_campus_filter(current_user)
        stage = await db.grief_support.find_one({"id": stage_id, **campus_filter}, {"_id": 0})
        if not stage:
            raise HTTPException(status_code=404, detail="Grief stage not found")

        # Idempotency guard: a double-tap or retry must not insert another
        # care_events row + activity_log row for the same completion.
        if stage.get("completed"):
            return {"success": True, "message": "Grief stage already completed"}

        # Get member name for logging
        member = await db.members.find_one({"id": stage["member_id"]}, {"_id": 0, "name": 1})
        member_name = member["name"] if member else "Unknown"

        update_data = {
            "completed": True,
            "completed_at": datetime.now(UTC),
            "completed_by_user_id": current_user["id"],
            "completed_by_user_name": current_user["name"],
            "updated_at": datetime.now(UTC),
        }

        if notes:
            update_data["notes"] = notes

        result = await db.grief_support.update_one({"id": stage_id}, {"$set": update_data})

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Grief stage not found")

        # Create timeline entry (will show in Timeline tab, NOT in Grief tab)
        # This entry does NOT have care_event_id, so it won't appear in Grief tab filter
        campus_tz = await _get_campus_timezone(stage["campus_id"])
        today_date = _get_date_in_timezone(campus_tz)

        timeline_event_id = generate_uuid()
        await db.care_events.insert_one(
            {
                "id": timeline_event_id,
                "member_id": stage["member_id"],
                "campus_id": stage["campus_id"],
                "event_type": "grief_loss",
                "event_date": today_date,
                "title": f"Grief Support: {stage['stage'].replace('_', ' ')}",
                "description": "Completed grief follow-up stage" + (f"\n\nNotes: {notes}" if notes else ""),
                "grief_stage_id": stage_id,  # Link for undo (but NOT care_event_id)
                "completed": True,
                "completed_at": datetime.now(UTC),
                "completed_by_user_id": current_user["id"],
                "completed_by_user_name": current_user["name"],
                "created_by_user_id": current_user["id"],
                "created_by_user_name": current_user["name"],
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            }
        )

        # Log activity
        await _log_activity(
            campus_id=stage["campus_id"],
            user_id=current_user["id"],
            user_name=current_user["name"],
            action_type=ActivityActionType.COMPLETE_TASK,
            member_id=stage["member_id"],
            member_name=member_name,
            care_event_id=timeline_event_id,
            event_type=EventType.GRIEF_LOSS,
            notes=f"Completed grief support stage: {stage['stage'].replace('_', ' ')}",
            user_photo_url=current_user.get("photo_url"),
        )

        # Update member's last contact date
        await db.members.update_one({"id": stage["member_id"]}, {"$set": {"last_contact_date": datetime.now(UTC)}})

        # Invalidate dashboard cache
        await _invalidate_dashboard_cache(stage["campus_id"])

        return {"success": True, "message": "Grief stage marked as completed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing grief stage: {e!s}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@post("/grief-support/{stage_id:str}/ignore")
async def ignore_grief_stage(stage_id: str, request: Request) -> dict:
    """Mark a grief support stage as ignored/dismissed"""
    _assert_initialized()
    current_user = await get_current_user(request)
    db = get_db()
    try:
        campus_filter = get_campus_filter(current_user)
        stage = await db.grief_support.find_one({"id": stage_id, **campus_filter}, {"_id": 0})
        if not stage:
            raise HTTPException(status_code=404, detail="Grief stage not found")

        # Idempotency: don't insert a second "ignored" timeline entry on retry.
        if stage.get("ignored") or stage.get("completed"):
            return {"success": True, "message": "Grief stage already resolved"}

        # Get member name for logging
        member = await db.members.find_one({"id": stage["member_id"]}, {"_id": 0, "name": 1})
        member_name = member["name"] if member else "Unknown"

        await db.grief_support.update_one(
            {"id": stage_id},
            {
                "$set": {
                    "ignored": True,
                    "ignored_at": datetime.now(UTC),
                    "ignored_by": current_user.get("id"),
                    "ignored_by_name": current_user.get("name"),
                }
            },
        )

        # Create timeline entry (will show in Timeline tab, NOT in Grief tab)
        campus_tz = await _get_campus_timezone(stage["campus_id"])
        today_date = _get_date_in_timezone(campus_tz)

        timeline_event_id = generate_uuid()
        await db.care_events.insert_one(
            {
                "id": timeline_event_id,
                "member_id": stage["member_id"],
                "campus_id": stage["campus_id"],
                "event_type": "grief_loss",
                "event_date": today_date,
                "title": f"Grief Support: {stage['stage'].replace('_', ' ')} (Ignored)",
                "description": "Stage was marked as ignored/not applicable",
                "grief_stage_id": stage_id,  # Link for undo (but NOT care_event_id)
                "ignored": True,
                "ignored_at": datetime.now(UTC),
                "ignored_by": current_user.get("id"),
                "ignored_by_name": current_user.get("name"),
                "created_by_user_id": current_user.get("id"),
                "created_by_user_name": current_user.get("name"),
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            }
        )

        # Log activity
        await _log_activity(
            campus_id=stage["campus_id"],
            user_id=current_user["id"],
            user_name=current_user["name"],
            action_type=ActivityActionType.IGNORE_TASK,
            member_id=stage["member_id"],
            member_name=member_name,
            care_event_id=timeline_event_id,
            event_type=EventType.GRIEF_LOSS,
            notes=f"Ignored grief support stage: {stage['stage'].replace('_', ' ')}",
            user_photo_url=current_user.get("photo_url"),
        )

        # Invalidate dashboard cache
        await _invalidate_dashboard_cache(stage["campus_id"])

        return {"success": True, "message": "Grief stage ignored"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@post("/grief-support/{stage_id:str}/undo")
async def undo_grief_stage(stage_id: str, request: Request) -> dict:
    """Undo completion or ignore of grief support stage"""
    _assert_initialized()
    current_user = await get_current_user(request)
    db = get_db()
    try:
        campus_filter = get_campus_filter(current_user)
        stage = await db.grief_support.find_one({"id": stage_id, **campus_filter}, {"_id": 0})
        if not stage:
            raise HTTPException(status_code=404, detail="Grief stage not found")

        # Delete timeline entries created for this stage (linked by grief_stage_id)
        await db.care_events.delete_many({"grief_stage_id": stage_id, **campus_filter})

        # Delete activity logs related to this grief stage — explicitly scope by
        # campus_id so the regex cannot accidentally match unrelated activity in
        # another campus.
        await db.activity_logs.delete_many(
            {
                "member_id": stage["member_id"],
                "campus_id": stage["campus_id"],
                "notes": {"$regex": f"{stage['stage'].replace('_', ' ')}", "$options": "i"},
            }
        )

        # Reset the grief stage
        await db.grief_support.update_one(
            {"id": stage_id},
            {
                "$set": {
                    "completed": False,
                    "completed_at": None,
                    "completed_by_user_id": None,
                    "completed_by_user_name": None,
                    "ignored": False,
                    "ignored_at": None,
                    "ignored_by": None,
                    "ignored_by_name": None,
                }
            },
        )

        # Invalidate dashboard cache
        await _invalidate_dashboard_cache(stage["campus_id"])

        return {"success": True, "message": "Grief support stage reset"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@post("/grief-support/{stage_id:str}/send-reminder")
async def send_grief_reminder(stage_id: str, request: Request) -> dict:
    """Send WhatsApp reminder for grief stage"""
    _assert_initialized()
    current_user = await get_current_user(request)
    db = get_db()
    try:
        campus_filter = get_campus_filter(current_user)
        stage = await db.grief_support.find_one({"id": stage_id, **campus_filter}, {"_id": 0})
        if not stage:
            raise HTTPException(status_code=404, detail="Grief stage not found")

        member = await db.members.find_one({"id": stage["member_id"], **campus_filter}, {"_id": 0})
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")

        church_name = os.environ.get("CHURCH_NAME", "Church")
        stage_names = {
            "1_week": "1 week",
            "2_weeks": "2 weeks",
            "1_month": "1 month",
            "3_months": "3 months",
            "6_months": "6 months",
            "1_year": "1 year",
        }
        stage_name = stage_names.get(stage["stage"], stage["stage"])

        message = f"{church_name} - Grief Support Check-in: It has been {stage_name} since your loss. We are thinking of you and praying for you. Please reach out if you need support."

        result = await _send_whatsapp_message(
            member["phone"], message, grief_support_id=stage_id, member_id=stage["member_id"]
        )

        if result["success"]:
            await db.grief_support.update_one(
                {"id": stage_id}, {"$set": {"reminder_sent": True, "updated_at": datetime.now(UTC)}}
            )

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending grief reminder: {e!s}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


# Route handlers list for Litestar registration
route_handlers = [
    list_grief_support,
    get_member_grief_timeline,
    complete_grief_stage,
    ignore_grief_stage,
    undo_grief_stage,
    send_grief_reminder,
]
