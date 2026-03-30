"""
Comprehensive unit tests for FaithTracker backend service layer.

Tests cover:
- CacheService (services/cache.py)
- MemberService (services/member_service.py)
- CareEventService (services/care_event_service.py)
- NotificationService (services/notification_service.py)
- ImageService (services/image_service.py)

All tests use mocked dependencies (Redis, MongoDB, httpx, PIL) for isolation.
"""

import io
import json
import os
import sys
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from constants import (
    ACCIDENT_FINAL_FOLLOWUP_DAYS,
    ACCIDENT_FIRST_FOLLOWUP_DAYS,
    ACCIDENT_SECOND_FOLLOWUP_DAYS,
    GRIEF_ONE_MONTH_DAYS,
    GRIEF_ONE_WEEK_DAYS,
    GRIEF_ONE_YEAR_DAYS,
    GRIEF_SIX_MONTHS_DAYS,
    GRIEF_THREE_MONTHS_DAYS,
    GRIEF_TWO_WEEKS_DAYS,
    MAX_PAGE_SIZE,
)
from enums import (
    ActivityActionType,
    EngagementStatus,
    EventType,
    GriefStage,
    NotificationChannel,
    NotificationStatus,
)

# ===================================================================
# Fixtures
# ===================================================================

CHURCH_ID = "church-test-001"
CAMPUS_ID = "campus-test-001"


def mock_facet_result(data, total=None):
    """Create a mock $facet aggregation result for paginated_query tests."""
    if total is None:
        total = len(data)
    facet_result = [{"data": data, "total": [{"count": total}] if total > 0 else []}]
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=facet_result)
    return cursor


MEMBER_ID = "member-test-001"
USER_ID = "user-test-001"
USER_NAME = "Test Pastor"
EVENT_ID = "event-test-001"


@pytest.fixture
def mock_redis():
    """Create a mock Redis client for CacheService tests."""
    client = AsyncMock()
    client.get = AsyncMock(return_value=None)
    client.setex = AsyncMock()
    client.delete = AsyncMock(return_value=1)
    client.scan = AsyncMock(return_value=(0, []))
    client.ping = AsyncMock()
    client.pipeline = MagicMock()
    pipe = AsyncMock()
    pipe.incr = MagicMock()
    pipe.expire = MagicMock()
    pipe.execute = AsyncMock(return_value=[1])
    client.pipeline.return_value = pipe
    return client


@pytest.fixture
def cache_service(mock_redis):
    """Create CacheService with mocked Redis client."""
    from services.cache import CacheService

    return CacheService(mock_redis)


@pytest.fixture
def mock_db():
    """Create a fully mocked async MongoDB database."""
    db = MagicMock()

    # Helper to create a mock collection with common methods
    def make_collection():
        coll = MagicMock()
        coll.find_one = AsyncMock(return_value=None)

        # Simulate MongoDB insert_one adding _id to the document
        async def _insert_one_side_effect(doc):
            from bson import ObjectId

            doc["_id"] = ObjectId()
            return MagicMock(inserted_id=doc["_id"])

        coll.insert_one = AsyncMock(side_effect=_insert_one_side_effect)
        coll.update_one = AsyncMock()
        coll.delete_one = AsyncMock()
        coll.delete_many = AsyncMock()
        coll.count_documents = AsyncMock(return_value=0)

        # Mock cursor for find()
        cursor = MagicMock()
        cursor.sort = MagicMock(return_value=cursor)
        cursor.skip = MagicMock(return_value=cursor)
        cursor.limit = MagicMock(return_value=cursor)
        cursor.to_list = AsyncMock(return_value=[])
        coll.find = MagicMock(return_value=cursor)

        # Mock aggregate
        agg_cursor = MagicMock()
        agg_cursor.to_list = AsyncMock(return_value=[])
        coll.aggregate = MagicMock(return_value=agg_cursor)

        return coll

    db.members = make_collection()
    db.care_events = make_collection()
    db.activity_logs = make_collection()
    db.notification_logs = make_collection()
    db.users = make_collection()

    return db


@pytest.fixture
def member_service(mock_db):
    """Create MemberService with mocked database."""
    from services.member_service import MemberService

    return MemberService(mock_db)


@pytest.fixture
def care_event_service(mock_db):
    """Create CareEventService with mocked database."""
    from services.care_event_service import CareEventService

    return CareEventService(mock_db)


@pytest.fixture
def notification_service(mock_db):
    """Create NotificationService with mocked database and no WhatsApp URL."""
    from services.notification_service import NotificationService

    return NotificationService(mock_db)


@pytest.fixture
def notification_service_with_wa(mock_db):
    """Create NotificationService with mocked database and WhatsApp URL."""
    from services.notification_service import NotificationService

    return NotificationService(mock_db, whatsapp_gateway_url="http://wa-gateway:3000")


