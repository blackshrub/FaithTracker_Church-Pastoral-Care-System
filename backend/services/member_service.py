import logging
from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from enums import ActivityActionType, EngagementStatus
from models import MemberCreate, MemberUpdate, generate_uuid
from utils import calculate_engagement_status, escape_regex, normalize_phone_number

logger = logging.getLogger(__name__)


class MemberService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._db = db

    async def get_by_id(
        self, member_id: str, church_id: str, projection: dict[str, int] | None = None
    ) -> dict[str, Any] | None:
        query = {"id": member_id, "church_id": church_id}
        if projection:
            projection["_id"] = 0
        else:
            projection = {"_id": 0}

        return await self._db.members.find_one(query, projection)

    async def get_many(
        self,
        church_id: str,
        campus_id: str | None = None,
        search: str | None = None,
        engagement_status: str | None = None,
        skip: int = 0,
        limit: int = DEFAULT_PAGE_SIZE,
        projection: dict[str, int] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        query: dict[str, Any] = {"church_id": church_id}

        if campus_id:
            query["campus_id"] = campus_id

        if search:
            safe_search = escape_regex(search)
            query["$or"] = [
                {"name": {"$regex": safe_search, "$options": "i"}},
                {"phone": {"$regex": safe_search, "$options": "i"}},
                {"email": {"$regex": safe_search, "$options": "i"}},
            ]

        if engagement_status:
            query["engagement_status"] = engagement_status

        if projection is None:
            projection = {
                "_id": 0,
                "id": 1,
                "name": 1,
                "phone": 1,
                "email": 1,
                "campus_id": 1,
                "engagement_status": 1,
                "days_since_last_contact": 1,
                "photo_url": 1,
                "birth_date": 1,
                "membership_status": 1,
            }
        projection["_id"] = 0

        from services.db_utils import paginated_query

        capped_limit = min(limit, MAX_PAGE_SIZE)
        members, total = await paginated_query(
            self._db.members, query, sort=[("name", 1)], skip=skip, limit=capped_limit, projection=projection
        )

        return members, total

    async def create(
        self, data: MemberCreate, church_id: str, campus_id: str, created_by_id: str, created_by_name: str
    ) -> dict[str, Any]:
        member_id = generate_uuid()
        now = datetime.now(UTC)

        phone = normalize_phone_number(data.phone) if data.phone else None

        member_doc = {
            "id": member_id,
            "church_id": church_id,
            "campus_id": campus_id,
            "name": data.name,
            "phone": phone,
            "email": data.email,
            "address": data.address,
            "birth_date": data.birth_date,
            "gender": data.gender,
            "membership_status": data.membership_status or "active",
            "family_group_id": data.family_group_id,
            "notes": data.notes,
            "categories": data.categories or [],
            "engagement_status": EngagementStatus.ACTIVE.value,
            "days_since_last_contact": 0,
            "last_contact_date": now,
            "photo_url": None,
            "created_at": now,
            "updated_at": now,
            "created_by": created_by_id,
        }

        await self._db.members.insert_one(member_doc)

        await self._log_activity(
            church_id=church_id,
            campus_id=campus_id,
            user_id=created_by_id,
            user_name=created_by_name,
            action=ActivityActionType.CREATE_MEMBER,
            member_id=member_id,
            member_name=data.name,
            details={"phone": phone, "email": data.email},
        )

        del member_doc["_id"]
        return member_doc

    async def update(
        self, member_id: str, church_id: str, data: MemberUpdate, updated_by_id: str, updated_by_name: str
    ) -> dict[str, Any] | None:
        member = await self.get_by_id(member_id, church_id)
        if not member:
            return None

        update_data: dict[str, Any] = {"updated_at": datetime.now(UTC)}

        if data.name is not None:
            update_data["name"] = data.name
        if data.phone is not None:
            update_data["phone"] = normalize_phone_number(data.phone) if data.phone else None
        if data.email is not None:
            update_data["email"] = data.email
        if data.address is not None:
            update_data["address"] = data.address
        if data.birth_date is not None:
            update_data["birth_date"] = data.birth_date
        if data.gender is not None:
            update_data["gender"] = data.gender
        if data.membership_status is not None:
            update_data["membership_status"] = data.membership_status
        if data.categories is not None:
            update_data["categories"] = data.categories
        if data.notes is not None:
            update_data["notes"] = data.notes

        await self._db.members.update_one({"id": member_id, "church_id": church_id}, {"$set": update_data})

        await self._log_activity(
            church_id=church_id,
            campus_id=member.get("campus_id"),
            user_id=updated_by_id,
            user_name=updated_by_name,
            action=ActivityActionType.UPDATE_MEMBER,
            member_id=member_id,
            member_name=data.name or member.get("name"),
            details={"updated_fields": list(update_data.keys())},
        )

        return await self.get_by_id(member_id, church_id)

    async def delete(self, member_id: str, church_id: str, deleted_by_id: str, deleted_by_name: str) -> bool:
        member = await self.get_by_id(member_id, church_id)
        if not member:
            return False

        await self._db.members.delete_one({"id": member_id, "church_id": church_id})
        cascade = {"member_id": member_id, "church_id": church_id}
        await self._db.care_events.delete_many(cascade)
        await self._db.grief_support.delete_many(cascade)
        await self._db.accident_followup.delete_many(cascade)
        await self._db.financial_aid_schedules.delete_many(cascade)
        await self._db.pastoral_notes.delete_many(cascade)
        await self._db.notification_logs.delete_many(cascade)
        await self._db.activity_logs.delete_many(cascade)

        await self._log_activity(
            church_id=church_id,
            campus_id=member.get("campus_id"),
            user_id=deleted_by_id,
            user_name=deleted_by_name,
            action=ActivityActionType.DELETE_MEMBER,
            member_id=member_id,
            member_name=member.get("name"),
            details={},
        )

        return True

    async def update_engagement(
        self, member_id: str, church_id: str, at_risk_days: int = 60, disconnected_days: int = 90
    ) -> None:
        member = await self.get_by_id(member_id, church_id, {"last_contact_date": 1})
        if not member:
            return

        status, days = calculate_engagement_status(member.get("last_contact_date"), at_risk_days, disconnected_days)

        await self._db.members.update_one(
            {"id": member_id, "church_id": church_id},
            {"$set": {"engagement_status": status.value, "days_since_last_contact": days}},
        )

    async def update_last_contact(self, member_id: str, church_id: str, contact_date: datetime | None = None) -> None:
        if contact_date is None:
            contact_date = datetime.now(UTC)

        await self._db.members.update_one(
            {"id": member_id, "church_id": church_id},
            {
                "$set": {
                    "last_contact_date": contact_date,
                    "engagement_status": EngagementStatus.ACTIVE.value,
                    "days_since_last_contact": 0,
                    "updated_at": datetime.now(UTC),
                }
            },
        )

    async def get_at_risk_members(
        self, church_id: str, campus_id: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {
            "church_id": church_id,
            "engagement_status": {"$in": [EngagementStatus.AT_RISK.value, EngagementStatus.DISCONNECTED.value]},
        }

        if campus_id:
            query["campus_id"] = campus_id

        projection = {
            "_id": 0,
            "id": 1,
            "name": 1,
            "phone": 1,
            "engagement_status": 1,
            "days_since_last_contact": 1,
            "last_contact_date": 1,
        }

        cursor = self._db.members.find(query, projection)
        cursor = cursor.sort("days_since_last_contact", -1).limit(limit)

        return await cursor.to_list(length=limit)

    async def _log_activity(
        self,
        church_id: str,
        campus_id: str | None,
        user_id: str,
        user_name: str,
        action: ActivityActionType,
        member_id: str | None,
        member_name: str | None,
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
            "details": details,
            "timestamp": datetime.now(UTC),
        }
        await self._db.activity_logs.insert_one(log_doc)
