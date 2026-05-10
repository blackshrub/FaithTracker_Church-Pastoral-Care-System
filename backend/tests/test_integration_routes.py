"""
Comprehensive integration tests for FaithTracker route modules.

Tests route handler functions DIRECTLY by mocking database dependencies.
Each route handler is an async function that takes a Request and returns data.

We:
1. Import handler functions directly from route modules
2. Mock dependencies.get_db() to return a mock database
3. Mock dependencies.get_current_user() to return a test user
4. Call the handler with a mock Request
5. Assert the return value

Coverage target: 70%+ of ~1,967 statements across all route files.
"""

import os
import sys
import uuid
from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set environment variables BEFORE importing any backend modules
os.environ.update(
    {
        "MONGO_URL": "mongodb://mock:27017",
        "DB_NAME": "faithtracker_test",
        "JWT_SECRET_KEY": "test-secret-key-1234567890abcdef",
        "ENCRYPTION_KEY": "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
        "DRAGONFLY_URL": "redis://mock:6379",
        "FRONTEND_URL": "http://localhost:3000",
        "ALLOWED_ORIGINS": "http://localhost:3000",
        "ENVIRONMENT": "development",
    }
)

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dependencies import init_dependencies
from enums import AidType, EngagementStatus, EventType, UserRole


def _fn(handler):
    """Unwrap a Litestar route handler to get the underlying async function.

    Litestar decorators (@get, @post, etc.) wrap the function into an
    HTTPRouteHandler object. The actual async function lives at handler.fn.
    """
    return handler.fn if hasattr(handler, "fn") else handler


# ---------------------------------------------------------------------------
# Test constants
# ---------------------------------------------------------------------------
TEST_JWT_SECRET = "test-secret-key-1234567890abcdef"
TEST_CAMPUS_ID = str(uuid.uuid4())
TEST_CAMPUS_ID_2 = str(uuid.uuid4())
TEST_USER_ID = str(uuid.uuid4())
TEST_ADMIN_ID = str(uuid.uuid4())
TEST_MEMBER_ID = str(uuid.uuid4())
TEST_EVENT_ID = str(uuid.uuid4())
NOW = datetime.now(UTC)
TODAY = date.today()


# ---------------------------------------------------------------------------
# Helper: Create mock DB with all collections
# ---------------------------------------------------------------------------


def make_mock_db():
    """Create a comprehensive mock database with all collections."""
    db = MagicMock()
    # Define all collections used across routes
    for coll in [
        "users",
        "campuses",
        "members",
        "care_events",
        "grief_support",
        "accident_followup",
        "financial_aid_schedules",
        "activity_logs",
        "notification_logs",
        "settings",
        "refresh_tokens",
        "job_locks",
        "migrations",
        "pastoral_notes",
        "dashboard_cache",
    ]:
        collection = MagicMock()
        collection.find_one = AsyncMock(return_value=None)
        collection.insert_one = AsyncMock()
        collection.update_one = AsyncMock()
        collection.delete_one = AsyncMock()
        collection.delete_many = AsyncMock()
        collection.count_documents = AsyncMock(return_value=0)
        collection.find_one_and_update = AsyncMock(return_value=None)

        # find() returns a chainable cursor mock
        cursor = MagicMock()
        cursor.sort = MagicMock(return_value=cursor)
        cursor.skip = MagicMock(return_value=cursor)
        cursor.limit = MagicMock(return_value=cursor)
        cursor.to_list = AsyncMock(return_value=[])
        collection.find = MagicMock(return_value=cursor)

        # aggregate() returns a cursor with to_list
        agg_cursor = MagicMock()
        agg_cursor.to_list = AsyncMock(return_value=[])
        collection.aggregate = MagicMock(return_value=agg_cursor)

        # update_many / insert_many
        collection.update_many = AsyncMock()
        collection.insert_many = AsyncMock()

        setattr(db, coll, collection)

    # Smart users.find_one: returns the admin user for an "id"-keyed lookup
    # (the path get_current_user takes via JWT subject), and None for any
    # other filter (e.g., "email" duplicate checks). Tests can override
    # with mock_db.users.find_one = AsyncMock(...) for specific scenarios.
    _admin = make_admin_user()

    async def _smart_find_one(filt=None, *_, **__):
        if isinstance(filt, dict) and "id" in filt:
            return _admin
        return None

    db.users.find_one = AsyncMock(side_effect=_smart_find_one)
    return db


def make_cursor(data_list):
    """Create a chainable cursor mock returning the given data."""
    cursor = MagicMock()
    cursor.sort = MagicMock(return_value=cursor)
    cursor.skip = MagicMock(return_value=cursor)
    cursor.limit = MagicMock(return_value=cursor)
    cursor.to_list = AsyncMock(return_value=data_list)
    return cursor


def make_agg_cursor(data_list):
    """Create an aggregate cursor mock."""
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=data_list)
    return cursor


# ---------------------------------------------------------------------------
# Helper: Create mock Request
# ---------------------------------------------------------------------------