def _make_member_data(**overrides):
    """Helper to create a mock MemberCreate-like object."""
    defaults = {
        "name": "John Doe",
        "phone": "081234567890",
        "email": "john@example.com",
        "address": "123 Test Street",
        "birth_date": date(1990, 5, 15),
        "gender": "male",
        "membership_status": "active",
        "family_group_id": None,
        "notes": "Test member",
        "categories": ["youth"],
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_member_update(**overrides):
    """Helper to create a mock MemberUpdate-like object with None defaults."""
    defaults = {
        "name": None,
        "phone": None,
        "email": None,
        "address": None,
        "birth_date": None,
        "gender": None,
        "membership_status": None,
        "categories": None,
        "notes": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_care_event_data(**overrides):
    """Helper to create a mock CareEventCreate-like object."""
    defaults = {
        "event_type": EventType.REGULAR_CONTACT.value,
        "event_date": datetime.now(UTC),
        "description": "Regular pastoral visit",
        "notes": "Member is doing well",
        "grief_stage": None,
        "aid_type": None,
        "aid_amount": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ===================================================================
# CacheService Tests
# ===================================================================


class TestCacheServiceMakeKey:
    """Test CacheService._make_key() key generation."""

    @pytest.mark.unit
    def test_make_key_without_church_id(self, cache_service):
        """Key without church_id should use prefix only."""
        key = cache_service._make_key("dashboard:stats")
        assert key == "ft:dashboard:stats"

    @pytest.mark.unit
    def test_make_key_with_church_id(self, cache_service):
        """Key with church_id should include church_id in the path."""
        key = cache_service._make_key("dashboard:stats", church_id="church-123")
        assert key == "ft:church-123:dashboard:stats"

    @pytest.mark.unit
    def test_make_key_with_empty_string_church_id(self, cache_service):
        """Empty string church_id should be treated as falsy (no church_id)."""
        key = cache_service._make_key("settings:engagement", church_id="")
        assert key == "ft:settings:engagement"

    @pytest.mark.unit
    def test_make_key_uses_constant_prefix(self, cache_service):
        """Key should always start with the KEY_PREFIX constant."""
        key = cache_service._make_key("anything")
        assert key.startswith(cache_service.KEY_PREFIX)


class TestCacheServiceGet:
    """Test CacheService.get() for cache retrieval."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_cache_miss_returns_none(self, cache_service, mock_redis):
        """Cache miss should return None."""
        mock_redis.get.return_value = None
        result = await cache_service.get("nonexistent")
        assert result is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_cache_hit_returns_deserialized(self, cache_service, mock_redis):
        """Cache hit should return deserialized JSON value."""
        test_data = {"total_members": 42, "active": 30}
        mock_redis.get.return_value = json.dumps(test_data)
        result = await cache_service.get("dashboard:stats", church_id=CHURCH_ID)
        assert result == test_data

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_cache_hit_with_list(self, cache_service, mock_redis):
        """Cache hit with list data should deserialize correctly."""
        test_data = [{"id": "1", "name": "Campus A"}, {"id": "2", "name": "Campus B"}]
        mock_redis.get.return_value = json.dumps(test_data)
        result = await cache_service.get("campuses:list")
        assert result == test_data
        assert len(result) == 2

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_redis_error_returns_none(self, cache_service, mock_redis):
        """Redis errors should be handled gracefully and return None."""
        import redis.asyncio as redis

        mock_redis.get.side_effect = redis.RedisError("Connection refused")
        result = await cache_service.get("dashboard:stats")
        assert result is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_calls_redis_with_correct_key(self, cache_service, mock_redis):
        """get() should construct the full key and pass it to Redis."""
        mock_redis.get.return_value = None
        await cache_service.get("settings:engagement", church_id="church-abc")
        mock_redis.get.assert_called_once_with("ft:church-abc:settings:engagement")


class TestCacheServiceSet:
    """Test CacheService.set() for cache storage."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_set_stores_with_default_ttl(self, cache_service, mock_redis):
        """set() should use DEFAULT_TTL when ttl is not specified."""
        result = await cache_service.set("mykey", {"value": 1})
        assert result is True
        mock_redis.setex.assert_called_once()
        args = mock_redis.setex.call_args
        assert args[0][1] == cache_service.DEFAULT_TTL  # TTL argument

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_set_stores_with_custom_ttl(self, cache_service, mock_redis):
        """set() should use the provided TTL value."""
        await cache_service.set("mykey", {"value": 1}, ttl=120)
        args = mock_redis.setex.call_args
        assert args[0][1] == 120

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_set_serializes_data_as_json(self, cache_service, mock_redis):
        """set() should serialize the value as JSON."""
        test_data = {"count": 5, "items": ["a", "b"]}
        await cache_service.set("mykey", test_data)
        args = mock_redis.setex.call_args
        stored_value = args[0][2]
        assert json.loads(stored_value) == test_data

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_set_handles_datetime_serialization(self, cache_service, mock_redis):
        """set() should handle datetime objects via default=str."""
        now = datetime.now(UTC)
        test_data = {"timestamp": now}
        result = await cache_service.set("mykey", test_data)
        assert result is True

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_set_redis_error_returns_false(self, cache_service, mock_redis):
        """Redis errors on set should return False."""
        import redis.asyncio as redis

        mock_redis.setex.side_effect = redis.RedisError("Write error")
        result = await cache_service.set("mykey", {"value": 1})
        assert result is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_set_and_get_roundtrip(self, cache_service, mock_redis):
        """set() followed by get() should return the original data."""
        test_data = {"members": 42, "events": 10}
        serialized = json.dumps(test_data, default=str)

        # set stores successfully
        await cache_service.set("stats", test_data, church_id=CHURCH_ID)

        # Simulate get returning what was stored
        mock_redis.get.return_value = serialized
        result = await cache_service.get("stats", church_id=CHURCH_ID)
        assert result == test_data


class TestCacheServiceDelete:
    """Test CacheService.delete() for cache removal."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_delete_returns_true(self, cache_service, mock_redis):
        """Successful delete should return True."""
        result = await cache_service.delete("mykey")
        assert result is True

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_delete_calls_redis_with_correct_key(self, cache_service, mock_redis):
        """delete() should pass the fully constructed key to Redis."""
        await cache_service.delete("dashboard:stats", church_id=CHURCH_ID)
        mock_redis.delete.assert_called_once_with(f"ft:{CHURCH_ID}:dashboard:stats")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_delete_redis_error_returns_false(self, cache_service, mock_redis):
        """Redis errors on delete should return False."""
        import redis.asyncio as redis

        mock_redis.delete.side_effect = redis.RedisError("Delete error")
        result = await cache_service.delete("mykey")
        assert result is False


class TestCacheServiceInvalidatePattern:
    """Test CacheService.invalidate_pattern() for bulk cache clearing."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_invalidate_pattern_no_matching_keys(self, cache_service, mock_redis):
        """When no keys match, should return 0 deleted."""
        mock_redis.scan.return_value = (0, [])
        deleted = await cache_service.invalidate_pattern("dashboard:*", church_id=CHURCH_ID)
        assert deleted == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_invalidate_pattern_with_matching_keys(self, cache_service, mock_redis):
        """When keys match, they should be deleted and count returned."""
        matching_keys = [
            f"ft:{CHURCH_ID}:dashboard:stats",
            f"ft:{CHURCH_ID}:dashboard:tasks",
        ]
        mock_redis.scan.return_value = (0, matching_keys)
        mock_redis.delete.return_value = 2
        deleted = await cache_service.invalidate_pattern("dashboard:*", church_id=CHURCH_ID)
        assert deleted == 2
        mock_redis.delete.assert_called_once_with(*matching_keys)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_invalidate_pattern_redis_error_returns_zero(self, cache_service, mock_redis):
        """Redis errors during pattern invalidation should return 0."""
        import redis.asyncio as redis

        mock_redis.scan.side_effect = redis.RedisError("Scan error")
        deleted = await cache_service.invalidate_pattern("dashboard:*")
        assert deleted == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_invalidate_pattern_paginates_scan(self, cache_service, mock_redis):
        """Scan should continue until cursor returns 0."""
        key1 = "ft:key1"
        key2 = "ft:key2"
        # First scan returns cursor=1 with one key, second returns cursor=0 with another
        mock_redis.scan.side_effect = [
            (1, [key1]),
            (0, [key2]),
        ]
        mock_redis.delete.return_value = 1

        deleted = await cache_service.invalidate_pattern("*")
        assert mock_redis.scan.call_count == 2
        assert deleted == 2


class TestCacheServiceConvenienceMethods:
    """Test CacheService convenience methods for dashboard, campuses, settings."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_dashboard_stats(self, cache_service, mock_redis):
        """get_dashboard_stats should use the correct key and church_id."""
        stats = {"total": 50}
        mock_redis.get.return_value = json.dumps(stats)
        result = await cache_service.get_dashboard_stats(CHURCH_ID)
        assert result == stats
        mock_redis.get.assert_called_once_with(f"ft:{CHURCH_ID}:dashboard:stats")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_set_dashboard_stats(self, cache_service, mock_redis):
        """set_dashboard_stats should use DASHBOARD_TTL."""
        stats = {"total": 50}
        result = await cache_service.set_dashboard_stats(CHURCH_ID, stats)
        assert result is True
        args = mock_redis.setex.call_args
        assert args[0][1] == cache_service.DASHBOARD_TTL

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_invalidate_dashboard(self, cache_service, mock_redis):
        """invalidate_dashboard should delete the dashboard stats key."""
        result = await cache_service.invalidate_dashboard(CHURCH_ID)
        assert result is True
        mock_redis.delete.assert_called_once_with(f"ft:{CHURCH_ID}:dashboard:stats")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_campuses(self, cache_service, mock_redis):
        """get_campuses uses global key (no church_id)."""
        campuses = [{"id": "1"}]
        mock_redis.get.return_value = json.dumps(campuses)
        result = await cache_service.get_campuses()
        assert result == campuses
        mock_redis.get.assert_called_once_with("ft:campuses:list")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_set_campuses(self, cache_service, mock_redis):
        """set_campuses should use SETTINGS_TTL."""
        campuses = [{"id": "1"}]
        await cache_service.set_campuses(campuses)
        args = mock_redis.setex.call_args
        assert args[0][1] == cache_service.SETTINGS_TTL

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_invalidate_campuses(self, cache_service, mock_redis):
        """invalidate_campuses should delete the campuses list key."""
        result = await cache_service.invalidate_campuses()
        assert result is True
        mock_redis.delete.assert_called_once_with("ft:campuses:list")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_settings(self, cache_service, mock_redis):
        """get_settings should use the key and church_id."""
        settings = {"at_risk_days": 60}
        mock_redis.get.return_value = json.dumps(settings)
        result = await cache_service.get_settings("settings:engagement", CHURCH_ID)
        assert result == settings

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_set_settings(self, cache_service, mock_redis):
        """set_settings should use SETTINGS_TTL."""
        settings = {"at_risk_days": 60}
        await cache_service.set_settings("settings:engagement", CHURCH_ID, settings)
        args = mock_redis.setex.call_args
        assert args[0][1] == cache_service.SETTINGS_TTL


class TestCacheServiceRateLimit:
    """Test CacheService.incr_rate_limit() for rate limiting."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_incr_rate_limit_returns_count(self, cache_service, mock_redis):
        """incr_rate_limit should return the incremented count."""
        pipe = mock_redis.pipeline.return_value
        pipe.execute.return_value = [5]
        count = await cache_service.incr_rate_limit("login:user@test.com")
        assert count == 5

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_incr_rate_limit_redis_error_returns_zero(self, cache_service, mock_redis):
        """Redis errors should return 0 (fail open)."""
        import redis.asyncio as redis

        pipe = mock_redis.pipeline.return_value
        pipe.execute.side_effect = redis.RedisError("Pipeline error")
        count = await cache_service.incr_rate_limit("login:user@test.com")
        assert count == 0


class TestCacheServiceHealthCheck:
    """Test CacheService.health_check()."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_health_check_healthy(self, cache_service, mock_redis):
        """Healthy Redis should return True."""
        mock_redis.ping.return_value = True
        result = await cache_service.health_check()
        assert result is True

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, cache_service, mock_redis):
        """Unhealthy Redis should return False."""
        import redis.asyncio as redis

        mock_redis.ping.side_effect = redis.RedisError("Connection refused")
        result = await cache_service.health_check()
        assert result is False


# ===================================================================
# MemberService Tests
# ===================================================================


class TestMemberServiceGetById:
    """Test MemberService.get_by_id()."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_by_id_found(self, member_service, mock_db):
        """Should return member when found."""
        member_doc = {"id": MEMBER_ID, "name": "John Doe", "church_id": CHURCH_ID}
        mock_db.members.find_one.return_value = member_doc

        result = await member_service.get_by_id(MEMBER_ID, CHURCH_ID)
        assert result is not None
        assert result["id"] == MEMBER_ID

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, member_service, mock_db):
        """Should return None when member not found."""
        mock_db.members.find_one.return_value = None
        result = await member_service.get_by_id(MEMBER_ID, CHURCH_ID)
        assert result is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_by_id_filters_by_church_id(self, member_service, mock_db):
        """Query should filter by both member_id and church_id for multi-tenancy."""
        mock_db.members.find_one.return_value = None
        await member_service.get_by_id(MEMBER_ID, CHURCH_ID)
        call_args = mock_db.members.find_one.call_args
        query = call_args[0][0]
        assert query["id"] == MEMBER_ID
        assert query["church_id"] == CHURCH_ID

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_by_id_with_projection(self, member_service, mock_db):
        """Should pass projection to MongoDB and always exclude _id."""
        mock_db.members.find_one.return_value = None
        await member_service.get_by_id(MEMBER_ID, CHURCH_ID, projection={"name": 1, "phone": 1})
        call_args = mock_db.members.find_one.call_args
        projection = call_args[0][1]
        assert projection["_id"] == 0
        assert projection["name"] == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_by_id_without_projection_excludes_mongo_id(self, member_service, mock_db):
        """Default projection should exclude _id."""
        mock_db.members.find_one.return_value = None
        await member_service.get_by_id(MEMBER_ID, CHURCH_ID)
        call_args = mock_db.members.find_one.call_args
        projection = call_args[0][1]
        assert projection == {"_id": 0}


class TestMemberServiceGetMany:
    """Test MemberService.get_many()."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_many_basic(self, member_service, mock_db):
        """Should return a list of members and total count."""
        members_list = [
            {"id": "m1", "name": "Alice"},
            {"id": "m2", "name": "Bob"},
        ]
        mock_db.members.aggregate = MagicMock(return_value=mock_facet_result(members_list))

        members, total = await member_service.get_many(CHURCH_ID)
        assert len(members) == 2
        assert total == 2

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_many_filters_by_campus_id(self, member_service, mock_db):
        """Should add campus_id to query when provided."""
        mock_db.members.aggregate = MagicMock(return_value=mock_facet_result([]))

        await member_service.get_many(CHURCH_ID, campus_id=CAMPUS_ID)
        pipeline = mock_db.members.aggregate.call_args[0][0]
        match_stage = pipeline[0]["$match"]
        assert match_stage["campus_id"] == CAMPUS_ID

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_many_filters_by_search(self, member_service, mock_db):
        """Should add search regex to query when provided."""
        mock_db.members.aggregate = MagicMock(return_value=mock_facet_result([]))

        await member_service.get_many(CHURCH_ID, search="John")
        pipeline = mock_db.members.aggregate.call_args[0][0]
        match_stage = pipeline[0]["$match"]
        assert "$or" in match_stage
        assert len(match_stage["$or"]) == 3  # name, phone, email

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_many_filters_by_engagement_status(self, member_service, mock_db):
        """Should add engagement_status filter when provided."""
        mock_db.members.aggregate = MagicMock(return_value=mock_facet_result([]))

        await member_service.get_many(CHURCH_ID, engagement_status=EngagementStatus.AT_RISK.value)
        pipeline = mock_db.members.aggregate.call_args[0][0]
        match_stage = pipeline[0]["$match"]
        assert match_stage["engagement_status"] == "at_risk"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_many_respects_max_page_size(self, member_service, mock_db):
        """Limit should be capped at MAX_PAGE_SIZE."""
        mock_db.members.aggregate = MagicMock(return_value=mock_facet_result([]))

        await member_service.get_many(CHURCH_ID, limit=MAX_PAGE_SIZE + 500)
        pipeline = mock_db.members.aggregate.call_args[0][0]
        facet_data = pipeline[-1]["$facet"]["data"]
        limit_stage = next(s for s in facet_data if "$limit" in s)
        assert limit_stage["$limit"] == MAX_PAGE_SIZE

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_many_search_escapes_regex_special_chars(self, member_service, mock_db):
        """Search text with regex special chars should be escaped."""
        mock_db.members.aggregate = MagicMock(return_value=mock_facet_result([]))

        await member_service.get_many(CHURCH_ID, search="John.Doe+")
        pipeline = mock_db.members.aggregate.call_args[0][0]
        match_stage = pipeline[0]["$match"]
        name_regex = match_stage["$or"][0]["name"]["$regex"]
        assert "\\." in name_regex
        assert "\\+" in name_regex

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_many_empty_result(self, member_service, mock_db):
        """Should return empty list and zero count when no members."""
        mock_db.members.aggregate = MagicMock(return_value=mock_facet_result([]))

        members, total = await member_service.get_many(CHURCH_ID)
        assert members == []
        assert total == 0


class TestMemberServiceCreate:
    """Test MemberService.create()."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_member_success(self, member_service, mock_db):
        """Should create a member and log activity."""
        data = _make_member_data()
        result = await member_service.create(data, CHURCH_ID, CAMPUS_ID, USER_ID, USER_NAME)

        assert result["name"] == "John Doe"
        assert result["church_id"] == CHURCH_ID
        assert result["campus_id"] == CAMPUS_ID
        assert result["engagement_status"] == EngagementStatus.ACTIVE.value
        assert result["days_since_last_contact"] == 0
        mock_db.members.insert_one.assert_called_once()
        mock_db.activity_logs.insert_one.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_member_normalizes_phone(self, member_service, mock_db):
        """Phone numbers starting with 0 should be normalized to +62."""
        data = _make_member_data(phone="081234567890")
        result = await member_service.create(data, CHURCH_ID, CAMPUS_ID, USER_ID, USER_NAME)
        assert result["phone"] == "+6281234567890"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_member_with_no_phone(self, member_service, mock_db):
        """Member with no phone should have None phone."""
        data = _make_member_data(phone=None)
        result = await member_service.create(data, CHURCH_ID, CAMPUS_ID, USER_ID, USER_NAME)
        assert result["phone"] is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_member_generates_uuid(self, member_service, mock_db):
        """Created member should have a valid UUID id."""
        data = _make_member_data()
        result = await member_service.create(data, CHURCH_ID, CAMPUS_ID, USER_ID, USER_NAME)
        assert result["id"] is not None
        assert len(result["id"]) == 36  # UUID format

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_member_sets_timestamps(self, member_service, mock_db):
        """Created member should have created_at and updated_at timestamps."""
        data = _make_member_data()
        result = await member_service.create(data, CHURCH_ID, CAMPUS_ID, USER_ID, USER_NAME)
        assert result["created_at"] is not None
        assert result["updated_at"] is not None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_member_logs_activity(self, member_service, mock_db):
        """Creating a member should log a CREATE_MEMBER activity."""
        data = _make_member_data()
        await member_service.create(data, CHURCH_ID, CAMPUS_ID, USER_ID, USER_NAME)

        log_call = mock_db.activity_logs.insert_one.call_args
        log_doc = log_call[0][0]
        assert log_doc["action"] == ActivityActionType.CREATE_MEMBER.value
        assert log_doc["user_id"] == USER_ID
        assert log_doc["user_name"] == USER_NAME

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_member_excludes_mongo_id(self, member_service, mock_db):
        """Returned member doc should not contain MongoDB _id field."""
        data = _make_member_data()
        # Simulate MongoDB adding _id
        result = await member_service.create(data, CHURCH_ID, CAMPUS_ID, USER_ID, USER_NAME)
        assert "_id" not in result


class TestMemberServiceUpdate:
    """Test MemberService.update()."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_update_member_not_found(self, member_service, mock_db):
        """Should return None when member doesn't exist."""
        mock_db.members.find_one.return_value = None
        data = _make_member_update(name="Updated Name")
        result = await member_service.update(MEMBER_ID, CHURCH_ID, data, USER_ID, USER_NAME)
        assert result is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_update_member_success(self, member_service, mock_db):
        """Should update member and return updated document."""
        existing = {"id": MEMBER_ID, "name": "Old Name", "church_id": CHURCH_ID, "campus_id": CAMPUS_ID}
        updated = {"id": MEMBER_ID, "name": "New Name", "church_id": CHURCH_ID, "campus_id": CAMPUS_ID}
        mock_db.members.find_one.side_effect = [existing, updated]

        data = _make_member_update(name="New Name")
        result = await member_service.update(MEMBER_ID, CHURCH_ID, data, USER_ID, USER_NAME)

        mock_db.members.update_one.assert_called_once()
        assert result["name"] == "New Name"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_update_member_only_sets_provided_fields(self, member_service, mock_db):
        """Only fields with non-None values should be updated."""
        existing = {"id": MEMBER_ID, "name": "Old Name", "church_id": CHURCH_ID, "campus_id": CAMPUS_ID}
        mock_db.members.find_one.side_effect = [existing, existing]

        data = _make_member_update(name="New Name")
        await member_service.update(MEMBER_ID, CHURCH_ID, data, USER_ID, USER_NAME)

        update_call = mock_db.members.update_one.call_args
        set_data = update_call[0][1]["$set"]
        # Should contain name and updated_at, but not phone, email, etc.
        assert "name" in set_data
        assert "updated_at" in set_data
        assert "phone" not in set_data
        assert "email" not in set_data

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_update_member_normalizes_phone(self, member_service, mock_db):
        """Updated phone numbers should be normalized."""
        existing = {"id": MEMBER_ID, "name": "Test", "church_id": CHURCH_ID, "campus_id": CAMPUS_ID}
        mock_db.members.find_one.side_effect = [existing, existing]

        data = _make_member_update(phone="081234567890")
        await member_service.update(MEMBER_ID, CHURCH_ID, data, USER_ID, USER_NAME)

        update_call = mock_db.members.update_one.call_args
        set_data = update_call[0][1]["$set"]
        assert set_data["phone"] == "+6281234567890"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_update_member_logs_activity(self, member_service, mock_db):
        """Updating a member should log an UPDATE_MEMBER activity."""
        existing = {"id": MEMBER_ID, "name": "Old Name", "church_id": CHURCH_ID, "campus_id": CAMPUS_ID}
        mock_db.members.find_one.side_effect = [existing, existing]

        data = _make_member_update(name="New Name")
        await member_service.update(MEMBER_ID, CHURCH_ID, data, USER_ID, USER_NAME)

        log_call = mock_db.activity_logs.insert_one.call_args
        log_doc = log_call[0][0]
        assert log_doc["action"] == ActivityActionType.UPDATE_MEMBER.value
        assert "updated_fields" in log_doc["details"]


class TestMemberServiceDelete:
    """Test MemberService.delete()."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_delete_member_not_found(self, member_service, mock_db):
        """Should return False when member doesn't exist."""
        mock_db.members.find_one.return_value = None
        result = await member_service.delete(MEMBER_ID, CHURCH_ID, USER_ID, USER_NAME)
        assert result is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_delete_member_success(self, member_service, mock_db):
        """Should delete member, related care events, and log activity."""
        existing = {"id": MEMBER_ID, "name": "John", "church_id": CHURCH_ID, "campus_id": CAMPUS_ID}
        mock_db.members.find_one.return_value = existing

        result = await member_service.delete(MEMBER_ID, CHURCH_ID, USER_ID, USER_NAME)

        assert result is True
        mock_db.members.delete_one.assert_called_once()
        mock_db.care_events.delete_many.assert_called_once()
        mock_db.activity_logs.insert_one.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_delete_member_cascades_care_events(self, member_service, mock_db):
        """Deleting a member should also delete their care events."""
        existing = {"id": MEMBER_ID, "name": "John", "church_id": CHURCH_ID, "campus_id": CAMPUS_ID}
        mock_db.members.find_one.return_value = existing

        await member_service.delete(MEMBER_ID, CHURCH_ID, USER_ID, USER_NAME)

        delete_events_call = mock_db.care_events.delete_many.call_args
        assert delete_events_call[0][0]["member_id"] == MEMBER_ID
        assert delete_events_call[0][0]["church_id"] == CHURCH_ID

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_delete_member_logs_activity(self, member_service, mock_db):
        """Deleting a member should log a DELETE_MEMBER activity."""
        existing = {"id": MEMBER_ID, "name": "John", "church_id": CHURCH_ID, "campus_id": CAMPUS_ID}
        mock_db.members.find_one.return_value = existing

        await member_service.delete(MEMBER_ID, CHURCH_ID, USER_ID, USER_NAME)

        log_call = mock_db.activity_logs.insert_one.call_args
        log_doc = log_call[0][0]
        assert log_doc["action"] == ActivityActionType.DELETE_MEMBER.value
        assert log_doc["member_name"] == "John"


class TestMemberServiceEngagement:
    """Test MemberService engagement status methods."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_update_engagement_active(self, member_service, mock_db):
        """Member contacted recently should be ACTIVE."""
        recent_date = datetime.now(UTC) - timedelta(days=10)
        member = {"id": MEMBER_ID, "last_contact_date": recent_date}
        mock_db.members.find_one.return_value = member

        await member_service.update_engagement(MEMBER_ID, CHURCH_ID)

        update_call = mock_db.members.update_one.call_args
        set_data = update_call[0][1]["$set"]
        assert set_data["engagement_status"] == EngagementStatus.ACTIVE.value

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_update_engagement_at_risk(self, member_service, mock_db):
        """Member not contacted for 60-89 days should be AT_RISK."""
        old_date = datetime.now(UTC) - timedelta(days=75)
        member = {"id": MEMBER_ID, "last_contact_date": old_date}
        mock_db.members.find_one.return_value = member

        await member_service.update_engagement(MEMBER_ID, CHURCH_ID)

        update_call = mock_db.members.update_one.call_args
        set_data = update_call[0][1]["$set"]
        assert set_data["engagement_status"] == EngagementStatus.AT_RISK.value

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_update_engagement_disconnected(self, member_service, mock_db):
        """Member not contacted for 90+ days should be DISCONNECTED."""
        old_date = datetime.now(UTC) - timedelta(days=120)
        member = {"id": MEMBER_ID, "last_contact_date": old_date}
        mock_db.members.find_one.return_value = member

        await member_service.update_engagement(MEMBER_ID, CHURCH_ID)

        update_call = mock_db.members.update_one.call_args
        set_data = update_call[0][1]["$set"]
        assert set_data["engagement_status"] == EngagementStatus.DISCONNECTED.value

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_update_engagement_no_contact_date(self, member_service, mock_db):
        """Member with no last_contact_date should be DISCONNECTED."""
        member = {"id": MEMBER_ID, "last_contact_date": None}
        mock_db.members.find_one.return_value = member

        await member_service.update_engagement(MEMBER_ID, CHURCH_ID)

        update_call = mock_db.members.update_one.call_args
        set_data = update_call[0][1]["$set"]
        assert set_data["engagement_status"] == EngagementStatus.DISCONNECTED.value

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_update_engagement_member_not_found(self, member_service, mock_db):
        """Should return without updating if member not found."""
        mock_db.members.find_one.return_value = None
        await member_service.update_engagement(MEMBER_ID, CHURCH_ID)
        mock_db.members.update_one.assert_not_called()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_update_engagement_custom_thresholds(self, member_service, mock_db):
        """Custom threshold values should override defaults."""
        # 25 days ago - would be ACTIVE with default 60, but AT_RISK with 20
        contact_date = datetime.now(UTC) - timedelta(days=25)
        member = {"id": MEMBER_ID, "last_contact_date": contact_date}
        mock_db.members.find_one.return_value = member

        await member_service.update_engagement(MEMBER_ID, CHURCH_ID, at_risk_days=20, disconnected_days=40)

        update_call = mock_db.members.update_one.call_args
        set_data = update_call[0][1]["$set"]
        assert set_data["engagement_status"] == EngagementStatus.AT_RISK.value

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_update_last_contact_default_date(self, member_service, mock_db):
        """update_last_contact with no date should use current time."""
        await member_service.update_last_contact(MEMBER_ID, CHURCH_ID)

        update_call = mock_db.members.update_one.call_args
        set_data = update_call[0][1]["$set"]
        assert set_data["engagement_status"] == EngagementStatus.ACTIVE.value
        assert set_data["days_since_last_contact"] == 0
        assert set_data["last_contact_date"] is not None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_update_last_contact_specific_date(self, member_service, mock_db):
        """update_last_contact with specific date should use that date."""
        specific_date = datetime(2025, 1, 15, tzinfo=UTC)
        await member_service.update_last_contact(MEMBER_ID, CHURCH_ID, contact_date=specific_date)

        update_call = mock_db.members.update_one.call_args
        set_data = update_call[0][1]["$set"]
        assert set_data["last_contact_date"] == specific_date


class TestMemberServiceGetAtRisk:
    """Test MemberService.get_at_risk_members()."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_at_risk_members_basic(self, member_service, mock_db):
        """Should query for AT_RISK and DISCONNECTED members."""
        at_risk_members = [
            {"id": "m1", "name": "At Risk Member", "engagement_status": "at_risk"},
        ]
        cursor = mock_db.members.find.return_value
        cursor.to_list.return_value = at_risk_members

        result = await member_service.get_at_risk_members(CHURCH_ID)
        assert len(result) == 1

        query = mock_db.members.find.call_args[0][0]
        assert query["engagement_status"]["$in"] == [
            EngagementStatus.AT_RISK.value,
            EngagementStatus.DISCONNECTED.value,
        ]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_at_risk_members_with_campus_filter(self, member_service, mock_db):
        """Should filter by campus_id when provided."""
        cursor = mock_db.members.find.return_value
        cursor.to_list.return_value = []

        await member_service.get_at_risk_members(CHURCH_ID, campus_id=CAMPUS_ID)
        query = mock_db.members.find.call_args[0][0]
        assert query["campus_id"] == CAMPUS_ID

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_at_risk_members_sorted_by_days(self, member_service, mock_db):
        """Results should be sorted by days_since_last_contact descending."""
        cursor = mock_db.members.find.return_value
        cursor.to_list.return_value = []

        await member_service.get_at_risk_members(CHURCH_ID)
        cursor.sort.assert_called_with("days_since_last_contact", -1)


# ===================================================================
# CareEventService Tests
# ===================================================================


class TestCareEventServiceGetById:
    """Test CareEventService.get_by_id()."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_by_id_found(self, care_event_service, mock_db):
        """Should return event when found."""
        event = {"id": EVENT_ID, "event_type": "birthday", "church_id": CHURCH_ID}
        mock_db.care_events.find_one.return_value = event

        result = await care_event_service.get_by_id(EVENT_ID, CHURCH_ID)
        assert result is not None
        assert result["id"] == EVENT_ID

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, care_event_service, mock_db):
        """Should return None when event not found."""
        mock_db.care_events.find_one.return_value = None
        result = await care_event_service.get_by_id(EVENT_ID, CHURCH_ID)
        assert result is None


class TestCareEventServiceGetForMember:
    """Test CareEventService.get_for_member()."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_for_member_basic(self, care_event_service, mock_db):
        """Should return events for a member."""
        events = [{"id": "e1"}, {"id": "e2"}]
        mock_db.care_events.aggregate = MagicMock(return_value=mock_facet_result(events))

        result, total = await care_event_service.get_for_member(MEMBER_ID, CHURCH_ID)
        assert len(result) == 2
        assert total == 2

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_for_member_filters_by_event_type(self, care_event_service, mock_db):
        """Should filter by event_type when provided."""
        mock_db.care_events.aggregate = MagicMock(return_value=mock_facet_result([]))

        await care_event_service.get_for_member(MEMBER_ID, CHURCH_ID, event_type="birthday")
        pipeline = mock_db.care_events.aggregate.call_args[0][0]
        match_stage = pipeline[0]["$match"]
        assert match_stage["event_type"] == "birthday"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_for_member_filters_by_completion(self, care_event_service, mock_db):
        """Should filter by is_completed when provided."""
        mock_db.care_events.aggregate = MagicMock(return_value=mock_facet_result([]))

        await care_event_service.get_for_member(MEMBER_ID, CHURCH_ID, is_completed=False)
        pipeline = mock_db.care_events.aggregate.call_args[0][0]
        match_stage = pipeline[0]["$match"]
        assert match_stage["is_completed"] is False


class TestCareEventServiceGetPendingTasks:
    """Test CareEventService.get_pending_tasks()."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_pending_tasks_basic(self, care_event_service, mock_db):
        """Should query for non-completed, non-ignored tasks."""
        agg_cursor = mock_db.care_events.aggregate.return_value
        agg_cursor.to_list.return_value = [{"id": "e1", "event_type": "birthday"}]

        result = await care_event_service.get_pending_tasks(CHURCH_ID)
        assert len(result) == 1

        pipeline = mock_db.care_events.aggregate.call_args[0][0]
        match_stage = pipeline[0]["$match"]
        assert match_stage["is_completed"] is False
        assert match_stage["is_ignored"] is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_pending_tasks_with_campus_filter(self, care_event_service, mock_db):
        """Should filter by campus_id when provided."""
        agg_cursor = mock_db.care_events.aggregate.return_value
        agg_cursor.to_list.return_value = []

        await care_event_service.get_pending_tasks(CHURCH_ID, campus_id=CAMPUS_ID)
        pipeline = mock_db.care_events.aggregate.call_args[0][0]
        match_stage = pipeline[0]["$match"]
        assert match_stage["campus_id"] == CAMPUS_ID

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_pending_tasks_with_event_types(self, care_event_service, mock_db):
        """Should filter by event_types when provided."""
        agg_cursor = mock_db.care_events.aggregate.return_value
        agg_cursor.to_list.return_value = []

        await care_event_service.get_pending_tasks(CHURCH_ID, event_types=["birthday", "grief_loss"])
        pipeline = mock_db.care_events.aggregate.call_args[0][0]
        match_stage = pipeline[0]["$match"]
        assert match_stage["event_type"] == {"$in": ["birthday", "grief_loss"]}

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_pending_tasks_with_due_before(self, care_event_service, mock_db):
        """Should filter tasks due before the given date."""
        agg_cursor = mock_db.care_events.aggregate.return_value
        agg_cursor.to_list.return_value = []

        due_date = datetime.now(UTC)
        await care_event_service.get_pending_tasks(CHURCH_ID, due_before=due_date)
        pipeline = mock_db.care_events.aggregate.call_args[0][0]
        match_stage = pipeline[0]["$match"]
        assert match_stage["event_date"] == {"$lte": due_date}


class TestCareEventServiceCreate:
    """Test CareEventService.create()."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_regular_event(self, care_event_service, mock_db):
        """Should create a regular care event and log activity."""
        data = _make_care_event_data()
        result = await care_event_service.create(data, MEMBER_ID, CHURCH_ID, CAMPUS_ID, USER_ID, USER_NAME, "John Doe")

        assert result["member_id"] == MEMBER_ID
        assert result["church_id"] == CHURCH_ID
        assert result["is_completed"] is False
        assert result["is_ignored"] is False
        mock_db.care_events.insert_one.assert_called_once()
        mock_db.activity_logs.insert_one.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_event_generates_uuid(self, care_event_service, mock_db):
        """Created event should have a valid UUID."""
        data = _make_care_event_data()
        result = await care_event_service.create(data, MEMBER_ID, CHURCH_ID, CAMPUS_ID, USER_ID, USER_NAME, "John Doe")
        assert result["id"] is not None
        assert len(result["id"]) == 36

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_grief_event_generates_timeline(self, care_event_service, mock_db):
        """Creating a grief event should auto-generate 6 follow-up events."""
        initial_date = datetime.now(UTC)
        data = _make_care_event_data(
            event_type=EventType.GRIEF_LOSS.value,
            event_date=initial_date,
            description="Loss of father",
        )

        await care_event_service.create(data, MEMBER_ID, CHURCH_ID, CAMPUS_ID, USER_ID, USER_NAME, "John Doe")

        # 1 original event + 6 grief timeline events = 7 inserts
        assert mock_db.care_events.insert_one.call_count == 7

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_accident_event_generates_followups(self, care_event_service, mock_db):
        """Creating an accident event should auto-generate 3 follow-up events."""
        initial_date = datetime.now(UTC)
        data = _make_care_event_data(
            event_type=EventType.ACCIDENT_ILLNESS.value,
            event_date=initial_date,
            description="Car accident",
        )

        await care_event_service.create(data, MEMBER_ID, CHURCH_ID, CAMPUS_ID, USER_ID, USER_NAME, "John Doe")

        # 1 original event + 3 accident followups = 4 inserts
        assert mock_db.care_events.insert_one.call_count == 4

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_birthday_event_no_timeline(self, care_event_service, mock_db):
        """Creating a birthday event should NOT generate follow-up events."""
        data = _make_care_event_data(event_type=EventType.BIRTHDAY.value)

        await care_event_service.create(data, MEMBER_ID, CHURCH_ID, CAMPUS_ID, USER_ID, USER_NAME, "John Doe")

        # Only 1 original event insert
        assert mock_db.care_events.insert_one.call_count == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_event_logs_activity(self, care_event_service, mock_db):
        """Creating an event should log a CREATE_CARE_EVENT activity."""
        data = _make_care_event_data()
        await care_event_service.create(data, MEMBER_ID, CHURCH_ID, CAMPUS_ID, USER_ID, USER_NAME, "John Doe")

        log_call = mock_db.activity_logs.insert_one.call_args
        log_doc = log_call[0][0]
        assert log_doc["action"] == ActivityActionType.CREATE_CARE_EVENT.value
        assert log_doc["member_id"] == MEMBER_ID
        assert log_doc["member_name"] == "John Doe"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_event_excludes_mongo_id(self, care_event_service, mock_db):
        """Returned event doc should not contain MongoDB _id field."""
        data = _make_care_event_data()
        result = await care_event_service.create(data, MEMBER_ID, CHURCH_ID, CAMPUS_ID, USER_ID, USER_NAME, "John Doe")
        assert "_id" not in result


class TestCareEventServiceGriefTimeline:
    """Test CareEventService._generate_grief_timeline() in detail."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_grief_timeline_generates_6_stages(self, care_event_service, mock_db):
        """Grief timeline should generate exactly 6 follow-up events."""
        initial_date = datetime(2025, 6, 1, tzinfo=UTC)

        event_ids = await care_event_service._generate_grief_timeline(
            MEMBER_ID, CHURCH_ID, CAMPUS_ID, initial_date, USER_ID, "Loss description"
        )

        assert len(event_ids) == 6
        assert mock_db.care_events.insert_one.call_count == 6

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_grief_timeline_correct_dates(self, care_event_service, mock_db):
        """Each grief follow-up should be scheduled at the correct offset."""
        initial_date = datetime(2025, 6, 1, tzinfo=UTC)

        await care_event_service._generate_grief_timeline(
            MEMBER_ID, CHURCH_ID, CAMPUS_ID, initial_date, USER_ID, "Loss"
        )

        expected_offsets = [
            GRIEF_ONE_WEEK_DAYS,
            GRIEF_TWO_WEEKS_DAYS,
            GRIEF_ONE_MONTH_DAYS,
            GRIEF_THREE_MONTHS_DAYS,
            GRIEF_SIX_MONTHS_DAYS,
            GRIEF_ONE_YEAR_DAYS,
        ]

        for i, offset in enumerate(expected_offsets):
            call_args = mock_db.care_events.insert_one.call_args_list[i]
            event_doc = call_args[0][0]
            expected_date = initial_date + timedelta(days=offset)
            assert event_doc["event_date"] == expected_date

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_grief_timeline_correct_stages(self, care_event_service, mock_db):
        """Each grief follow-up should have the correct grief_stage."""
        initial_date = datetime(2025, 6, 1, tzinfo=UTC)

        await care_event_service._generate_grief_timeline(MEMBER_ID, CHURCH_ID, CAMPUS_ID, initial_date, USER_ID, None)

        expected_stages = [
            GriefStage.ONE_WEEK.value,
            GriefStage.TWO_WEEKS.value,
            GriefStage.ONE_MONTH.value,
            GriefStage.THREE_MONTHS.value,
            GriefStage.SIX_MONTHS.value,
            GriefStage.ONE_YEAR.value,
        ]

        for i, expected_stage in enumerate(expected_stages):
            call_args = mock_db.care_events.insert_one.call_args_list[i]
            event_doc = call_args[0][0]
            assert event_doc["grief_stage"] == expected_stage

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_grief_timeline_event_type_is_grief(self, care_event_service, mock_db):
        """All timeline events should have grief_loss event type."""
        initial_date = datetime(2025, 6, 1, tzinfo=UTC)

        await care_event_service._generate_grief_timeline(
            MEMBER_ID, CHURCH_ID, CAMPUS_ID, initial_date, USER_ID, "Loss"
        )

        for call_args in mock_db.care_events.insert_one.call_args_list:
            event_doc = call_args[0][0]
            assert event_doc["event_type"] == EventType.GRIEF_LOSS.value

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_grief_timeline_all_uncompleted(self, care_event_service, mock_db):
        """All generated timeline events should be uncompleted."""
        initial_date = datetime(2025, 6, 1, tzinfo=UTC)

        await care_event_service._generate_grief_timeline(
            MEMBER_ID, CHURCH_ID, CAMPUS_ID, initial_date, USER_ID, "Loss"
        )

        for call_args in mock_db.care_events.insert_one.call_args_list:
            event_doc = call_args[0][0]
            assert event_doc["is_completed"] is False
            assert event_doc["is_ignored"] is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_grief_timeline_description_includes_stage(self, care_event_service, mock_db):
        """Timeline event descriptions should include the stage description."""
        initial_date = datetime(2025, 6, 1, tzinfo=UTC)

        await care_event_service._generate_grief_timeline(
            MEMBER_ID, CHURCH_ID, CAMPUS_ID, initial_date, USER_ID, "Father passed"
        )

        first_event = mock_db.care_events.insert_one.call_args_list[0][0][0]
        assert "Father passed" in first_event["description"]
        assert "1 week check-in" in first_event["description"]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_grief_timeline_none_description(self, care_event_service, mock_db):
        """When description is None, should use 'Grief support' as fallback."""
        initial_date = datetime(2025, 6, 1, tzinfo=UTC)

        await care_event_service._generate_grief_timeline(MEMBER_ID, CHURCH_ID, CAMPUS_ID, initial_date, USER_ID, None)

        first_event = mock_db.care_events.insert_one.call_args_list[0][0][0]
        assert "Grief support" in first_event["description"]


class TestCareEventServiceAccidentFollowups:
    """Test CareEventService._generate_accident_followups() in detail."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_accident_followups_generates_3_events(self, care_event_service, mock_db):
        """Accident followups should generate exactly 3 events."""
        initial_date = datetime(2025, 6, 1, tzinfo=UTC)

        event_ids = await care_event_service._generate_accident_followups(
            MEMBER_ID, CHURCH_ID, CAMPUS_ID, initial_date, USER_ID, "Car accident"
        )

        assert len(event_ids) == 3
        assert mock_db.care_events.insert_one.call_count == 3

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_accident_followups_correct_dates(self, care_event_service, mock_db):
        """Each followup should be scheduled at the correct offset (3, 7, 14 days)."""
        initial_date = datetime(2025, 6, 1, tzinfo=UTC)

        await care_event_service._generate_accident_followups(
            MEMBER_ID, CHURCH_ID, CAMPUS_ID, initial_date, USER_ID, "Accident"
        )

        expected_offsets = [
            ACCIDENT_FIRST_FOLLOWUP_DAYS,
            ACCIDENT_SECOND_FOLLOWUP_DAYS,
            ACCIDENT_FINAL_FOLLOWUP_DAYS,
        ]

        for i, offset in enumerate(expected_offsets):
            call_args = mock_db.care_events.insert_one.call_args_list[i]
            event_doc = call_args[0][0]
            expected_date = initial_date + timedelta(days=offset)
            assert event_doc["event_date"] == expected_date

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_accident_followups_event_type(self, care_event_service, mock_db):
        """All followup events should have accident_illness type."""
        initial_date = datetime(2025, 6, 1, tzinfo=UTC)

        await care_event_service._generate_accident_followups(
            MEMBER_ID, CHURCH_ID, CAMPUS_ID, initial_date, USER_ID, "Accident"
        )

        for call_args in mock_db.care_events.insert_one.call_args_list:
            event_doc = call_args[0][0]
            assert event_doc["event_type"] == EventType.ACCIDENT_ILLNESS.value

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_accident_followups_none_description(self, care_event_service, mock_db):
        """When description is None, should use 'Accident/Illness' as fallback."""
        initial_date = datetime(2025, 6, 1, tzinfo=UTC)

        await care_event_service._generate_accident_followups(
            MEMBER_ID, CHURCH_ID, CAMPUS_ID, initial_date, USER_ID, None
        )

        first_event = mock_db.care_events.insert_one.call_args_list[0][0][0]
        assert "Accident/Illness" in first_event["description"]


class TestCareEventServiceComplete:
    """Test CareEventService.complete()."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_complete_event_not_found(self, care_event_service, mock_db):
        """Should return None when event not found."""
        mock_db.care_events.find_one.return_value = None
        result = await care_event_service.complete(EVENT_ID, CHURCH_ID, USER_ID, USER_NAME)
        assert result is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_complete_event_success(self, care_event_service, mock_db):
        """Should mark event as completed and update member last_contact_date."""
        event = {
            "id": EVENT_ID,
            "member_id": MEMBER_ID,
            "event_type": "birthday",
            "church_id": CHURCH_ID,
            "campus_id": CAMPUS_ID,
        }
        completed_event = {**event, "is_completed": True}
        member = {"id": MEMBER_ID, "name": "John Doe"}

        mock_db.care_events.find_one.side_effect = [event, completed_event]
        mock_db.members.find_one.return_value = member

        result = await care_event_service.complete(EVENT_ID, CHURCH_ID, USER_ID, USER_NAME)

        assert result is not None
        # Should update care event
        mock_db.care_events.update_one.assert_called_once()
        update_args = mock_db.care_events.update_one.call_args
        set_data = update_args[0][1]["$set"]
        assert set_data["is_completed"] is True
        assert set_data["completed_by"] == USER_ID

        # Should update member's last contact date
        mock_db.members.update_one.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_complete_event_with_notes(self, care_event_service, mock_db):
        """Completion notes should be saved."""
        event = {
            "id": EVENT_ID,
            "member_id": MEMBER_ID,
            "event_type": "birthday",
            "church_id": CHURCH_ID,
            "campus_id": CAMPUS_ID,
        }
        mock_db.care_events.find_one.side_effect = [event, event]
        mock_db.members.find_one.return_value = {"id": MEMBER_ID, "name": "John"}

        await care_event_service.complete(
            EVENT_ID, CHURCH_ID, USER_ID, USER_NAME, notes="Called and wished happy birthday"
        )

        update_args = mock_db.care_events.update_one.call_args
        set_data = update_args[0][1]["$set"]
        assert set_data["completion_notes"] == "Called and wished happy birthday"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_complete_event_logs_activity(self, care_event_service, mock_db):
        """Completing an event should log a COMPLETE_TASK activity."""
        event = {
            "id": EVENT_ID,
            "member_id": MEMBER_ID,
            "event_type": "birthday",
            "church_id": CHURCH_ID,
            "campus_id": CAMPUS_ID,
        }
        mock_db.care_events.find_one.side_effect = [event, event]
        mock_db.members.find_one.return_value = {"id": MEMBER_ID, "name": "John"}

        await care_event_service.complete(EVENT_ID, CHURCH_ID, USER_ID, USER_NAME)

        log_call = mock_db.activity_logs.insert_one.call_args
        log_doc = log_call[0][0]
        assert log_doc["action"] == ActivityActionType.COMPLETE_TASK.value


class TestCareEventServiceIgnore:
    """Test CareEventService.ignore()."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_ignore_event_not_found(self, care_event_service, mock_db):
        """Should return None when event not found."""
        mock_db.care_events.find_one.return_value = None
        result = await care_event_service.ignore(EVENT_ID, CHURCH_ID, USER_ID, USER_NAME)
        assert result is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_ignore_event_success(self, care_event_service, mock_db):
        """Should mark event as ignored."""
        event = {
            "id": EVENT_ID,
            "member_id": MEMBER_ID,
            "event_type": "birthday",
            "church_id": CHURCH_ID,
            "campus_id": CAMPUS_ID,
        }
        ignored_event = {**event, "is_ignored": True}
        member = {"id": MEMBER_ID, "name": "John"}

        mock_db.care_events.find_one.side_effect = [event, ignored_event]
        mock_db.members.find_one.return_value = member

        result = await care_event_service.ignore(EVENT_ID, CHURCH_ID, USER_ID, USER_NAME)

        assert result is not None
        update_args = mock_db.care_events.update_one.call_args
        set_data = update_args[0][1]["$set"]
        assert set_data["is_ignored"] is True
        assert set_data["ignored_by"] == USER_ID

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_ignore_event_with_reason(self, care_event_service, mock_db):
        """Ignore reason should be saved."""
        event = {
            "id": EVENT_ID,
            "member_id": MEMBER_ID,
            "event_type": "birthday",
            "church_id": CHURCH_ID,
            "campus_id": CAMPUS_ID,
        }
        mock_db.care_events.find_one.side_effect = [event, event]
        mock_db.members.find_one.return_value = {"id": MEMBER_ID, "name": "John"}

        await care_event_service.ignore(EVENT_ID, CHURCH_ID, USER_ID, USER_NAME, reason="Member relocated")

        update_args = mock_db.care_events.update_one.call_args
        set_data = update_args[0][1]["$set"]
        assert set_data["ignore_reason"] == "Member relocated"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_ignore_event_logs_activity(self, care_event_service, mock_db):
        """Ignoring an event should log an IGNORE_TASK activity."""
        event = {
            "id": EVENT_ID,
            "member_id": MEMBER_ID,
            "event_type": "birthday",
            "church_id": CHURCH_ID,
            "campus_id": CAMPUS_ID,
        }
        mock_db.care_events.find_one.side_effect = [event, event]
        mock_db.members.find_one.return_value = {"id": MEMBER_ID, "name": "John"}

        await care_event_service.ignore(EVENT_ID, CHURCH_ID, USER_ID, USER_NAME)

        log_call = mock_db.activity_logs.insert_one.call_args
        log_doc = log_call[0][0]
        assert log_doc["action"] == ActivityActionType.IGNORE_TASK.value


class TestCareEventServiceDelete:
    """Test CareEventService.delete()."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_delete_event_not_found(self, care_event_service, mock_db):
        """Should return False when event not found."""
        mock_db.care_events.find_one.return_value = None
        result = await care_event_service.delete(EVENT_ID, CHURCH_ID, USER_ID, USER_NAME)
        assert result is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_delete_event_success(self, care_event_service, mock_db):
        """Should delete event and log activity."""
        event = {
            "id": EVENT_ID,
            "member_id": MEMBER_ID,
            "event_type": "birthday",
            "church_id": CHURCH_ID,
            "campus_id": CAMPUS_ID,
        }
        mock_db.care_events.find_one.return_value = event
        mock_db.members.find_one.return_value = {"id": MEMBER_ID, "name": "John"}

        result = await care_event_service.delete(EVENT_ID, CHURCH_ID, USER_ID, USER_NAME)

        assert result is True
        mock_db.care_events.delete_one.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_delete_event_logs_activity(self, care_event_service, mock_db):
        """Deleting an event should log a DELETE_CARE_EVENT activity."""
        event = {
            "id": EVENT_ID,
            "member_id": MEMBER_ID,
            "event_type": "grief_loss",
            "church_id": CHURCH_ID,
            "campus_id": CAMPUS_ID,
        }
        mock_db.care_events.find_one.return_value = event
        mock_db.members.find_one.return_value = {"id": MEMBER_ID, "name": "John"}

        await care_event_service.delete(EVENT_ID, CHURCH_ID, USER_ID, USER_NAME)

        log_call = mock_db.activity_logs.insert_one.call_args
        log_doc = log_call[0][0]
        assert log_doc["action"] == ActivityActionType.DELETE_CARE_EVENT.value
        assert log_doc["event_type"] == "grief_loss"


# ===================================================================
# NotificationService Tests
# ===================================================================


class TestNotificationServiceSendWhatsApp:
    """Test NotificationService.send_whatsapp()."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_whatsapp_no_gateway_configured(self, notification_service, mock_db):
        """Should return error when WhatsApp gateway is not configured."""
        result = await notification_service.send_whatsapp("+6281234567890", "Hello!", CHURCH_ID)
        assert result["success"] is False
        assert "not configured" in result["error"]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_whatsapp_success(self, notification_service_with_wa, mock_db):
        """Should create notification log and return success."""
        result = await notification_service_with_wa.send_whatsapp("+6281234567890", "Hello!", CHURCH_ID)

        assert result["success"] is True
        assert "notification_id" in result
        mock_db.notification_logs.insert_one.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_whatsapp_truncates_long_message(self, notification_service_with_wa, mock_db):
        """Message in notification log should be truncated to 500 chars."""
        long_message = "x" * 1000
        await notification_service_with_wa.send_whatsapp("+6281234567890", long_message, CHURCH_ID)

        log_call = mock_db.notification_logs.insert_one.call_args
        log_doc = log_call[0][0]
        assert len(log_doc["message"]) == 500

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_whatsapp_logs_correct_fields(self, notification_service_with_wa, mock_db):
        """Notification log should contain correct fields."""
        await notification_service_with_wa.send_whatsapp(
            "+6281234567890", "Hello!", CHURCH_ID, member_id=MEMBER_ID, event_id=EVENT_ID
        )

        log_call = mock_db.notification_logs.insert_one.call_args
        log_doc = log_call[0][0]
        assert log_doc["church_id"] == CHURCH_ID
        assert log_doc["member_id"] == MEMBER_ID
        assert log_doc["event_id"] == EVENT_ID
        assert log_doc["channel"] == NotificationChannel.WHATSAPP.value
        assert log_doc["recipient"] == "+6281234567890"
        assert log_doc["status"] == NotificationStatus.PENDING.value


class TestNotificationServiceSendWhatsAppBackground:
    """Test NotificationService._send_whatsapp_background()."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_background_send_success(self, notification_service_with_wa, mock_db):
        """Successful background send should update status to SENT."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"id": "msg-123"}'
        mock_response.json.return_value = {"id": "msg-123"}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        with patch("services.http_client.get_http_client", new_callable=AsyncMock, return_value=mock_client):
            await notification_service_with_wa._send_whatsapp_background(
                "notif-123", "+6281234567890", "Hello!", retry=False
            )

        # Should have updated status to SENT
        update_calls = mock_db.notification_logs.update_one.call_args_list
        # The last update should be the success update
        last_update = update_calls[-1]
        set_data = last_update[0][1]["$set"]
        assert set_data["status"] == NotificationStatus.SENT.value

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_background_send_failure(self, notification_service_with_wa, mock_db):
        """Failed background send should update status to FAILED after retries."""
        import httpx

        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.ConnectError("Connection refused")
        with patch("services.http_client.get_http_client", new_callable=AsyncMock, return_value=mock_client):
            await notification_service_with_wa._send_whatsapp_background(
                "notif-123", "+6281234567890", "Hello!", retry=False
            )

        # Should have updated status to FAILED
        update_calls = mock_db.notification_logs.update_one.call_args_list
        last_update = update_calls[-1]
        set_data = last_update[0][1]["$set"]
        assert set_data["status"] == NotificationStatus.FAILED.value
        assert "Connection" in set_data["error"]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_background_send_http_error_status(self, notification_service_with_wa, mock_db):
        """Non-200/201 HTTP status should be treated as failure."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        with patch("services.http_client.get_http_client", new_callable=AsyncMock, return_value=mock_client):
            await notification_service_with_wa._send_whatsapp_background(
                "notif-123", "+6281234567890", "Hello!", retry=False
            )

        update_calls = mock_db.notification_logs.update_one.call_args_list
        last_update = update_calls[-1]
        set_data = last_update[0][1]["$set"]
        assert set_data["status"] == NotificationStatus.FAILED.value

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_background_send_timeout(self, notification_service_with_wa, mock_db):
        """Timeout should be handled gracefully."""
        import httpx

        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("Request timed out")
        with patch("services.http_client.get_http_client", new_callable=AsyncMock, return_value=mock_client):
            await notification_service_with_wa._send_whatsapp_background(
                "notif-123", "+6281234567890", "Hello!", retry=False
            )

        update_calls = mock_db.notification_logs.update_one.call_args_list
        last_update = update_calls[-1]
        set_data = last_update[0][1]["$set"]
        assert set_data["status"] == NotificationStatus.FAILED.value
        assert "Timeout" in set_data["error"]


class TestNotificationServiceBulkWhatsApp:
    """Test NotificationService.send_bulk_whatsapp()."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_bulk_whatsapp_no_gateway(self, notification_service, mock_db):
        """Without gateway, all sends should fail."""
        recipients = [
            {"phone": "+6281234567890", "message": "Hello 1"},
            {"phone": "+6281234567891", "message": "Hello 2"},
        ]

        result = await notification_service.send_bulk_whatsapp(recipients, CHURCH_ID)
        assert result["sent"] == 0
        assert result["failed"] == 2

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_bulk_whatsapp_success(self, notification_service_with_wa, mock_db):
        """With gateway configured, sends should return notification IDs."""
        recipients = [
            {"phone": "+6281234567890", "message": "Hello 1"},
            {"phone": "+6281234567891", "message": "Hello 2"},
        ]

        result = await notification_service_with_wa.send_bulk_whatsapp(recipients, CHURCH_ID, delay_between=0)
        assert result["sent"] == 2
        assert result["failed"] == 0
        assert len(result["notification_ids"]) == 2


class TestNotificationServiceGetStatus:
    """Test NotificationService.get_notification_status()."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_notification_status_found(self, notification_service, mock_db):
        """Should return notification log when found."""
        log = {"id": "notif-123", "status": "sent", "church_id": CHURCH_ID}
        mock_db.notification_logs.find_one.return_value = log

        result = await notification_service.get_notification_status("notif-123", CHURCH_ID)
        assert result is not None
        assert result["status"] == "sent"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_notification_status_not_found(self, notification_service, mock_db):
        """Should return None when notification not found."""
        mock_db.notification_logs.find_one.return_value = None
        result = await notification_service.get_notification_status("nonexistent", CHURCH_ID)
        assert result is None


class TestNotificationServiceGetRecent:
    """Test NotificationService.get_recent_notifications()."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_recent_notifications_basic(self, notification_service, mock_db):
        """Should return recent notifications for church."""
        notifications = [{"id": "n1"}, {"id": "n2"}]
        cursor = mock_db.notification_logs.find.return_value
        cursor.to_list.return_value = notifications

        result = await notification_service.get_recent_notifications(CHURCH_ID)
        assert len(result) == 2

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_recent_notifications_with_member_filter(self, notification_service, mock_db):
        """Should filter by member_id when provided."""
        cursor = mock_db.notification_logs.find.return_value
        cursor.to_list.return_value = []

        await notification_service.get_recent_notifications(CHURCH_ID, member_id=MEMBER_ID)
        query = mock_db.notification_logs.find.call_args[0][0]
        assert query["member_id"] == MEMBER_ID


# ===================================================================
# ImageService Tests
# ===================================================================


class TestImageServiceProcessSync:
    """Test ImageService._process_image_sync() for image resizing."""

    @pytest.mark.unit
    def test_process_image_sync_creates_all_sizes(self, tmp_path):
        """Should create one file for each size in the sizes dict."""
        from services.image_service import MEMBER_PHOTO_SIZES, ImageService

        # Create a test image in memory
        img = Image.new("RGB", (800, 600), color="red")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        image_bytes = buf.getvalue()

        output_base = tmp_path / "test_member"

        with patch("services.image_service.UPLOAD_DIR", tmp_path):
            results = ImageService._process_image_sync(image_bytes, MEMBER_PHOTO_SIZES, output_base)

        assert "thumbnail" in results
        assert "medium" in results
        assert "large" in results

        # Verify files were created
        for size_name in MEMBER_PHOTO_SIZES:
            path = tmp_path / f"test_member_{size_name}.jpg"
            assert path.exists()

    @pytest.mark.unit
    def test_process_image_sync_respects_max_dimensions(self, tmp_path):
        """Output images should not exceed the specified dimensions."""
        from services.image_service import ImageService

        # Create a large test image
        img = Image.new("RGB", (2000, 1500), color="blue")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        image_bytes = buf.getvalue()

        sizes = {"small": (100, 100)}
        output_base = tmp_path / "resize_test"

        with patch("services.image_service.UPLOAD_DIR", tmp_path):
            ImageService._process_image_sync(image_bytes, sizes, output_base)

        output_path = tmp_path / "resize_test_small.jpg"
        resized = Image.open(output_path)
        assert resized.width <= 100
        assert resized.height <= 100

    @pytest.mark.unit
    def test_process_image_sync_converts_rgba_to_rgb(self, tmp_path):
        """RGBA images should be converted to RGB for JPEG output."""
        from services.image_service import ImageService

        img = Image.new("RGBA", (200, 200), color=(255, 0, 0, 128))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        image_bytes = buf.getvalue()

        sizes = {"test": (100, 100)}
        output_base = tmp_path / "rgba_test"

        with patch("services.image_service.UPLOAD_DIR", tmp_path):
            results = ImageService._process_image_sync(image_bytes, sizes, output_base)
        assert "test" in results

        output_path = tmp_path / "rgba_test_test.jpg"
        resized = Image.open(output_path)
        assert resized.mode == "RGB"

    @pytest.mark.unit
    def test_process_image_sync_converts_palette_to_rgb(self, tmp_path):
        """Palette mode (P) images should be converted to RGB."""
        from services.image_service import ImageService

        img = Image.new("P", (200, 200))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        image_bytes = buf.getvalue()

        sizes = {"test": (100, 100)}
        output_base = tmp_path / "palette_test"

        with patch("services.image_service.UPLOAD_DIR", tmp_path):
            results = ImageService._process_image_sync(image_bytes, sizes, output_base)
        assert "test" in results

    @pytest.mark.unit
    def test_process_image_sync_maintains_aspect_ratio(self, tmp_path):
        """Thumbnail should maintain aspect ratio (not stretch)."""
        from services.image_service import ImageService

        # Create a non-square image (400x200)
        img = Image.new("RGB", (400, 200), color="green")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        image_bytes = buf.getvalue()

        sizes = {"test": (100, 100)}
        output_base = tmp_path / "aspect_test"

        with patch("services.image_service.UPLOAD_DIR", tmp_path):
            ImageService._process_image_sync(image_bytes, sizes, output_base)

        output_path = tmp_path / "aspect_test_test.jpg"
        resized = Image.open(output_path)
        # For a 400x200 image in a 100x100 box, thumbnail preserves aspect ratio
        # Width should be 100, height should be 50
        assert resized.width == 100
        assert resized.height == 50


class TestImageServiceProcessSingle:
    """Test ImageService._process_single_image_sync()."""

    @pytest.mark.unit
    def test_process_single_image_sync(self, tmp_path):
        """Should create a single resized image."""
        from services.image_service import USER_PHOTO_SIZE, ImageService

        img = Image.new("RGB", (800, 800), color="blue")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        image_bytes = buf.getvalue()

        output_path = tmp_path / "user_photo.jpg"

        with patch("services.image_service.UPLOAD_DIR", tmp_path):
            ImageService._process_single_image_sync(image_bytes, USER_PHOTO_SIZE, output_path)

        assert output_path.exists()
        resized = Image.open(output_path)
        assert resized.width <= 400
        assert resized.height <= 400

    @pytest.mark.unit
    def test_process_single_image_converts_rgba(self, tmp_path):
        """RGBA images should be converted to RGB."""
        from services.image_service import ImageService

        img = Image.new("RGBA", (500, 500), color=(0, 255, 0, 200))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        image_bytes = buf.getvalue()

        output_path = tmp_path / "user_rgba.jpg"

        with patch("services.image_service.UPLOAD_DIR", tmp_path):
            ImageService._process_single_image_sync(image_bytes, (400, 400), output_path)

        resized = Image.open(output_path)
        assert resized.mode == "RGB"


class TestImageServiceProcessMemberPhoto:
    """Test ImageService.process_member_photo() async method."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_member_photo(self, tmp_path):
        """Should generate all size variants for a member photo."""
        from services.image_service import ImageService

        img = Image.new("RGB", (800, 800), color="red")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        image_bytes = buf.getvalue()

        with patch("services.image_service.UPLOAD_DIR", tmp_path):
            results = await ImageService.process_member_photo(image_bytes, MEMBER_ID, CHURCH_ID)

        assert "thumbnail" in results
        assert "medium" in results
        assert "large" in results


class TestImageServiceProcessUserPhoto:
    """Test ImageService.process_user_photo() async method."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_user_photo(self, tmp_path):
        """Should generate a single resized photo for user."""
        from services.image_service import ImageService

        img = Image.new("RGB", (600, 600), color="blue")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        image_bytes = buf.getvalue()

        with patch("services.image_service.UPLOAD_DIR", tmp_path):
            result = await ImageService.process_user_photo(image_bytes, USER_ID)

        assert result is not None
        assert USER_ID in result


class TestImageServiceBackgroundProcessing:
    """Test ImageService background processing methods."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_member_photo_background_success(self, mock_db, tmp_path):
        """Should process photo and update member document."""
        from services.image_service import ImageService

        img = Image.new("RGB", (400, 400), color="red")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        image_bytes = buf.getvalue()

        with patch("services.image_service.UPLOAD_DIR", tmp_path):
            await ImageService.process_member_photo_background(image_bytes, MEMBER_ID, CHURCH_ID, mock_db)

        # Should update the member's photo_url in the database
        mock_db.members.update_one.assert_called_once()
        update_args = mock_db.members.update_one.call_args
        set_data = update_args[0][1]["$set"]
        assert "photo_url" in set_data
        assert "photo_sizes" in set_data
        assert MEMBER_ID in set_data["photo_url"]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_member_photo_background_error(self, mock_db):
        """Errors in background processing should be logged, not raised."""
        from services.image_service import ImageService

        # Pass invalid image bytes
        with patch("services.image_service.UPLOAD_DIR", MagicMock()):
            # This should not raise an exception
            await ImageService.process_member_photo_background(b"not-an-image", MEMBER_ID, CHURCH_ID, mock_db)

        # Member update should NOT have been called
        mock_db.members.update_one.assert_not_called()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_user_photo_background_success(self, mock_db, tmp_path):
        """Should process photo and update user document."""
        from services.image_service import ImageService

        img = Image.new("RGB", (400, 400), color="blue")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        image_bytes = buf.getvalue()

        with patch("services.image_service.UPLOAD_DIR", tmp_path):
            await ImageService.process_user_photo_background(image_bytes, USER_ID, mock_db)

        mock_db.users.update_one.assert_called_once()
        update_args = mock_db.users.update_one.call_args
        set_data = update_args[0][1]["$set"]
        assert "photo_url" in set_data
        assert USER_ID in set_data["photo_url"]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_user_photo_background_error(self, mock_db):
        """Errors in user photo processing should be logged, not raised."""
        from services.image_service import ImageService

        with patch("services.image_service.UPLOAD_DIR", MagicMock()):
            await ImageService.process_user_photo_background(b"not-an-image", USER_ID, mock_db)

        mock_db.users.update_one.assert_not_called()


class TestImageServiceDeletePhotos:
    """Test ImageService.delete_member_photos() and delete_user_photo()."""

    @pytest.mark.unit
    def test_delete_member_photos_existing(self, tmp_path):
        """Should delete all size variants of member photos."""
        from services.image_service import MEMBER_PHOTO_SIZES, ImageService

        # Create fake photo files
        member_dir = tmp_path / "members" / CHURCH_ID
        member_dir.mkdir(parents=True)
        for size_name in MEMBER_PHOTO_SIZES:
            (member_dir / f"{MEMBER_ID}_{size_name}.jpg").write_text("fake")

        with patch("services.image_service.UPLOAD_DIR", tmp_path):
            result = ImageService.delete_member_photos(MEMBER_ID, CHURCH_ID)

        assert result is True
        for size_name in MEMBER_PHOTO_SIZES:
            assert not (member_dir / f"{MEMBER_ID}_{size_name}.jpg").exists()

    @pytest.mark.unit
    def test_delete_member_photos_nonexistent(self, tmp_path):
        """Should return False when no photos exist to delete."""
        from services.image_service import ImageService

        member_dir = tmp_path / "members" / CHURCH_ID
        member_dir.mkdir(parents=True)

        with patch("services.image_service.UPLOAD_DIR", tmp_path):
            result = ImageService.delete_member_photos("nonexistent", CHURCH_ID)

        assert result is False

    @pytest.mark.unit
    def test_delete_user_photo_existing(self, tmp_path):
        """Should delete user photo file."""
        from services.image_service import ImageService

        users_dir = tmp_path / "users"
        users_dir.mkdir(parents=True)
        photo_path = users_dir / f"{USER_ID}.jpg"
        photo_path.write_text("fake")

        with patch("services.image_service.UPLOAD_DIR", tmp_path):
            result = ImageService.delete_user_photo(USER_ID)

        assert result is True
        assert not photo_path.exists()

    @pytest.mark.unit
    def test_delete_user_photo_nonexistent(self, tmp_path):
        """Should return False when user photo doesn't exist."""
        from services.image_service import ImageService

        users_dir = tmp_path / "users"
        users_dir.mkdir(parents=True)

        with patch("services.image_service.UPLOAD_DIR", tmp_path):
            result = ImageService.delete_user_photo("nonexistent")

        assert result is False


class TestImageServiceConstants:
    """Test ImageService constants are correctly defined."""

    @pytest.mark.unit
    def test_member_photo_sizes(self):
        """Member photo sizes should have thumbnail, medium, and large."""
        from services.image_service import MEMBER_PHOTO_SIZES

        assert "thumbnail" in MEMBER_PHOTO_SIZES
        assert "medium" in MEMBER_PHOTO_SIZES
        assert "large" in MEMBER_PHOTO_SIZES
        assert MEMBER_PHOTO_SIZES["thumbnail"] == (100, 100)
        assert MEMBER_PHOTO_SIZES["medium"] == (300, 300)
        assert MEMBER_PHOTO_SIZES["large"] == (600, 600)

    @pytest.mark.unit
    def test_user_photo_size(self):
        """User photo size should be 400x400."""
        from services.image_service import USER_PHOTO_SIZE

        assert USER_PHOTO_SIZE == (400, 400)

    @pytest.mark.unit
    def test_jpeg_quality(self):
        """JPEG quality should be 85."""
        from services.image_service import JPEG_QUALITY

        assert JPEG_QUALITY == 85


# Import PIL for image tests
try:
    from PIL import Image
except ImportError:
    pytest.skip("PIL/Pillow not installed", allow_module_level=True)
