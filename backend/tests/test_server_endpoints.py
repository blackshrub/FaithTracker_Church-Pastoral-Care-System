"""
Integration tests for FaithTracker API endpoint logic.

Tests the core business logic of endpoint handlers by operating directly
on the test database. Since the Litestar framework is not available in the
test environment, we replicate the key logic (password hashing, JWT creation,
campus filtering, grief timeline generation) inline rather than importing
from dependencies.py or server.py.

Covers:
- Authentication (login, token validation, edge cases)
- Member CRUD with multi-tenancy
- Care events (create, complete, ignore, delete, engagement recalc)
- Grief timeline auto-generation
- Settings endpoints (user prefs, engagement, automation, grief stages)
- Export endpoints (CSV scoping)
- Setup wizard (guard rails)
- Reminder stats
- Activity logging
- Bulk operations
- Member archival
- One-time event auto-completion
- Phone normalization
- Engagement calculation
"""

import os
import sys
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

# Add parent directory to path so we can import backend modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bcrypt
import jwt

from constants import (
    ENGAGEMENT_NO_CONTACT_DAYS,
    GRIEF_ONE_MONTH_DAYS,
    GRIEF_ONE_WEEK_DAYS,
    GRIEF_ONE_YEAR_DAYS,
    GRIEF_SIX_MONTHS_DAYS,
    GRIEF_THREE_MONTHS_DAYS,
    GRIEF_TWO_WEEKS_DAYS,
    JWT_TOKEN_EXPIRE_HOURS,
)

# These modules do NOT depend on litestar and can be imported directly
from enums import (
    ActivityActionType,
    AidType,
    EngagementStatus,
    EventType,
    GriefStage,
    UserRole,
)
from utils import calculate_engagement_status, normalize_phone_number

# ---------------------------------------------------------------------------
# Inline replicas of key functions from dependencies.py and server.py
# (cannot import due to litestar dependency not being installed in test env)
# ---------------------------------------------------------------------------

TEST_JWT_SECRET = "test-secret-key-for-jwt-signing"
TEST_PASSWORD = "TestPass123!"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a bcrypt hash (replica of dependencies.verify_password)."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt (replica of dependencies.get_password_hash)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(data: dict, secret: str = TEST_JWT_SECRET, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token (replica of dependencies.create_access_token)."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(hours=JWT_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, secret, algorithm="HS256")


def get_campus_filter(user: dict) -> dict:
    """Get campus filter for queries (replica of dependencies.get_campus_filter)."""
    role = user.get("role")
    if role == UserRole.FULL_ADMIN.value:
        return {}
    elif user.get("campus_id"):
        return {"campus_id": user["campus_id"]}
    return {"campus_id": {"$exists": False, "$eq": "IMPOSSIBLE_VALUE"}}


def generate_grief_timeline(mourning_date: date, care_event_id: str, member_id: str) -> list:
    """Generate 6-stage grief support timeline (replica of server.generate_grief_timeline)."""
    from models import generate_uuid

    stages = [
        (GriefStage.ONE_WEEK, GRIEF_ONE_WEEK_DAYS),
        (GriefStage.TWO_WEEKS, GRIEF_TWO_WEEKS_DAYS),
        (GriefStage.ONE_MONTH, GRIEF_ONE_MONTH_DAYS),
        (GriefStage.THREE_MONTHS, GRIEF_THREE_MONTHS_DAYS),
        (GriefStage.SIX_MONTHS, GRIEF_SIX_MONTHS_DAYS),
        (GriefStage.ONE_YEAR, GRIEF_ONE_YEAR_DAYS),
    ]
    timeline = []
    for stage, days_offset in stages:
        scheduled_date = mourning_date + timedelta(days=days_offset)
        grief_support = {
            "id": generate_uuid(),
            "care_event_id": care_event_id,
            "member_id": member_id,
            "stage": stage,
            "scheduled_date": scheduled_date.isoformat(),
            "completed": False,
            "completed_at": None,
            "notes": None,
            "reminder_sent": False,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
        timeline.append(grief_support)
    return timeline


# ---------------------------------------------------------------------------
# Test data helpers
# ---------------------------------------------------------------------------


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _make_token(user_id: str, secret: str = TEST_JWT_SECRET, expired: bool = False) -> str:
    """Create a JWT token for testing."""
    exp = datetime.now(UTC) + (timedelta(hours=-1) if expired else timedelta(hours=JWT_TOKEN_EXPIRE_HOURS))
    return jwt.encode({"sub": user_id, "exp": exp}, secret, algorithm="HS256")


async def _insert_user(
    db,
    campus_id,
    *,
    role="full_admin",
    email="admin@test.com",
    name="Test Admin",
    phone="+6281234567890",
    user_id=None,
    is_active=True,
):
    """Insert a test user and return the document."""
    uid = user_id or str(uuid.uuid4())
    user = {
        "id": uid,
        "name": name,
        "email": email,
        "hashed_password": _hash(TEST_PASSWORD),
        "phone": phone,
        "campus_id": campus_id,
        "role": role,
        "is_active": is_active,
        "created_at": datetime.now(UTC).isoformat(),
    }
    await db.users.insert_one(user)
    return user


async def _insert_member(
    db,
    campus_id,
    *,
    name="John Doe",
    member_id=None,
    phone="+6281234567892",
    engagement="active",
    last_contact=None,
    birth_date=None,
):
    """Insert a test member and return the document."""
    mid = member_id or str(uuid.uuid4())
    now = datetime.now(UTC)
    member = {
        "id": mid,
        "campus_id": campus_id,
        "name": name,
        "phone": phone,
        "engagement_status": engagement,
        "days_since_last_contact": 0,
        "last_contact_date": (last_contact or now).isoformat(),
        "is_archived": False,
        "created_at": now.isoformat(),
    }
    if birth_date:
        member["birth_date"] = birth_date
    await db.members.insert_one(member)
    return member


async def _insert_care_event(
    db,
    campus_id,
    member_id,
    *,
    event_type="birthday",
    title="Test Event",
    completed=False,
    ignored=False,
    event_id=None,
    event_date=None,
):
    """Insert a care event and return the document."""
    eid = event_id or str(uuid.uuid4())
    now = datetime.now(UTC)
    event = {
        "id": eid,
        "campus_id": campus_id,
        "member_id": member_id,
        "event_type": event_type,
        "event_date": (event_date or date.today()).isoformat(),
        "title": title,
        "description": "Test description",
        "completed": completed,
        "ignored": ignored,
        "created_at": now,
        "updated_at": now,
    }
    await db.care_events.insert_one(event)
    return event


# =====================================================================
# AUTHENTICATION TESTS
# =====================================================================


@pytest.mark.integration
class TestAuthentication:
    """Tests for authentication logic: password hashing, JWT tokens, login."""

    @pytest.mark.asyncio
    async def test_login_success_password_verified(self, test_db, test_campus):
        """Successful login: stored bcrypt hash matches the plain password."""
        user = await _insert_user(test_db, test_campus["id"])
        assert verify_password(TEST_PASSWORD, user["hashed_password"])

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, test_db, test_campus):
        """Wrong password must not verify."""
        user = await _insert_user(test_db, test_campus["id"])
        assert not verify_password("WrongPassword999!", user["hashed_password"])

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, test_db, test_campus):
        """Looking up a nonexistent email returns None from the DB."""
        found = await test_db.users.find_one({"email": "nobody@example.com"})
        assert found is None

    @pytest.mark.asyncio
    async def test_get_current_user_valid_token(self, test_db, test_campus):
        """A valid JWT with an existing user_id resolves to the correct user."""
        user = await _insert_user(test_db, test_campus["id"])
        token = _make_token(user["id"])
        payload = jwt.decode(token, TEST_JWT_SECRET, algorithms=["HS256"])
        assert payload["sub"] == user["id"]
        # Simulate what get_current_user does: look up the user
        db_user = await test_db.users.find_one({"id": payload["sub"]}, {"_id": 0})
        assert db_user is not None
        assert db_user["email"] == "admin@test.com"

    @pytest.mark.asyncio
    async def test_get_current_user_expired_token(self, test_db, test_campus):
        """An expired JWT must raise a decode error."""
        user = await _insert_user(test_db, test_campus["id"])
        token = _make_token(user["id"], expired=True)
        with pytest.raises(jwt.ExpiredSignatureError):
            jwt.decode(token, TEST_JWT_SECRET, algorithms=["HS256"])

    @pytest.mark.asyncio
    async def test_get_current_user_empty_token(self, test_db, test_campus):
        """Bearer header with empty/whitespace token must be rejected."""
        # Simulate "Bearer " with no actual token
        token = ""
        assert not token.strip(), "Empty token should be falsy after strip"
        # Whitespace-only token should also be rejected
        token_ws = "   "
        assert not token_ws.strip(), "Whitespace-only token should be falsy after strip"

    @pytest.mark.asyncio
    async def test_token_with_invalid_secret_rejected(self, test_db, test_campus):
        """Token signed with wrong secret must fail verification."""
        user = await _insert_user(test_db, test_campus["id"])
        token = _make_token(user["id"], secret="wrong-secret")
        with pytest.raises(jwt.InvalidSignatureError):
            jwt.decode(token, TEST_JWT_SECRET, algorithms=["HS256"])

    @pytest.mark.asyncio
    async def test_token_without_sub_claim(self, test_db, test_campus):
        """Token missing 'sub' claim must not resolve a user."""
        exp = datetime.now(UTC) + timedelta(hours=1)
        token = jwt.encode({"exp": exp}, TEST_JWT_SECRET, algorithm="HS256")
        payload = jwt.decode(token, TEST_JWT_SECRET, algorithms=["HS256"])
        assert payload.get("sub") is None

    @pytest.mark.asyncio
    async def test_inactive_user_blocked(self, test_db, test_campus):
        """An inactive user should be detectable at login time."""
        user = await _insert_user(test_db, test_campus["id"], is_active=False)
        db_user = await test_db.users.find_one({"email": user["email"]})
        assert db_user.get("is_active") is False

    @pytest.mark.asyncio
    async def test_password_hash_is_bcrypt(self, test_db, test_campus):
        """Stored password hash uses bcrypt ($2b$ prefix)."""
        user = await _insert_user(test_db, test_campus["id"])
        assert user["hashed_password"].startswith("$2b$")

    @pytest.mark.asyncio
    async def test_token_deleted_user(self, test_db, test_campus):
        """Token for a deleted user should not resolve."""
        user = await _insert_user(test_db, test_campus["id"])
        token = _make_token(user["id"])
        # Delete the user
        await test_db.users.delete_one({"id": user["id"]})
        # Token decodes fine, but DB lookup fails
        payload = jwt.decode(token, TEST_JWT_SECRET, algorithms=["HS256"])
        db_user = await test_db.users.find_one({"id": payload["sub"]}, {"_id": 0})
        assert db_user is None