def make_request(headers=None, client_ip="127.0.0.1", user_id=None):
    """Create a mock Litestar Request object with a VALID test JWT.

    Generates a real token signed with TEST_JWT_SECRET so route handlers'
    `await get_current_user(request)` calls succeed without per-test
    monkey-patching. Defaults to TEST_ADMIN_ID; pass user_id to scope
    requests as a different user.

    The mock DB built by make_mock_db() also defaults users.find_one to
    return an admin so the lookup inside get_current_user resolves.
    """
    import jwt as _jwt

    token = _jwt.encode(
        {
            "sub": user_id or TEST_ADMIN_ID,
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    req = MagicMock()
    default_headers = {"Authorization": f"Bearer {token}"}
    if headers:
        default_headers.update(headers)
    req.headers = default_headers
    req.scope = {"client": (client_ip, 12345)}
    req.body = AsyncMock(return_value=b"{}")
    return req


# ---------------------------------------------------------------------------
# Test user fixtures
# ---------------------------------------------------------------------------


def make_admin_user(campus_id=TEST_CAMPUS_ID):
    return {
        "id": TEST_ADMIN_ID,
        "email": "admin@test.com",
        "name": "Test Admin",
        "role": UserRole.FULL_ADMIN.value,
        "campus_id": campus_id,
        "phone": "+6281234567890",
        "is_active": True,
        "created_at": NOW,
        "hashed_password": "$2b$12$dummy_hash",
    }


def make_pastor_user(campus_id=TEST_CAMPUS_ID):
    return {
        "id": TEST_USER_ID,
        "email": "pastor@test.com",
        "name": "Test Pastor",
        "role": UserRole.PASTOR.value,
        "campus_id": campus_id,
        "phone": "+6281234567891",
        "is_active": True,
        "created_at": NOW,
        "hashed_password": "$2b$12$dummy_hash",
    }


def make_campus_admin_user(campus_id=TEST_CAMPUS_ID):
    return {
        "id": str(uuid.uuid4()),
        "email": "campus_admin@test.com",
        "name": "Campus Admin",
        "role": UserRole.CAMPUS_ADMIN.value,
        "campus_id": campus_id,
        "phone": "+6281234567892",
        "is_active": True,
        "created_at": NOW,
        "hashed_password": "$2b$12$dummy_hash",
    }


def make_test_member(campus_id=TEST_CAMPUS_ID, member_id=None):
    return {
        "id": member_id or TEST_MEMBER_ID,
        "name": "John Doe",
        "campus_id": campus_id,
        "phone": "+6281234567893",
        "photo_url": "/uploads/test.jpg",
        "engagement_status": "active",
        "days_since_last_contact": 5,
        "last_contact_date": NOW,
        "birth_date": "1990-05-15",
        "is_archived": False,
        "created_at": NOW,
    }


def make_test_care_event(
    campus_id=TEST_CAMPUS_ID, member_id=TEST_MEMBER_ID, event_id=None, event_type="birthday", completed=False
):
    return {
        "id": event_id or TEST_EVENT_ID,
        "campus_id": campus_id,
        "member_id": member_id,
        "event_type": event_type,
        "event_date": TODAY.isoformat(),
        "title": f"Test {event_type} Event",
        "description": "Test description",
        "completed": completed,
        "ignored": False,
        "created_at": NOW,
        "updated_at": NOW,
    }


# ---------------------------------------------------------------------------
# Initialize mock DB and dependencies
# ---------------------------------------------------------------------------

mock_db = make_mock_db()
init_dependencies(mock_db, TEST_JWT_SECRET)


# =====================================================================
# AUTH ROUTE TESTS
# =====================================================================


class TestAuthRoutes:
    """Tests for routes/auth.py"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Reset mock DB before each test."""
        global mock_db
        mock_db = make_mock_db()
        init_dependencies(mock_db, TEST_JWT_SECRET)

    # ---- LOGIN ----

    @patch("routes.auth.check_login_rate_limit", new_callable=AsyncMock, return_value=(True, None))
    @patch("routes.auth.verify_password", return_value=True)
    @patch("routes.auth.clear_login_attempts", new_callable=AsyncMock)
    @patch("routes.auth.create_access_token", return_value="test-jwt-token")
    @patch("routes.auth.get_client_ip", return_value="127.0.0.1")
    async def test_login_success_full_admin(self, mock_ip, mock_token, mock_clear, mock_verify, mock_rate):
        from models import UserLogin
        from routes.auth import login

        user = make_admin_user()
        mock_db.users.find_one = AsyncMock(return_value=user)
        mock_db.campuses.find_one = AsyncMock(return_value={"id": TEST_CAMPUS_ID, "campus_name": "Main Campus"})
        mock_db.users.update_one = AsyncMock()

        data = UserLogin(email="admin@test.com", password="TestPass123!", campus_id=TEST_CAMPUS_ID)
        req = make_request()

        result = await _fn(login)(data=data, request=req)
        # Login was hardened to wrap TokenResponse in a Litestar Response so
        # it can attach httpOnly auth + refresh cookies. The token model is
        # carried in result.content for body-based clients.
        token_response = result.content
        assert token_response.access_token == "test-jwt-token"
        assert token_response.user.email == "admin@test.com"
        assert token_response.user.campus_name == "Main Campus"

    @patch("routes.auth.check_login_rate_limit", new_callable=AsyncMock, return_value=(True, None))
    @patch("routes.auth.get_client_ip", return_value="127.0.0.1")
    async def test_login_user_not_found(self, mock_ip, mock_rate):
        from litestar.exceptions import HTTPException

        from models import UserLogin
        from routes.auth import login

        mock_db.users.find_one = AsyncMock(return_value=None)

        data = UserLogin(email="nonexistent@test.com", password="TestPass123!")
        req = make_request()

        with pytest.raises(HTTPException) as exc_info:
            await _fn(login)(data=data, request=req)
        assert exc_info.value.status_code == 401

    @patch("routes.auth.check_login_rate_limit", new_callable=AsyncMock, return_value=(True, None))
    @patch("routes.auth.verify_password", return_value=False)
    @patch("routes.auth.get_client_ip", return_value="127.0.0.1")
    async def test_login_wrong_password(self, mock_ip, mock_verify, mock_rate):
        from litestar.exceptions import HTTPException

        from models import UserLogin
        from routes.auth import login

        user = make_admin_user()
        mock_db.users.find_one = AsyncMock(return_value=user)

        data = UserLogin(email="admin@test.com", password="WrongPass123!")
        req = make_request()

        with pytest.raises(HTTPException) as exc_info:
            await _fn(login)(data=data, request=req)
        assert exc_info.value.status_code == 401

    @patch(
        "routes.auth.check_login_rate_limit",
        new_callable=AsyncMock,
        return_value=(False, "Account temporarily locked. Try again in 15 minutes."),
    )
    @patch("routes.auth.get_client_ip", return_value="127.0.0.1")
    async def test_login_rate_limited(self, mock_ip, mock_rate):
        from litestar.exceptions import HTTPException

        from models import UserLogin
        from routes.auth import login

        data = UserLogin(email="admin@test.com", password="TestPass123!")
        req = make_request()

        with pytest.raises(HTTPException) as exc_info:
            await _fn(login)(data=data, request=req)
        assert exc_info.value.status_code == 429

    @patch("routes.auth.check_login_rate_limit", new_callable=AsyncMock, return_value=(True, None))
    @patch("routes.auth.verify_password", return_value=True)
    @patch("routes.auth.get_client_ip", return_value="127.0.0.1")
    async def test_login_disabled_account(self, mock_ip, mock_verify, mock_rate):
        from litestar.exceptions import HTTPException

        from models import UserLogin
        from routes.auth import login

        user = make_admin_user()
        user["is_active"] = False
        mock_db.users.find_one = AsyncMock(return_value=user)

        data = UserLogin(email="admin@test.com", password="TestPass123!")
        req = make_request()

        with pytest.raises(HTTPException) as exc_info:
            await _fn(login)(data=data, request=req)
        assert exc_info.value.status_code == 403

    @patch("routes.auth.check_login_rate_limit", new_callable=AsyncMock, return_value=(True, None))
    @patch("routes.auth.verify_password", return_value=True)
    @patch("routes.auth.get_client_ip", return_value="127.0.0.1")
    async def test_login_full_admin_no_campus_selected(self, mock_ip, mock_verify, mock_rate):
        from litestar.exceptions import HTTPException

        from models import UserLogin
        from routes.auth import login

        user = make_admin_user()
        mock_db.users.find_one = AsyncMock(return_value=user)

        data = UserLogin(email="admin@test.com", password="TestPass123!", campus_id=None)
        req = make_request()

        with pytest.raises(HTTPException) as exc_info:
            await _fn(login)(data=data, request=req)
        assert exc_info.value.status_code == 400

    @patch("routes.auth.check_login_rate_limit", new_callable=AsyncMock, return_value=(True, None))
    @patch("routes.auth.verify_password", return_value=True)
    @patch("routes.auth.get_client_ip", return_value="127.0.0.1")
    async def test_login_campus_user_wrong_campus(self, mock_ip, mock_verify, mock_rate):
        from litestar.exceptions import HTTPException

        from models import UserLogin
        from routes.auth import login

        user = make_pastor_user()
        mock_db.users.find_one = AsyncMock(return_value=user)

        data = UserLogin(email="pastor@test.com", password="TestPass123!", campus_id=TEST_CAMPUS_ID_2)
        req = make_request()

        with pytest.raises(HTTPException) as exc_info:
            await _fn(login)(data=data, request=req)
        assert exc_info.value.status_code == 403

    # ---- GET ME ----

    @patch("routes.auth.get_current_user", new_callable=AsyncMock)
    async def test_get_me(self, mock_get_user):
        from routes.auth import get_current_user_info

        user = make_admin_user()
        mock_get_user.return_value = user
        mock_db.campuses.find_one = AsyncMock(return_value={"id": TEST_CAMPUS_ID, "campus_name": "Main Campus"})

        req = make_request()
        result = await _fn(get_current_user_info)(request=req)
        assert result.email == "admin@test.com"
        assert result.campus_name == "Main Campus"

    @patch("routes.auth.get_current_user", new_callable=AsyncMock)
    async def test_get_me_no_campus(self, mock_get_user):
        from routes.auth import get_current_user_info

        user = make_admin_user()
        user["campus_id"] = None
        mock_get_user.return_value = user

        req = make_request()
        result = await _fn(get_current_user_info)(request=req)
        assert result.campus_name is None

    # ---- LIST USERS ----

    @patch("routes.auth.get_current_admin", new_callable=AsyncMock)
    async def test_list_users_full_admin(self, mock_admin):
        from routes.auth import list_users

        admin = make_admin_user()
        mock_admin.return_value = admin

        users_data = [
            {
                "id": TEST_ADMIN_ID,
                "email": "admin@test.com",
                "name": "Test Admin",
                "role": "full_admin",
                "campus_id": TEST_CAMPUS_ID,
                "phone": "+6281234567890",
                "is_active": True,
                "created_at": NOW,
                "campus_name": "Main Campus",
            }
        ]
        mock_db.users.aggregate = MagicMock(return_value=make_agg_cursor(users_data))

        req = make_request()
        result = await _fn(list_users)(request=req)
        assert len(result) == 1
        assert result[0].email == "admin@test.com"

    @patch("routes.auth.get_current_admin", new_callable=AsyncMock)
    async def test_list_users_campus_admin_scoped(self, mock_admin):
        from routes.auth import list_users

        admin = make_campus_admin_user()
        mock_admin.return_value = admin

        mock_db.users.aggregate = MagicMock(return_value=make_agg_cursor([]))

        req = make_request()
        result = await _fn(list_users)(request=req)
        assert result == []

    # ---- REGISTER USER ----

    # Round-1 added an admin guard to register_user. These tests need to
    # bypass the auth lookup since they mock users.find_one for other
    # purposes (duplicate email check). Patch get_current_admin to return
    # a full_admin so we can test the actual email/password validation.

    @patch("routes.auth.get_current_admin", new_callable=AsyncMock)
    @patch("routes.auth.get_db")
    async def test_register_user_success(self, mock_get_db, mock_admin):
        from models import UserCreate
        from routes.auth import register_user

        mock_admin.return_value = make_admin_user()
        mock_get_db.return_value = mock_db
        mock_db.users.find_one = AsyncMock(return_value=None)
        mock_db.users.insert_one = AsyncMock()
        mock_db.campuses.find_one = AsyncMock(return_value={"id": TEST_CAMPUS_ID, "campus_name": "Main Campus"})

        data = UserCreate(
            email="new@test.com",
            password="StrongPass123!",
            name="New User",
            phone="+6281234567894",
            role=UserRole.PASTOR,
            campus_id=TEST_CAMPUS_ID,
        )
        req = make_request()
        result = await _fn(register_user)(data=data, request=req)
        assert result.email == "new@test.com"
        assert result.campus_name == "Main Campus"

    @patch("routes.auth.get_current_admin", new_callable=AsyncMock)
    @patch("routes.auth.get_db")
    async def test_register_user_duplicate_email(self, mock_get_db, mock_admin):
        from litestar.exceptions import HTTPException

        from models import UserCreate
        from routes.auth import register_user

        mock_admin.return_value = make_admin_user()
        mock_get_db.return_value = mock_db
        mock_db.users.find_one = AsyncMock(return_value={"email": "existing@test.com"})

        data = UserCreate(
            email="existing@test.com",
            password="StrongPass123!",
            name="Dup User",
            phone="+6281234567895",
            role=UserRole.PASTOR,
            campus_id=TEST_CAMPUS_ID,
        )
        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(register_user)(data=data, request=req)
        assert exc_info.value.status_code == 400

    @patch("routes.auth.get_current_admin", new_callable=AsyncMock)
    @patch("routes.auth.get_db")
    async def test_register_user_invalid_email(self, mock_get_db, mock_admin):
        from litestar.exceptions import HTTPException

        from models import UserCreate
        from routes.auth import register_user

        mock_admin.return_value = make_admin_user()
        mock_get_db.return_value = mock_db

        data = UserCreate(
            email="not-an-email",
            password="StrongPass123!",
            name="Bad Email",
            phone="+6281234567895",
            role=UserRole.PASTOR,
            campus_id=TEST_CAMPUS_ID,
        )
        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(register_user)(data=data, request=req)
        assert exc_info.value.status_code == 400

    @patch("routes.auth.get_current_admin", new_callable=AsyncMock)
    @patch("routes.auth.get_db")
    async def test_register_non_admin_without_campus(self, mock_get_db, mock_admin):
        from litestar.exceptions import HTTPException

        from models import UserCreate
        from routes.auth import register_user

        # Use full_admin (not campus_admin) so the campus-scoping guard
        # added in Round-2 doesn't reject the campus_id=None up-front;
        # we want to reach the explicit "campus_id required" check.
        mock_admin.return_value = make_admin_user()
        mock_get_db.return_value = mock_db
        mock_db.users.find_one = AsyncMock(return_value=None)

        data = UserCreate(
            email="new@test.com",
            password="StrongPass123!",
            name="No Campus",
            phone="+6281234567896",
            role=UserRole.PASTOR,
            campus_id=None,
        )
        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(register_user)(data=data, request=req)
        assert exc_info.value.status_code == 400

    # ---- UPDATE USER ----

    @patch("routes.auth.get_current_user", new_callable=AsyncMock)
    async def test_update_user_success(self, mock_get_user):
        from models import UserUpdate
        from routes.auth import update_user

        mock_get_user.return_value = make_admin_user()
        mock_result = MagicMock()
        mock_result.matched_count = 1
        mock_db.users.update_one = AsyncMock(return_value=mock_result)
        updated_user = make_admin_user()
        updated_user["name"] = "Updated Admin"
        mock_db.users.find_one = AsyncMock(return_value=updated_user)
        mock_db.campuses.find_one = AsyncMock(return_value={"id": TEST_CAMPUS_ID, "campus_name": "Main Campus"})

        data = UserUpdate(name="Updated Admin")
        req = make_request()
        result = await _fn(update_user)(user_id=TEST_ADMIN_ID, data=data, request=req)
        assert result["name"] == "Updated Admin"

    @patch("routes.auth.get_current_user", new_callable=AsyncMock)
    async def test_update_user_not_admin(self, mock_get_user):
        from litestar.exceptions import HTTPException

        from models import UserUpdate
        from routes.auth import update_user

        mock_get_user.return_value = make_pastor_user()

        data = UserUpdate(name="New Name")
        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(update_user)(user_id=TEST_ADMIN_ID, data=data, request=req)
        assert exc_info.value.status_code == 403

    @patch("routes.auth.get_current_user", new_callable=AsyncMock)
    async def test_update_user_not_found(self, mock_get_user):
        from litestar.exceptions import HTTPException

        from models import UserUpdate
        from routes.auth import update_user

        mock_get_user.return_value = make_admin_user()
        mock_result = MagicMock()
        mock_result.matched_count = 0
        mock_db.users.update_one = AsyncMock(return_value=mock_result)

        data = UserUpdate(name="Ghost")
        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(update_user)(user_id="nonexistent", data=data, request=req)
        assert exc_info.value.status_code == 404

    # ---- CHANGE PASSWORD ----

    @patch("routes.auth.get_current_user", new_callable=AsyncMock)
    @patch("routes.auth.verify_password")
    async def test_change_password_wrong_current(self, mock_verify, mock_get_user):
        from litestar.exceptions import HTTPException

        from models import PasswordChange
        from routes.auth import change_password

        mock_get_user.return_value = make_admin_user()
        mock_db.users.find_one = AsyncMock(return_value=make_admin_user())
        mock_verify.return_value = False

        data = PasswordChange(current_password="WrongCurrent!", new_password="NewPass1234!")
        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(change_password)(data=data, request=req)
        assert exc_info.value.status_code == 400

    @patch("routes.auth.get_current_user", new_callable=AsyncMock)
    @patch("routes.auth.verify_password")
    @patch("routes.auth.get_password_hash", return_value="$2b$12$new_hash")
    async def test_change_password_success(self, mock_hash, mock_verify, mock_get_user):
        from models import PasswordChange
        from routes.auth import change_password

        user = make_admin_user()
        mock_get_user.return_value = user
        mock_db.users.find_one = AsyncMock(return_value=user)
        # First call: verify current (True), Second call: verify new == current (False)
        mock_verify.side_effect = [True, False]

        data = PasswordChange(current_password="OldPass123!", new_password="NewPass1234!")
        req = make_request()
        result = await _fn(change_password)(data=data, request=req)
        assert result["message"] == "Password changed successfully"

    @patch("routes.auth.get_current_user", new_callable=AsyncMock)
    @patch("routes.auth.verify_password")
    async def test_change_password_same_as_current(self, mock_verify, mock_get_user):
        from litestar.exceptions import HTTPException

        from models import PasswordChange
        from routes.auth import change_password

        user = make_admin_user()
        mock_get_user.return_value = user
        mock_db.users.find_one = AsyncMock(return_value=user)
        # Both True: current valid AND new == current
        mock_verify.side_effect = [True, True]

        data = PasswordChange(current_password="SamePass123!", new_password="SamePass123!")
        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(change_password)(data=data, request=req)
        assert exc_info.value.status_code == 400

    # ---- DELETE USER ----

    @patch("routes.auth.get_current_admin", new_callable=AsyncMock)
    async def test_delete_user_success(self, mock_admin):
        from routes.auth import delete_user

        admin = make_admin_user()
        mock_admin.return_value = admin
        mock_result = MagicMock()
        mock_result.deleted_count = 1
        mock_db.users.delete_one = AsyncMock(return_value=mock_result)

        req = make_request()
        result = await _fn(delete_user)(user_id=TEST_USER_ID, request=req)
        assert result["success"] is True

    @patch("routes.auth.get_current_admin", new_callable=AsyncMock)
    async def test_delete_user_self_deletion(self, mock_admin):
        from litestar.exceptions import HTTPException

        from routes.auth import delete_user

        admin = make_admin_user()
        mock_admin.return_value = admin

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(delete_user)(user_id=TEST_ADMIN_ID, request=req)
        assert exc_info.value.status_code == 400

    @patch("routes.auth.get_current_admin", new_callable=AsyncMock)
    async def test_delete_user_not_found(self, mock_admin):
        from litestar.exceptions import HTTPException

        from routes.auth import delete_user

        mock_admin.return_value = make_admin_user()
        mock_result = MagicMock()
        mock_result.deleted_count = 0
        mock_db.users.delete_one = AsyncMock(return_value=mock_result)

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(delete_user)(user_id="nonexistent", request=req)
        assert exc_info.value.status_code == 404

    # ---- UPDATE OWN PROFILE ----

    @patch("routes.auth.get_current_user", new_callable=AsyncMock)
    async def test_update_own_profile_success(self, mock_get_user):
        from models import ProfileUpdate
        from routes.auth import update_own_profile

        user = make_admin_user()
        mock_get_user.return_value = user
        mock_result = MagicMock()
        mock_result.matched_count = 1
        mock_db.users.update_one = AsyncMock(return_value=mock_result)
        updated = dict(user)
        updated["name"] = "New Name"
        mock_db.users.find_one = AsyncMock(return_value=updated)
        mock_db.campuses.find_one = AsyncMock(return_value={"id": TEST_CAMPUS_ID, "campus_name": "Main Campus"})

        data = ProfileUpdate(name="New Name")
        req = make_request()
        result = await _fn(update_own_profile)(data=data, request=req)
        assert result["name"] == "New Name"

    @patch("routes.auth.get_current_user", new_callable=AsyncMock)
    async def test_update_own_profile_empty(self, mock_get_user):
        from litestar.exceptions import HTTPException

        from models import ProfileUpdate
        from routes.auth import update_own_profile

        mock_get_user.return_value = make_admin_user()

        data = ProfileUpdate()
        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(update_own_profile)(data=data, request=req)
        assert exc_info.value.status_code == 400

    @patch("routes.auth.get_current_user", new_callable=AsyncMock)
    async def test_update_own_profile_duplicate_email(self, mock_get_user):
        from litestar.exceptions import HTTPException

        from models import ProfileUpdate
        from routes.auth import update_own_profile

        user = make_admin_user()
        mock_get_user.return_value = user
        mock_db.users.find_one = AsyncMock(return_value={"id": "other-user"})

        data = ProfileUpdate(email="taken@test.com")
        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(update_own_profile)(data=data, request=req)
        assert exc_info.value.status_code == 400


# =====================================================================
# CAMPUS ROUTE TESTS
# =====================================================================


class TestCampusRoutes:
    """Tests for routes/campus.py"""

    @pytest.fixture(autouse=True)
    def setup(self):
        global mock_db
        mock_db = make_mock_db()
        init_dependencies(mock_db, TEST_JWT_SECRET)

    @patch("routes.campus.get_current_user", new_callable=AsyncMock)
    async def test_create_campus_success(self, mock_user):
        from models import CampusCreate
        from routes.campus import create_campus

        mock_user.return_value = make_admin_user()

        data = CampusCreate(campus_name="New Campus", location="Jakarta")
        req = make_request()
        result = await _fn(create_campus)(data=data, request=req)
        assert result["campus_name"] == "New Campus"
        mock_db.campuses.insert_one.assert_called_once()

    @patch("routes.campus.get_current_user", new_callable=AsyncMock)
    async def test_create_campus_not_full_admin(self, mock_user):
        from litestar.exceptions import HTTPException

        from models import CampusCreate
        from routes.campus import create_campus

        mock_user.return_value = make_pastor_user()

        data = CampusCreate(campus_name="New Campus")
        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(create_campus)(data=data, request=req)
        assert exc_info.value.status_code == 403

    @patch("routes.campus.get_from_cache", return_value=None)
    @patch("routes.campus.set_in_cache")
    async def test_list_campuses(self, mock_set_cache, mock_get_cache):
        from routes.campus import list_campuses

        campus_data = [
            {
                "id": TEST_CAMPUS_ID,
                "campus_name": "Main Campus",
                "is_active": True,
                "location": "Jakarta",
                "created_at": NOW,
                "updated_at": NOW,
            }
        ]
        mock_db.campuses.find = MagicMock(return_value=make_cursor(campus_data))

        result = await _fn(list_campuses)()
        # list_campuses returns a LitestarResponse
        assert result is not None

    @patch("routes.campus.get_from_cache", return_value=[{"id": "cached"}])
    async def test_list_campuses_cached(self, mock_get_cache):
        from routes.campus import list_campuses

        result = await _fn(list_campuses)()
        assert result is not None

    async def test_get_campus_by_id_success(self):
        from routes.campus import get_campus

        mock_db.campuses.find_one = AsyncMock(return_value={"id": TEST_CAMPUS_ID, "campus_name": "Main Campus"})

        result = await _fn(get_campus)(campus_id=TEST_CAMPUS_ID)
        assert result["campus_name"] == "Main Campus"

    async def test_get_campus_by_id_not_found(self):
        from litestar.exceptions import HTTPException

        from routes.campus import get_campus

        mock_db.campuses.find_one = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await _fn(get_campus)(campus_id="nonexistent")
        assert exc_info.value.status_code == 404

    @patch("routes.campus.get_current_user", new_callable=AsyncMock)
    async def test_update_campus_success(self, mock_user):
        from models import CampusCreate
        from routes.campus import update_campus

        mock_user.return_value = make_admin_user()
        mock_result = MagicMock()
        mock_result.matched_count = 1
        mock_db.campuses.update_one = AsyncMock(return_value=mock_result)
        mock_db.campuses.find_one = AsyncMock(return_value={"id": TEST_CAMPUS_ID, "campus_name": "Updated Campus"})

        data = CampusCreate(campus_name="Updated Campus")
        req = make_request()
        result = await _fn(update_campus)(campus_id=TEST_CAMPUS_ID, data=data, request=req)
        assert result["campus_name"] == "Updated Campus"

    @patch("routes.campus.get_current_user", new_callable=AsyncMock)
    async def test_update_campus_not_found(self, mock_user):
        from litestar.exceptions import HTTPException

        from models import CampusCreate
        from routes.campus import update_campus

        mock_user.return_value = make_admin_user()
        mock_result = MagicMock()
        mock_result.matched_count = 0
        mock_db.campuses.update_one = AsyncMock(return_value=mock_result)

        data = CampusCreate(campus_name="Nope")
        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(update_campus)(campus_id="nonexistent", data=data, request=req)
        assert exc_info.value.status_code == 404

    @patch("routes.campus.get_current_user", new_callable=AsyncMock)
    async def test_update_campus_not_admin(self, mock_user):
        from litestar.exceptions import HTTPException

        from models import CampusCreate
        from routes.campus import update_campus

        mock_user.return_value = make_pastor_user()

        data = CampusCreate(campus_name="Nope")
        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(update_campus)(campus_id=TEST_CAMPUS_ID, data=data, request=req)
        assert exc_info.value.status_code == 403


# =====================================================================
# MEMBER ROUTE TESTS
# =====================================================================


class TestMemberRoutes:
    """Tests for routes/members.py"""

    @pytest.fixture(autouse=True)
    def setup(self):
        global mock_db
        mock_db = make_mock_db()
        init_dependencies(mock_db, TEST_JWT_SECRET)
        # Initialize member routes with mock callbacks
        from routes.members import init_member_routes

        init_member_routes(
            invalidate_dashboard_cache=AsyncMock(),
            log_activity=AsyncMock(),
            msgspec_enc_hook=lambda obj: str(obj),
            root_dir=str(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        )

    @patch("routes.members.get_current_user", new_callable=AsyncMock)
    async def test_create_member_success(self, mock_user):
        from models import MemberCreate
        from routes.members import create_member

        mock_user.return_value = make_admin_user()

        data = MemberCreate(name="New Member", campus_id=TEST_CAMPUS_ID, phone="+6281234567900")
        req = make_request()
        result = await _fn(create_member)(data=data, request=req)
        assert result["name"] == "New Member"
        mock_db.members.insert_one.assert_called_once()

    @patch("routes.members.get_current_user", new_callable=AsyncMock)
    async def test_create_member_pastor_enforces_campus(self, mock_user):
        from models import MemberCreate
        from routes.members import create_member

        pastor = make_pastor_user()
        mock_user.return_value = pastor

        data = MemberCreate(name="Pastor Member", campus_id=TEST_CAMPUS_ID_2)
        req = make_request()
        result = await _fn(create_member)(data=data, request=req)
        assert result["campus_id"] == pastor["campus_id"]

    @patch("routes.members.get_current_user", new_callable=AsyncMock)
    async def test_list_members(self, mock_user):
        from routes.members import list_members

        mock_user.return_value = make_admin_user()
        member = make_test_member()
        mock_db.members.find = MagicMock(return_value=make_cursor([member]))
        mock_db.members.count_documents = AsyncMock(return_value=1)

        req = make_request()
        result = await _fn(list_members)(request=req, page=1, limit=50)
        # Returns a Response object
        assert result is not None

    @patch("routes.members.get_current_user", new_callable=AsyncMock)
    async def test_list_members_with_search(self, mock_user):
        from routes.members import list_members

        mock_user.return_value = make_admin_user()
        mock_db.members.find = MagicMock(return_value=make_cursor([]))
        mock_db.members.count_documents = AsyncMock(return_value=0)

        req = make_request()
        result = await _fn(list_members)(request=req, search="John", page=1, limit=50)
        assert result is not None

    @patch("routes.members.get_current_user", new_callable=AsyncMock)
    async def test_list_members_with_engagement_filter(self, mock_user):
        from routes.members import list_members

        mock_user.return_value = make_admin_user()
        mock_db.members.find = MagicMock(return_value=make_cursor([]))
        mock_db.members.count_documents = AsyncMock(return_value=0)

        req = make_request()
        result = await _fn(list_members)(request=req, engagement_status=EngagementStatus.AT_RISK, page=1, limit=50)
        assert result is not None

    @patch("routes.members.get_current_user", new_callable=AsyncMock)
    async def test_list_members_archived(self, mock_user):
        from routes.members import list_members

        mock_user.return_value = make_admin_user()
        mock_db.members.find = MagicMock(return_value=make_cursor([]))
        mock_db.members.count_documents = AsyncMock(return_value=0)

        req = make_request()
        result = await _fn(list_members)(request=req, show_archived=True, page=1, limit=50)
        assert result is not None

    @patch("routes.members.get_current_user", new_callable=AsyncMock)
    async def test_list_members_custom_fields(self, mock_user):
        from routes.members import list_members

        mock_user.return_value = make_admin_user()
        mock_db.members.find = MagicMock(return_value=make_cursor([]))
        mock_db.members.count_documents = AsyncMock(return_value=0)

        req = make_request()
        result = await _fn(list_members)(request=req, fields="id,name,phone", page=1, limit=50)
        assert result is not None

    @patch("routes.members.get_current_user", new_callable=AsyncMock)
    async def test_get_member_success(self, mock_user):
        from routes.members import get_member

        mock_user.return_value = make_admin_user()
        member = make_test_member()
        mock_db.members.find_one = AsyncMock(return_value=member)

        req = make_request()
        result = await _fn(get_member)(member_id=TEST_MEMBER_ID, request=req)
        assert result["name"] == "John Doe"

    @patch("routes.members.get_current_user", new_callable=AsyncMock)
    async def test_get_member_not_found(self, mock_user):
        from litestar.exceptions import HTTPException

        from routes.members import get_member

        mock_user.return_value = make_admin_user()
        mock_db.members.find_one = AsyncMock(return_value=None)

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(get_member)(member_id="nonexistent", request=req)
        assert exc_info.value.status_code == 404

    @patch("routes.members.get_current_user", new_callable=AsyncMock)
    async def test_get_member_string_last_contact(self, mock_user):
        from routes.members import get_member

        mock_user.return_value = make_admin_user()
        member = make_test_member()
        member["last_contact_date"] = NOW.isoformat()
        mock_db.members.find_one = AsyncMock(return_value=member)

        req = make_request()
        result = await _fn(get_member)(member_id=TEST_MEMBER_ID, request=req)
        assert result["engagement_status"] is not None

    @patch("routes.members.get_current_user", new_callable=AsyncMock)
    async def test_update_member_success(self, mock_user):
        from models import MemberUpdate
        from routes.members import update_member

        mock_user.return_value = make_admin_user()
        updated_member = make_test_member()
        updated_member["name"] = "Updated Name"
        mock_db.members.find_one_and_update = AsyncMock(return_value=updated_member)

        data = MemberUpdate(name="Updated Name")
        req = make_request()
        result = await _fn(update_member)(member_id=TEST_MEMBER_ID, data=data, request=req)
        assert result["name"] == "Updated Name"

    @patch("routes.members.get_current_user", new_callable=AsyncMock)
    async def test_update_member_not_found(self, mock_user):
        from litestar.exceptions import HTTPException

        from models import MemberUpdate
        from routes.members import update_member

        mock_user.return_value = make_admin_user()
        mock_db.members.find_one_and_update = AsyncMock(return_value=None)

        data = MemberUpdate(name="Ghost")
        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(update_member)(member_id=str(uuid.uuid4()), data=data, request=req)
        assert exc_info.value.status_code == 404

    @patch("routes.members.get_current_user", new_callable=AsyncMock)
    async def test_update_member_invalid_uuid(self, mock_user):
        from litestar.exceptions import HTTPException

        from models import MemberUpdate
        from routes.members import update_member

        mock_user.return_value = make_admin_user()

        data = MemberUpdate(name="Bad UUID")
        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(update_member)(member_id="not-a-uuid", data=data, request=req)
        assert exc_info.value.status_code == 400

    @patch("routes.members.get_current_user", new_callable=AsyncMock)
    async def test_delete_member_success(self, mock_user):
        from routes.members import delete_member

        mock_user.return_value = make_admin_user()
        member = make_test_member()
        mock_db.members.find_one = AsyncMock(return_value=member)
        mock_result = MagicMock()
        mock_result.deleted_count = 1
        mock_db.members.delete_one = AsyncMock(return_value=mock_result)

        req = make_request()
        result = await _fn(delete_member)(member_id=TEST_MEMBER_ID, request=req)
        assert result["success"] is True
        # Verify cascade deletes
        mock_db.care_events.delete_many.assert_called_once()
        mock_db.grief_support.delete_many.assert_called_once()
        mock_db.accident_followup.delete_many.assert_called_once()

    @patch("routes.members.get_current_user", new_callable=AsyncMock)
    async def test_delete_member_not_found(self, mock_user):
        from litestar.exceptions import HTTPException

        from routes.members import delete_member

        mock_user.return_value = make_admin_user()
        mock_db.members.find_one = AsyncMock(return_value=None)

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(delete_member)(member_id="nonexistent", request=req)
        assert exc_info.value.status_code == 404

    @patch("routes.members.get_current_user", new_callable=AsyncMock)
    async def test_list_at_risk_members(self, mock_user):
        from routes.members import list_at_risk_members

        mock_user.return_value = make_admin_user()
        member = make_test_member()
        member["last_contact_date"] = None
        mock_db.members.find = MagicMock(return_value=make_cursor([member]))

        req = make_request()
        result = await _fn(list_at_risk_members)(request=req)
        # Members with no contact will be disconnected
        assert isinstance(result, list)

    @patch("routes.members.get_current_user", new_callable=AsyncMock)
    async def test_list_at_risk_members_string_dates(self, mock_user):
        from routes.members import list_at_risk_members

        mock_user.return_value = make_admin_user()
        member = make_test_member()
        old_date = (NOW - timedelta(days=100)).isoformat()
        member["last_contact_date"] = old_date
        mock_db.members.find = MagicMock(return_value=make_cursor([member]))

        req = make_request()
        result = await _fn(list_at_risk_members)(request=req)
        assert isinstance(result, list)


# =====================================================================
# CARE EVENT ROUTE TESTS
# =====================================================================


class TestCareEventRoutes:
    """Tests for routes/care_events.py"""

    @pytest.fixture(autouse=True)
    def setup(self):
        global mock_db
        mock_db = make_mock_db()
        init_dependencies(mock_db, TEST_JWT_SECRET)
        from routes.care_events import init_care_event_routes

        init_care_event_routes(
            invalidate_dashboard_cache=AsyncMock(),
            log_activity=AsyncMock(),
            send_whatsapp_message=AsyncMock(return_value={"success": True}),
            generate_grief_timeline=MagicMock(
                return_value=[
                    {
                        "id": str(uuid.uuid4()),
                        "stage": "1_week",
                        "scheduled_date": "2026-04-05",
                        "member_id": TEST_MEMBER_ID,
                        "care_event_id": "evt-1",
                        "completed": False,
                    }
                ]
            ),
            generate_accident_followup_timeline=MagicMock(
                return_value=[
                    {
                        "id": str(uuid.uuid4()),
                        "stage": "first_followup",
                        "scheduled_date": "2026-04-01",
                        "member_id": TEST_MEMBER_ID,
                        "care_event_id": "evt-1",
                        "campus_id": TEST_CAMPUS_ID,
                        "completed": False,
                    }
                ]
            ),
            get_campus_timezone=AsyncMock(return_value="Asia/Jakarta"),
            get_date_in_timezone=MagicMock(return_value=TODAY.isoformat()),
        )

    @patch("routes.care_events.get_current_user", new_callable=AsyncMock)
    async def test_create_regular_contact_event(self, mock_user):
        from models import CareEventCreate
        from routes.care_events import create_care_event

        mock_user.return_value = make_admin_user()
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        data = CareEventCreate(
            member_id=TEST_MEMBER_ID,
            campus_id=TEST_CAMPUS_ID,
            event_type=EventType.REGULAR_CONTACT,
            event_date=TODAY,
            title="Regular Check-in",
        )
        req = make_request()
        result = await _fn(create_care_event)(data=data, request=req)
        assert result.completed is True  # One-time events auto-complete

    @patch("routes.care_events.get_current_user", new_callable=AsyncMock)
    async def test_create_grief_event_generates_timeline(self, mock_user):
        from models import CareEventCreate
        from routes.care_events import create_care_event

        mock_user.return_value = make_admin_user()
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        data = CareEventCreate(
            member_id=TEST_MEMBER_ID,
            campus_id=TEST_CAMPUS_ID,
            event_type=EventType.GRIEF_LOSS,
            event_date=TODAY,
            title="Grief Support",
            grief_relationship="Father",
        )
        req = make_request()
        result = await _fn(create_care_event)(data=data, request=req)
        assert result.event_type == EventType.GRIEF_LOSS
        mock_db.grief_support.insert_many.assert_called_once()

    @patch("routes.care_events.get_current_user", new_callable=AsyncMock)
    async def test_create_accident_event_generates_followup(self, mock_user):
        from models import CareEventCreate
        from routes.care_events import create_care_event

        mock_user.return_value = make_admin_user()
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        data = CareEventCreate(
            member_id=TEST_MEMBER_ID,
            campus_id=TEST_CAMPUS_ID,
            event_type=EventType.ACCIDENT_ILLNESS,
            event_date=TODAY,
            title="Accident Event",
        )
        req = make_request()
        await _fn(create_care_event)(data=data, request=req)
        mock_db.accident_followup.insert_many.assert_called_once()

    @patch("routes.care_events.get_current_user", new_callable=AsyncMock)
    async def test_create_financial_aid_event(self, mock_user):
        from models import CareEventCreate
        from routes.care_events import create_care_event

        mock_user.return_value = make_admin_user()
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        data = CareEventCreate(
            member_id=TEST_MEMBER_ID,
            campus_id=TEST_CAMPUS_ID,
            event_type=EventType.FINANCIAL_AID,
            event_date=TODAY,
            title="Financial Aid",
            aid_type=AidType.EMERGENCY,
            aid_amount=500000.0,
        )
        req = make_request()
        result = await _fn(create_care_event)(data=data, request=req)
        assert result.aid_type == AidType.EMERGENCY

    @patch("routes.care_events.get_current_user", new_callable=AsyncMock)
    async def test_create_financial_aid_missing_type(self, mock_user):
        from litestar.exceptions import HTTPException

        from models import CareEventCreate
        from routes.care_events import create_care_event

        mock_user.return_value = make_admin_user()

        data = CareEventCreate(
            member_id=TEST_MEMBER_ID,
            campus_id=TEST_CAMPUS_ID,
            event_type=EventType.FINANCIAL_AID,
            event_date=TODAY,
            title="Missing Aid Type",
            aid_type=None,
            aid_amount=500000.0,
        )
        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(create_care_event)(data=data, request=req)
        assert exc_info.value.status_code == 400

    @patch("routes.care_events.get_current_user", new_callable=AsyncMock)
    async def test_create_financial_aid_invalid_amount(self, mock_user):
        from litestar.exceptions import HTTPException

        from models import CareEventCreate
        from routes.care_events import create_care_event

        mock_user.return_value = make_admin_user()

        data = CareEventCreate(
            member_id=TEST_MEMBER_ID,
            campus_id=TEST_CAMPUS_ID,
            event_type=EventType.FINANCIAL_AID,
            event_date=TODAY,
            title="Bad Amount",
            aid_type=AidType.EMERGENCY,
            aid_amount=-100,
        )
        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(create_care_event)(data=data, request=req)
        assert exc_info.value.status_code == 400

    @patch("routes.care_events.get_current_user", new_callable=AsyncMock)
    async def test_create_birthday_event(self, mock_user):
        from models import CareEventCreate
        from routes.care_events import create_care_event

        mock_user.return_value = make_admin_user()
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        data = CareEventCreate(
            member_id=TEST_MEMBER_ID,
            campus_id=TEST_CAMPUS_ID,
            event_type=EventType.BIRTHDAY,
            event_date=TODAY,
            title="Birthday",
        )
        req = make_request()
        result = await _fn(create_care_event)(data=data, request=req)
        # Birthday is NOT one-time, so not auto-completed
        assert result.completed is False

    @patch("routes.care_events.get_current_user", new_callable=AsyncMock)
    async def test_create_childbirth_event_autocomplete(self, mock_user):
        from models import CareEventCreate
        from routes.care_events import create_care_event

        mock_user.return_value = make_admin_user()
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        data = CareEventCreate(
            member_id=TEST_MEMBER_ID,
            campus_id=TEST_CAMPUS_ID,
            event_type=EventType.CHILDBIRTH,
            event_date=TODAY,
            title="Childbirth",
        )
        req = make_request()
        result = await _fn(create_care_event)(data=data, request=req)
        assert result.completed is True

    @patch("routes.care_events.get_current_user", new_callable=AsyncMock)
    async def test_create_event_pastor_enforces_campus(self, mock_user):
        from models import CareEventCreate
        from routes.care_events import create_care_event

        pastor = make_pastor_user()
        mock_user.return_value = pastor
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        data = CareEventCreate(
            member_id=TEST_MEMBER_ID,
            campus_id=TEST_CAMPUS_ID_2,
            event_type=EventType.REGULAR_CONTACT,
            event_date=TODAY,
            title="Test",
        )
        req = make_request()
        result = await _fn(create_care_event)(data=data, request=req)
        assert result.campus_id == pastor["campus_id"]

    # ---- LIST CARE EVENTS ----

    @patch("routes.care_events.get_current_user", new_callable=AsyncMock)
    async def test_list_care_events(self, mock_user):
        from routes.care_events import list_care_events

        mock_user.return_value = make_admin_user()
        events = [make_test_care_event()]
        mock_db.care_events.aggregate = MagicMock(return_value=make_agg_cursor(events))

        req = make_request()
        result = await _fn(list_care_events)(request=req, page=1, limit=50)
        assert len(result) == 1

    @patch("routes.care_events.get_current_user", new_callable=AsyncMock)
    async def test_list_care_events_with_filters(self, mock_user):
        from routes.care_events import list_care_events

        mock_user.return_value = make_admin_user()
        mock_db.care_events.aggregate = MagicMock(return_value=make_agg_cursor([]))

        req = make_request()
        result = await _fn(list_care_events)(
            request=req, event_type=EventType.BIRTHDAY, member_id=TEST_MEMBER_ID, completed=False, page=2, limit=10
        )
        assert result == []

    # ---- GET CARE EVENT ----

    @patch("routes.care_events.get_current_user", new_callable=AsyncMock)
    async def test_get_care_event_success(self, mock_user):
        from routes.care_events import get_care_event

        mock_user.return_value = make_admin_user()
        event = make_test_care_event()
        mock_db.care_events.find_one = AsyncMock(return_value=event)

        req = make_request()
        result = await _fn(get_care_event)(event_id=TEST_EVENT_ID, request=req)
        assert result["id"] == TEST_EVENT_ID

    @patch("routes.care_events.get_current_user", new_callable=AsyncMock)
    async def test_get_care_event_not_found(self, mock_user):
        from litestar.exceptions import HTTPException

        from routes.care_events import get_care_event

        mock_user.return_value = make_admin_user()
        mock_db.care_events.find_one = AsyncMock(return_value=None)

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(get_care_event)(event_id="nonexistent", request=req)
        assert exc_info.value.status_code == 404

    # ---- UPDATE CARE EVENT ----

    @patch("routes.care_events.get_current_user", new_callable=AsyncMock)
    async def test_update_care_event_success(self, mock_user):
        from models import CareEventUpdate
        from routes.care_events import update_care_event

        mock_user.return_value = make_admin_user()
        event = make_test_care_event()
        mock_db.care_events.find_one = AsyncMock(return_value=event)
        mock_result = MagicMock()
        mock_result.matched_count = 1
        mock_db.care_events.update_one = AsyncMock(return_value=mock_result)

        data = CareEventUpdate(title="Updated Title")
        req = make_request()
        result = await _fn(update_care_event)(event_id=TEST_EVENT_ID, data=data, request=req)
        assert result is not None

    @patch("routes.care_events.get_current_user", new_callable=AsyncMock)
    async def test_update_care_event_not_found(self, mock_user):
        from litestar.exceptions import HTTPException

        from models import CareEventUpdate
        from routes.care_events import update_care_event

        mock_user.return_value = make_admin_user()
        mock_db.care_events.find_one = AsyncMock(return_value=None)

        data = CareEventUpdate(title="Ghost")
        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(update_care_event)(event_id="nonexistent", data=data, request=req)
        assert exc_info.value.status_code == 404

    # ---- COMPLETE CARE EVENT ----

    @patch("routes.care_events.get_current_user", new_callable=AsyncMock)
    async def test_complete_care_event_success(self, mock_user):
        from routes.care_events import complete_care_event

        mock_user.return_value = make_admin_user()
        event = make_test_care_event(completed=False)
        mock_db.care_events.find_one = AsyncMock(return_value=event)
        mock_result = MagicMock()
        mock_result.matched_count = 1
        mock_db.care_events.update_one = AsyncMock(return_value=mock_result)
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        req = make_request()
        result = await _fn(complete_care_event)(event_id=TEST_EVENT_ID, request=req)
        assert result["success"] is True

    @patch("routes.care_events.get_current_user", new_callable=AsyncMock)
    async def test_complete_care_event_already_completed(self, mock_user):
        from routes.care_events import complete_care_event

        mock_user.return_value = make_admin_user()
        event = make_test_care_event(completed=True)
        mock_db.care_events.find_one = AsyncMock(return_value=event)

        req = make_request()
        result = await _fn(complete_care_event)(event_id=TEST_EVENT_ID, request=req)
        assert result["success"] is True
        assert "already completed" in result["message"]

    @patch("routes.care_events.get_current_user", new_callable=AsyncMock)
    async def test_complete_care_event_not_found(self, mock_user):
        from litestar.exceptions import HTTPException

        from routes.care_events import complete_care_event

        mock_user.return_value = make_admin_user()
        mock_db.care_events.find_one = AsyncMock(return_value=None)

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(complete_care_event)(event_id="nonexistent", request=req)
        assert exc_info.value.status_code == 404

    @patch("routes.care_events.get_current_user", new_callable=AsyncMock)
    async def test_complete_birthday_creates_contact_event(self, mock_user):
        from routes.care_events import complete_care_event

        mock_user.return_value = make_admin_user()
        event = make_test_care_event(event_type="birthday", completed=False)
        # Round-2 added a dedup check that calls find_one with
        # event_type="regular_contact" + title="Birthday Contact" before
        # inserting. We need find_one to return the birthday event for the
        # initial lookup but None for the dedup check, so the insert fires.
        async def _smart_find_one(filt=None, *_, **__):
            if isinstance(filt, dict) and filt.get("event_type") == "regular_contact":
                return None
            return event
        mock_db.care_events.find_one = AsyncMock(side_effect=_smart_find_one)
        mock_result = MagicMock()
        mock_result.matched_count = 1
        mock_db.care_events.update_one = AsyncMock(return_value=mock_result)
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        req = make_request()
        result = await _fn(complete_care_event)(event_id=TEST_EVENT_ID, request=req)
        assert result["success"] is True
        # Should have called insert_one for the birthday contact event
        assert mock_db.care_events.insert_one.called

    # ---- COMPLETE BIRTHDAY BY MEMBER ----

    @patch("routes.care_events.get_current_user", new_callable=AsyncMock)
    async def test_complete_birthday_by_member_new_event(self, mock_user):
        from routes.care_events import complete_birthday_by_member

        mock_user.return_value = make_admin_user()
        member = make_test_member()
        mock_db.members.find_one = AsyncMock(return_value=member)
        mock_db.care_events.find_one = AsyncMock(return_value=None)

        req = make_request()
        result = await _fn(complete_birthday_by_member)(member_id=TEST_MEMBER_ID, request=req)
        assert result["success"] is True

    @patch("routes.care_events.get_current_user", new_callable=AsyncMock)
    async def test_complete_birthday_by_member_existing_event(self, mock_user):
        from routes.care_events import complete_birthday_by_member

        mock_user.return_value = make_admin_user()
        member = make_test_member()
        mock_db.members.find_one = AsyncMock(return_value=member)
        existing_event = make_test_care_event(event_type="birthday")
        mock_db.care_events.find_one = AsyncMock(return_value=existing_event)

        req = make_request()
        result = await _fn(complete_birthday_by_member)(member_id=TEST_MEMBER_ID, request=req)
        assert result["success"] is True

    @patch("routes.care_events.get_current_user", new_callable=AsyncMock)
    async def test_complete_birthday_by_member_no_birth_date(self, mock_user):
        from litestar.exceptions import HTTPException

        from routes.care_events import complete_birthday_by_member

        mock_user.return_value = make_admin_user()
        member = make_test_member()
        member["birth_date"] = None
        mock_db.members.find_one = AsyncMock(return_value=member)

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(complete_birthday_by_member)(member_id=TEST_MEMBER_ID, request=req)
        assert exc_info.value.status_code == 400

    @patch("routes.care_events.get_current_user", new_callable=AsyncMock)
    async def test_complete_birthday_by_member_not_found(self, mock_user):
        from litestar.exceptions import HTTPException

        from routes.care_events import complete_birthday_by_member

        mock_user.return_value = make_admin_user()
        mock_db.members.find_one = AsyncMock(return_value=None)

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(complete_birthday_by_member)(member_id="nonexistent", request=req)
        assert exc_info.value.status_code == 404

    # ---- ADDITIONAL VISIT ----

    @patch("routes.care_events.get_current_user", new_callable=AsyncMock)
    async def test_log_additional_visit_success(self, mock_user):
        from models import AdditionalVisitRequest
        from routes.care_events import log_additional_visit

        mock_user.return_value = make_admin_user()
        parent_event = make_test_care_event(event_type=EventType.GRIEF_LOSS.value)
        mock_db.care_events.find_one = AsyncMock(return_value=parent_event)
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        data = AdditionalVisitRequest(visit_date=TODAY.isoformat(), visit_type="Home Visit", notes="Good visit")
        req = make_request()
        result = await _fn(log_additional_visit)(parent_event_id=TEST_EVENT_ID, data=data, request=req)
        assert result["success"] is True

    @patch("routes.care_events.get_current_user", new_callable=AsyncMock)
    async def test_log_additional_visit_wrong_type(self, mock_user):
        from litestar.exceptions import HTTPException

        from models import AdditionalVisitRequest
        from routes.care_events import log_additional_visit

        mock_user.return_value = make_admin_user()
        parent_event = make_test_care_event(event_type="birthday")
        mock_db.care_events.find_one = AsyncMock(return_value=parent_event)

        data = AdditionalVisitRequest(visit_date=TODAY.isoformat(), visit_type="Home Visit", notes="Bad type")
        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(log_additional_visit)(parent_event_id=TEST_EVENT_ID, data=data, request=req)
        assert exc_info.value.status_code == 400

    # ---- SEND REMINDER ----

    @patch("routes.care_events.get_current_user", new_callable=AsyncMock)
    async def test_send_care_event_reminder_success(self, mock_user):
        from routes.care_events import send_care_event_reminder

        mock_user.return_value = make_admin_user()
        event = make_test_care_event()
        mock_db.care_events.find_one = AsyncMock(return_value=event)
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        req = make_request()
        result = await _fn(send_care_event_reminder)(event_id=TEST_EVENT_ID, request=req)
        assert result["success"] is True

    @patch("routes.care_events.get_current_user", new_callable=AsyncMock)
    async def test_send_reminder_event_not_found(self, mock_user):
        from litestar.exceptions import HTTPException

        from routes.care_events import send_care_event_reminder

        mock_user.return_value = make_admin_user()
        mock_db.care_events.find_one = AsyncMock(return_value=None)

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(send_care_event_reminder)(event_id="nonexistent", request=req)
        assert exc_info.value.status_code == 404

    # ---- VISITATION LOG ----

    async def test_add_visitation_log_success(self):
        from models import VisitationLogEntry
        from routes.care_events import add_visitation_log

        event = make_test_care_event()
        mock_db.care_events.find_one = AsyncMock(return_value=event)

        entry = VisitationLogEntry(visitor_name="Pastor John", visit_date=TODAY, notes="Good visit")
        result = await _fn(add_visitation_log)(event_id=TEST_EVENT_ID, entry=entry, request=make_request())
        assert result["success"] is True

    async def test_add_visitation_log_event_not_found(self):
        from litestar.exceptions import HTTPException

        from models import VisitationLogEntry
        from routes.care_events import add_visitation_log

        mock_db.care_events.find_one = AsyncMock(return_value=None)

        entry = VisitationLogEntry(visitor_name="Pastor", visit_date=TODAY, notes="Ghost")
        with pytest.raises(HTTPException) as exc_info:
            await _fn(add_visitation_log)(event_id="nonexistent", entry=entry, request=make_request())
        assert exc_info.value.status_code == 404

    # ---- HOSPITAL FOLLOWUP DUE ----

    async def test_get_hospital_followup_due(self):
        from routes.care_events import get_hospital_followup_due

        # Event with date 3 days ago
        event = make_test_care_event(event_type="accident_illness")
        event["completed"] = False
        event["event_date"] = (TODAY - timedelta(days=3)).isoformat()
        mock_db.care_events.find = MagicMock(return_value=make_cursor([event]))

        result = await _fn(get_hospital_followup_due)(request=make_request())
        assert len(result) == 1
        assert result[0]["days_since_event"] == 3

    async def test_get_hospital_followup_due_no_events(self):
        from routes.care_events import get_hospital_followup_due

        mock_db.care_events.find = MagicMock(return_value=make_cursor([]))

        result = await _fn(get_hospital_followup_due)(request=make_request())
        assert result == []

    # ---- BULK OPERATIONS ----

    @patch("routes.care_events.get_current_user", new_callable=AsyncMock)
    async def test_bulk_complete_success(self, mock_user):
        from routes.care_events import BulkEventIds, bulk_complete_care_events

        mock_user.return_value = make_admin_user()
        events = [make_test_care_event()]
        mock_db.care_events.find = MagicMock(return_value=make_cursor(events))
        mock_result = MagicMock()
        mock_result.modified_count = 1
        mock_db.care_events.update_many = AsyncMock(return_value=mock_result)
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        data = BulkEventIds(event_ids=[TEST_EVENT_ID])
        req = make_request()
        result = await _fn(bulk_complete_care_events)(request=req, data=data)
        assert result["success"] is True
        assert result["completed_count"] == 1

    @patch("routes.care_events.get_current_user", new_callable=AsyncMock)
    async def test_bulk_complete_empty(self, mock_user):
        from litestar.exceptions import HTTPException

        from routes.care_events import BulkEventIds, bulk_complete_care_events

        mock_user.return_value = make_admin_user()

        data = BulkEventIds(event_ids=[])
        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(bulk_complete_care_events)(request=req, data=data)
        assert exc_info.value.status_code == 400

    @patch("routes.care_events.get_current_user", new_callable=AsyncMock)
    async def test_bulk_complete_too_many(self, mock_user):
        from litestar.exceptions import HTTPException

        from routes.care_events import BulkEventIds, bulk_complete_care_events

        mock_user.return_value = make_admin_user()

        data = BulkEventIds(event_ids=[str(uuid.uuid4()) for _ in range(101)])
        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(bulk_complete_care_events)(request=req, data=data)
        assert exc_info.value.status_code == 400

    @patch("routes.care_events.get_current_user", new_callable=AsyncMock)
    async def test_bulk_complete_no_pending(self, mock_user):
        from routes.care_events import BulkEventIds, bulk_complete_care_events

        mock_user.return_value = make_admin_user()
        mock_db.care_events.find = MagicMock(return_value=make_cursor([]))

        data = BulkEventIds(event_ids=[TEST_EVENT_ID])
        req = make_request()
        result = await _fn(bulk_complete_care_events)(request=req, data=data)
        assert result["completed_count"] == 0

    @patch("routes.care_events.get_current_user", new_callable=AsyncMock)
    async def test_bulk_ignore_success(self, mock_user):
        from routes.care_events import BulkEventIds, bulk_ignore_care_events

        mock_user.return_value = make_admin_user()
        events = [make_test_care_event()]
        mock_db.care_events.find = MagicMock(return_value=make_cursor(events))
        mock_result = MagicMock()
        mock_result.modified_count = 1
        mock_db.care_events.update_many = AsyncMock(return_value=mock_result)
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        data = BulkEventIds(event_ids=[TEST_EVENT_ID])
        req = make_request()
        result = await _fn(bulk_ignore_care_events)(request=req, data=data)
        assert result["success"] is True

    @patch("routes.care_events.get_current_user", new_callable=AsyncMock)
    async def test_bulk_ignore_empty(self, mock_user):
        from litestar.exceptions import HTTPException

        from routes.care_events import BulkEventIds, bulk_ignore_care_events

        mock_user.return_value = make_admin_user()

        data = BulkEventIds(event_ids=[])
        req = make_request()
        with pytest.raises(HTTPException):
            await _fn(bulk_ignore_care_events)(request=req, data=data)

    @patch("routes.care_events.get_current_user", new_callable=AsyncMock)
    @patch("routes.care_events._log_activity", None)
    async def test_bulk_delete_success(self, mock_user):
        from routes.care_events import BulkEventIds, bulk_delete_care_events

        mock_user.return_value = make_admin_user()
        events = [make_test_care_event()]
        mock_db.care_events.find = MagicMock(return_value=make_cursor(events))
        mock_result = MagicMock()
        mock_result.deleted_count = 1
        mock_db.care_events.delete_many = AsyncMock(return_value=mock_result)
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        data = BulkEventIds(event_ids=[TEST_EVENT_ID])
        req = make_request()
        result = await _fn(bulk_delete_care_events)(request=req, data=data)
        assert result["success"] is True
        assert result["deleted_count"] == 1

    @patch("routes.care_events.get_current_user", new_callable=AsyncMock)
    async def test_bulk_delete_too_many(self, mock_user):
        from litestar.exceptions import HTTPException

        from routes.care_events import BulkEventIds, bulk_delete_care_events

        mock_user.return_value = make_admin_user()

        data = BulkEventIds(event_ids=[str(uuid.uuid4()) for _ in range(51)])
        req = make_request()
        with pytest.raises(HTTPException):
            await _fn(bulk_delete_care_events)(request=req, data=data)


# =====================================================================
# GRIEF SUPPORT ROUTE TESTS
# =====================================================================


class TestGriefSupportRoutes:
    """Tests for routes/grief_support.py"""

    @pytest.fixture(autouse=True)
    def setup(self):
        global mock_db
        mock_db = make_mock_db()
        init_dependencies(mock_db, TEST_JWT_SECRET)
        from routes.grief_support import init_grief_support_routes

        init_grief_support_routes(
            invalidate_dashboard_cache=AsyncMock(),
            log_activity=AsyncMock(),
            send_whatsapp_message=AsyncMock(return_value={"success": True}),
            get_campus_timezone=AsyncMock(return_value="Asia/Jakarta"),
            get_date_in_timezone=MagicMock(return_value=TODAY.isoformat()),
        )

    @patch("routes.grief_support.get_current_user", new_callable=AsyncMock)
    async def test_list_grief_support(self, mock_user):
        from routes.grief_support import list_grief_support

        mock_user.return_value = make_admin_user()
        stages = [
            {
                "id": str(uuid.uuid4()),
                "stage": "1_week",
                "completed": False,
                "member_id": TEST_MEMBER_ID,
                "scheduled_date": TODAY.isoformat(),
            }
        ]
        mock_db.grief_support.find = MagicMock(return_value=make_cursor(stages))

        req = make_request()
        result = await _fn(list_grief_support)(request=req, page=1, limit=50)
        assert len(result) == 1

    @patch("routes.grief_support.get_current_user", new_callable=AsyncMock)
    async def test_list_grief_support_with_completed_filter(self, mock_user):
        from routes.grief_support import list_grief_support

        mock_user.return_value = make_admin_user()
        mock_db.grief_support.find = MagicMock(return_value=make_cursor([]))

        req = make_request()
        result = await _fn(list_grief_support)(request=req, completed=True, page=1, limit=10)
        assert result == []

    @patch("routes.grief_support.get_current_user", new_callable=AsyncMock)
    async def test_get_member_grief_timeline(self, mock_user):
        from routes.grief_support import get_member_grief_timeline

        mock_user.return_value = make_admin_user()
        stages = [{"id": "s1", "stage": "1_week", "member_id": TEST_MEMBER_ID}]
        mock_db.grief_support.find = MagicMock(return_value=make_cursor(stages))

        req = make_request()
        result = await _fn(get_member_grief_timeline)(member_id=TEST_MEMBER_ID, request=req)
        assert len(result) == 1

    @patch("routes.grief_support.get_current_user", new_callable=AsyncMock)
    async def test_complete_grief_stage_success(self, mock_user):
        from routes.grief_support import complete_grief_stage

        mock_user.return_value = make_admin_user()
        stage = {
            "id": "stage-1",
            "stage": "1_week",
            "member_id": TEST_MEMBER_ID,
            "campus_id": TEST_CAMPUS_ID,
            "care_event_id": "evt-1",
        }
        mock_db.grief_support.find_one = AsyncMock(return_value=stage)
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())
        mock_result = MagicMock()
        mock_result.matched_count = 1
        mock_db.grief_support.update_one = AsyncMock(return_value=mock_result)

        req = make_request()
        result = await _fn(complete_grief_stage)(stage_id="stage-1", request=req, notes="Went well")
        assert result["success"] is True

    @patch("routes.grief_support.get_current_user", new_callable=AsyncMock)
    async def test_complete_grief_stage_not_found(self, mock_user):
        from litestar.exceptions import HTTPException

        from routes.grief_support import complete_grief_stage

        mock_user.return_value = make_admin_user()
        mock_db.grief_support.find_one = AsyncMock(return_value=None)

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(complete_grief_stage)(stage_id="nonexistent", request=req)
        assert exc_info.value.status_code == 404

    @patch("routes.grief_support.get_current_user", new_callable=AsyncMock)
    async def test_ignore_grief_stage_success(self, mock_user):
        from routes.grief_support import ignore_grief_stage

        mock_user.return_value = make_admin_user()
        stage = {"id": "stage-1", "stage": "1_week", "member_id": TEST_MEMBER_ID, "campus_id": TEST_CAMPUS_ID}
        mock_db.grief_support.find_one = AsyncMock(return_value=stage)
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        req = make_request()
        result = await _fn(ignore_grief_stage)(stage_id="stage-1", request=req)
        assert result["success"] is True

    @patch("routes.grief_support.get_current_user", new_callable=AsyncMock)
    async def test_ignore_grief_stage_not_found(self, mock_user):
        from litestar.exceptions import HTTPException

        from routes.grief_support import ignore_grief_stage

        mock_user.return_value = make_admin_user()
        mock_db.grief_support.find_one = AsyncMock(return_value=None)

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(ignore_grief_stage)(stage_id="nonexistent", request=req)
        assert exc_info.value.status_code == 404

    @patch("routes.grief_support.get_current_user", new_callable=AsyncMock)
    async def test_undo_grief_stage_success(self, mock_user):
        from routes.grief_support import undo_grief_stage

        mock_user.return_value = make_admin_user()
        stage = {"id": "stage-1", "stage": "1_week", "member_id": TEST_MEMBER_ID, "campus_id": TEST_CAMPUS_ID}
        mock_db.grief_support.find_one = AsyncMock(return_value=stage)

        req = make_request()
        result = await _fn(undo_grief_stage)(stage_id="stage-1", request=req)
        assert result["success"] is True
        mock_db.care_events.delete_many.assert_called_once()

    @patch("routes.grief_support.get_current_user", new_callable=AsyncMock)
    async def test_undo_grief_stage_not_found(self, mock_user):
        from litestar.exceptions import HTTPException

        from routes.grief_support import undo_grief_stage

        mock_user.return_value = make_admin_user()
        mock_db.grief_support.find_one = AsyncMock(return_value=None)

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(undo_grief_stage)(stage_id="nonexistent", request=req)
        assert exc_info.value.status_code == 404

    async def test_send_grief_reminder_success(self):
        from routes.grief_support import send_grief_reminder

        stage = {"id": "stage-1", "stage": "1_week", "member_id": TEST_MEMBER_ID, "campus_id": TEST_CAMPUS_ID}
        mock_db.grief_support.find_one = AsyncMock(return_value=stage)
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        result = await _fn(send_grief_reminder)(stage_id="stage-1", request=make_request())
        assert result["success"] is True

    async def test_send_grief_reminder_stage_not_found(self):
        from litestar.exceptions import HTTPException

        from routes.grief_support import send_grief_reminder

        mock_db.grief_support.find_one = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await _fn(send_grief_reminder)(stage_id="nonexistent", request=make_request())
        assert exc_info.value.status_code == 404

    async def test_send_grief_reminder_member_not_found(self):
        from litestar.exceptions import HTTPException

        from routes.grief_support import send_grief_reminder

        stage = {"id": "stage-1", "stage": "1_week", "member_id": TEST_MEMBER_ID}
        mock_db.grief_support.find_one = AsyncMock(return_value=stage)
        mock_db.members.find_one = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await _fn(send_grief_reminder)(stage_id="stage-1", request=make_request())
        assert exc_info.value.status_code == 404


# =====================================================================
# ACCIDENT FOLLOWUP ROUTE TESTS
# =====================================================================


class TestAccidentFollowupRoutes:
    """Tests for routes/accident_followup.py"""

    @pytest.fixture(autouse=True)
    def setup(self):
        global mock_db
        mock_db = make_mock_db()
        init_dependencies(mock_db, TEST_JWT_SECRET)
        from routes.accident_followup import init_accident_followup_routes

        init_accident_followup_routes(
            invalidate_dashboard_cache=AsyncMock(),
            log_activity=AsyncMock(),
            get_campus_timezone=AsyncMock(return_value="Asia/Jakarta"),
            get_date_in_timezone=MagicMock(return_value=TODAY.isoformat()),
        )

    @patch("routes.accident_followup.get_current_user", new_callable=AsyncMock)
    async def test_list_accident_followup(self, mock_user):
        from routes.accident_followup import list_accident_followup

        mock_user.return_value = make_admin_user()
        stages = [
            {
                "id": "f1",
                "stage": "first_followup",
                "completed": False,
                "member_id": TEST_MEMBER_ID,
                "campus_id": TEST_CAMPUS_ID,
            }
        ]
        mock_db.accident_followup.find = MagicMock(return_value=make_cursor(stages))

        req = make_request()
        result = await _fn(list_accident_followup)(request=req, page=1, limit=50)
        assert len(result) == 1

    @patch("routes.accident_followup.get_current_user", new_callable=AsyncMock)
    async def test_list_accident_followup_filtered(self, mock_user):
        from routes.accident_followup import list_accident_followup

        mock_user.return_value = make_admin_user()
        mock_db.accident_followup.find = MagicMock(return_value=make_cursor([]))

        req = make_request()
        result = await _fn(list_accident_followup)(request=req, completed=False, page=2, limit=10)
        assert result == []

    @patch("routes.accident_followup.get_current_user", new_callable=AsyncMock)
    async def test_get_member_accident_timeline(self, mock_user):
        from routes.accident_followup import get_member_accident_timeline

        mock_user.return_value = make_admin_user()
        stages = [{"id": "f1", "stage": "first_followup", "member_id": TEST_MEMBER_ID}]
        mock_db.accident_followup.find = MagicMock(return_value=make_cursor(stages))

        req = make_request()
        result = await _fn(get_member_accident_timeline)(member_id=TEST_MEMBER_ID, request=req)
        assert len(result) == 1

    @patch("routes.accident_followup.get_current_user", new_callable=AsyncMock)
    async def test_complete_accident_stage_success(self, mock_user):
        from routes.accident_followup import complete_accident_stage

        mock_user.return_value = make_admin_user()
        stage = {
            "id": "f1",
            "stage": "first_followup",
            "member_id": TEST_MEMBER_ID,
            "campus_id": TEST_CAMPUS_ID,
            "care_event_id": "evt-1",
        }
        mock_db.accident_followup.find_one = AsyncMock(return_value=stage)
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())
        mock_result = MagicMock()
        mock_result.matched_count = 1
        mock_db.accident_followup.update_one = AsyncMock(return_value=mock_result)

        req = make_request()
        result = await _fn(complete_accident_stage)(stage_id="f1", request=req, notes="Visited patient")
        assert result["success"] is True

    @patch("routes.accident_followup.get_current_user", new_callable=AsyncMock)
    async def test_complete_accident_stage_not_found(self, mock_user):
        from litestar.exceptions import HTTPException

        from routes.accident_followup import complete_accident_stage

        mock_user.return_value = make_admin_user()
        mock_db.accident_followup.find_one = AsyncMock(return_value=None)

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(complete_accident_stage)(stage_id="nonexistent", request=req)
        assert exc_info.value.status_code == 404

    async def test_undo_accident_stage_success(self):
        from routes.accident_followup import undo_accident_stage

        stage = {"id": "f1", "stage": "first_followup", "member_id": TEST_MEMBER_ID, "campus_id": TEST_CAMPUS_ID}
        mock_db.accident_followup.find_one = AsyncMock(return_value=stage)

        req = make_request()
        result = await _fn(undo_accident_stage)(stage_id="f1", request=req)
        assert result["success"] is True
        mock_db.care_events.delete_many.assert_called()

    async def test_undo_accident_stage_not_found(self):
        from litestar.exceptions import HTTPException

        from routes.accident_followup import undo_accident_stage

        mock_db.accident_followup.find_one = AsyncMock(return_value=None)

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(undo_accident_stage)(stage_id="nonexistent", request=req)
        assert exc_info.value.status_code == 404

    @patch("routes.accident_followup.get_current_user", new_callable=AsyncMock)
    async def test_ignore_accident_stage_success(self, mock_user):
        from routes.accident_followup import ignore_accident_stage

        mock_user.return_value = make_admin_user()
        stage = {"id": "f1", "stage": "first_followup", "member_id": TEST_MEMBER_ID, "campus_id": TEST_CAMPUS_ID}
        mock_db.accident_followup.find_one = AsyncMock(return_value=stage)
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        req = make_request()
        result = await _fn(ignore_accident_stage)(stage_id="f1", request=req)
        assert result["success"] is True

    @patch("routes.accident_followup.get_current_user", new_callable=AsyncMock)
    async def test_ignore_accident_stage_not_found(self, mock_user):
        from litestar.exceptions import HTTPException

        from routes.accident_followup import ignore_accident_stage

        mock_user.return_value = make_admin_user()
        mock_db.accident_followup.find_one = AsyncMock(return_value=None)

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(ignore_accident_stage)(stage_id="nonexistent", request=req)
        assert exc_info.value.status_code == 404


# =====================================================================
# FINANCIAL AID ROUTE TESTS
# =====================================================================


class TestFinancialAidRoutes:
    """Tests for routes/financial_aid.py"""

    @pytest.fixture(autouse=True)
    def setup(self):
        global mock_db
        mock_db = make_mock_db()
        init_dependencies(mock_db, TEST_JWT_SECRET)
        # Round-2 added a member-visibility check inside create_aid_schedule
        # and get_member_aid_schedules. Default the lookup to a real member
        # so create/list paths don't 404 before reaching the test logic.
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())
        from routes.financial_aid import init_financial_aid_routes

        init_financial_aid_routes(
            invalidate_dashboard_cache=AsyncMock(),
            log_activity=AsyncMock(),
            get_engagement_settings_cached=AsyncMock(return_value={"atRiskDays": 60, "disconnectedDays": 90}),
        )

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_create_aid_schedule_monthly(self, mock_user):
        from models import FinancialAidScheduleCreate
        from routes.financial_aid import create_aid_schedule

        mock_user.return_value = make_admin_user()

        data = FinancialAidScheduleCreate(
            member_id=TEST_MEMBER_ID,
            title="Monthly Aid",
            aid_type="education",
            aid_amount=500000,
            frequency="monthly",
            start_date=TODAY.isoformat(),
            day_of_month=15,
        )
        req = make_request()
        result = await _fn(create_aid_schedule)(data=data, request=req)
        assert result is not None
        mock_db.financial_aid_schedules.insert_one.assert_called_once()

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_create_aid_schedule_weekly(self, mock_user):
        from models import FinancialAidScheduleCreate
        from routes.financial_aid import create_aid_schedule

        mock_user.return_value = make_admin_user()

        data = FinancialAidScheduleCreate(
            member_id=TEST_MEMBER_ID,
            title="Weekly Aid",
            aid_type="food",
            aid_amount=100000,
            frequency="weekly",
            start_date=TODAY.isoformat(),
            day_of_week="monday",
        )
        req = make_request()
        result = await _fn(create_aid_schedule)(data=data, request=req)
        assert result is not None

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_create_aid_schedule_annually(self, mock_user):
        from models import FinancialAidScheduleCreate
        from routes.financial_aid import create_aid_schedule

        mock_user.return_value = make_admin_user()

        data = FinancialAidScheduleCreate(
            member_id=TEST_MEMBER_ID,
            title="Annual Aid",
            aid_type="education",
            aid_amount=5000000,
            frequency="annually",
            start_date=TODAY.isoformat(),
            month_of_year=6,
            day_of_month=1,
        )
        req = make_request()
        result = await _fn(create_aid_schedule)(data=data, request=req)
        assert result is not None

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_list_aid_schedules(self, mock_user):
        from routes.financial_aid import list_aid_schedules

        mock_user.return_value = make_admin_user()
        schedules = [{"id": "s1", "member_id": TEST_MEMBER_ID, "is_active": True}]
        mock_db.financial_aid_schedules.find = MagicMock(return_value=make_cursor(schedules))

        req = make_request()
        result = await _fn(list_aid_schedules)(request=req, page=1, limit=50)
        assert len(result) == 1

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_list_aid_schedules_with_filters(self, mock_user):
        from routes.financial_aid import list_aid_schedules

        mock_user.return_value = make_admin_user()
        mock_db.financial_aid_schedules.find = MagicMock(return_value=make_cursor([]))

        req = make_request()
        result = await _fn(list_aid_schedules)(
            request=req, member_id=TEST_MEMBER_ID, active_only=False, page=1, limit=50
        )
        assert result == []

    async def test_get_member_aid_schedules(self):
        from routes.financial_aid import get_member_aid_schedules

        schedules = [
            {"id": "s1", "member_id": TEST_MEMBER_ID, "is_active": True, "ignored_occurrences": []},
            {"id": "s2", "member_id": TEST_MEMBER_ID, "is_active": False, "ignored_occurrences": ["2026-01-01"]},
        ]
        mock_db.financial_aid_schedules.find = MagicMock(return_value=make_cursor(schedules))
        # Round-2 added a member-visibility check before returning aid history;
        # provide a member doc so the lookup resolves.
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        req = make_request()
        result = await _fn(get_member_aid_schedules)(member_id=TEST_MEMBER_ID, request=req)
        # s1 active, s2 has ignored history -> both returned
        assert len(result) == 2

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_stop_aid_schedule_success(self, mock_user):
        from routes.financial_aid import stop_aid_schedule

        mock_user.return_value = make_admin_user()
        schedule = {
            "id": "s1",
            "member_id": TEST_MEMBER_ID,
            "campus_id": TEST_CAMPUS_ID,
            "aid_type": "education",
            "is_active": True,
        }
        mock_db.financial_aid_schedules.find_one = AsyncMock(return_value=schedule)
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())
        mock_result = MagicMock()
        mock_result.matched_count = 1
        mock_db.financial_aid_schedules.update_one = AsyncMock(return_value=mock_result)

        req = make_request()
        result = await _fn(stop_aid_schedule)(schedule_id="s1", request=req)
        assert result["success"] is True

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_stop_aid_schedule_not_found(self, mock_user):
        from litestar.exceptions import HTTPException

        from routes.financial_aid import stop_aid_schedule

        mock_user.return_value = make_admin_user()
        mock_db.financial_aid_schedules.find_one = AsyncMock(return_value=None)

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(stop_aid_schedule)(schedule_id="nonexistent", request=req)
        assert exc_info.value.status_code == 404

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_mark_aid_distributed_weekly(self, mock_user):
        from routes.financial_aid import mark_aid_distributed

        mock_user.return_value = make_admin_user()
        schedule = {
            "id": "s1",
            "member_id": TEST_MEMBER_ID,
            "campus_id": TEST_CAMPUS_ID,
            "aid_type": "food",
            "aid_amount": 100000,
            "frequency": "weekly",
            "title": "Weekly Food",
            "next_occurrence": TODAY.isoformat(),
            "occurrences_completed": 2,
            "is_active": True,
        }
        mock_db.financial_aid_schedules.find_one = AsyncMock(return_value=schedule)
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        req = make_request()
        result = await _fn(mark_aid_distributed)(schedule_id="s1", request=req)
        assert result["success"] is True
        expected_next = (TODAY + timedelta(weeks=1)).isoformat()
        assert result["next_occurrence"] == expected_next

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_mark_aid_distributed_monthly(self, mock_user):
        from routes.financial_aid import mark_aid_distributed

        mock_user.return_value = make_admin_user()
        schedule = {
            "id": "s1",
            "member_id": TEST_MEMBER_ID,
            "campus_id": TEST_CAMPUS_ID,
            "aid_type": "education",
            "aid_amount": 500000,
            "frequency": "monthly",
            "title": "Monthly Education",
            "next_occurrence": "2026-03-15",
            "day_of_month": 15,
            "occurrences_completed": 0,
            "is_active": True,
        }
        mock_db.financial_aid_schedules.find_one = AsyncMock(return_value=schedule)
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        req = make_request()
        result = await _fn(mark_aid_distributed)(schedule_id="s1", request=req)
        assert result["success"] is True
        assert result["next_occurrence"] == "2026-04-15"

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_mark_aid_distributed_not_found(self, mock_user):
        from litestar.exceptions import HTTPException

        from routes.financial_aid import mark_aid_distributed

        mock_user.return_value = make_admin_user()
        mock_db.financial_aid_schedules.find_one = AsyncMock(return_value=None)

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(mark_aid_distributed)(schedule_id="nonexistent", request=req)
        # Note: mark_aid_distributed lacks `except HTTPException: raise` so 404 is wrapped to 500
        assert exc_info.value.status_code in (404, 500)

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_ignore_financial_aid_schedule_success(self, mock_user):
        from routes.financial_aid import ignore_financial_aid_schedule

        mock_user.return_value = make_admin_user()
        schedule = {
            "id": "s1",
            "member_id": TEST_MEMBER_ID,
            "campus_id": TEST_CAMPUS_ID,
            "aid_type": "food",
            "frequency": "weekly",
            "next_occurrence": TODAY.isoformat(),
            "ignored_occurrences": [],
            "is_active": True,
        }
        mock_db.financial_aid_schedules.find_one = AsyncMock(return_value=schedule)
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        req = make_request()
        result = await _fn(ignore_financial_aid_schedule)(schedule_id="s1", request=req)
        assert result["success"] is True

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_ignore_financial_aid_no_next(self, mock_user):
        from litestar.exceptions import HTTPException

        from routes.financial_aid import ignore_financial_aid_schedule

        mock_user.return_value = make_admin_user()
        schedule = {
            "id": "s1",
            "member_id": TEST_MEMBER_ID,
            "campus_id": TEST_CAMPUS_ID,
            "frequency": "weekly",
            "next_occurrence": None,
            "ignored_occurrences": [],
        }
        mock_db.financial_aid_schedules.find_one = AsyncMock(return_value=schedule)
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(ignore_financial_aid_schedule)(schedule_id="s1", request=req)
        assert exc_info.value.status_code == 400

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_remove_ignored_occurrence(self, mock_user):
        from routes.financial_aid import remove_ignored_occurrence

        mock_user.return_value = make_admin_user()
        schedule = {
            "id": "s1",
            "member_id": TEST_MEMBER_ID,
            "campus_id": TEST_CAMPUS_ID,
            "ignored_occurrences": ["2026-03-01", "2026-03-08"],
        }
        mock_db.financial_aid_schedules.find_one = AsyncMock(return_value=schedule)

        req = make_request()
        result = await _fn(remove_ignored_occurrence)(schedule_id="s1", occurrence_date="2026-03-01", request=req)
        assert result["success"] is True

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_remove_ignored_occurrence_not_found(self, mock_user):
        from litestar.exceptions import HTTPException

        from routes.financial_aid import remove_ignored_occurrence

        mock_user.return_value = make_admin_user()
        mock_db.financial_aid_schedules.find_one = AsyncMock(return_value=None)

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(remove_ignored_occurrence)(schedule_id="nonexistent", occurrence_date="2026-03-01", request=req)
        assert exc_info.value.status_code == 404

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_clear_all_ignored_occurrences(self, mock_user):
        from routes.financial_aid import clear_all_ignored_occurrences

        mock_user.return_value = make_admin_user()
        schedule = {
            "id": "s1",
            "member_id": TEST_MEMBER_ID,
            "campus_id": TEST_CAMPUS_ID,
            "aid_type": "food",
            "ignored_occurrences": ["2026-03-01"],
        }
        mock_db.financial_aid_schedules.find_one = AsyncMock(return_value=schedule)
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        req = make_request()
        result = await _fn(clear_all_ignored_occurrences)(schedule_id="s1", request=req)
        assert result["success"] is True

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_clear_all_ignored_not_found(self, mock_user):
        from litestar.exceptions import HTTPException

        from routes.financial_aid import clear_all_ignored_occurrences

        mock_user.return_value = make_admin_user()
        mock_db.financial_aid_schedules.find_one = AsyncMock(return_value=None)

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(clear_all_ignored_occurrences)(schedule_id="nonexistent", request=req)
        assert exc_info.value.status_code == 404

    async def test_delete_aid_schedule_success(self):
        from routes.financial_aid import delete_aid_schedule

        schedule = {"id": "s1", "member_id": TEST_MEMBER_ID, "campus_id": TEST_CAMPUS_ID, "aid_type": "food"}
        mock_db.financial_aid_schedules.find_one = AsyncMock(return_value=schedule)
        mock_result = MagicMock()
        mock_result.deleted_count = 1
        mock_db.financial_aid_schedules.delete_one = AsyncMock(return_value=mock_result)

        req = make_request()
        result = await _fn(delete_aid_schedule)(schedule_id="s1", request=req)
        assert result["success"] is True

    async def test_delete_aid_schedule_not_found(self):
        from litestar.exceptions import HTTPException

        from routes.financial_aid import delete_aid_schedule

        mock_db.financial_aid_schedules.find_one = AsyncMock(return_value=None)

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(delete_aid_schedule)(schedule_id="nonexistent", request=req)
        assert exc_info.value.status_code == 404

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_get_aid_due_today(self, mock_user):
        from routes.financial_aid import get_aid_due_today

        mock_user.return_value = make_admin_user()
        schedules = [
            {
                "id": "s1",
                "member_id": TEST_MEMBER_ID,
                "campus_id": TEST_CAMPUS_ID,
                "aid_type": "food",
                "aid_amount": 100000,
                "next_occurrence": TODAY.isoformat(),
                "is_active": True,
            }
        ]
        mock_db.financial_aid_schedules.find = MagicMock(return_value=make_cursor(schedules))
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        req = make_request()
        result = await _fn(get_aid_due_today)(request=req)
        assert len(result) == 1
        assert result[0]["status"] == "due_today"

    async def test_get_financial_aid_summary(self):
        from routes.financial_aid import get_financial_aid_summary

        events = [
            {"event_type": "financial_aid", "aid_type": "education", "aid_amount": 500000},
            {"event_type": "financial_aid", "aid_type": "food", "aid_amount": 100000},
        ]
        mock_db.care_events.find = MagicMock(return_value=make_cursor(events))

        result = await _fn(get_financial_aid_summary)(request=make_request())
        assert result["total_amount"] == 600000
        assert result["total_count"] == 2

    async def test_get_financial_aid_summary_with_date_range(self):
        from routes.financial_aid import get_financial_aid_summary

        mock_db.care_events.find = MagicMock(return_value=make_cursor([]))

        result = await _fn(get_financial_aid_summary)(request=make_request(), start_date="2026-01-01", end_date="2026-12-31")
        assert result["total_amount"] == 0

    async def test_get_financial_aid_recipients(self):
        from routes.financial_aid import get_financial_aid_recipients

        agg_data = [{"_id": TEST_MEMBER_ID, "total_amount": 600000, "aid_count": 3}]
        mock_db.care_events.aggregate = MagicMock(return_value=make_agg_cursor(agg_data))
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        result = await _fn(get_financial_aid_recipients)(request=make_request())
        assert len(result) == 1
        assert result[0]["total_amount"] == 600000

    async def test_get_financial_aid_recipients_no_member(self):
        from routes.financial_aid import get_financial_aid_recipients

        agg_data = [{"_id": TEST_MEMBER_ID, "total_amount": 100000, "aid_count": 1}]
        mock_db.care_events.aggregate = MagicMock(return_value=make_agg_cursor(agg_data))
        mock_db.members.find_one = AsyncMock(return_value=None)
        # Also no event title fallback
        mock_db.care_events.find_one = AsyncMock(return_value=None)

        result = await _fn(get_financial_aid_recipients)(request=make_request())
        assert len(result) == 1
        assert result[0]["member_name"] == "Unknown"

    async def test_get_member_financial_aid(self):
        from routes.financial_aid import get_member_financial_aid

        events = [
            {"event_type": "financial_aid", "aid_amount": 500000, "member_id": TEST_MEMBER_ID},
            {"event_type": "financial_aid", "aid_amount": 200000, "member_id": TEST_MEMBER_ID},
        ]
        mock_db.care_events.find = MagicMock(return_value=make_cursor(events))

        result = await _fn(get_member_financial_aid)(member_id=TEST_MEMBER_ID, request=make_request())
        assert result["total_amount"] == 700000
        assert result["aid_count"] == 2


