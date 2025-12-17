"""
FaithTracker Dashboard & Analytics Routes
Handles dashboard statistics, reminders, and analytics endpoints
"""

from litestar import get, Request
from litestar.exceptions import HTTPException
import logging
import asyncio
from datetime import datetime, timezone, date, timedelta
from zoneinfo import ZoneInfo
from typing import Optional, Callable, Awaitable

from enums import EventType
from dependencies import (
    get_db, get_current_user, get_campus_filter, safe_error_detail
)

logger = logging.getLogger(__name__)

# Jakarta timezone for analytics
JAKARTA_TZ = ZoneInfo("Asia/Jakarta")

# Callbacks to server.py functions (set via init_dashboard_routes)
_get_campus_timezone: Optional[Callable[[str], Awaitable[str]]] = None
_get_date_in_timezone: Optional[Callable[[str], str]] = None
_get_writeoff_settings: Optional[Callable[[], Awaitable[dict]]] = None


def init_dashboard_routes(
    get_campus_timezone: Callable[[str], Awaitable[str]],
    get_date_in_timezone: Callable[[str], str],
    get_writeoff_settings: Callable[[], Awaitable[dict]],
):
    """Initialize dashboard routes with callbacks to server.py functions"""
    global _get_campus_timezone, _get_date_in_timezone, _get_writeoff_settings
    
    _get_campus_timezone = get_campus_timezone
    _get_date_in_timezone = get_date_in_timezone
    _get_writeoff_settings = get_writeoff_settings


# ==================== DASHBOARD HELPER ====================