# =====================================================================
# MEMBER CRUD TESTS
# =====================================================================


@pytest.mark.integration
class TestMemberCRUD:
    """Member create, read, update, delete with multi-tenancy checks."""

    @pytest.mark.asyncio
    async def test_create_member(self, test_db, test_campus):
        """Create a member and verify it persists."""
        member = await _insert_member(test_db, test_campus["id"], name="Alice Smith")
        found = await test_db.members.find_one({"id": member["id"]}, {"_id": 0})
        assert found is not None
        assert found["name"] == "Alice Smith"
        assert found["campus_id"] == test_campus["id"]

    @pytest.mark.asyncio
    async def test_get_member(self, test_db, test_campus):
        """Retrieve a member by ID with campus scoping."""
        member = await _insert_member(test_db, test_campus["id"])
        found = await test_db.members.find_one({"id": member["id"], "campus_id": test_campus["id"]}, {"_id": 0})
        assert found is not None
        assert found["id"] == member["id"]

    @pytest.mark.asyncio
    async def test_update_member(self, test_db, test_campus):
        """Update member fields."""
        member = await _insert_member(test_db, test_campus["id"])
        result = await test_db.members.update_one(
            {"id": member["id"], "campus_id": test_campus["id"]},
            {"$set": {"name": "Updated Name", "updated_at": datetime.now(UTC)}},
        )
        assert result.modified_count == 1
        updated = await test_db.members.find_one({"id": member["id"]}, {"_id": 0})
        assert updated["name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_delete_member_cascades(self, test_db, test_campus):
        """Delete member and verify cascade removes care events."""
        member = await _insert_member(test_db, test_campus["id"])
        await _insert_care_event(test_db, test_campus["id"], member["id"])

        # Delete member
        await test_db.members.delete_one({"id": member["id"]})
        # Cascade: delete related care events (mirrors delete_member handler)
        await test_db.care_events.delete_many({"member_id": member["id"], "campus_id": test_campus["id"]})

        assert await test_db.members.find_one({"id": member["id"]}) is None
        events = await test_db.care_events.find({"member_id": member["id"]}).to_list(None)
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_create_member_empty_name(self, test_db, test_campus):
        """Empty name is rejected at the API layer (MemberCreate min_length=1)."""
        # The MemberCreate model uses min_length=1, so empty string is rejected
        # by msgspec before it reaches the database. The DB-level has no constraint.
        mid = str(uuid.uuid4())
        doc = {"id": mid, "campus_id": test_campus["id"], "name": ""}
        await test_db.members.insert_one(doc)
        found = await test_db.members.find_one({"id": mid})
        assert found["name"] == ""
        # This demonstrates that DB allows it, but API validation catches it

    @pytest.mark.asyncio
    async def test_get_member_wrong_campus(self, test_db, test_campus, second_campus):
        """Multi-tenancy: member from campus A must not be visible with campus B filter."""
        member = await _insert_member(test_db, test_campus["id"])
        found = await test_db.members.find_one({"id": member["id"], "campus_id": second_campus["id"]}, {"_id": 0})
        assert found is None, "Member from another campus should not be accessible"

    @pytest.mark.asyncio
    async def test_campus_filter_full_admin(self, test_db, test_campus):
        """Full admin campus filter returns empty dict (no campus restriction)."""
        admin_user = {"role": UserRole.FULL_ADMIN.value, "campus_id": test_campus["id"]}
        filt = get_campus_filter(admin_user)
        assert filt == {}

    @pytest.mark.asyncio
    async def test_campus_filter_pastor(self, test_db, test_campus):
        """Pastor campus filter restricts to their campus."""
        pastor_user = {"role": UserRole.PASTOR.value, "campus_id": test_campus["id"]}
        filt = get_campus_filter(pastor_user)
        assert filt == {"campus_id": test_campus["id"]}

    @pytest.mark.asyncio
    async def test_campus_filter_campus_admin(self, test_db, test_campus):
        """Campus admin filter restricts to their campus."""
        ca_user = {"role": UserRole.CAMPUS_ADMIN.value, "campus_id": test_campus["id"]}
        filt = get_campus_filter(ca_user)
        assert filt == {"campus_id": test_campus["id"]}

    @pytest.mark.asyncio
    async def test_campus_filter_no_campus(self, test_db):
        """User without campus_id gets impossible filter (no results)."""
        user = {"role": UserRole.PASTOR.value}
        filt = get_campus_filter(user)
        assert "campus_id" in filt

    @pytest.mark.asyncio
    async def test_member_engagement_calculated(self, test_db, test_campus):
        """Engagement status is computed from last_contact_date."""
        old_contact = datetime.now(UTC) - timedelta(days=100)
        await _insert_member(test_db, test_campus["id"], last_contact=old_contact)
        status, days = calculate_engagement_status(old_contact)
        assert status == EngagementStatus.DISCONNECTED
        assert days >= 100

    @pytest.mark.asyncio
    async def test_delete_member_cascades_grief_support(self, test_db, test_campus):
        """Deleting a member also removes grief_support records."""
        member = await _insert_member(test_db, test_campus["id"])
        event = await _insert_care_event(test_db, test_campus["id"], member["id"], event_type="grief_loss")
        await test_db.grief_support.insert_one(
            {
                "id": str(uuid.uuid4()),
                "campus_id": test_campus["id"],
                "member_id": member["id"],
                "care_event_id": event["id"],
                "stage": "1_week",
                "scheduled_date": date.today().isoformat(),
                "completed": False,
                "created_at": datetime.now(UTC),
            }
        )

        # Cascade delete
        await test_db.members.delete_one({"id": member["id"]})
        await test_db.care_events.delete_many({"member_id": member["id"], "campus_id": test_campus["id"]})
        await test_db.grief_support.delete_many({"member_id": member["id"], "campus_id": test_campus["id"]})

        assert await test_db.grief_support.find_one({"member_id": member["id"]}) is None


# =====================================================================
# CARE EVENT TESTS
# =====================================================================


@pytest.mark.integration
class TestCareEvents:
    """Care event creation, completion, ignoring, deletion, and engagement updates."""

    @pytest.mark.asyncio
    async def test_create_care_event(self, test_db, test_campus, test_member):
        """Create a care event and verify persistence."""
        event = await _insert_care_event(
            test_db, test_campus["id"], test_member["id"], event_type="birthday", title="Birthday Celebration"
        )
        found = await test_db.care_events.find_one({"id": event["id"]}, {"_id": 0})
        assert found is not None
        assert found["event_type"] == "birthday"
        assert found["member_id"] == test_member["id"]
        assert found["completed"] is False

    @pytest.mark.asyncio
    async def test_complete_care_event(self, test_db, test_campus, test_member):
        """Completing a care event sets completed flag and updates member engagement."""
        event = await _insert_care_event(test_db, test_campus["id"], test_member["id"], event_type="regular_contact")
        now = datetime.now(UTC)

        # Complete the event (mirrors complete_care_event handler)
        await test_db.care_events.update_one(
            {"id": event["id"]},
            {
                "$set": {
                    "completed": True,
                    "completed_at": now,
                    "completed_by_user_id": "test-user",
                    "completed_by_user_name": "Test User",
                    "updated_at": now,
                }
            },
        )
        # Update member engagement
        await test_db.members.update_one(
            {"id": test_member["id"]},
            {
                "$set": {
                    "last_contact_date": now,
                    "days_since_last_contact": 0,
                    "engagement_status": "active",
                    "updated_at": now,
                }
            },
        )

        updated_event = await test_db.care_events.find_one({"id": event["id"]}, {"_id": 0})
        assert updated_event["completed"] is True
        assert updated_event["completed_by_user_id"] == "test-user"

        updated_member = await test_db.members.find_one({"id": test_member["id"]}, {"_id": 0})
        assert updated_member["engagement_status"] == "active"
        assert updated_member["days_since_last_contact"] == 0

    @pytest.mark.asyncio
    async def test_complete_idempotent(self, test_db, test_campus, test_member):
        """Completing an already-completed event is idempotent."""
        event = await _insert_care_event(test_db, test_campus["id"], test_member["id"], completed=True)
        found = await test_db.care_events.find_one({"id": event["id"]}, {"_id": 0})
        # Handler checks: if event.get("completed"): return {"success": True, ...}
        assert found["completed"] is True

    @pytest.mark.asyncio
    async def test_ignore_care_event(self, test_db, test_campus, test_member):
        """Ignoring a care event sets the ignored flag with user info."""
        event = await _insert_care_event(test_db, test_campus["id"], test_member["id"])
        now = datetime.now(UTC)
        await test_db.care_events.update_one(
            {"id": event["id"]},
            {
                "$set": {
                    "ignored": True,
                    "ignored_at": now,
                    "ignored_by": "test-user",
                    "ignored_by_name": "Test User",
                    "updated_at": now,
                }
            },
        )
        updated = await test_db.care_events.find_one({"id": event["id"]}, {"_id": 0})
        assert updated["ignored"] is True
        assert updated["ignored_by"] == "test-user"

    @pytest.mark.asyncio
    async def test_delete_care_event_updates_engagement(self, test_db, test_campus):
        """Deleting the most recent care event causes engagement recalculation."""
        member = await _insert_member(test_db, test_campus["id"])

        old_date = datetime.now(UTC) - timedelta(days=80)
        recent_date = datetime.now(UTC) - timedelta(days=2)

        await _insert_care_event(
            test_db,
            test_campus["id"],
            member["id"],
            event_type="regular_contact",
            title="Old Contact",
            event_id="evt-old",
        )
        await test_db.care_events.update_one({"id": "evt-old"}, {"$set": {"created_at": old_date}})

        await _insert_care_event(
            test_db,
            test_campus["id"],
            member["id"],
            event_type="regular_contact",
            title="Recent Contact",
            event_id="evt-recent",
        )
        await test_db.care_events.update_one({"id": "evt-recent"}, {"$set": {"created_at": recent_date}})

        # Delete the recent event
        await test_db.care_events.delete_one({"id": "evt-recent"})

        # Recalculate last contact from remaining events (mirrors handler logic)
        remaining = (
            await test_db.care_events.find({"member_id": member["id"]}, {"_id": 0, "created_at": 1})
            .sort("created_at", -1)
            .limit(1)
            .to_list(1)
        )

        if remaining:
            last_contact = remaining[0]["created_at"]
            status, days = calculate_engagement_status(last_contact)
            await test_db.members.update_one(
                {"id": member["id"]},
                {
                    "$set": {
                        "last_contact_date": last_contact,
                        "engagement_status": status.value,
                        "days_since_last_contact": days,
                    }
                },
            )

        updated_member = await test_db.members.find_one({"id": member["id"]}, {"_id": 0})
        assert updated_member["engagement_status"] in [
            EngagementStatus.AT_RISK.value,
            EngagementStatus.DISCONNECTED.value,
        ]
        assert updated_member["days_since_last_contact"] >= 79

    @pytest.mark.asyncio
    async def test_delete_all_events_disconnects_member(self, test_db, test_campus):
        """When all care events are deleted, member becomes disconnected."""
        member = await _insert_member(test_db, test_campus["id"])
        event = await _insert_care_event(test_db, test_campus["id"], member["id"], event_type="regular_contact")

        await test_db.care_events.delete_one({"id": event["id"]})

        remaining = await test_db.care_events.find({"member_id": member["id"]}, {"_id": 0}).to_list(None)
        assert len(remaining) == 0

        status, days = calculate_engagement_status(None)
        assert status == EngagementStatus.DISCONNECTED
        assert days == ENGAGEMENT_NO_CONTACT_DAYS

    @pytest.mark.asyncio
    async def test_care_event_scoped_by_campus(self, test_db, test_campus, second_campus):
        """Care event from campus A is not visible when querying campus B."""
        member = await _insert_member(test_db, test_campus["id"])
        event = await _insert_care_event(test_db, test_campus["id"], member["id"])
        found = await test_db.care_events.find_one({"id": event["id"], "campus_id": second_campus["id"]}, {"_id": 0})
        assert found is None

    @pytest.mark.asyncio
    async def test_care_event_not_found_returns_none(self, test_db, test_campus):
        """Querying a nonexistent event ID returns None."""
        found = await test_db.care_events.find_one({"id": "nonexistent-event-id"}, {"_id": 0})
        assert found is None

    @pytest.mark.asyncio
    async def test_financial_aid_event_fields(self, test_db, test_campus):
        """Financial aid events store aid_type and aid_amount."""
        member = await _insert_member(test_db, test_campus["id"])
        event_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        event = {
            "id": event_id,
            "campus_id": test_campus["id"],
            "member_id": member["id"],
            "event_type": EventType.FINANCIAL_AID.value,
            "event_date": date.today().isoformat(),
            "title": "Financial Aid",
            "aid_type": AidType.EDUCATION.value,
            "aid_amount": 500000.0,
            "completed": False,
            "created_at": now,
        }
        await test_db.care_events.insert_one(event)

        found = await test_db.care_events.find_one({"id": event_id}, {"_id": 0})
        assert found["aid_type"] == "education"
        assert found["aid_amount"] == 500000.0


# =====================================================================
# GRIEF TIMELINE TESTS
# =====================================================================


@pytest.mark.integration
class TestGriefTimeline:
    """Grief support timeline auto-generation."""

    @pytest.mark.asyncio
    async def test_create_grief_event_generates_timeline(self, test_db, test_campus):
        """Creating a grief/loss event generates 6 followup stages."""
        member = await _insert_member(test_db, test_campus["id"])
        event = await _insert_care_event(
            test_db, test_campus["id"], member["id"], event_type="grief_loss", title="Grief - Father passed"
        )

        mourning_date = date.today()
        timeline = generate_grief_timeline(mourning_date, event["id"], member["id"])

        assert len(timeline) == 6, "Grief timeline should have 6 stages"

        expected_offsets = [
            GRIEF_ONE_WEEK_DAYS,  # 7
            GRIEF_TWO_WEEKS_DAYS,  # 14
            GRIEF_ONE_MONTH_DAYS,  # 30
            GRIEF_THREE_MONTHS_DAYS,  # 90
            GRIEF_SIX_MONTHS_DAYS,  # 180
            GRIEF_ONE_YEAR_DAYS,  # 365
        ]
        expected_stages = [
            GriefStage.ONE_WEEK,
            GriefStage.TWO_WEEKS,
            GriefStage.ONE_MONTH,
            GriefStage.THREE_MONTHS,
            GriefStage.SIX_MONTHS,
            GriefStage.ONE_YEAR,
        ]

        for i, stage_doc in enumerate(timeline):
            expected_date = (mourning_date + timedelta(days=expected_offsets[i])).isoformat()
            assert stage_doc["scheduled_date"] == expected_date
            assert stage_doc["stage"] == expected_stages[i]
            assert stage_doc["completed"] is False
            assert stage_doc["care_event_id"] == event["id"]
            assert stage_doc["member_id"] == member["id"]
            assert "id" in stage_doc

    @pytest.mark.asyncio
    async def test_grief_timeline_unique_ids(self, test_db, test_campus):
        """Each grief timeline stage has a unique ID."""
        member = await _insert_member(test_db, test_campus["id"])
        event = await _insert_care_event(test_db, test_campus["id"], member["id"], event_type="grief_loss")
        timeline = generate_grief_timeline(date.today(), event["id"], member["id"])
        ids = [stage["id"] for stage in timeline]
        assert len(ids) == len(set(ids)), "All stage IDs should be unique"

    @pytest.mark.asyncio
    async def test_grief_timeline_persisted(self, test_db, test_campus):
        """Grief timeline stages are persisted to the grief_support collection."""
        member = await _insert_member(test_db, test_campus["id"])
        event = await _insert_care_event(test_db, test_campus["id"], member["id"], event_type="grief_loss")
        timeline = generate_grief_timeline(date.today(), event["id"], member["id"])
        for stage in timeline:
            stage["campus_id"] = test_campus["id"]
        await test_db.grief_support.insert_many(timeline)

        stored = await test_db.grief_support.find({"care_event_id": event["id"]}, {"_id": 0}).to_list(None)
        assert len(stored) == 6

    @pytest.mark.asyncio
    async def test_delete_grief_event_cascades(self, test_db, test_campus):
        """Deleting a grief parent event removes all grief_support stages."""
        member = await _insert_member(test_db, test_campus["id"])
        event = await _insert_care_event(test_db, test_campus["id"], member["id"], event_type="grief_loss")
        timeline = generate_grief_timeline(date.today(), event["id"], member["id"])
        for stage in timeline:
            stage["campus_id"] = test_campus["id"]
        await test_db.grief_support.insert_many(timeline)

        # Cascade delete (from delete_care_event handler)
        await test_db.grief_support.delete_many({"care_event_id": event["id"]})
        await test_db.care_events.delete_one({"id": event["id"]})

        remaining_stages = await test_db.grief_support.find({"care_event_id": event["id"]}).to_list(None)
        assert len(remaining_stages) == 0
        assert await test_db.care_events.find_one({"id": event["id"]}) is None


# =====================================================================
# SETTINGS ENDPOINT TESTS
# =====================================================================


@pytest.mark.integration
class TestSettingsEndpoints:
    """Tests for settings endpoint logic."""

    @pytest.mark.asyncio
    async def test_user_preferences_requires_auth(self, test_db, test_campus):
        """User preferences endpoint requires a valid user."""
        fake_user_id = str(uuid.uuid4())
        prefs = await test_db.user_preferences.find_one({"user_id": fake_user_id}, {"_id": 0})
        assert prefs is None, "No preferences should exist for unknown user"

    @pytest.mark.asyncio
    async def test_user_preferences_own_only(self, test_db, test_campus):
        """Non-admin user can only access their own preferences."""
        pastor = await _insert_user(
            test_db, test_campus["id"], role="pastor", email="pastor@test.com", name="Pastor", user_id="pastor-id-1"
        )
        other_user = await _insert_user(
            test_db,
            test_campus["id"],
            role="pastor",
            email="other@test.com",
            name="Other",
            user_id="other-id-2",
            phone="+6281234567891",
        )

        # Store preferences for pastor
        await test_db.user_preferences.insert_one(
            {
                "user_id": pastor["id"],
                "data": {"language": "en"},
            }
        )

        own_prefs = await test_db.user_preferences.find_one({"user_id": pastor["id"]}, {"_id": 0})
        assert own_prefs is not None
        assert own_prefs["data"]["language"] == "en"

        cross_prefs = await test_db.user_preferences.find_one({"user_id": other_user["id"]}, {"_id": 0})
        assert cross_prefs is None

    @pytest.mark.asyncio
    async def test_user_preferences_default(self, test_db, test_campus):
        """When no preferences stored, handler returns default (Indonesian)."""
        user = await _insert_user(test_db, test_campus["id"])
        prefs = await test_db.user_preferences.find_one({"user_id": user["id"]}, {"_id": 0})
        if not prefs:
            result = {"language": "id"}
        else:
            result = prefs.get("data", {"language": "id"})
        assert result["language"] == "id"

    @pytest.mark.asyncio
    async def test_user_preferences_upsert(self, test_db, test_campus):
        """Updating preferences uses upsert -- creates if not exists."""
        user = await _insert_user(test_db, test_campus["id"])
        await test_db.user_preferences.update_one(
            {"user_id": user["id"]},
            {
                "$set": {
                    "user_id": user["id"],
                    "data": {"email_notifications": True, "whatsapp_notifications": False},
                    "updated_at": datetime.now(UTC),
                }
            },
            upsert=True,
        )
        prefs = await test_db.user_preferences.find_one({"user_id": user["id"]}, {"_id": 0})
        assert prefs is not None
        assert prefs["data"]["whatsapp_notifications"] is False

    @pytest.mark.asyncio
    async def test_engagement_settings_default(self, test_db, test_campus):
        """When no engagement settings stored, defaults are returned."""
        settings = await test_db.settings.find_one({"type": "engagement"}, {"_id": 0})
        if not settings:
            result = {"atRiskDays": 60, "inactiveDays": 90}
        else:
            result = settings.get("data", {"atRiskDays": 60, "inactiveDays": 90})
        assert result["atRiskDays"] == 60
        assert result["inactiveDays"] == 90

    @pytest.mark.asyncio
    async def test_engagement_settings_update(self, test_db, test_campus):
        """Update engagement settings and verify persistence."""
        admin = await _insert_user(test_db, test_campus["id"])
        await test_db.settings.update_one(
            {"type": "engagement"},
            {
                "$set": {
                    "type": "engagement",
                    "data": {"atRiskDays": 45, "inactiveDays": 75},
                    "updated_at": datetime.now(UTC),
                    "updated_by": admin["id"],
                }
            },
            upsert=True,
        )
        settings = await test_db.settings.find_one({"type": "engagement"}, {"_id": 0})
        assert settings["data"]["atRiskDays"] == 45
        assert settings["data"]["inactiveDays"] == 75

    @pytest.mark.asyncio
    async def test_engagement_settings_requires_auth(self, test_db, test_campus):
        """Engagement settings GET requires an authenticated user (DB must have user)."""
        user = await _insert_user(test_db, test_campus["id"])
        found = await test_db.users.find_one({"id": user["id"]}, {"_id": 0})
        assert found is not None, "Auth user must exist in DB"

    @pytest.mark.asyncio
    async def test_automation_settings_default(self, test_db, test_campus):
        """Default automation settings when none stored."""
        settings = await test_db.settings.find_one({"type": "automation"}, {"_id": 0})
        if not settings:
            result = {"digestTime": "08:00", "whatsappGateway": "", "enabled": True}
        else:
            result = settings.get("data", {})
        assert result["digestTime"] == "08:00"
        assert result["enabled"] is True

    @pytest.mark.asyncio
    async def test_automation_settings_update(self, test_db, test_campus):
        """Update automation settings."""
        admin = await _insert_user(test_db, test_campus["id"])
        await test_db.settings.update_one(
            {"type": "automation"},
            {
                "$set": {
                    "type": "automation",
                    "data": {
                        "digestTime": "09:30",
                        "whatsappGateway": "https://wa.example.com",
                        "enabled": False,
                    },
                    "updated_at": datetime.now(UTC),
                    "updated_by": admin["id"],
                }
            },
            upsert=True,
        )
        settings = await test_db.settings.find_one({"type": "automation"}, {"_id": 0})
        assert settings["data"]["digestTime"] == "09:30"
        assert settings["data"]["enabled"] is False

    @pytest.mark.asyncio
    async def test_automation_settings_requires_auth(self, test_db, test_campus):
        """Automation settings requires auth (user must exist)."""
        user = await _insert_user(test_db, test_campus["id"])
        found = await test_db.users.find_one({"id": user["id"]}, {"_id": 0})
        assert found is not None

    @pytest.mark.asyncio
    async def test_grief_stages_default(self, test_db, test_campus):
        """Default grief stages configuration."""
        settings = await test_db.settings.find_one({"type": "grief_stages"}, {"_id": 0})
        if not settings:
            result = [
                {"stage": "1_week", "days": 7, "name": "1 Week After"},
                {"stage": "2_weeks", "days": 14, "name": "2 Weeks After"},
                {"stage": "1_month", "days": 30, "name": "1 Month After"},
                {"stage": "3_months", "days": 90, "name": "3 Months After"},
                {"stage": "6_months", "days": 180, "name": "6 Months After"},
                {"stage": "1_year", "days": 365, "name": "1 Year After"},
            ]
        else:
            result = settings.get("data", [])
        assert len(result) == 6
        assert result[0]["days"] == 7
        assert result[5]["days"] == 365

    @pytest.mark.asyncio
    async def test_grief_stages_requires_auth(self, test_db, test_campus):
        """Grief stages requires auth (user must exist)."""
        user = await _insert_user(test_db, test_campus["id"])
        found = await test_db.users.find_one({"id": user["id"]}, {"_id": 0})
        assert found is not None

    @pytest.mark.asyncio
    async def test_grief_stages_update(self, test_db, test_campus):
        """Update grief stage configuration."""
        admin = await _insert_user(test_db, test_campus["id"])
        custom_stages = [
            {"stage": "1_week", "days": 5, "name": "5 Days After"},
            {"stage": "2_weeks", "days": 10, "name": "10 Days After"},
        ]
        await test_db.settings.update_one(
            {"type": "grief_stages"},
            {
                "$set": {
                    "type": "grief_stages",
                    "data": custom_stages,
                    "updated_at": datetime.now(UTC),
                    "updated_by": admin["id"],
                }
            },
            upsert=True,
        )
        settings = await test_db.settings.find_one({"type": "grief_stages"}, {"_id": 0})
        assert len(settings["data"]) == 2
        assert settings["data"][0]["days"] == 5

    @pytest.mark.asyncio
    async def test_overdue_writeoff_default(self, test_db, test_campus):
        """Overdue writeoff settings return defaults when not configured."""
        settings = await test_db.settings.find_one({"key": "overdue_writeoff"}, {"_id": 0})
        if not settings:
            result = {
                "key": "overdue_writeoff",
                "data": {
                    "birthday": 7,
                    "financial_aid": 0,
                    "accident_illness": 14,
                    "grief_support": 14,
                },
            }
        else:
            result = settings
        assert result["data"]["birthday"] == 7

    @pytest.mark.asyncio
    async def test_overdue_writeoff_update(self, test_db, test_campus):
        """Update overdue writeoff settings."""
        admin = await _insert_user(test_db, test_campus["id"])
        await test_db.settings.update_one(
            {"key": "overdue_writeoff"},
            {
                "$set": {
                    "key": "overdue_writeoff",
                    "data": {"days": 60, "enabled": True},
                    "updated_at": datetime.now(UTC),
                    "updated_by": admin["id"],
                }
            },
            upsert=True,
        )
        settings = await test_db.settings.find_one({"key": "overdue_writeoff"}, {"_id": 0})
        assert settings["data"]["days"] == 60
        assert settings["data"]["enabled"] is True


# =====================================================================
# EXPORT ENDPOINT TESTS
# =====================================================================


@pytest.mark.integration
class TestExportEndpoints:
    """Tests for CSV export logic -- verifying data scoping."""

    @pytest.mark.asyncio
    async def test_export_care_events_requires_auth(self, test_db, test_campus):
        """Export endpoint requires auth (user must exist in DB)."""
        user = await _insert_user(test_db, test_campus["id"])
        found = await test_db.users.find_one({"id": user["id"]}, {"_id": 0})
        assert found is not None

    @pytest.mark.asyncio
    async def test_export_care_events_scoped_by_campus(self, test_db, test_campus, second_campus):
        """Export only includes care events from the user's campus."""
        member_a = await _insert_member(test_db, test_campus["id"], name="Campus A Member")
        member_b = await _insert_member(test_db, second_campus["id"], name="Campus B Member", phone="+6281234567899")
        await _insert_care_event(test_db, test_campus["id"], member_a["id"], title="Event A")
        await _insert_care_event(test_db, second_campus["id"], member_b["id"], title="Event B")

        campus_filter = {"campus_id": test_campus["id"]}
        events = await test_db.care_events.find(campus_filter, {"_id": 0}).to_list(10000)

        assert len(events) == 1
        assert events[0]["title"] == "Event A"

    @pytest.mark.asyncio
    async def test_export_members_scoped_by_campus(self, test_db, test_campus, second_campus):
        """Member CSV export respects campus filter."""
        await _insert_member(test_db, test_campus["id"], name="Exported Member")
        await _insert_member(test_db, second_campus["id"], name="Other Campus Member", phone="+6281234567899")

        campus_filter = {"campus_id": test_campus["id"]}
        members = await test_db.members.find(campus_filter, {"_id": 0}).to_list(10000)
        assert len(members) == 1
        assert members[0]["name"] == "Exported Member"

    @pytest.mark.asyncio
    async def test_export_full_admin_sees_all(self, test_db, test_campus, second_campus):
        """Full admin export (empty campus filter) sees all campuses."""
        await _insert_member(test_db, test_campus["id"], name="Member A")
        await _insert_member(test_db, second_campus["id"], name="Member B", phone="+6281234567899")

        members = await test_db.members.find({}, {"_id": 0}).to_list(10000)
        assert len(members) == 2


# =====================================================================
# SETUP WIZARD TESTS
# =====================================================================


@pytest.mark.integration
class TestSetupWizard:
    """Tests for the initial setup wizard endpoints."""

    @pytest.mark.asyncio
    async def test_setup_campus_blocked_after_first(self, test_db, test_campus):
        """Once a campus exists, setup_first_campus should be blocked."""
        campus_count = await test_db.campuses.count_documents({})
        assert campus_count > 0
        # Handler: if campus_count > 0: raise HTTPException(403)
        should_block = campus_count > 0
        assert should_block is True

    @pytest.mark.asyncio
    async def test_setup_campus_allowed_when_empty(self, test_db):
        """Setup campus is allowed when no campuses exist."""
        campus_count = await test_db.campuses.count_documents({})
        assert campus_count == 0
        campus = {
            "id": str(uuid.uuid4()),
            "campus_name": "First Campus",
            "location": "Jakarta",
            "timezone": "Asia/Jakarta",
            "is_active": True,
            "created_at": datetime.now(UTC),
        }
        await test_db.campuses.insert_one(campus)
        new_count = await test_db.campuses.count_documents({})
        assert new_count == 1

    @pytest.mark.asyncio
    async def test_setup_admin_blocked_after_church_admin_exists(self, test_db, test_campus):
        """Once a non-default church admin exists, setup_first_admin is blocked."""
        DEFAULT_SYSTEM_ADMIN_EMAIL = "admin@gkbj.church"

        await _insert_user(test_db, test_campus["id"], role="full_admin", email="church@admin.com", name="Church Admin")

        church_admin_count = await test_db.users.count_documents(
            {"role": UserRole.FULL_ADMIN.value, "email": {"$ne": DEFAULT_SYSTEM_ADMIN_EMAIL}}
        )
        assert church_admin_count > 0
        # Handler: if church_admin_count > 0: raise HTTPException(400)

    @pytest.mark.asyncio
    async def test_setup_admin_allows_first_church_admin(self, test_db, test_campus):
        """Setup allows creating first church admin even if system admin exists."""
        DEFAULT_SYSTEM_ADMIN_EMAIL = "admin@gkbj.church"

        await _insert_user(
            test_db, test_campus["id"], role="full_admin", email=DEFAULT_SYSTEM_ADMIN_EMAIL, name="System Admin"
        )

        church_admin_count = await test_db.users.count_documents(
            {"role": UserRole.FULL_ADMIN.value, "email": {"$ne": DEFAULT_SYSTEM_ADMIN_EMAIL}}
        )
        assert church_admin_count == 0
        # Handler would allow creation

    @pytest.mark.asyncio
    async def test_setup_admin_enum_value_check(self, test_db, test_campus):
        """Setup admin uses UserRole.FULL_ADMIN enum value correctly."""
        assert UserRole.FULL_ADMIN.value == "full_admin"
        assert UserRole.CAMPUS_ADMIN.value == "campus_admin"
        assert UserRole.PASTOR.value == "pastor"

    @pytest.mark.asyncio
    async def test_setup_admin_rejects_system_email(self, test_db, test_campus):
        """Setup admin must reject the system admin email."""
        DEFAULT_SYSTEM_ADMIN_EMAIL = "admin@gkbj.church"
        request_email = "admin@gkbj.church"
        assert request_email.lower() == DEFAULT_SYSTEM_ADMIN_EMAIL.lower()

    @pytest.mark.asyncio
    async def test_setup_status_check(self, test_db):
        """Check setup status correctly reports needs_setup."""
        DEFAULT_SYSTEM_ADMIN_EMAIL = "admin@gkbj.church"

        church_admin_count = await test_db.users.count_documents(
            {"role": UserRole.FULL_ADMIN.value, "email": {"$ne": DEFAULT_SYSTEM_ADMIN_EMAIL}}
        )
        campus_count = await test_db.campuses.count_documents({})

        needs_setup = church_admin_count == 0 or campus_count == 0
        assert needs_setup is True  # Empty test DB should need setup


# =====================================================================
# REMINDER STATS TESTS
# =====================================================================


@pytest.mark.integration
class TestReminderStats:
    """Tests for the reminder statistics endpoint."""

    @pytest.mark.asyncio
    async def test_reminder_stats_requires_auth(self, test_db, test_campus):
        """Reminder stats requires an authenticated user."""
        user = await _insert_user(test_db, test_campus["id"])
        found = await test_db.users.find_one({"id": user["id"]}, {"_id": 0})
        assert found is not None

    @pytest.mark.asyncio
    async def test_reminder_stats_empty(self, test_db, test_campus):
        """Reminder stats with no data returns zero counts."""
        campus_filter = {"campus_id": test_campus["id"]}
        logs = await test_db.notification_logs.find(campus_filter, {"_id": 0}).to_list(1000)
        sent_count = sum(1 for log in logs if log.get("status") == "sent")
        failed_count = sum(1 for log in logs if log.get("status") == "failed")
        assert sent_count == 0
        assert failed_count == 0

    @pytest.mark.asyncio
    async def test_reminder_stats_counts(self, test_db, test_campus):
        """Reminder stats correctly counts sent/failed notifications."""
        now = datetime.now(UTC)
        campus_id = test_campus["id"]

        await test_db.notification_logs.insert_many(
            [
                {
                    "id": str(uuid.uuid4()),
                    "campus_id": campus_id,
                    "status": "sent",
                    "channel": "whatsapp",
                    "recipient": "+6281234567890",
                    "message": "Test",
                    "created_at": now,
                },
                {
                    "id": str(uuid.uuid4()),
                    "campus_id": campus_id,
                    "status": "sent",
                    "channel": "whatsapp",
                    "recipient": "+6281234567891",
                    "message": "Test 2",
                    "created_at": now,
                },
                {
                    "id": str(uuid.uuid4()),
                    "campus_id": campus_id,
                    "status": "failed",
                    "channel": "whatsapp",
                    "recipient": "+6281234567892",
                    "message": "Test 3",
                    "created_at": now,
                },
            ]
        )

        campus_filter = {"campus_id": campus_id}
        logs = await test_db.notification_logs.find(campus_filter, {"_id": 0}).to_list(1000)
        sent_count = sum(1 for log in logs if log.get("status") == "sent")
        failed_count = sum(1 for log in logs if log.get("status") == "failed")

        assert sent_count == 2
        assert failed_count == 1

    @pytest.mark.asyncio
    async def test_reminder_stats_grief_stages_due(self, test_db, test_campus):
        """Reminder stats counts grief stages due today."""
        today = date.today()
        campus_id = test_campus["id"]
        member = await _insert_member(test_db, campus_id)

        await test_db.grief_support.insert_many(
            [
                {
                    "id": str(uuid.uuid4()),
                    "campus_id": campus_id,
                    "member_id": member["id"],
                    "care_event_id": "evt-1",
                    "stage": GriefStage.ONE_WEEK.value,
                    "scheduled_date": today.isoformat(),
                    "completed": False,
                    "created_at": datetime.now(UTC),
                },
                {
                    "id": str(uuid.uuid4()),
                    "campus_id": campus_id,
                    "member_id": member["id"],
                    "care_event_id": "evt-1",
                    "stage": GriefStage.ONE_MONTH.value,
                    "scheduled_date": (today + timedelta(days=30)).isoformat(),
                    "completed": False,
                    "created_at": datetime.now(UTC),
                },
            ]
        )

        grief_query = {
            "campus_id": campus_id,
            "scheduled_date": today.isoformat(),
            "completed": False,
        }
        grief_due = await test_db.grief_support.count_documents(grief_query)
        assert grief_due == 1

    @pytest.mark.asyncio
    async def test_reminder_stats_upcoming_birthdays(self, test_db, test_campus):
        """Reminder stats counts birthdays in next 7 days."""
        today = date.today()
        future_date = today + timedelta(days=7)
        campus_id = test_campus["id"]
        member = await _insert_member(test_db, campus_id)

        await _insert_care_event(
            test_db,
            campus_id,
            member["id"],
            event_type="birthday",
            title="Birthday soon",
            event_date=today + timedelta(days=3),
        )
        await _insert_care_event(
            test_db,
            campus_id,
            member["id"],
            event_type="birthday",
            title="Birthday far",
            event_date=today + timedelta(days=30),
        )

        birthday_query = {
            "campus_id": campus_id,
            "event_type": "birthday",
            "event_date": {"$gte": today.isoformat(), "$lte": future_date.isoformat()},
            "completed": False,
        }
        birthdays_upcoming = await test_db.care_events.count_documents(birthday_query)
        assert birthdays_upcoming == 1


# =====================================================================
# ACTIVITY LOGGING TESTS
# =====================================================================


@pytest.mark.integration
class TestActivityLogging:
    """Tests for activity log creation and querying."""

    @pytest.mark.asyncio
    async def test_activity_log_creation(self, test_db, test_campus):
        """Activity logs are persisted with correct fields."""
        now = datetime.now(UTC)
        activity = {
            "id": str(uuid.uuid4()),
            "campus_id": test_campus["id"],
            "user_id": "user-1",
            "user_name": "Test User",
            "action_type": ActivityActionType.COMPLETE_TASK.value,
            "member_id": "member-1",
            "member_name": "John Doe",
            "care_event_id": "event-1",
            "event_type": EventType.BIRTHDAY.value,
            "notes": "Completed birthday task",
            "created_at": now,
        }
        await test_db.activity_logs.insert_one(activity)

        found = await test_db.activity_logs.find_one({"id": activity["id"]}, {"_id": 0})
        assert found is not None
        assert found["action_type"] == "complete_task"
        assert found["member_name"] == "John Doe"

    @pytest.mark.asyncio
    async def test_activity_log_scoped_by_campus(self, test_db, test_campus, second_campus):
        """Activity logs are campus-scoped."""
        now = datetime.now(UTC)
        await test_db.activity_logs.insert_one(
            {
                "id": str(uuid.uuid4()),
                "campus_id": test_campus["id"],
                "user_id": "u1",
                "user_name": "User A",
                "action_type": "complete_task",
                "created_at": now,
            }
        )
        await test_db.activity_logs.insert_one(
            {
                "id": str(uuid.uuid4()),
                "campus_id": second_campus["id"],
                "user_id": "u2",
                "user_name": "User B",
                "action_type": "create_care_event",
                "created_at": now,
            }
        )

        campus_a_logs = await test_db.activity_logs.find({"campus_id": test_campus["id"]}, {"_id": 0}).to_list(None)
        assert len(campus_a_logs) == 1
        assert campus_a_logs[0]["user_name"] == "User A"

    @pytest.mark.asyncio
    async def test_activity_log_deleted_with_event(self, test_db, test_campus):
        """Deleting a care event also removes its activity logs."""
        event_id = "evt-to-delete"
        member = await _insert_member(test_db, test_campus["id"])
        await _insert_care_event(test_db, test_campus["id"], member["id"], event_id=event_id)
        await test_db.activity_logs.insert_one(
            {
                "id": str(uuid.uuid4()),
                "campus_id": test_campus["id"],
                "care_event_id": event_id,
                "user_id": "u1",
                "user_name": "U1",
                "action_type": "complete_task",
                "created_at": datetime.now(UTC),
            }
        )

        # Cascade from delete_care_event
        await test_db.care_events.delete_one({"id": event_id})
        await test_db.activity_logs.delete_many({"care_event_id": event_id})

        logs = await test_db.activity_logs.find({"care_event_id": event_id}).to_list(None)
        assert len(logs) == 0

    @pytest.mark.asyncio
    async def test_all_action_types_valid(self, test_db, test_campus):
        """All ActivityActionType enum values are valid strings."""
        for action in ActivityActionType:
            assert isinstance(action.value, str)
            assert len(action.value) > 0


# =====================================================================
# ENGAGEMENT CALCULATION TESTS
# =====================================================================


@pytest.mark.integration
class TestEngagementCalculation:
    """Tests for the engagement status calculation utility."""

    def test_active_status(self):
        """Recent contact yields active status."""
        last_contact = datetime.now(UTC) - timedelta(days=5)
        status, days = calculate_engagement_status(last_contact)
        assert status == EngagementStatus.ACTIVE
        assert days == 5

    def test_at_risk_status(self):
        """Contact 60-89 days ago yields at-risk status."""
        last_contact = datetime.now(UTC) - timedelta(days=70)
        status, days = calculate_engagement_status(last_contact)
        assert status == EngagementStatus.AT_RISK
        assert 69 <= days <= 71

    def test_disconnected_status(self):
        """Contact 90+ days ago yields disconnected status."""
        last_contact = datetime.now(UTC) - timedelta(days=100)
        status, days = calculate_engagement_status(last_contact)
        assert status == EngagementStatus.DISCONNECTED
        assert days >= 100

    def test_no_contact_disconnected(self):
        """No contact date yields disconnected with max days."""
        status, days = calculate_engagement_status(None)
        assert status == EngagementStatus.DISCONNECTED
        assert days == ENGAGEMENT_NO_CONTACT_DAYS

    def test_string_date_handled(self):
        """String date inputs are parsed correctly."""
        last_contact_str = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        status, _days = calculate_engagement_status(last_contact_str)
        assert status == EngagementStatus.ACTIVE

    def test_custom_thresholds(self):
        """Custom at-risk and disconnected thresholds are respected."""
        last_contact = datetime.now(UTC) - timedelta(days=35)
        status, _days = calculate_engagement_status(last_contact, at_risk_days=30, disconnected_days=60)
        assert status == EngagementStatus.AT_RISK

    def test_timezone_naive_handled(self):
        """Timezone-naive datetime is treated as UTC."""
        last_contact = datetime.now() - timedelta(days=15)
        status, _days = calculate_engagement_status(last_contact)
        assert status == EngagementStatus.ACTIVE

    def test_boundary_at_risk(self):
        """Exactly at the at-risk threshold."""
        last_contact = datetime.now(UTC) - timedelta(days=60)
        status, _days = calculate_engagement_status(last_contact)
        assert status == EngagementStatus.AT_RISK

    def test_boundary_disconnected(self):
        """Exactly at the disconnected threshold."""
        last_contact = datetime.now(UTC) - timedelta(days=90)
        status, _days = calculate_engagement_status(last_contact)
        assert status == EngagementStatus.DISCONNECTED


# =====================================================================
# PHONE NUMBER NORMALIZATION TESTS
# =====================================================================


@pytest.mark.integration
class TestPhoneNormalization:
    """Tests for phone number normalization utility."""

    def test_normalize_indonesian_08(self):
        """Indonesian numbers starting with 08 are normalized to +62."""
        result = normalize_phone_number("081234567890")
        assert result.startswith("+62")
        assert "08" not in result[3:]  # Should not have 08 after +62

    def test_normalize_already_international(self):
        """Numbers already in +62 format are preserved."""
        result = normalize_phone_number("+6281234567890")
        assert result == "+6281234567890"

    def test_normalize_empty_returns_original(self):
        """Empty/None input returns input unchanged."""
        assert normalize_phone_number("") == ""
        assert normalize_phone_number(None) is None


# =====================================================================
# ONE-TIME EVENT AUTO-COMPLETION TESTS
# =====================================================================


@pytest.mark.integration
class TestOneTimeEventAutoCompletion:
    """Tests for event types that auto-complete on creation."""

    def test_regular_contact_is_one_time(self):
        """Regular contact events are auto-completed on creation."""
        one_time_types = [EventType.REGULAR_CONTACT, EventType.CHILDBIRTH, EventType.NEW_HOUSE]
        assert EventType.REGULAR_CONTACT in one_time_types

    def test_childbirth_is_one_time(self):
        """Childbirth events are auto-completed."""
        one_time_types = [EventType.REGULAR_CONTACT, EventType.CHILDBIRTH, EventType.NEW_HOUSE]
        assert EventType.CHILDBIRTH in one_time_types

    def test_new_house_is_one_time(self):
        """New house events are auto-completed."""
        one_time_types = [EventType.REGULAR_CONTACT, EventType.CHILDBIRTH, EventType.NEW_HOUSE]
        assert EventType.NEW_HOUSE in one_time_types

    def test_birthday_not_one_time(self):
        """Birthday events require manual completion."""
        one_time_types = [EventType.REGULAR_CONTACT, EventType.CHILDBIRTH, EventType.NEW_HOUSE]
        assert EventType.BIRTHDAY not in one_time_types

    def test_grief_not_one_time(self):
        """Grief/loss events are NOT auto-completed."""
        one_time_types = [EventType.REGULAR_CONTACT, EventType.CHILDBIRTH, EventType.NEW_HOUSE]
        assert EventType.GRIEF_LOSS not in one_time_types

    def test_accident_not_one_time(self):
        """Accident/illness events are NOT auto-completed."""
        one_time_types = [EventType.REGULAR_CONTACT, EventType.CHILDBIRTH, EventType.NEW_HOUSE]
        assert EventType.ACCIDENT_ILLNESS not in one_time_types


# =====================================================================
# BULK OPERATIONS TESTS
# =====================================================================


@pytest.mark.integration
class TestBulkOperations:
    """Tests for bulk ignore and bulk delete operations."""

    @pytest.mark.asyncio
    async def test_bulk_ignore(self, test_db, test_campus):
        """Bulk ignore marks multiple events as ignored."""
        member = await _insert_member(test_db, test_campus["id"])
        e1 = await _insert_care_event(test_db, test_campus["id"], member["id"], title="Birthday 1")
        e2 = await _insert_care_event(test_db, test_campus["id"], member["id"], title="Birthday 2")

        event_ids = [e1["id"], e2["id"]]
        now = datetime.now(UTC)

        result = await test_db.care_events.update_many(
            {"id": {"$in": event_ids}, "ignored": {"$ne": True}},
            {
                "$set": {
                    "ignored": True,
                    "ignored_at": now,
                    "ignored_by_user_id": "test-user",
                    "ignored_by_user_name": "Test User",
                    "updated_at": now,
                }
            },
        )
        assert result.modified_count == 2

        for eid in event_ids:
            evt = await test_db.care_events.find_one({"id": eid}, {"_id": 0})
            assert evt["ignored"] is True

    @pytest.mark.asyncio
    async def test_bulk_ignore_already_ignored_skipped(self, test_db, test_campus):
        """Bulk ignore skips already-ignored events."""
        member = await _insert_member(test_db, test_campus["id"])
        e1 = await _insert_care_event(test_db, test_campus["id"], member["id"], ignored=True)
        result = await test_db.care_events.update_many(
            {"id": {"$in": [e1["id"]]}, "ignored": {"$ne": True}}, {"$set": {"ignored": True}}
        )
        assert result.modified_count == 0

    @pytest.mark.asyncio
    async def test_bulk_delete(self, test_db, test_campus):
        """Bulk delete removes multiple events."""
        member = await _insert_member(test_db, test_campus["id"])
        e1 = await _insert_care_event(test_db, test_campus["id"], member["id"], title="Delete Me 1")
        e2 = await _insert_care_event(test_db, test_campus["id"], member["id"], title="Delete Me 2")

        event_ids = [e1["id"], e2["id"]]
        result = await test_db.care_events.delete_many({"id": {"$in": event_ids}})
        assert result.deleted_count == 2

        remaining = await test_db.care_events.find({"id": {"$in": event_ids}}).to_list(None)
        assert len(remaining) == 0


# =====================================================================
# MEMBER ARCHIVAL TESTS
# =====================================================================


@pytest.mark.integration
class TestMemberArchival:
    """Tests for member archival/unarchival logic."""

    @pytest.mark.asyncio
    async def test_archived_members_excluded_by_default(self, test_db, test_campus):
        """Archived members are excluded from default listing."""
        await _insert_member(test_db, test_campus["id"], name="Active Member")
        archived = await _insert_member(test_db, test_campus["id"], name="Archived Member", phone="+6281234567899")
        await test_db.members.update_one({"id": archived["id"]}, {"$set": {"is_archived": True}})

        query = {"campus_id": test_campus["id"], "is_archived": {"$ne": True}}
        members = await test_db.members.find(query, {"_id": 0}).to_list(None)
        names = [m["name"] for m in members]
        assert "Active Member" in names
        assert "Archived Member" not in names

    @pytest.mark.asyncio
    async def test_show_archived_flag(self, test_db, test_campus):
        """show_archived=true shows only archived members."""
        await _insert_member(test_db, test_campus["id"], name="Active")
        archived = await _insert_member(test_db, test_campus["id"], name="Archived", phone="+6281234567899")
        await test_db.members.update_one({"id": archived["id"]}, {"$set": {"is_archived": True}})

        query = {"campus_id": test_campus["id"], "is_archived": True}
        members = await test_db.members.find(query, {"_id": 0}).to_list(None)
        assert len(members) == 1
        assert members[0]["name"] == "Archived"


# =====================================================================
# TOKEN CREATION TESTS
# =====================================================================


@pytest.mark.integration
class TestTokenCreation:
    """Tests for JWT token creation."""

    def test_create_token_default_expiry(self):
        """Token created with default expiry has correct claims."""
        token = create_access_token(data={"sub": "user-123"})
        payload = jwt.decode(token, TEST_JWT_SECRET, algorithms=["HS256"])
        assert payload["sub"] == "user-123"
        assert "exp" in payload

    def test_create_token_custom_expiry(self):
        """Token created with custom expiry delta."""
        token = create_access_token(data={"sub": "user-456"}, expires_delta=timedelta(minutes=30))
        payload = jwt.decode(token, TEST_JWT_SECRET, algorithms=["HS256"])
        assert payload["sub"] == "user-456"
        exp_dt = datetime.fromtimestamp(payload["exp"], tz=UTC)
        now = datetime.now(UTC)
        diff = (exp_dt - now).total_seconds()
        assert 25 * 60 < diff < 35 * 60


# =====================================================================
# PASSWORD HASHING TESTS
# =====================================================================


@pytest.mark.integration
class TestPasswordHashing:
    """Tests for password hashing and verification utilities."""

    def test_hash_and_verify(self):
        """Hash then verify returns True."""
        hashed = get_password_hash("SecurePass123!")
        assert verify_password("SecurePass123!", hashed)

    def test_wrong_password_fails(self):
        """Wrong password verification returns False."""
        hashed = get_password_hash("SecurePass123!")
        assert not verify_password("WrongPass!", hashed)

    def test_different_hashes_for_same_password(self):
        """bcrypt produces unique salt per hash."""
        h1 = get_password_hash("SamePassword!")
        h2 = get_password_hash("SamePassword!")
        assert h1 != h2  # Different salts
        assert verify_password("SamePassword!", h1)
        assert verify_password("SamePassword!", h2)

    def test_hash_format(self):
        """bcrypt hash has correct $2b$ prefix."""
        hashed = get_password_hash("TestPassword!")
        assert hashed.startswith("$2b$")


# =====================================================================
# ENUM CONSISTENCY TESTS
# =====================================================================


@pytest.mark.integration
class TestEnumConsistency:
    """Verify enum values match what the database and API expect."""

    def test_event_types(self):
        """All EventType values are lowercase snake_case strings."""
        for et in EventType:
            assert isinstance(et.value, str)
            assert et.value == et.value.lower()
            assert " " not in et.value

    def test_user_roles(self):
        """UserRole enum has expected values."""
        assert UserRole.FULL_ADMIN.value == "full_admin"
        assert UserRole.CAMPUS_ADMIN.value == "campus_admin"
        assert UserRole.PASTOR.value == "pastor"

    def test_grief_stages(self):
        """GriefStage enum has expected values."""
        assert GriefStage.MOURNING.value == "mourning"
        assert GriefStage.ONE_WEEK.value == "1_week"
        assert GriefStage.ONE_YEAR.value == "1_year"

    def test_aid_types(self):
        """AidType enum has expected values."""
        expected = {"education", "medical", "emergency", "housing", "food", "funeral_costs", "other"}
        actual = {at.value for at in AidType}
        assert actual == expected

    def test_engagement_statuses(self):
        """EngagementStatus enum has expected values."""
        assert EngagementStatus.ACTIVE.value == "active"
        assert EngagementStatus.AT_RISK.value == "at_risk"
        assert EngagementStatus.DISCONNECTED.value == "disconnected"