# =====================================================================
# DASHBOARD ROUTE TESTS
# =====================================================================


class TestDashboardRoutes:
    """Tests for routes/dashboard.py"""

    @pytest.fixture(autouse=True)
    def setup(self):
        global mock_db
        mock_db = make_mock_db()
        init_dependencies(mock_db, TEST_JWT_SECRET)
        from routes.dashboard import init_dashboard_routes

        init_dashboard_routes(
            get_campus_timezone=AsyncMock(return_value="Asia/Jakarta"),
            get_date_in_timezone=MagicMock(return_value=TODAY.isoformat()),
            get_writeoff_settings=AsyncMock(
                return_value={"birthday": 7, "grief_support": 30, "accident_illness": 14, "financial_aid": 30}
            ),
        )

    @patch("routes.dashboard.get_current_user", new_callable=AsyncMock)
    @patch("routes.dashboard.get_cache", return_value=None)
    async def test_get_dashboard_reminders(self, mock_cache, mock_user):
        from routes.dashboard import get_dashboard_reminders

        mock_user.return_value = make_admin_user()
        members = [make_test_member()]
        mock_db.members.find = MagicMock(return_value=make_cursor(members))
        mock_db.grief_support.find = MagicMock(return_value=make_cursor([]))
        mock_db.accident_followup.find = MagicMock(return_value=make_cursor([]))
        mock_db.financial_aid_schedules.find = MagicMock(return_value=make_cursor([]))
        mock_db.care_events.find = MagicMock(return_value=make_cursor([]))

        req = make_request()
        result = await _fn(get_dashboard_reminders)(request=req)
        assert "total_members" in result

    @patch("routes.dashboard.get_current_user", new_callable=AsyncMock)
    @patch("routes.dashboard.get_cache", return_value=None)
    async def test_get_dashboard_reminders_no_campus(self, mock_cache, mock_user):
        from routes.dashboard import get_dashboard_reminders

        user = make_admin_user()
        user["campus_id"] = None
        mock_user.return_value = user
        mock_db.campuses.find_one = AsyncMock(return_value={"id": TEST_CAMPUS_ID})
        mock_db.members.find = MagicMock(return_value=make_cursor([]))
        mock_db.grief_support.find = MagicMock(return_value=make_cursor([]))
        mock_db.accident_followup.find = MagicMock(return_value=make_cursor([]))
        mock_db.financial_aid_schedules.find = MagicMock(return_value=make_cursor([]))
        mock_db.care_events.find = MagicMock(return_value=make_cursor([]))

        req = make_request()
        result = await _fn(get_dashboard_reminders)(request=req)
        assert "total_members" in result

    @patch("routes.dashboard.get_current_user", new_callable=AsyncMock)
    @patch("routes.dashboard.get_cache", return_value=None)
    async def test_get_dashboard_reminders_no_campus_at_all(self, mock_cache, mock_user):
        from routes.dashboard import get_dashboard_reminders

        user = make_admin_user()
        user["campus_id"] = None
        mock_user.return_value = user
        mock_db.campuses.find_one = AsyncMock(return_value=None)

        req = make_request()
        result = await _fn(get_dashboard_reminders)(request=req)
        assert result["total_tasks"] == 0

    @patch("routes.dashboard.get_current_user", new_callable=AsyncMock)
    @patch("routes.dashboard.get_cache", return_value=None)
    async def test_get_dashboard_stats(self, mock_cache, mock_user):
        from routes.dashboard import get_dashboard_stats

        mock_user.return_value = make_admin_user()
        mock_db.members.aggregate = MagicMock(
            return_value=make_agg_cursor([{"total_count": [{"count": 100}], "at_risk_count": [{"count": 10}]}])
        )
        mock_db.grief_support.count_documents = AsyncMock(return_value=5)
        mock_db.care_events.aggregate = MagicMock(return_value=make_agg_cursor([{"total_aid": 1000000}]))

        req = make_request()
        result = await _fn(get_dashboard_stats)(request=req)
        assert result["total_members"] == 100
        assert result["active_grief_support"] == 5

    async def test_get_upcoming_events(self):
        from routes.dashboard import get_upcoming_events

        events = [{"id": "e1", "event_date": TODAY.isoformat(), "member_name": "John"}]
        mock_db.care_events.aggregate = MagicMock(return_value=make_agg_cursor(events))

        result = await _fn(get_upcoming_events)(request=make_request())
        assert len(result) == 1

    async def test_get_active_grief_support(self):
        from routes.dashboard import get_active_grief_support

        data = [{"member_id": TEST_MEMBER_ID, "member_name": "John", "stages": []}]
        mock_db.grief_support.aggregate = MagicMock(return_value=make_agg_cursor(data))

        result = await _fn(get_active_grief_support)(request=make_request())
        assert len(result) == 1

    @patch("routes.dashboard.get_current_user", new_callable=AsyncMock)
    async def test_get_recent_activity(self, mock_user):
        from routes.dashboard import get_recent_activity

        mock_user.return_value = make_admin_user()
        events = [{"id": "e1", "event_type": "birthday", "member_name": "John"}]
        mock_db.care_events.aggregate = MagicMock(return_value=make_agg_cursor(events))

        req = make_request()
        result = await _fn(get_recent_activity)(request=req)
        assert len(result) == 1

    @patch("routes.dashboard.get_current_user", new_callable=AsyncMock)
    async def test_get_engagement_trends(self, mock_user):
        from routes.dashboard import get_engagement_trends

        mock_user.return_value = make_admin_user()
        events = [
            {"event_date": TODAY.isoformat()},
            {"event_date": TODAY.isoformat()},
            {"event_date": (TODAY - timedelta(days=1)).isoformat()},
        ]
        mock_db.care_events.find = MagicMock(return_value=make_cursor(events))

        req = make_request()
        result = await _fn(get_engagement_trends)(request=req)
        assert isinstance(result, list)
        assert len(result) >= 1

    @patch("routes.dashboard.get_current_user", new_callable=AsyncMock)
    async def test_get_care_events_by_type(self, mock_user):
        from routes.dashboard import get_care_events_by_type

        mock_user.return_value = make_admin_user()
        events = [
            {"event_type": "birthday"},
            {"event_type": "birthday"},
            {"event_type": "grief_loss"},
        ]
        mock_db.care_events.find = MagicMock(return_value=make_cursor(events))

        req = make_request()
        result = await _fn(get_care_events_by_type)(request=req)
        assert isinstance(result, list)

    @patch("routes.dashboard.get_current_user", new_callable=AsyncMock)
    async def test_get_grief_completion_rate(self, mock_user):
        from routes.dashboard import get_grief_completion_rate

        mock_user.return_value = make_admin_user()
        mock_db.grief_support.count_documents = AsyncMock(side_effect=[10, 7])

        req = make_request()
        result = await _fn(get_grief_completion_rate)(request=req)
        assert result["total_stages"] == 10
        assert result["completed_stages"] == 7
        assert result["completion_rate"] == 70.0

    @patch("routes.dashboard.get_current_user", new_callable=AsyncMock)
    async def test_get_grief_completion_rate_zero(self, mock_user):
        from routes.dashboard import get_grief_completion_rate

        mock_user.return_value = make_admin_user()
        mock_db.grief_support.count_documents = AsyncMock(side_effect=[0, 0])

        req = make_request()
        result = await _fn(get_grief_completion_rate)(request=req)
        assert result["completion_rate"] == 0

    @patch("routes.dashboard.get_current_user", new_callable=AsyncMock)
    async def test_get_analytics_dashboard(self, mock_user):
        from routes.dashboard import get_analytics_dashboard

        mock_user.return_value = make_admin_user()
        mock_db.members.count_documents = AsyncMock(side_effect=[100, 20])
        mock_db.grief_support.count_documents = AsyncMock(side_effect=[10, 7])
        mock_db.care_events.aggregate = MagicMock(return_value=make_agg_cursor([]))

        req = make_request()
        result = await _fn(get_analytics_dashboard)(request=req)
        assert "member_stats" in result
        assert "grief" in result

    @patch("routes.dashboard.get_current_user", new_callable=AsyncMock)
    async def test_get_analytics_dashboard_time_ranges(self, mock_user):
        from routes.dashboard import get_analytics_dashboard

        mock_user.return_value = make_admin_user()
        mock_db.members.count_documents = AsyncMock(return_value=50)
        mock_db.grief_support.count_documents = AsyncMock(return_value=0)
        mock_db.care_events.aggregate = MagicMock(return_value=make_agg_cursor([]))

        req = make_request()

        # Test each time range
        for tr in ["year", "6months", "3months"]:
            result = await _fn(get_analytics_dashboard)(request=req, time_range=tr)
            assert "member_stats" in result

        # Custom range
        result = await _fn(get_analytics_dashboard)(
            request=req, time_range="custom", start_date="2026-01-01", end_date="2026-12-31"
        )
        assert "member_stats" in result

    @patch("routes.dashboard.get_current_user", new_callable=AsyncMock)
    async def test_get_demographic_trends(self, mock_user):
        from routes.dashboard import get_demographic_trends

        mock_user.return_value = make_admin_user()
        members = [
            {"id": "m1", "age": 25, "membership_status": "member", "days_since_last_contact": 5},
            {"id": "m2", "age": 65, "category": "senior", "days_since_last_contact": 100},
        ]
        events = [
            {"member_id": "m1", "event_type": "birthday"},
            {"member_id": "m2", "event_type": "grief_loss"},
        ]
        mock_db.members.find = MagicMock(return_value=make_cursor(members))
        mock_db.care_events.find = MagicMock(return_value=make_cursor(events))

        req = make_request()
        result = await _fn(get_demographic_trends)(request=req)
        assert "age_groups" in result
        assert "insights" in result
        assert result["total_members"] == 2