async def calculate_dashboard_reminders(campus_id: str, campus_tz, today_date: str):
    """Calculate all dashboard reminder data - optimized query with parallel fetching"""
    db = get_db()
    try:
        logger.info(f"Calculating dashboard reminders for campus {campus_id}, date {today_date}")

        today = datetime.strptime(today_date, '%Y-%m-%d').date()
        tomorrow = today + timedelta(days=1)
        week_ahead = today + timedelta(days=7)

        # Parallel fetch: writeoff settings + all main data sources
        writeoff_task = _get_writeoff_settings()
        MAX_MEMBERS_LIST = 10000
        MAX_TASKS_LIST = 5000

        members_task = db.members.find(
            {"campus_id": campus_id, "is_archived": {"$ne": True}},
            {"_id": 0, "id": 1, "name": 1, "phone": 1, "photo_url": 1, "birth_date": 1,
             "engagement_status": 1, "days_since_last_contact": 1}
        ).to_list(MAX_MEMBERS_LIST)
        grief_task = db.grief_support.find(
            {"campus_id": campus_id, "completed": False, "ignored": {"$ne": True}},
            {"_id": 0, "id": 1, "member_id": 1, "campus_id": 1, "care_event_id": 1,
             "stage": 1, "scheduled_date": 1, "completed": 1, "notes": 1}
        ).to_list(MAX_TASKS_LIST)
        accident_task = db.accident_followup.find(
            {"campus_id": campus_id, "completed": False, "ignored": {"$ne": True}},
            {"_id": 0, "id": 1, "member_id": 1, "campus_id": 1, "care_event_id": 1,
             "stage": 1, "scheduled_date": 1, "completed": 1, "notes": 1}
        ).to_list(MAX_TASKS_LIST)
        aid_task = db.financial_aid_schedules.find(
            {"campus_id": campus_id, "is_active": True, "ignored": {"$ne": True}},
            {"_id": 0, "id": 1, "member_id": 1, "campus_id": 1, "aid_amount": 1,
             "frequency": 1, "next_occurrence": 1, "is_active": 1, "notes": 1}
        ).to_list(MAX_TASKS_LIST)
        # Fetch birthday events to filter out completed/ignored ones from dashboard
        # Note: Frontend now uses member_id-based endpoint which creates events on-the-fly
        year_start = f"{today.year}-01-01"
        birthday_events_task = db.care_events.find(
            {"campus_id": campus_id, "event_type": "birthday"},
            {"_id": 0, "member_id": 1, "completed": 1, "completed_at": 1, "ignored": 1, "ignored_at": 1,
             "completed_by_user_name": 1, "ignored_by_name": 1}
        ).to_list(MAX_TASKS_LIST)

        writeoff_settings, members, grief_stages, accident_followups, aid_schedules, birthday_events = await asyncio.gather(
            writeoff_task, members_task, grief_task, accident_task, aid_task, birthday_events_task
        )

        # Build map of member_ids with completed/ignored birthdays this year
        # We keep them visible but mark as completed so other staff can see them
        year_start_dt = datetime.strptime(year_start, '%Y-%m-%d')
        completed_birthday_info = {}  # member_id -> {completed, completed_by_user_name, ignored}

        for e in birthday_events:
            member_id = e["member_id"]
            completed_at = e.get("completed_at")
            ignored_at = e.get("ignored_at")

            if e.get("completed") and completed_at:
                # Handle both datetime and string formats
                if isinstance(completed_at, str):
                    try:
                        completed_at = datetime.strptime(completed_at[:10], '%Y-%m-%d')
                    except ValueError:
                        completed_at = None
                if completed_at and completed_at >= year_start_dt:
                    completed_birthday_info[member_id] = {
                        "completed": True,
                        "completed_by_user_name": e.get("completed_by_user_name", "Unknown")
                    }
                    continue

            if e.get("ignored") and ignored_at:
                if isinstance(ignored_at, str):
                    try:
                        ignored_at = datetime.strptime(ignored_at[:10], '%Y-%m-%d')
                    except ValueError:
                        ignored_at = None
                if ignored_at and ignored_at >= year_start_dt:
                    completed_birthday_info[member_id] = {
                        "ignored": True,
                        "ignored_by_name": e.get("ignored_by_name", "Unknown")
                    }

        logger.info(f"Found {len(members)} members for campus {campus_id}")
        
        # Build member map for quick lookup and calculate ages
        member_map = {}
        for m in members:
            age = None
            if m.get("birth_date"):
                try:
                    birth_date = datetime.strptime(m["birth_date"], '%Y-%m-%d').date()
                    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
                except ValueError:
                    pass
            m["age"] = age
            member_map[m["id"]] = m
        
        # Initialize all arrays
        birthdays_today = []
        upcoming_birthdays = []
        today_tasks = []
        overdue_birthdays = []
        upcoming_tasks = []
        grief_today = []
        suggestions_list = []

        # Process accident follow-ups
        accident_today = []
        accident_writeoff = writeoff_settings.get("accident_illness", 14)
        
        for followup in accident_followups:
            try:
                sched_date = datetime.strptime(followup["scheduled_date"], '%Y-%m-%d').date()
            except (ValueError, TypeError):
                continue
            days_overdue = (today - sched_date).days

            if sched_date == today:
                today_tasks.append({
                    "type": "accident_followup",
                    "date": followup["scheduled_date"],
                    "member_id": followup["member_id"],
                    "member_name": member_map.get(followup["member_id"], {}).get("name"),
                    "member_phone": member_map.get(followup["member_id"], {}).get("phone"),
                    "member_photo_url": member_map.get(followup["member_id"], {}).get("photo_url"),
                    "member_age": member_map.get(followup["member_id"], {}).get("age"),
                    "days_since_last_contact": member_map.get(followup["member_id"], {}).get("days_since_last_contact"),
                    "details": f"{followup['stage'].replace('_', ' ')}",
                    "data": followup
                })
            elif sched_date < today:
                if accident_writeoff == 0 or days_overdue <= accident_writeoff:
                    accident_today.append({
                        **followup,
                        "member_name": member_map.get(followup["member_id"], {}).get("name"),
                        "member_phone": member_map.get(followup["member_id"], {}).get("phone"),
                        "member_photo_url": member_map.get(followup["member_id"], {}).get("photo_url"),
                        "days_overdue": days_overdue
                    })
            elif tomorrow <= sched_date <= week_ahead:
                upcoming_tasks.append({
                    "type": "accident_followup",
                    "date": followup["scheduled_date"],
                    "member_id": followup["member_id"],
                    "member_name": member_map.get(followup["member_id"], {}).get("name"),
                    "member_phone": member_map.get(followup["member_id"], {}).get("phone"),
                    "member_photo_url": member_map.get(followup["member_id"], {}).get("photo_url"),
                    "details": f"{followup['stage'].replace('_', ' ')}",
                    "data": followup
                })
        
        # At-risk and disconnected members
        at_risk = [
            {
                "type": "at_risk", "id": m.get("id"), "name": m.get("name"),
                "phone": m.get("phone"), "photo_url": m.get("photo_url"), "age": m.get("age"),
                "member_id": m.get("id"), "member_name": m.get("name"),
                "member_phone": m.get("phone"), "member_photo_url": m.get("photo_url"),
                "member_age": m.get("age"), "days_since_last_contact": m.get("days_since_last_contact", 0),
            }
            for m in members if m.get("engagement_status") == "at_risk"
        ]
        disconnected = [
            {
                "type": "disconnected", "id": m.get("id"), "name": m.get("name"),
                "phone": m.get("phone"), "photo_url": m.get("photo_url"), "age": m.get("age"),
                "member_id": m.get("id"), "member_name": m.get("name"),
                "member_phone": m.get("phone"), "member_photo_url": m.get("photo_url"),
                "member_age": m.get("age"), "days_since_last_contact": m.get("days_since_last_contact", 0),
            }
            for m in members if m.get("engagement_status") == "disconnected"
        ]

        # Process financial aid schedules
        aid_due = []
        financial_aid_writeoff = writeoff_settings.get("financial_aid", 30)
        
        for schedule in aid_schedules:
            next_occurrence = schedule.get("next_occurrence")
            if not next_occurrence:
                continue
            try:
                next_date = datetime.strptime(next_occurrence, '%Y-%m-%d').date()
                if next_date == today:
                    today_tasks.append({
                        "type": "financial_aid", "date": next_occurrence,
                        "member_id": schedule["member_id"],
                        "member_name": member_map.get(schedule["member_id"], {}).get("name"),
                        "member_phone": member_map.get(schedule["member_id"], {}).get("phone"),
                        "member_photo_url": member_map.get(schedule["member_id"], {}).get("photo_url"),
                        "member_age": member_map.get(schedule["member_id"], {}).get("age"),
                        "days_since_last_contact": member_map.get(schedule["member_id"], {}).get("days_since_last_contact"),
                        "details": f"Rp {schedule.get('aid_amount', 0):,.0f}",
                        "data": schedule
                    })
                elif next_date < today:
                    days_overdue = (today - next_date).days
                    if financial_aid_writeoff == 0 or days_overdue <= financial_aid_writeoff:
                        aid_due.append({
                            **schedule,
                            "member_name": member_map.get(schedule["member_id"], {}).get("name"),
                            "member_phone": member_map.get(schedule["member_id"], {}).get("phone"),
                            "member_photo_url": member_map.get(schedule["member_id"], {}).get("photo_url"),
                            "days_overdue": days_overdue
                        })
                elif tomorrow <= next_date <= week_ahead:
                    upcoming_tasks.append({
                        "type": "financial_aid", "date": next_occurrence,
                        "member_id": schedule["member_id"],
                        "member_name": member_map.get(schedule["member_id"], {}).get("name"),
                        "member_phone": member_map.get(schedule["member_id"], {}).get("phone"),
                        "member_photo_url": member_map.get(schedule["member_id"], {}).get("photo_url"),
                        "details": f"Rp {schedule.get('aid_amount', 0):,.0f}",
                        "data": schedule
                    })
            except (ValueError, TypeError):
                continue

        # Process birthdays - include completed ones so other staff can see them
        # Note: Frontend uses member_id-based endpoint which creates events on-the-fly
        birthday_writeoff = writeoff_settings.get("birthday", 7)
        for member in members:
            member_id = member["id"]
            birth_date_str = member.get("birth_date")
            if not birth_date_str:
                continue

            # Check if this birthday was completed/ignored this year
            completion_info = completed_birthday_info.get(member_id, {})
            is_completed = completion_info.get("completed", False)
            is_ignored = completion_info.get("ignored", False)

            try:
                birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
                this_year_birthday = birth_date.replace(year=today.year)

                # Build base birthday data
                base_data = {
                    "type": "birthday", "member_id": member_id,
                    "member_name": member.get("name"), "member_phone": member.get("phone"),
                    "member_photo_url": member.get("photo_url"), "member_age": member.get("age"),
                    "days_since_last_contact": member.get("days_since_last_contact"),
                    "details": f"Turning {member.get('age', '?')} years old", "data": member,
                    "completed": is_completed,
                    "ignored": is_ignored,
                    "completed_by_user_name": completion_info.get("completed_by_user_name"),
                    "ignored_by_name": completion_info.get("ignored_by_name")
                }

                if this_year_birthday == today:
                    birthdays_today.append({**base_data, "date": today_date})
                elif this_year_birthday < today:
                    days_overdue = (today - this_year_birthday).days
                    # Only show INCOMPLETE overdue birthdays (completed ones don't need attention)
                    # Today's birthdays show completed status so staff can see who was contacted
                    if not is_completed and not is_ignored:
                        if birthday_writeoff == 0 or days_overdue <= birthday_writeoff:
                            overdue_birthdays.append({
                                **base_data, "date": this_year_birthday.isoformat(),
                                "days_overdue": days_overdue
                            })
                elif tomorrow <= this_year_birthday <= week_ahead:
                    upcoming_birthdays.append({
                        **base_data, "date": this_year_birthday.isoformat(),
                        "days_until": (this_year_birthday - today).days
                    })
            except (ValueError, TypeError):
                continue

        # Process grief stages
        grief_writeoff = writeoff_settings.get("grief_support", 30)
        for stage in grief_stages:
            try:
                sched_date = datetime.strptime(stage["scheduled_date"], '%Y-%m-%d').date()
            except (ValueError, TypeError):
                continue
            days_overdue = (today - sched_date).days
            if sched_date == today:
                today_tasks.append({
                    "type": "grief_support", "date": stage["scheduled_date"],
                    "member_id": stage["member_id"],
                    "member_name": member_map.get(stage["member_id"], {}).get("name"),
                    "member_phone": member_map.get(stage["member_id"], {}).get("phone"),
                    "member_photo_url": member_map.get(stage["member_id"], {}).get("photo_url"),
                    "member_age": member_map.get(stage["member_id"], {}).get("age"),
                    "days_since_last_contact": member_map.get(stage["member_id"], {}).get("days_since_last_contact"),
                    "details": f"{stage['stage'].replace('_', ' ')} stage", "data": stage
                })
            elif sched_date < today:
                if grief_writeoff == 0 or days_overdue <= grief_writeoff:
                    grief_today.append({
                        **stage,
                        "member_name": member_map.get(stage["member_id"], {}).get("name"),
                        "member_phone": member_map.get(stage["member_id"], {}).get("phone"),
                        "member_photo_url": member_map.get(stage["member_id"], {}).get("photo_url"),
                        "days_overdue": days_overdue
                    })
            elif tomorrow <= sched_date <= week_ahead:
                upcoming_tasks.append({
                    "type": "grief_support", "date": stage["scheduled_date"],
                    "member_id": stage["member_id"],
                    "member_name": member_map.get(stage["member_id"], {}).get("name"),
                    "member_phone": member_map.get(stage["member_id"], {}).get("phone"),
                    "member_photo_url": member_map.get(stage["member_id"], {}).get("photo_url"),
                    "details": f"{stage['stage'].replace('_', ' ')} stage", "data": stage
                })

        # Add upcoming birthdays to upcoming_tasks so they appear in Upcoming tab
        for birthday in upcoming_birthdays:
            upcoming_tasks.append({
                "type": "birthday",
                "date": birthday["date"],
                "member_id": birthday["member_id"],
                "member_name": birthday["member_name"],
                "member_phone": birthday["member_phone"],
                "member_photo_url": birthday["member_photo_url"],
                "member_age": birthday.get("member_age"),
                "details": birthday.get("details", "Birthday"),
                "days_until": birthday.get("days_until"),
                "data": birthday
            })

        upcoming_tasks.sort(key=lambda x: x["date"])
        
        return {
            "birthdays_today": birthdays_today, "overdue_birthdays": overdue_birthdays,
            "upcoming_birthdays": upcoming_birthdays, "today_tasks": today_tasks,
            "grief_today": grief_today, "accident_followup": accident_today,
            "at_risk_members": at_risk, "disconnected_members": disconnected,
            "financial_aid_due": aid_due, "ai_suggestions": suggestions_list,
            "upcoming_tasks": upcoming_tasks,
            "total_tasks": len(birthdays_today) + len(grief_today) + len(accident_today) + len(at_risk) + len(disconnected),
            "total_members": len(members)
        }
    except Exception as e:
        logger.error(f"Error calculating dashboard reminders: {str(e)}")
        raise


