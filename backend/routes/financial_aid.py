"""
FaithTracker Financial Aid Routes
Handles financial aid schedules, distributions, tracking, and summaries
"""

from litestar import get, post, delete, Request
from litestar.exceptions import HTTPException
from litestar.params import Parameter
import logging
from datetime import datetime, timezone, date, timedelta
from typing import Optional, Callable, Awaitable

from enums import EventType, ActivityActionType
from constants import MAX_PAGE_NUMBER, MAX_LIMIT
from models import (
    generate_uuid, FinancialAidSchedule, FinancialAidScheduleCreate, to_mongo_doc
)
from dependencies import (
    get_db, get_current_user, get_campus_filter, safe_error_detail
)
from utils import calculate_engagement_status

logger = logging.getLogger(__name__)

# Callbacks to server.py functions (set via init_financial_aid_routes)
_invalidate_dashboard_cache: Optional[Callable[[str], Awaitable[None]]] = None
_log_activity: Optional[Callable[..., Awaitable[None]]] = None
_get_engagement_settings_cached: Optional[Callable[[], Awaitable[dict]]] = None


def init_financial_aid_routes(
    invalidate_dashboard_cache: Callable[[str], Awaitable[None]],
    log_activity: Callable[..., Awaitable[None]],
    get_engagement_settings_cached: Callable[[], Awaitable[dict]],
):
    """Initialize financial aid routes with callbacks to server.py functions"""
    global _invalidate_dashboard_cache, _log_activity, _get_engagement_settings_cached
    
    _invalidate_dashboard_cache = invalidate_dashboard_cache
    _log_activity = log_activity
    _get_engagement_settings_cached = get_engagement_settings_cached


# ==================== FINANCIAL AID SCHEDULE ENDPOINTS ====================