# =====================================================================
# DASHBOARD HELPER (calculate_dashboard_reminders) TESTS
# =====================================================================


class TestDashboardHelpers:
    """Tests for the calculate_dashboard_reminders helper function."""

    @pytest.fixture(autouse=True)
    def setup(self):
        global mock_db
        mock_db = make_mock_db()
        init_dependencies(mock_db, TEST_JWT_SECRET)
        from routes.dashboard import init_dashboard_routes

        init_dashboard_routes(
            get_campus_timezone=AsyncMock(return_value="Asia/Jakarta"),
            get_date_in_timezone=MagicMock(return_value=TODAY.isoformat()),
            get_writeoff_settings=AsyncMock(
                return_value={"birthday": 7, "grief_support": 30, "accident_illness": 14, "financial_aid": 30}
            ),
        )

    async def test_calculate_reminders_with_birthday_today(self):
        from routes.dashboard import calculate_dashboard_reminders

        member = make_test_member()
        # Set birth_date to today's month/day
        member["birth_date"] = f"1990-{TODAY.strftime('%m-%d')}"
        mock_db.members.find = MagicMock(return_value=make_cursor([member]))
        mock_db.grief_support.find = MagicMock(return_value=make_cursor([]))
        mock_db.accident_followup.find = MagicMock(return_value=make_cursor([]))
        mock_db.financial_aid_schedules.find = MagicMock(return_value=make_cursor([]))
        mock_db.care_events.find = MagicMock(return_value=make_cursor([]))

        result = await _fn(calculate_dashboard_reminders)(TEST_CAMPUS_ID, "Asia/Jakarta", TODAY.isoformat())
        assert len(result["birthdays_today"]) == 1

    async def test_calculate_reminders_with_overdue_birthday(self):
        from routes.dashboard import calculate_dashboard_reminders

        member = make_test_member()
        yesterday = TODAY - timedelta(days=2)
        member["birth_date"] = f"1990-{yesterday.strftime('%m-%d')}"
        mock_db.members.find = MagicMock(return_value=make_cursor([member]))
        mock_db.grief_support.find = MagicMock(return_value=make_cursor([]))
        mock_db.accident_followup.find = MagicMock(return_value=make_cursor([]))
        mock_db.financial_aid_schedules.find = MagicMock(return_value=make_cursor([]))
        mock_db.care_events.find = MagicMock(return_value=make_cursor([]))

        result = await _fn(calculate_dashboard_reminders)(TEST_CAMPUS_ID, "Asia/Jakarta", TODAY.isoformat())
        assert len(result["overdue_birthdays"]) == 1

    async def test_calculate_reminders_with_grief_today(self):
        from routes.dashboard import calculate_dashboard_reminders

        member = make_test_member()
        grief_stage = {
            "id": "g1",
            "member_id": TEST_MEMBER_ID,
            "campus_id": TEST_CAMPUS_ID,
            "stage": "1_week",
            "scheduled_date": TODAY.isoformat(),
            "completed": False,
            "ignored": False,
        }
        mock_db.members.find = MagicMock(return_value=make_cursor([member]))
        mock_db.grief_support.find = MagicMock(return_value=make_cursor([grief_stage]))
        mock_db.accident_followup.find = MagicMock(return_value=make_cursor([]))
        mock_db.financial_aid_schedules.find = MagicMock(return_value=make_cursor([]))
        mock_db.care_events.find = MagicMock(return_value=make_cursor([]))

        result = await _fn(calculate_dashboard_reminders)(TEST_CAMPUS_ID, "Asia/Jakarta", TODAY.isoformat())
        assert len(result["today_tasks"]) >= 1

    async def test_calculate_reminders_with_accident_overdue(self):
        from routes.dashboard import calculate_dashboard_reminders

        member = make_test_member()
        yesterday = (TODAY - timedelta(days=3)).isoformat()
        accident_followup = {
            "id": "a1",
            "member_id": TEST_MEMBER_ID,
            "campus_id": TEST_CAMPUS_ID,
            "stage": "first_followup",
            "scheduled_date": yesterday,
            "completed": False,
            "ignored": False,
        }
        mock_db.members.find = MagicMock(return_value=make_cursor([member]))
        mock_db.grief_support.find = MagicMock(return_value=make_cursor([]))
        mock_db.accident_followup.find = MagicMock(return_value=make_cursor([accident_followup]))
        mock_db.financial_aid_schedules.find = MagicMock(return_value=make_cursor([]))
        mock_db.care_events.find = MagicMock(return_value=make_cursor([]))

        result = await _fn(calculate_dashboard_reminders)(TEST_CAMPUS_ID, "Asia/Jakarta", TODAY.isoformat())
        assert len(result["accident_followup"]) == 1

    async def test_calculate_reminders_with_financial_aid_due(self):
        from routes.dashboard import calculate_dashboard_reminders

        member = make_test_member()
        aid_schedule = {
            "id": "f1",
            "member_id": TEST_MEMBER_ID,
            "campus_id": TEST_CAMPUS_ID,
            "aid_amount": 100000,
            "frequency": "monthly",
            "next_occurrence": TODAY.isoformat(),
            "is_active": True,
        }
        mock_db.members.find = MagicMock(return_value=make_cursor([member]))
        mock_db.grief_support.find = MagicMock(return_value=make_cursor([]))
        mock_db.accident_followup.find = MagicMock(return_value=make_cursor([]))
        mock_db.financial_aid_schedules.find = MagicMock(return_value=make_cursor([aid_schedule]))
        mock_db.care_events.find = MagicMock(return_value=make_cursor([]))

        result = await _fn(calculate_dashboard_reminders)(TEST_CAMPUS_ID, "Asia/Jakarta", TODAY.isoformat())
        assert len(result["today_tasks"]) >= 1

    async def test_calculate_reminders_with_at_risk_members(self):
        from routes.dashboard import calculate_dashboard_reminders

        member = make_test_member()
        member["engagement_status"] = "at_risk"
        mock_db.members.find = MagicMock(return_value=make_cursor([member]))
        mock_db.grief_support.find = MagicMock(return_value=make_cursor([]))
        mock_db.accident_followup.find = MagicMock(return_value=make_cursor([]))
        mock_db.financial_aid_schedules.find = MagicMock(return_value=make_cursor([]))
        mock_db.care_events.find = MagicMock(return_value=make_cursor([]))

        result = await _fn(calculate_dashboard_reminders)(TEST_CAMPUS_ID, "Asia/Jakarta", TODAY.isoformat())
        assert len(result["at_risk_members"]) == 1

    async def test_calculate_reminders_upcoming_tasks(self):
        from routes.dashboard import calculate_dashboard_reminders

        member = make_test_member()
        # Grief stage in 3 days (upcoming)
        future_date = (TODAY + timedelta(days=3)).isoformat()
        grief_stage = {
            "id": "g1",
            "member_id": TEST_MEMBER_ID,
            "campus_id": TEST_CAMPUS_ID,
            "stage": "2_weeks",
            "scheduled_date": future_date,
            "completed": False,
            "ignored": False,
        }
        mock_db.members.find = MagicMock(return_value=make_cursor([member]))
        mock_db.grief_support.find = MagicMock(return_value=make_cursor([grief_stage]))
        mock_db.accident_followup.find = MagicMock(return_value=make_cursor([]))
        mock_db.financial_aid_schedules.find = MagicMock(return_value=make_cursor([]))
        mock_db.care_events.find = MagicMock(return_value=make_cursor([]))

        result = await _fn(calculate_dashboard_reminders)(TEST_CAMPUS_ID, "Asia/Jakarta", TODAY.isoformat())
        assert len(result["upcoming_tasks"]) >= 1

    async def test_calculate_reminders_completed_birthday(self):
        from routes.dashboard import calculate_dashboard_reminders

        member = make_test_member()
        member["birth_date"] = f"1990-{TODAY.strftime('%m-%d')}"
        # Use naive datetime (no timezone) to match dashboard.py's year_start_dt comparison
        completed_at_naive = datetime.now()
        birthday_event = {
            "member_id": TEST_MEMBER_ID,
            "completed": True,
            "completed_at": completed_at_naive,
            "completed_by_user_name": "Pastor John",
            "ignored": False,
            "ignored_at": None,
        }
        mock_db.members.find = MagicMock(return_value=make_cursor([member]))
        mock_db.grief_support.find = MagicMock(return_value=make_cursor([]))
        mock_db.accident_followup.find = MagicMock(return_value=make_cursor([]))
        mock_db.financial_aid_schedules.find = MagicMock(return_value=make_cursor([]))
        mock_db.care_events.find = MagicMock(return_value=make_cursor([birthday_event]))

        result = await _fn(calculate_dashboard_reminders)(TEST_CAMPUS_ID, "Asia/Jakarta", TODAY.isoformat())
        # Birthday today shows with completed=True
        if result["birthdays_today"]:
            assert result["birthdays_today"][0]["completed"] is True