# ==================== DASHBOARD ENDPOINTS ====================

@get("/dashboard/reminders")
async def get_dashboard_reminders(request: Request) -> dict:
    """Get pre-calculated dashboard reminders - optimized for fast loading"""
    current_user = await get_current_user(request)
    db = get_db()
    try:
        campus_id = current_user.get("campus_id")
        if not campus_id:
            default_campus = await db.campuses.find_one({"is_active": True}, {"_id": 0, "id": 1})
            if default_campus:
                campus_id = default_campus["id"]
            else:
                return {"birthdays_today": [], "upcoming_birthdays": [], "grief_today": [],
                        "accident_followup": [], "at_risk_members": [], "disconnected_members": [],
                        "financial_aid_due": [], "ai_suggestions": [], "total_tasks": 0, "total_members": 0}
        
        campus_tz = await _get_campus_timezone(campus_id)
        today_date = _get_date_in_timezone(campus_tz)
        cache_key = f"dashboard_reminders_{campus_id}_{today_date}"
        cached = await db.dashboard_cache.find_one({"cache_key": cache_key})
        if cached and cached.get("data"):
            return cached["data"]

        data = await calculate_dashboard_reminders(campus_id, campus_tz, today_date)
        cache_data = {"cache_key": cache_key, "data": data,
                      "calculated_at": datetime.now(timezone.utc),
                      "expires_at": datetime.now(timezone.utc) + timedelta(hours=1)}
        await db.dashboard_cache.update_one({"cache_key": cache_key}, {"$set": cache_data}, upsert=True)
        data["cache_version"] = cache_data["calculated_at"].isoformat()
        return data
    except Exception as e:
        logger.error(f"Error getting dashboard reminders: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@get("/dashboard/stats")
async def get_dashboard_stats() -> dict:
    """Get overall dashboard statistics"""
    db = get_db()
    try:
        member_stats_pipeline = [{"$facet": {
            "total_count": [{"$count": "count"}],
            "at_risk_count": [{"$match": {"engagement_status": {"$in": ["at_risk", "disconnected"]}}}, {"$count": "count"}]
        }}]
        member_stats_result = await db.members.aggregate(member_stats_pipeline).to_list(1)
        member_stats = member_stats_result[0] if member_stats_result else {}
        total_members = member_stats.get("total_count", [{}])[0].get("count", 0)
        at_risk_count = member_stats.get("at_risk_count", [{}])[0].get("count", 0)
        active_grief = await db.grief_support.count_documents({"completed": False})
        today = date.today()
        month_start = today.replace(day=1).isoformat()
        financial_aid_pipeline = [
            {"$match": {"event_type": EventType.FINANCIAL_AID, "event_date": {"$gte": month_start}}},
            {"$group": {"_id": None, "total_aid": {"$sum": {"$ifNull": ["$aid_amount", 0]}}}}
        ]
        financial_aid_result = await db.care_events.aggregate(financial_aid_pipeline).to_list(1)
        total_aid = financial_aid_result[0]["total_aid"] if financial_aid_result else 0
        return {"total_members": total_members, "active_grief_support": active_grief,
                "members_at_risk": at_risk_count, "month_financial_aid": total_aid}
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@get("/dashboard/upcoming")
async def get_upcoming_events(days: int = 7) -> dict:
    """Get upcoming events for next N days"""
    db = get_db()
    try:
        today = date.today()
        future_date = today + timedelta(days=days)
        pipeline = [
            {"$match": {"event_date": {"$gte": today.isoformat(), "$lte": future_date.isoformat()}, "completed": False}},
            {"$lookup": {"from": "members", "localField": "member_id", "foreignField": "id", "as": "member_info"}},
            {"$addFields": {"member_name": {"$arrayElemAt": ["$member_info.name", 0]}, "member_phone": {"$arrayElemAt": ["$member_info.phone", 0]}}},
            {"$project": {"_id": 0, "member_info": 0}}, {"$sort": {"event_date": 1}}, {"$limit": 100}
        ]
        events = await db.care_events.aggregate(pipeline).to_list(100)
        return events
    except Exception as e:
        logger.error(f"Error getting upcoming events: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@get("/dashboard/grief-active")
async def get_active_grief_support() -> dict:
    """Get members currently in grief support timeline"""
    db = get_db()
    try:
        pipeline = [
            {"$match": {"completed": False}}, {"$sort": {"scheduled_date": 1}},
            {"$lookup": {"from": "members", "localField": "member_id", "foreignField": "id", "as": "member_info"}},
            {"$addFields": {"member_name": {"$arrayElemAt": ["$member_info.name", 0]}}},
            {"$group": {"_id": "$member_id", "member_id": {"$first": "$member_id"},
                        "member_name": {"$first": {"$ifNull": ["$member_name", "Unknown"]}},
                        "stages": {"$push": {"$arrayToObject": {"$filter": {"input": {"$objectToArray": "$$ROOT"},
                                  "cond": {"$not": [{"$in": ["$$this.k", ["_id", "member_info", "member_name"]]}]}}}}}}},
            {"$project": {"_id": 0}}, {"$limit": 100}
        ]
        result = await db.grief_support.aggregate(pipeline).to_list(100)
        return result
    except Exception as e:
        logger.error(f"Error getting active grief support: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@get("/dashboard/recent-activity")
async def get_recent_activity(request: Request, limit: int = 20) -> dict:
    """Get recent care events"""
    current_user = await get_current_user(request)
    db = get_db()
    try:
        campus_filter = get_campus_filter(current_user)
        match_stage = {"$match": campus_filter} if campus_filter else {"$match": {}}
        pipeline = [match_stage,
            {"$lookup": {"from": "members", "localField": "member_id", "foreignField": "id", "as": "member_info"}},
            {"$addFields": {"member_name": {"$arrayElemAt": ["$member_info.name", 0]}}},
            {"$project": {"_id": 0, "member_info": 0}}, {"$sort": {"created_at": -1}}, {"$limit": limit}
        ]
        events = await db.care_events.aggregate(pipeline).to_list(limit)
        return events
    except Exception as e:
        logger.error(f"Error getting recent activity: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


# ==================== ANALYTICS ENDPOINTS ====================

@get("/analytics/engagement-trends")
async def get_engagement_trends(request: Request, days: int = 30) -> dict:
    """Get engagement trends over time"""
    current_user = await get_current_user(request)
    db = get_db()
    try:
        start_date = date.today() - timedelta(days=days)
        query = {"event_date": {"$gte": start_date.isoformat()}}
        campus_filter = get_campus_filter(current_user)
        if campus_filter:
            query.update(campus_filter)
        events = await db.care_events.find(query, {"_id": 0, "event_date": 1}).to_list(1000)
        date_counts = {}
        for event in events:
            event_date = event.get('event_date')
            if isinstance(event_date, str):
                event_date = event_date[:10]
            date_counts[event_date] = date_counts.get(event_date, 0) + 1
        return [{"date": d, "count": c} for d, c in sorted(date_counts.items())]
    except Exception as e:
        logger.error(f"Error getting engagement trends: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@get("/analytics/care-events-by-type")
async def get_care_events_by_type(request: Request) -> dict:
    """Get distribution of care events by type"""
    current_user = await get_current_user(request)
    db = get_db()
    try:
        campus_filter = get_campus_filter(current_user)
        query = campus_filter if campus_filter else {}
        events = await db.care_events.find(query, {"_id": 0, "event_type": 1}).to_list(10000)
        type_counts = {}
        for event in events:
            event_type = event.get('event_type')
            type_counts[event_type] = type_counts.get(event_type, 0) + 1
        return [{"type": t, "count": c} for t, c in type_counts.items()]
    except Exception as e:
        logger.error(f"Error getting events by type: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@get("/analytics/grief-completion-rate")
async def get_grief_completion_rate(request: Request) -> dict:
    """Get grief support completion rate"""
    current_user = await get_current_user(request)
    db = get_db()
    try:
        campus_filter = get_campus_filter(current_user)
        query = campus_filter if campus_filter else {}
        total_stages = await db.grief_support.count_documents(query)
        completed_stages = await db.grief_support.count_documents({**query, "completed": True})
        completion_rate = (completed_stages / total_stages * 100) if total_stages > 0 else 0
        return {"total_stages": total_stages, "completed_stages": completed_stages,
                "pending_stages": total_stages - completed_stages, "completion_rate": round(completion_rate, 2)}
    except Exception as e:
        logger.error(f"Error getting grief completion rate: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@get("/analytics/dashboard")
async def get_analytics_dashboard(request: Request, time_range: str = "all",
                                   start_date: Optional[str] = None, end_date: Optional[str] = None) -> dict:
    """Comprehensive analytics dashboard"""
    current_user = await get_current_user(request)
    db = get_db()
    try:
        campus_filter = get_campus_filter(current_user)
        today = datetime.now(JAKARTA_TZ).date()
        current_year = today.year
        member_filter = {**campus_filter, "is_archived": {"$ne": True}}
        
        event_date_filter = {}
        if time_range == "year":
            event_date_filter = {"event_date": {"$gte": f"{current_year}-01-01"}}
        elif time_range == "6months":
            event_date_filter = {"event_date": {"$gte": (today - timedelta(days=180)).isoformat()}}
        elif time_range == "3months":
            event_date_filter = {"event_date": {"$gte": (today - timedelta(days=90)).isoformat()}}
        elif time_range == "custom" and start_date and end_date:
            event_date_filter = {"event_date": {"$gte": start_date, "$lte": end_date}}

        total_members, members_with_photos, grief_total, grief_completed = await asyncio.gather(
            db.members.count_documents(member_filter),
            db.members.count_documents({**member_filter, "photo_url": {"$exists": True, "$ne": None, "$ne": ""}}),
            db.grief_support.count_documents(campus_filter),
            db.grief_support.count_documents({**campus_filter, "completed": True})
        )

        events_by_type_agg = await db.care_events.aggregate([
            {"$match": {**campus_filter, **event_date_filter, "event_type": {"$ne": "birthday"}}},
            {"$group": {"_id": "$event_type", "count": {"$sum": 1}}}
        ]).to_list(20)

        financial_agg = await db.care_events.aggregate([
            {"$match": {**campus_filter, "event_type": "financial_aid"}},
            {"$group": {"_id": {"$ifNull": ["$aid_type", "other"]}, "count": {"$sum": 1},
                        "total_amount": {"$sum": {"$ifNull": ["$aid_amount", 0]}}}}
        ]).to_list(20)

        member_stats = {"total": total_members, "with_photos": members_with_photos}
        grief_rate = round((grief_completed / grief_total * 100) if grief_total > 0 else 0, 2)
        total_non_birthday = sum(e.get("count", 0) for e in events_by_type_agg)
        events_by_type = [{"name": (e["_id"] or "unknown").replace("_", " ").upper(), "value": e["count"],
                          "percentage": round(e["count"] / total_non_birthday * 100) if total_non_birthday > 0 else 0}
                         for e in events_by_type_agg]
        total_financial = sum(f.get("total_amount", 0) for f in financial_agg)
        financial_by_type = [{"name": (f["_id"] or "other").replace("_", " "), "value": f["total_amount"],
                             "count": f["count"]} for f in financial_agg]

        return {"member_stats": member_stats, "events_by_type": events_by_type,
                "financial": {"total_aid": total_financial, "by_type": financial_by_type},
                "grief": {"total_stages": grief_total, "completed_stages": grief_completed, "completion_rate": grief_rate}}
    except Exception as e:
        logger.error(f"Error getting analytics dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@get("/analytics/demographic-trends")
async def get_demographic_trends(request: Request) -> dict:
    """Analyze demographic trends"""
    current_user = await get_current_user(request)
    db = get_db()
    try:
        today = datetime.now(JAKARTA_TZ).date()
        campus_filter = get_campus_filter(current_user)
        members = await db.members.find(campus_filter, {"_id": 0}).to_list(1000)
        events = await db.care_events.find({**campus_filter}, {"_id": 0}).to_list(2000)
        
        age_groups = {'Children (0-12)': {'count': 0, 'care_events': 0}, 'Teenagers (13-17)': {'count': 0, 'care_events': 0},
                      'Young Adults (18-30)': {'count': 0, 'care_events': 0}, 'Adults (31-60)': {'count': 0, 'care_events': 0},
                      'Seniors (60+)': {'count': 0, 'care_events': 0}}
        membership_trends = {}

        for member in members:
            age = member.get('age') or 0
            membership = member.get('membership_status') or member.get('category') or 'Unknown'
            if membership not in membership_trends:
                membership_trends[membership] = {'count': 0, 'engagement_score': 0}
            
            age_group = 'Children (0-12)' if age <= 12 else 'Teenagers (13-17)' if age <= 17 else \
                        'Young Adults (18-30)' if age <= 30 else 'Adults (31-60)' if age <= 60 else 'Seniors (60+)'
            age_groups[age_group]['count'] += 1
            
            days_since_contact = member.get('days_since_last_contact') or 999
            engagement_score = max(0, 100 - days_since_contact)
            membership_trends[membership]['count'] += 1
            membership_trends[membership]['engagement_score'] += engagement_score
            
            member_events = [e for e in events if e['member_id'] == member['id']]
            age_groups[age_group]['care_events'] += len(member_events)
        
        for data in membership_trends.values():
            data['avg_engagement'] = round(data['engagement_score'] / data['count']) if data['count'] > 0 else 0
        
        insights = []
        highest_count = max(age_groups.items(), key=lambda x: x[1]['count'])
        highest_care = max(age_groups.items(), key=lambda x: x[1]['care_events'])
        insights.append(f"Largest demographic: {highest_count[0]} ({highest_count[1]['count']} members)")
        insights.append(f"Most care needed: {highest_care[0]} ({highest_care[1]['care_events']} events)")
        if membership_trends:
            lowest_eng = min(membership_trends.items(), key=lambda x: x[1]['avg_engagement'])
            insights.append(f"Lowest engagement: {lowest_eng[0]} (avg: {lowest_eng[1]['avg_engagement']})")
        
        return {"age_groups": [{"name": k, **v} for k, v in age_groups.items()],
                "membership_trends": [{"status": k, **v} for k, v in membership_trends.items()],
                "insights": insights, "total_members": len(members), "analysis_date": today.isoformat()}
    except Exception as e:
        logger.error(f"Error analyzing demographic trends: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


# Export list of all route handlers
route_handlers = [
    get_dashboard_reminders, get_dashboard_stats, get_upcoming_events,
    get_active_grief_support, get_recent_activity,
    get_engagement_trends, get_care_events_by_type, get_grief_completion_rate,
    get_analytics_dashboard, get_demographic_trends,
]