@post("/financial-aid-schedules")
async def create_aid_schedule(data: FinancialAidScheduleCreate, request: Request) -> dict:
    """Create a financial aid schedule"""
    current_user = await get_current_user(request)
    db = get_db()
    # Convert Struct to dict for existing code compatibility
    schedule = to_mongo_doc(data)
    try:
        # Calculate next occurrence based on frequency
        today = date.today()
        start_date = date.fromisoformat(schedule['start_date']) if isinstance(schedule['start_date'], str) else schedule['start_date']
        next_occurrence = start_date
        
        if schedule['frequency'] == 'weekly' and schedule.get('day_of_week'):
            # For weekly: Find next occurrence of specified weekday from TODAY
            days_ahead = {'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6}
            target_weekday = days_ahead[schedule['day_of_week']]
            current_weekday = today.weekday()
            
            if target_weekday >= current_weekday:
                # This week
                days_to_add = target_weekday - current_weekday
            else:
                # Next week
                days_to_add = 7 - current_weekday + target_weekday
            
            next_occurrence = today + timedelta(days=days_to_add)
            
        elif schedule['frequency'] == 'monthly' and schedule.get('day_of_month'):
            # For monthly: Use start_date (supports backdating)
            day_of_month = schedule['day_of_month']
            start_month = start_date.month
            start_year = start_date.year
            
            # Validate day exists in the specified month
            try:
                first_occurrence = date(start_year, start_month, day_of_month)
                
                # Use the actual start date (even if in past - will show as overdue)
                next_occurrence = first_occurrence
                        
            except ValueError:
                # Day doesn't exist in this month (e.g., Feb 31, Nov 31)
                raise HTTPException(
                    status_code=400, 
                    detail=f"Day {day_of_month} does not exist in the specified month"
                )
            
        elif schedule['frequency'] == 'annually' and schedule.get('month_of_year'):
            # Find next occurrence of this month/day from today onward
            month_of_year = schedule['month_of_year']
            day_of_month = schedule.get('day_of_month', 1)  # Default to 1st if not specified
            
            # Try this year first
            try:
                next_occurrence = date(today.year, month_of_year, day_of_month)
                if next_occurrence < today:
                    # This year's date has passed, go to next year
                    next_occurrence = date(today.year + 1, month_of_year, day_of_month)
            except ValueError:
                # Day doesn't exist in month (e.g., Feb 31), use last day of month
                if month_of_year == 2:
                    # February - check leap year
                    if (today.year % 4 == 0 and today.year % 100 != 0) or (today.year % 400 == 0):
                        day_of_month = min(day_of_month, 29)
                    else:
                        day_of_month = min(day_of_month, 28)
                elif month_of_year in [4, 6, 9, 11]:
                    day_of_month = min(day_of_month, 30)
                else:
                    day_of_month = min(day_of_month, 31)
                
                next_occurrence = date(today.year, month_of_year, day_of_month)
                if next_occurrence < today:
                    next_occurrence = date(today.year + 1, month_of_year, day_of_month)
        
        aid_schedule = FinancialAidSchedule(
            member_id=schedule['member_id'],
            campus_id=current_user['campus_id'],
            title=schedule['title'],
            aid_type=schedule['aid_type'],
            aid_amount=schedule['aid_amount'],
            frequency=schedule['frequency'],
            start_date=start_date,
            end_date=schedule.get('end_date'),
            day_of_week=schedule.get('day_of_week'),
            day_of_month=schedule.get('day_of_month'),
            month_of_year=schedule.get('month_of_year'),
            next_occurrence=next_occurrence,
            created_by=current_user['id'],
            notes=schedule.get('notes')
        )
        
        # Serialize for MongoDB using to_mongo_doc for consistent date handling
        schedule_dict = to_mongo_doc(aid_schedule)

        await db.financial_aid_schedules.insert_one(schedule_dict)
        
        # Invalidate dashboard cache
        await _invalidate_dashboard_cache(current_user['campus_id'])
        
        return aid_schedule
    except Exception as e:
        logger.error(f"Error creating aid schedule: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@get("/financial-aid-schedules")
async def list_aid_schedules(
    request: Request,
    member_id: Optional[str] = None,
    active_only: bool = True,
    page: int = Parameter(default=1, ge=1, le=MAX_PAGE_NUMBER),
    limit: int = Parameter(default=50, ge=1, le=MAX_LIMIT),
) -> dict:
    """List financial aid schedules with pagination"""
    current_user = await get_current_user(request)
    db = get_db()
    try:
        query = get_campus_filter(current_user)

        if member_id:
            query['member_id'] = member_id

        if active_only:
            query['is_active'] = True

        skip = (page - 1) * limit
        schedules = await db.financial_aid_schedules.find(query, {"_id": 0}).skip(skip).limit(limit).to_list(limit)
        return schedules
    except Exception as e:
        logger.error(f"Error listing aid schedules: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@delete("/financial-aid-schedules/{schedule_id:str}/ignored-occurrence/{occurrence_date:str}", status_code=200)
async def remove_ignored_occurrence(schedule_id: str, occurrence_date: str, request: Request) -> dict:
    """Remove a specific ignored occurrence from the schedule and its activity log"""
    current_user = await get_current_user(request)
    db = get_db()
    try:
        # Build query with campus filter
        query = {"id": schedule_id}
        campus_filter = get_campus_filter(current_user)
        if campus_filter:
            query.update(campus_filter)

        schedule = await db.financial_aid_schedules.find_one(query, {"_id": 0})
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")

        # Remove the occurrence from ignored list
        ignored_list = schedule.get("ignored_occurrences", [])
        if occurrence_date in ignored_list:
            ignored_list.remove(occurrence_date)

        await db.financial_aid_schedules.update_one(
            {"id": schedule_id},
            {"$set": {
                "ignored_occurrences": ignored_list,
                "updated_at": datetime.now(timezone.utc)
            }}
        )

        # Delete activity log for this ignore action
        await db.activity_logs.delete_many({
            "member_id": schedule["member_id"],
            "event_type": "financial_aid",
            "action_type": "ignore_task",
            "notes": {"$regex": occurrence_date, "$options": "i"}
        })

        # Invalidate dashboard cache
        await _invalidate_dashboard_cache(schedule["campus_id"])

        return {"success": True, "message": "Ignored occurrence removed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing ignored occurrence: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@post("/financial-aid-schedules/{schedule_id:str}/clear-ignored")
async def clear_all_ignored_occurrences(schedule_id: str, request: Request) -> dict:
    """Clear all ignored occurrences for a schedule"""
    current_user = await get_current_user(request)
    db = get_db()
    try:
        schedule = await db.financial_aid_schedules.find_one({"id": schedule_id}, {"_id": 0})
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")
        
        # Get member name for logging
        member = await db.members.find_one({"id": schedule["member_id"]}, {"_id": 0})
        member_name = member["name"] if member else "Unknown"
        
        await db.financial_aid_schedules.update_one(
            {"id": schedule_id},
            {"$set": {
                "ignored_occurrences": [],
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        
        # Log activity
        await _log_activity(
            campus_id=schedule["campus_id"],
            user_id=current_user["id"],
            user_name=current_user["name"],
            action_type=ActivityActionType.CLEAR_IGNORED,
            member_id=schedule["member_id"],
            member_name=member_name,
            event_type=EventType.FINANCIAL_AID,
            notes=f"Cleared all ignored occurrences for {schedule.get('aid_type', 'financial aid')} schedule",
            user_photo_url=current_user.get("photo_url")
        )
        
        # Invalidate dashboard cache
        await _invalidate_dashboard_cache(schedule["campus_id"])
        
        return {"success": True, "message": "All ignored occurrences cleared"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing ignored occurrences: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@delete("/financial-aid-schedules/{schedule_id:str}", status_code=200)
async def delete_aid_schedule(schedule_id: str, request: Request) -> dict:
    """Delete a financial aid schedule and related activity logs"""
    db = get_db()
    try:
        # Get schedule details before deleting
        schedule = await db.financial_aid_schedules.find_one({"id": schedule_id}, {"_id": 0})
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")
        
        # Delete activity logs related to this schedule
        # Match by member_id and notes containing aid_type or "financial aid"
        await db.activity_logs.delete_many({
            "member_id": schedule["member_id"],
            "event_type": "financial_aid",
            "notes": {"$regex": schedule.get('aid_type', 'financial aid'), "$options": "i"}
        })
        
        # Delete the schedule
        result = await db.financial_aid_schedules.delete_one({"id": schedule_id})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Schedule not found")
        
        # Invalidate dashboard cache
        await _invalidate_dashboard_cache(schedule["campus_id"])
        
        return {"success": True, "message": "Financial aid schedule and related logs deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting aid schedule: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@post("/financial-aid-schedules/{schedule_id:str}/stop")
async def stop_aid_schedule(schedule_id: str, request: Request) -> dict:
    """Manually stop a financial aid schedule"""
    current_user = await get_current_user(request)
    db = get_db()
    try:
        # Get schedule first
        schedule = await db.financial_aid_schedules.find_one({"id": schedule_id}, {"_id": 0})
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")
        
        # Get member name for logging
        member = await db.members.find_one({"id": schedule["member_id"]}, {"_id": 0})
        member_name = member["name"] if member else "Unknown"
        
        result = await db.financial_aid_schedules.update_one(
            {"id": schedule_id},
            {"$set": {
                "is_active": False,
                "stopped_by_user_id": current_user["id"],
                "stopped_by_user_name": current_user["name"],
                "stopped_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Schedule not found")
        
        # Log activity
        await _log_activity(
            campus_id=schedule["campus_id"],
            user_id=current_user["id"],
            user_name=current_user["name"],
            action_type=ActivityActionType.STOP_SCHEDULE,
            member_id=schedule["member_id"],
            member_name=member_name,
            event_type=EventType.FINANCIAL_AID,
            notes=f"Stopped {schedule.get('aid_type', 'financial aid')} schedule",
            user_photo_url=current_user.get("photo_url")
        )
        
        # Invalidate dashboard cache
        await _invalidate_dashboard_cache(schedule["campus_id"])
        
        return {"success": True, "message": "Financial aid schedule stopped"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping aid schedule: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@get("/financial-aid-schedules/member/{member_id:str}")
async def get_member_aid_schedules(member_id: str, request: Request) -> dict:
    """Get financial aid schedules for specific member (active + stopped with history)"""
    db = get_db()
    try:
        logger.info(f"[GET AID SCHEDULES] Querying for member_id={member_id}")
        
        # Get ALL schedules for this member (don't limit to 20)
        schedules = await db.financial_aid_schedules.find(
            {"member_id": member_id},
            {"_id": 0}
        ).sort("next_occurrence", 1).to_list(None)  # None = no limit
        
        # Log all schedule IDs found
        logger.info(f"[GET AID SCHEDULES] Found {len(schedules)} schedule IDs for member")
        
        # Filter: active schedules OR stopped schedules with ignored history
        filtered = [
            s for s in schedules 
            if s.get("is_active") or (s.get("ignored_occurrences") and len(s.get("ignored_occurrences", [])) > 0)
        ]
        
        # Enhanced logging for debugging
        logger.info(f"Total schedules: {len(schedules)}, Active+WithHistory: {len(filtered)}")
        if len(filtered) == 0 and len(schedules) > 0:
            # Debug why filter returned nothing
            for s in schedules[:3]:  # Check first 3
                logger.info(f"  Debug schedule: id={s.get('id')[:8]}, is_active={s.get('is_active')} (type={type(s.get('is_active'))}), ignored_occ={s.get('ignored_occurrences')} (type={type(s.get('ignored_occurrences'))}), member_id={s.get('member_id')[:8] if s.get('member_id') else 'None'}")
        
        return filtered
    except Exception as e:
        logger.error(f"Error getting member aid schedules: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@get("/financial-aid-schedules/due-today")
async def get_aid_due_today(request: Request) -> dict:
    """Get financial aid schedules due today and overdue"""
    current_user = await get_current_user(request)
    db = get_db()
    try:
        today = date.today().isoformat()
        query = get_campus_filter(current_user)
        query.update({
            "next_occurrence": {"$lte": today},  # Today and overdue
            "is_active": True
        })
        
        schedules = await db.financial_aid_schedules.find(query, {"_id": 0}).to_list(100)
        
        # Add member info and calculate overdue days
        for schedule in schedules:
            member = await db.members.find_one({"id": schedule["member_id"]}, {"_id": 0, "name": 1, "phone": 1, "photo_url": 1})
            if member:
                schedule["member_name"] = member["name"]
                schedule["member_phone"] = member["phone"]
                schedule["member_photo_url"] = member.get("photo_url")
                
                # Calculate how many days overdue
                next_date = date.fromisoformat(schedule["next_occurrence"])
                days_overdue = (date.today() - next_date).days
                schedule["days_overdue"] = max(0, days_overdue)
                schedule["status"] = "overdue" if days_overdue > 0 else "due_today"
        
        return schedules
    except Exception as e:
        logger.error(f"Error getting aid due today: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@post("/financial-aid-schedules/{schedule_id:str}/mark-distributed")
async def mark_aid_distributed(schedule_id: str, request: Request) -> dict:
    """Mark scheduled aid as distributed and advance to next occurrence"""
    current_user = await get_current_user(request)
    db = get_db()
    try:
        # Get the schedule
        schedule = await db.financial_aid_schedules.find_one({"id": schedule_id}, {"_id": 0})
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")
        
        # Get member name for logging
        member = await db.members.find_one({"id": schedule["member_id"]}, {"_id": 0, "name": 1})
        member_name = member["name"] if member else "Unknown"
        
        # Create care event for this payment
        payment_event_id = generate_uuid()
        await db.care_events.insert_one({
            "id": payment_event_id,
            "member_id": schedule["member_id"],
            "campus_id": schedule["campus_id"],
            "event_type": "financial_aid",
            "event_date": schedule["next_occurrence"],
            "title": f"{schedule['title']} - Scheduled Payment",
            "aid_type": schedule["aid_type"],
            "aid_amount": schedule["aid_amount"],
            "aid_notes": f"From {schedule['frequency']} schedule",
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
            campus_id=schedule["campus_id"],
            user_id=current_user["id"],
            user_name=current_user["name"],
            action_type=ActivityActionType.COMPLETE_TASK,
            member_id=schedule["member_id"],
            member_name=member_name,
            care_event_id=payment_event_id,
            event_type=EventType.FINANCIAL_AID,
            notes=f"Marked {schedule.get('aid_type', 'financial aid')} as distributed - Rp {schedule.get('aid_amount', 0):,.0f}",
            user_photo_url=current_user.get("photo_url")
        )
        
        # Update member's last contact date and engagement status
        settings = await _get_engagement_settings_cached()
        status, days = calculate_engagement_status(datetime.now(timezone.utc), settings.get("atRiskDays", 60), settings.get("disconnectedDays", 90))
        
        await db.members.update_one(
            {"id": schedule["member_id"]},
            {"$set": {
                "last_contact_date": datetime.now(timezone.utc),
                "engagement_status": status,
                "days_since_last_contact": days,
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        
        # Calculate next occurrence
        current_date = date.fromisoformat(schedule["next_occurrence"])
        today = date.today()
        
        if schedule["frequency"] == "weekly":
            next_date = current_date + timedelta(weeks=1)
        elif schedule["frequency"] == "monthly":
            # Safely advance to next month, handling day-of-month edge cases
            day_of_month = schedule.get("day_of_month", current_date.day)
            
            if current_date.month == 12:
                # December -> January next year
                next_year = current_date.year + 1
                next_month = 1
            else:
                next_year = current_date.year
                next_month = current_date.month + 1
            
            # Handle months with fewer days (e.g., Jan 31 -> Feb 28/29)
            try:
                next_date = date(next_year, next_month, day_of_month)
            except ValueError:
                # Day doesn't exist in next month, use last valid day
                if next_month == 2:
                    # February
                    if (next_year % 4 == 0 and next_year % 100 != 0) or (next_year % 400 == 0):
                        next_date = date(next_year, next_month, min(day_of_month, 29))
                    else:
                        next_date = date(next_year, next_month, min(day_of_month, 28))
                elif next_month in [4, 6, 9, 11]:
                    next_date = date(next_year, next_month, min(day_of_month, 30))
                else:
                    next_date = date(next_year, next_month, min(day_of_month, 31))
        elif schedule["frequency"] == "annually":
            next_date = current_date.replace(year=current_date.year + 1)
        else:
            next_date = current_date
        
        # Update schedule with new next occurrence
        # Log before update for debugging
        logger.info(f"[DISTRIBUTE] Before update - Schedule {schedule_id}: is_active={schedule.get('is_active')}, ignored_occurrences={schedule.get('ignored_occurrences')}, next_occurrence={schedule.get('next_occurrence')}")
        
        await db.financial_aid_schedules.update_one(
            {"id": schedule_id},
            {"$set": {
                "next_occurrence": next_date.isoformat(),
                "occurrences_completed": (schedule.get("occurrences_completed", 0) + 1),
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        
        # Log after update for debugging
        updated_schedule = await db.financial_aid_schedules.find_one({"id": schedule_id}, {"_id": 0})
        logger.info(f"[DISTRIBUTE] After update - Schedule {schedule_id}: is_active={updated_schedule.get('is_active')}, ignored_occurrences={updated_schedule.get('ignored_occurrences')}, next_occurrence={updated_schedule.get('next_occurrence')}")
        
        # Invalidate dashboard cache
        await _invalidate_dashboard_cache(schedule["campus_id"])
        
        return {
            "success": True,
            "message": "Payment marked as distributed and schedule advanced",
            "next_occurrence": next_date.isoformat()
        }
    except Exception as e:
        logger.error(f"Error marking aid distributed: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@post("/financial-aid-schedules/{schedule_id:str}/ignore")
async def ignore_financial_aid_schedule(schedule_id: str, request: Request) -> dict:
    """Mark a specific financial aid occurrence as ignored (not the entire schedule)"""
    current_user = await get_current_user(request)
    db = get_db()
    try:
        schedule = await db.financial_aid_schedules.find_one({"id": schedule_id}, {"_id": 0})
        if not schedule:
            raise HTTPException(status_code=404, detail="Financial aid schedule not found")
        
        # Get member name for logging
        member = await db.members.find_one({"id": schedule["member_id"]}, {"_id": 0, "name": 1})
        member_name = member["name"] if member else "Unknown"
        
        current_occurrence = schedule.get("next_occurrence")
        if not current_occurrence:
            raise HTTPException(status_code=400, detail="No next occurrence to ignore")
        
        # Add current occurrence to ignored list
        ignored_list = schedule.get("ignored_occurrences", [])
        if current_occurrence not in ignored_list:
            ignored_list.append(current_occurrence)
        
        # Calculate next occurrence (skip ignored dates)
        current_date = date.fromisoformat(current_occurrence) if isinstance(current_occurrence, str) else current_occurrence
        
        # Log before update for debugging
        logger.info(f"[IGNORE] Before update - Schedule {schedule_id}: member_id={schedule.get('member_id')}, is_active={schedule.get('is_active')}, ignored_occurrences={schedule.get('ignored_occurrences')}, next_occurrence={schedule.get('next_occurrence')}")
        
        if schedule["frequency"] == "weekly":
            next_date = current_date + timedelta(weeks=1)
        elif schedule["frequency"] == "monthly":
            # Safely advance to next month, handling day-of-month edge cases
            day_of_month = schedule.get("day_of_month", current_date.day)
            
            if current_date.month == 12:
                # December -> January next year
                next_year = current_date.year + 1
                next_month = 1
            else:
                next_year = current_date.year
                next_month = current_date.month + 1
            
            # Handle months with fewer days (e.g., Jan 31 -> Feb 28/29)
            try:
                next_date = date(next_year, next_month, day_of_month)
            except ValueError:
                # Day doesn't exist in next month, use last valid day
                if next_month == 2:
                    # February
                    if (next_year % 4 == 0 and next_year % 100 != 0) or (next_year % 400 == 0):
                        next_date = date(next_year, next_month, min(day_of_month, 29))
                    else:
                        next_date = date(next_year, next_month, min(day_of_month, 28))
                elif next_month in [4, 6, 9, 11]:
                    next_date = date(next_year, next_month, min(day_of_month, 30))
                else:
                    next_date = date(next_year, next_month, min(day_of_month, 31))
        elif schedule["frequency"] == "annually":
            next_date = current_date.replace(year=current_date.year + 1)
        else:
            next_date = current_date
        
        await db.financial_aid_schedules.update_one(
            {"id": schedule_id},
            {"$set": {
                "ignored_occurrences": ignored_list,
                "next_occurrence": next_date.isoformat(),
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        
        # Log activity
        await _log_activity(
            campus_id=schedule["campus_id"],
            user_id=current_user["id"],
            user_name=current_user["name"],
            action_type=ActivityActionType.IGNORE_TASK,
            member_id=schedule["member_id"],
            member_name=member_name,
            event_type=EventType.FINANCIAL_AID,
            notes=f"Ignored {schedule.get('aid_type', 'financial aid')} payment on {current_occurrence}",
            user_photo_url=current_user.get("photo_url")
        )
        
        # Invalidate dashboard cache
        await _invalidate_dashboard_cache(schedule["campus_id"])
        
        return {
            "success": True, 
            "message": f"Occurrence on {current_occurrence} ignored. Next payment: {next_date.isoformat()}",
            "ignored_date": current_occurrence,
            "next_occurrence": next_date.isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


# ==================== FINANCIAL AID ENDPOINTS ====================

@get("/financial-aid/summary")
async def get_financial_aid_summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> dict:
    """Get financial aid summary by type and date range"""
    db = get_db()
    try:
        query = {"event_type": EventType.FINANCIAL_AID}
        
        if start_date:
            query["event_date"] = {"$gte": start_date}
        if end_date:
            if "event_date" in query:
                query["event_date"]["$lte"] = end_date
            else:
                query["event_date"] = {"$lte": end_date}
        
        events = await db.care_events.find(query, {"_id": 0}).to_list(1000)
        
        # Calculate totals by type
        totals_by_type = {}
        total_amount = 0
        
        for event in events:
            aid_type = event.get('aid_type', 'other')
            amount = event.get('aid_amount', 0) or 0
            
            if aid_type not in totals_by_type:
                totals_by_type[aid_type] = {"count": 0, "total_amount": 0}
            
            totals_by_type[aid_type]["count"] += 1
            totals_by_type[aid_type]["total_amount"] += amount
            total_amount += amount
        
        return {
            "total_amount": total_amount,
            "total_count": len(events),
            "by_type": totals_by_type
        }
    except Exception as e:
        logger.error(f"Error getting financial aid summary: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@get("/financial-aid/recipients")
async def get_financial_aid_recipients() -> dict:
    """Get list of all financial aid recipients with totals"""
    db = get_db()
    try:
        # Aggregate financial aid by member
        pipeline = [
            {"$match": {"event_type": EventType.FINANCIAL_AID}},
            {"$group": {
                "_id": "$member_id",
                "total_amount": {"$sum": "$aid_amount"},
                "aid_count": {"$sum": 1}
            }},
            {"$sort": {"total_amount": -1}}
        ]
        
        recipients_data = await db.care_events.aggregate(pipeline).to_list(1000)
        
        # Fetch member names and photos
        recipients = []
        for data in recipients_data:
            member_id = data["_id"]
            if member_id:
                member = await db.members.find_one({"id": member_id}, {"_id": 0, "name": 1, "photo_url": 1})
                member_name = "Unknown"
                photo_url = None
                
                if member:
                    member_name = member.get("name", "Unknown")
                    photo_url = member.get("photo_url")
                else:
                    # Try to get name from the first event's title
                    event = await db.care_events.find_one(
                        {"member_id": member_id, "event_type": EventType.FINANCIAL_AID},
                        {"_id": 0, "title": 1}
                    )
                    if event and event.get("title"):
                        title = event["title"]
                        if " - " in title:
                            member_name = title.split(" - ", 1)[1].strip()
                
                recipients.append({
                    "member_id": member_id,
                    "member_name": member_name,
                    "photo_url": photo_url,
                    "total_amount": data["total_amount"],
                    "aid_count": data["aid_count"]
                })
        
        return recipients
    except Exception as e:
        logger.error(f"Error getting financial aid recipients: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@get("/financial-aid/member/{member_id:str}")
async def get_member_financial_aid(member_id: str) -> dict:
    """Get all financial aid given to a member"""
    db = get_db()
    try:
        aid_events = await db.care_events.find({
            "member_id": member_id,
            "event_type": EventType.FINANCIAL_AID
        }, {"_id": 0}).sort([("event_date", -1), ("created_at", -1)]).to_list(100)
        
        total_amount = sum(event.get('aid_amount', 0) or 0 for event in aid_events)
        
        return {
            "member_id": member_id,
            "total_amount": total_amount,
            "aid_count": len(aid_events),
            "aid_history": aid_events
        }
    except Exception as e:
        logger.error(f"Error getting member financial aid: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


# Export list of all route handlers
route_handlers = [
    # Schedule endpoints
    create_aid_schedule,
    list_aid_schedules,
    remove_ignored_occurrence,
    clear_all_ignored_occurrences,
    delete_aid_schedule,
    stop_aid_schedule,
    get_member_aid_schedules,
    get_aid_due_today,
    mark_aid_distributed,
    ignore_financial_aid_schedule,
    # Summary endpoints
    get_financial_aid_summary,
    get_financial_aid_recipients,
    get_member_financial_aid,
]