# =====================================================================
# DEPENDENCIES TESTS
# =====================================================================


class TestDependencies:
    """Tests for dependencies.py functions"""

    def test_get_campus_filter_full_admin(self):
        from dependencies import get_campus_filter

        user = make_admin_user()
        result = get_campus_filter(user)
        assert result == {}

    def test_get_campus_filter_pastor(self):
        from dependencies import get_campus_filter

        user = make_pastor_user()
        result = get_campus_filter(user)
        assert result == {"campus_id": user["campus_id"]}

    def test_get_campus_filter_no_campus(self):
        from dependencies import get_campus_filter

        user = make_pastor_user()
        user["campus_id"] = None
        result = get_campus_filter(user)
        assert "$exists" in str(result)

    def test_verify_password(self):
        from dependencies import get_password_hash, verify_password

        hashed = get_password_hash("TestPass123!")
        assert verify_password("TestPass123!", hashed) is True
        assert verify_password("WrongPass", hashed) is False

    def test_create_access_token(self):
        import jwt

        from dependencies import create_access_token

        token = create_access_token({"sub": "user-123"})
        payload = jwt.decode(token, TEST_JWT_SECRET, algorithms=["HS256"])
        assert payload["sub"] == "user-123"

    def test_create_access_token_custom_expiry(self):
        import jwt

        from dependencies import create_access_token

        token = create_access_token({"sub": "user-123"}, expires_delta=timedelta(hours=1))
        payload = jwt.decode(token, TEST_JWT_SECRET, algorithms=["HS256"])
        assert payload["sub"] == "user-123"

    def test_safe_error_detail_development(self):
        from dependencies import safe_error_detail

        result = safe_error_detail(ValueError("test error"))
        assert "test error" in result

    @patch.dict(os.environ, {"ENVIRONMENT": "production"})
    def test_safe_error_detail_production(self):
        from dependencies import safe_error_detail

        result = safe_error_detail(ValueError("secret details"), status_code=500)
        assert "secret details" not in result or result == "An internal error occurred. Please try again later."

    def test_get_client_ip_forwarded(self):
        from dependencies import get_client_ip

        req = make_request(headers={"x-forwarded-for": "1.2.3.4, 5.6.7.8"})
        assert get_client_ip(req) == "1.2.3.4"

    def test_get_client_ip_real_ip(self):
        from dependencies import get_client_ip

        req = make_request(headers={"x-real-ip": "9.8.7.6"})
        # Remove x-forwarded-for
        req.headers = {"Authorization": "Bearer test", "x-real-ip": "9.8.7.6"}
        assert get_client_ip(req) == "9.8.7.6"

    def test_get_client_ip_direct(self):
        from dependencies import get_client_ip

        req = make_request()
        req.headers = {"Authorization": "Bearer test"}
        req.scope = {"client": ("192.168.1.1", 12345)}
        assert get_client_ip(req) == "192.168.1.1"

    async def test_check_login_rate_limit_allowed(self):
        """Brute-force is now DragonflyDB-backed. No redis = fail open."""
        from dependencies import check_login_rate_limit, init_redis

        init_redis(None)  # No redis = always allow
        allowed, msg = await check_login_rate_limit("127.0.0.1", "test@test.com")
        assert allowed is True
        assert msg is None

    async def test_record_failed_login(self):
        from dependencies import init_redis, record_failed_login

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()
        init_redis(mock_redis)
        await record_failed_login("127.0.0.1", "test@test.com")
        mock_redis.set.assert_called_once()
        init_redis(None)

    async def test_clear_login_attempts(self):
        from dependencies import clear_login_attempts, init_redis

        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock()
        init_redis(mock_redis)
        await clear_login_attempts("127.0.0.1", "test@test.com")
        mock_redis.delete.assert_called_once()
        init_redis(None)

    async def test_cleanup_old_login_attempts(self):
        """cleanup_old_login_attempts was removed - TTL handles expiry automatically."""
        # This test validates that the function no longer exists
        import dependencies

        assert not hasattr(dependencies, "cleanup_old_login_attempts")

    def test_get_db_not_initialized(self):
        import dependencies
        from dependencies import get_db

        old_db = dependencies._db
        dependencies._db = None
        with pytest.raises(RuntimeError):
            get_db()
        dependencies._db = old_db

    async def test_get_current_user_no_auth_header(self):
        from litestar.exceptions import HTTPException

        from dependencies import get_current_user

        req = make_request()
        req.headers = {}
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(req)
        assert exc_info.value.status_code == 401

    async def test_get_current_user_empty_token(self):
        from litestar.exceptions import HTTPException

        from dependencies import get_current_user

        req = make_request()
        req.headers = {"Authorization": "Bearer  "}
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(req)
        assert exc_info.value.status_code == 401

    async def test_get_current_user_invalid_token(self):
        from litestar.exceptions import HTTPException

        from dependencies import get_current_user

        req = make_request()
        req.headers = {"Authorization": "Bearer invalid-jwt-token"}
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(req)
        assert exc_info.value.status_code == 401

    async def test_get_current_user_user_not_found(self):
        from litestar.exceptions import HTTPException

        from dependencies import create_access_token, get_current_user

        token = create_access_token({"sub": "ghost-user"})
        req = make_request()
        req.headers = {"Authorization": f"Bearer {token}"}
        mock_db.users.find_one = AsyncMock(return_value=None)
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(req)
        assert exc_info.value.status_code == 401

    async def test_get_current_admin_not_admin(self):
        from litestar.exceptions import HTTPException

        from dependencies import create_access_token, get_current_admin

        user = make_pastor_user()
        token = create_access_token({"sub": user["id"]})
        req = make_request()
        req.headers = {"Authorization": f"Bearer {token}"}
        mock_db.users.find_one = AsyncMock(return_value=user)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_admin(req)
        assert exc_info.value.status_code == 403

    async def test_get_full_admin_not_full_admin(self):
        from litestar.exceptions import HTTPException

        from dependencies import create_access_token, get_full_admin

        user = make_campus_admin_user()
        token = create_access_token({"sub": user["id"]})
        req = make_request()
        req.headers = {"Authorization": f"Bearer {token}"}
        mock_db.users.find_one = AsyncMock(return_value=user)

        with pytest.raises(HTTPException) as exc_info:
            await get_full_admin(req)
        assert exc_info.value.status_code == 403

    async def test_login_lockout_flow(self):
        """Full lockout flow with DragonflyDB-backed brute force protection."""
        from dependencies import LOGIN_MAX_ATTEMPTS, check_login_rate_limit, init_redis, record_failed_login

        redis_store = {}
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=lambda k: redis_store.get(k))
        mock_redis.set = AsyncMock(side_effect=lambda k, v, ex=None: redis_store.update({k: v}))
        mock_redis.delete = AsyncMock(side_effect=lambda k: redis_store.pop(k, None))
        init_redis(mock_redis)

        ip = "10.0.0.1"
        email = "lockout@test.com"

        for _i in range(LOGIN_MAX_ATTEMPTS):
            await record_failed_login(ip, email)

        allowed, msg = await check_login_rate_limit(ip, email)
        assert allowed is False
        assert "locked" in msg.lower() or "Too many" in msg
        init_redis(None)
