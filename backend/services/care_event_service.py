import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from constants import (
    ACCIDENT_FINAL_FOLLOWUP_DAYS,
    ACCIDENT_FIRST_FOLLOWUP_DAYS,
    ACCIDENT_SECOND_FOLLOWUP_DAYS,
    DEFAULT_PAGE_SIZE,
    GRIEF_ONE_MONTH_DAYS,
    GRIEF_ONE_WEEK_DAYS,
    GRIEF_ONE_YEAR_DAYS,
    GRIEF_SIX_MONTHS_DAYS,
    GRIEF_THREE_MONTHS_DAYS,
    GRIEF_TWO_WEEKS_DAYS,
    MAX_PAGE_SIZE,
)
from enums import ActivityActionType, EventType, GriefStage
from models import CareEventCreate, generate_uuid

logger = logging.getLogger(__name__)


class CareEventService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._db = db

    async def get_by_id(
        self, event_id: str, church_id: str, projection: dict[str, int] | None = None
    ) -> dict[str, Any] | None:
        query = {"id": event_id, "church_id": church_id}
        if projection:
            projection["_id"] = 0
        else:
            projection = {"_id": 0}

        return await self._db.care_events.find_one(query, projection)

    async def get_for_member(
        self,
        member_id: str,
        church_id: str,
        event_type: str | None = None,
        is_completed: bool | None = None,
        skip: int = 0,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[dict[str, Any]], int]:
        query: dict[str, Any] = {"member_id": member_id, "church_id": church_id}

        if event_type:
            query["event_type"] = event_type
        if is_completed is not None:
            query["is_completed"] = is_completed

        from services.db_utils import paginated_query

        capped_limit = min(limit, MAX_PAGE_SIZE)
        events, total = await paginated_query(
            self._db.care_events, query, sort=[("event_date", -1)], skip=skip, limit=capped_limit, projection={"_id": 0}
        )

        return events, total

    async def get_pending_tasks(
        self,
        church_id: str,
        campus_id: str | None = None,
        event_types: list[str] | None = None,
        due_before: datetime | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"church_id": church_id, "is_completed": False, "is_ignored": False}

        if campus_id:
            query["campus_id"] = campus_id
        if event_types:
            query["event_type"] = {"$in": event_types}
        if due_before:
            query["event_date"] = {"$lte": due_before}

        pipeline = [
            {"$match": query},
            {"$lookup": {"from": "members", "localField": "member_id", "foreignField": "id", "as": "member"}},
            {"$unwind": {"path": "$member", "preserveNullAndEmptyArrays": True}},
            {
                "$project": {
                    "_id": 0,
                    "id": 1,
                    "member_id": 1,
                    "member_name": "$member.name",
                    "member_phone": "$member.phone",
                    "event_type": 1,
                    "event_date": 1,
                    "description": 1,
                    "notes": 1,
                    "grief_stage": 1,
                }
            },
            {"$sort": {"event_date": 1}},
            {"$limit": limit},
        ]

        return await self._db.care_events.aggregate(pipeline).to_list(length=limit)

    async def create(
        self,
        data: CareEventCreate,
        member_id: str,
        church_id: str,
        campus_id: str,
        created_by_id: str,
        created_by_name: str,
        member_name: str,
    ) -> dict[str, Any]:
        event_id = generate_uuid()
        now = datetime.now(UTC)

        event_doc = {
            "id": event_id,
            "church_id": church_id,
            "campus_id": campus_id,
            "member_id": member_id,
            "event_type": data.event_type,
            "event_date": data.event_date or now,
            "description": data.description,
            "notes": data.notes,
            "is_completed": False,
            "is_ignored": False,
            "completed_at": None,
            "completed_by": None,
            "grief_stage": data.grief_stage,
            "aid_type": data.aid_type,
            "aid_amount": data.aid_amount,
            "created_at": now,
            "created_by": created_by_id,
        }

        await self._db.care_events.insert_one(event_doc)

        event_date = data.event_date if isinstance(data.event_date, datetime) else now

        if data.event_type == EventType.GRIEF_LOSS.value:
            await self._generate_grief_timeline(
                member_id=member_id,
                church_id=church_id,
                campus_id=campus_id,
                initial_date=event_date,
                created_by_id=created_by_id,
                description=data.description,
            )

        if data.event_type == EventType.ACCIDENT_ILLNESS.value:
            await self._generate_accident_followups(
                member_id=member_id,
                church_id=church_id,
                campus_id=campus_id,
                initial_date=event_date,
                created_by_id=created_by_id,
                description=data.description,
            )

        await self._log_activity(
            church_id=church_id,
            campus_id=campus_id,
            user_id=created_by_id,
            user_name=created_by_name,
            action=ActivityActionType.CREATE_CARE_EVENT,
            member_id=member_id,
            member_name=member_name,
            event_id=event_id,
            event_type=data.event_type,
            details={"description": data.description},
        )

        del event_doc["_id"]
        return event_doc

    async def complete(
        self, event_id: str, church_id: str, completed_by_id: str, completed_by_name: str, notes: str | None = None
    ) -> dict[str, Any] | None:
        event = await self.get_by_id(event_id, church_id)
        if not event:
            return None

        now = datetime.now(UTC)
        update_data = {
            "is_completed": True,
            "completed_at": now,
            "completed_by": completed_by_id,
        }
        if notes:
            update_data["completion_notes"] = notes

        await self._db.care_events.update_one({"id": event_id, "church_id": church_id}, {"$set": update_data})

        await self._db.members.update_one(
            {"id": event["member_id"], "church_id": church_id}, {"$set": {"last_contact_date": now}}
        )

        member = await self._db.members.find_one(
            {"id": event["member_id"], "church_id": church_id}, {"name": 1, "_id": 0}
        )

        await self._log_activity(
            church_id=church_id,
            campus_id=event.get("campus_id"),
            user_id=completed_by_id,
            user_name=completed_by_name,
            action=ActivityActionType.COMPLETE_TASK,
            member_id=event["member_id"],
            member_name=member.get("name") if member else None,
            event_id=event_id,
            event_type=event["event_type"],
            details={"notes": notes} if notes else {},
        )

        return await self.get_by_id(event_id, church_id)

    async def ignore(
        self, event_id: str, church_id: str, ignored_by_id: str, ignored_by_name: str, reason: str | None = None
    ) -> dict[str, Any] | None:
        event = await self.get_by_id(event_id, church_id)
        if not event:
            return None

        await self._db.care_events.update_one(
            {"id": event_id, "church_id": church_id},
            {
                "$set": {
                    "is_ignored": True,
                    "ignored_at": datetime.now(UTC),
                    "ignored_by": ignored_by_id,
                    "ignore_reason": reason,
                }
            },
        )

        member = await self._db.members.find_one(
            {"id": event["member_id"], "church_id": church_id}, {"name": 1, "_id": 0}
        )

        await self._log_activity(
            church_id=church_id,
            campus_id=event.get("campus_id"),
            user_id=ignored_by_id,
            user_name=ignored_by_name,
            action=ActivityActionType.IGNORE_TASK,
            member_id=event["member_id"],
            member_name=member.get("name") if member else None,
            event_id=event_id,
            event_type=event["event_type"],
            details={"reason": reason} if reason else {},
        )

        return await self.get_by_id(event_id, church_id)

    async def delete(self, event_id: str, church_id: str, deleted_by_id: str, deleted_by_name: str) -> bool:
        event = await self.get_by_id(event_id, church_id)
        if not event:
            return False

        await self._db.care_events.delete_one({"id": event_id, "church_id": church_id})

        member = await self._db.members.find_one(
            {"id": event["member_id"], "church_id": church_id}, {"name": 1, "_id": 0}
        )

        await self._log_activity(
            church_id=church_id,
            campus_id=event.get("campus_id"),
            user_id=deleted_by_id,
            user_name=deleted_by_name,
            action=ActivityActionType.DELETE_CARE_EVENT,
            member_id=event["member_id"],
            member_name=member.get("name") if member else None,
            event_id=event_id,
            event_type=event["event_type"],
            details={},
        )

        return True

    async def _generate_grief_timeline(
        self,
        member_id: str,
        church_id: str,
        campus_id: str,
        initial_date: datetime,
        created_by_id: str,
        description: str | None,
    ) -> list[str]:
        stages = [
            (GRIEF_ONE_WEEK_DAYS, GriefStage.ONE_WEEK, "1 week check-in"),
            (GRIEF_TWO_WEEKS_DAYS, GriefStage.TWO_WEEKS, "2 weeks check-in"),
            (GRIEF_ONE_MONTH_DAYS, GriefStage.ONE_MONTH, "1 month check-in"),
            (GRIEF_THREE_MONTHS_DAYS, GriefStage.THREE_MONTHS, "3 months check-in"),
            (GRIEF_SIX_MONTHS_DAYS, GriefStage.SIX_MONTHS, "6 months check-in"),
            (GRIEF_ONE_YEAR_DAYS, GriefStage.ONE_YEAR, "1 year memorial"),
        ]

        event_ids = []
        for days, stage, stage_desc in stages:
            event_id = generate_uuid()
            event_date = initial_date + timedelta(days=days)

            event_doc = {
                "id": event_id,
                "church_id": church_id,
                "campus_id": campus_id,
                "member_id": member_id,
                "event_type": EventType.GRIEF_LOSS.value,
                "event_date": event_date,
                "description": f"{description or 'Grief support'} - {stage_desc}",
                "grief_stage": stage.value,
                "is_completed": False,
                "is_ignored": False,
                "created_at": datetime.now(UTC),
                "created_by": created_by_id,
            }

            await self._db.care_events.insert_one(event_doc)
            event_ids.append(event_id)

        return event_ids

    async def _generate_accident_followups(
        self,
        member_id: str,
        church_id: str,
        campus_id: str,
        initial_date: datetime,
        created_by_id: str,
        description: str | None,
    ) -> list[str]:
        followups = [
            (ACCIDENT_FIRST_FOLLOWUP_DAYS, "First follow-up (3 days)"),
            (ACCIDENT_SECOND_FOLLOWUP_DAYS, "Second follow-up (1 week)"),
            (ACCIDENT_FINAL_FOLLOWUP_DAYS, "Final follow-up (2 weeks)"),
        ]

        event_ids = []
        for days, followup_desc in followups:
            event_id = generate_uuid()
            event_date = initial_date + timedelta(days=days)

            event_doc = {
                "id": event_id,
                "church_id": church_id,
                "campus_id": campus_id,
                "member_id": member_id,
                "event_type": EventType.ACCIDENT_ILLNESS.value,
                "event_date": event_date,
                "description": f"{description or 'Accident/Illness'} - {followup_desc}",
                "is_completed": False,
                "is_ignored": False,
                "created_at": datetime.now(UTC),
                "created_by": created_by_id,
            }

            await self._db.care_events.insert_one(event_doc)
            event_ids.append(event_id)

        return event_ids

    async def _log_activity(
        self,
        church_id: str,
        campus_id: str | None,
        user_id: str,
        user_name: str,
        action: ActivityActionType,
        member_id: str | None,
        member_name: str | None,
        event_id: str | None,
        event_type: str | None,
        details: dict[str, Any],
    ) -> None:
        log_doc = {
            "id": generate_uuid(),
            "church_id": church_id,
            "campus_id": campus_id,
            "user_id": user_id,
            "user_name": user_name,
            "action": action.value,
            "member_id": member_id,
            "member_name": member_name,
            "event_id": event_id,
            "event_type": event_type,
            "details": details,
            "timestamp": datetime.now(UTC),
        }
        await self._db.activity_logs.insert_one(log_doc)
