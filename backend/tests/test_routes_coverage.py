"""
Additional coverage tests for the three weakest route files:
  - routes/auth.py (targeting uncovered lines: 52, 92-94, 198-200, 288-290, 306, 310-314,
    337-339, 355, 371, 384-386, 398, 407, 428-430, 436-491, 511-513)
  - routes/members.py (targeting uncovered lines: 94-96, 194-196, 241-243, 256, 273-275,
    292, 298-300, 322-324, 337, 345, 378-380, 386-461)
  - routes/financial_aid.py (targeting uncovered lines: 67, 87-89, 104-120, 148-150,
    176-178, 191, 224-226, 270-272, 297, 305-307, 337, 358-360, 389-390, 393-395,
    428-430, 510-511, 519-534, 574, 597-627, 662-663, 684, 708-710, 750-752, 763-765,
    786-788)

Uses the same pattern as test_integration_routes.py: import route handlers directly,
mock DB with AsyncMock, test specific uncovered branches.
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
from enums import UserRole

# ---------------------------------------------------------------------------
# Constants
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


def _fn(handler):
    """Unwrap a Litestar route handler to get the underlying async function."""
    return handler.fn if hasattr(handler, "fn") else handler


# ---------------------------------------------------------------------------
# Mock helpers (same as test_integration_routes.py)
# ---------------------------------------------------------------------------


def make_mock_db():
    db = MagicMock()
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

        cursor = MagicMock()
        cursor.sort = MagicMock(return_value=cursor)
        cursor.skip = MagicMock(return_value=cursor)
        cursor.limit = MagicMock(return_value=cursor)
        cursor.to_list = AsyncMock(return_value=[])
        collection.find = MagicMock(return_value=cursor)

        agg_cursor = MagicMock()
        agg_cursor.to_list = AsyncMock(return_value=[])
        collection.aggregate = MagicMock(return_value=agg_cursor)

        collection.update_many = AsyncMock()
        collection.insert_many = AsyncMock()

        setattr(db, coll, collection)

    # Smart users.find_one: returns the admin user for an "id"-keyed lookup
    # (the path get_current_user takes), and None for any other filter
    # (e.g., "email" duplicate checks). Tests can still override with
    # mock_db.users.find_one = AsyncMock(...) for specific scenarios.
    _admin = make_admin_user()

    async def _smart_find_one(filt=None, *_, **__):
        if isinstance(filt, dict) and "id" in filt:
            return _admin
        return None

    db.users.find_one = AsyncMock(side_effect=_smart_find_one)
    return db


def make_cursor(data_list):
    cursor = MagicMock()
    cursor.sort = MagicMock(return_value=cursor)
    cursor.skip = MagicMock(return_value=cursor)
    cursor.limit = MagicMock(return_value=cursor)
    cursor.to_list = AsyncMock(return_value=data_list)
    return cursor


def make_agg_cursor(data_list):
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=data_list)
    return cursor


def make_request(headers=None, client_ip="127.0.0.1", user_id=None):
    """Mock Litestar Request with a real JWT signed by TEST_JWT_SECRET so
    route handlers' get_current_user(request) calls succeed without per-test
    monkey-patching. Defaults to TEST_ADMIN_ID."""
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
# Test user/member fixtures
# ---------------------------------------------------------------------------


def make_admin_user(campus_id=None):
    return {
        "id": TEST_ADMIN_ID,
        "email": "admin@test.com",
        "name": "Test Admin",
        "role": UserRole.FULL_ADMIN.value,
        "campus_id": campus_id or TEST_CAMPUS_ID,
        "phone": "+6281234567890",
        "is_active": True,
        "created_at": NOW,
        "hashed_password": "$2b$12$dummy_hash",
    }


def make_pastor_user(campus_id=None):
    return {
        "id": TEST_USER_ID,
        "email": "pastor@test.com",
        "name": "Test Pastor",
        "role": UserRole.PASTOR.value,
        "campus_id": campus_id or TEST_CAMPUS_ID,
        "phone": "+6281234567891",
        "is_active": True,
        "created_at": NOW,
        "hashed_password": "$2b$12$dummy_hash",
    }


def make_campus_admin_user(campus_id=None):
    return {
        "id": str(uuid.uuid4()),
        "email": "campus_admin@test.com",
        "name": "Campus Admin",
        "role": UserRole.CAMPUS_ADMIN.value,
        "campus_id": campus_id or TEST_CAMPUS_ID,
        "phone": "+6281234567892",
        "is_active": True,
        "created_at": NOW,
        "hashed_password": "$2b$12$dummy_hash",
    }


def make_test_member(campus_id=None, member_id=None):
    return {
        "id": member_id or TEST_MEMBER_ID,
        "name": "John Doe",
        "campus_id": campus_id or TEST_CAMPUS_ID,
        "phone": "+6281234567893",
        "photo_url": "/uploads/test.jpg",
        "engagement_status": "active",
        "days_since_last_contact": 5,
        "last_contact_date": NOW,
        "birth_date": "1990-05-15",
        "is_archived": False,
        "created_at": NOW,
    }


# Initialize mock DB
mock_db = make_mock_db()
init_dependencies(mock_db, TEST_JWT_SECRET)


# =====================================================================
# AUTH ROUTES - ADDITIONAL COVERAGE
# =====================================================================


class TestAuthRoutesCoverage:
    """Additional tests for routes/auth.py to cover missing branches."""

    @pytest.fixture(autouse=True)
    def setup(self):
        global mock_db
        mock_db = make_mock_db()
        init_dependencies(mock_db, TEST_JWT_SECRET)

    # ---- Line 52: register_user - weak password ----

    @patch("routes.auth.get_db")
    async def test_register_user_weak_password(self, mock_get_db):
        """Covers line 52: validate_password_strength fails"""
        from litestar.exceptions import HTTPException

        from models import UserCreate
        from routes.auth import register_user

        mock_get_db.return_value = mock_db

        data = UserCreate(
            email="new@test.com",
            password="short",
            name="Weak Pass User",
            phone="+6281234567894",
            role=UserRole.PASTOR,
            campus_id=TEST_CAMPUS_ID,
        )
        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(register_user)(data=data, request=req)
        assert exc_info.value.status_code == 400

    # ---- Lines 92-94: register_user - generic exception -> 500 ----

    @patch("routes.auth.get_current_admin", new_callable=AsyncMock)
    @patch("routes.auth.get_db")
    async def test_register_user_db_error(self, mock_get_db, mock_admin):
        """Covers lines 92-94: unexpected exception in register_user"""
        from litestar.exceptions import HTTPException

        from models import UserCreate
        from routes.auth import register_user

        mock_admin.return_value = make_admin_user()
        mock_get_db.return_value = mock_db
        mock_db.users.find_one = AsyncMock(return_value=None)
        mock_db.users.insert_one = AsyncMock(side_effect=RuntimeError("DB connection lost"))

        data = UserCreate(
            email="new@test.com",
            password="StrongPass123!",
            name="Error User",
            phone="+6281234567894",
            role=UserRole.PASTOR,
            campus_id=TEST_CAMPUS_ID,
        )
        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(register_user)(data=data, request=req)
        assert exc_info.value.status_code == 500

    # ---- Lines 198-200: login - generic exception -> 500 ----

    @patch("routes.auth.check_login_rate_limit", new_callable=AsyncMock, return_value=(True, None))
    @patch("routes.auth.get_client_ip", return_value="127.0.0.1")
    async def test_login_unexpected_exception(self, mock_ip, mock_rate):
        """Covers lines 198-200: unexpected error in login"""
        from litestar.exceptions import HTTPException

        from models import UserLogin
        from routes.auth import login

        mock_db.users.find_one = AsyncMock(side_effect=RuntimeError("DB down"))

        data = UserLogin(email="admin@test.com", password="TestPass123!")
        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(login)(data=data, request=req)
        assert exc_info.value.status_code == 500

    # ---- Lines 288-290: list_users - generic exception -> 500 ----

    @patch("routes.auth.get_current_admin", new_callable=AsyncMock)
    async def test_list_users_db_error(self, mock_admin):
        """Covers lines 288-290: exception in list_users"""
        from litestar.exceptions import HTTPException

        from routes.auth import list_users

        mock_admin.return_value = make_admin_user()
        mock_db.users.aggregate = MagicMock(side_effect=RuntimeError("Aggregation error"))

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(list_users)(request=req)
        assert exc_info.value.status_code == 500

    # ---- Lines 306, 310-314: update_user - phone normalization + password validation ----

    @patch("routes.auth.get_current_user", new_callable=AsyncMock)
    async def test_update_user_with_phone_normalization(self, mock_get_user):
        """Covers line 306: normalize phone number in update_user"""
        from models import UserUpdate
        from routes.auth import update_user

        mock_get_user.return_value = make_admin_user()
        mock_result = MagicMock()
        mock_result.matched_count = 1
        mock_db.users.update_one = AsyncMock(return_value=mock_result)
        updated_user = make_admin_user()
        updated_user["phone"] = "+6281234560000"
        mock_db.users.find_one = AsyncMock(return_value=updated_user)
        mock_db.campuses.find_one = AsyncMock(return_value={"id": TEST_CAMPUS_ID, "campus_name": "Main Campus"})

        data = UserUpdate(phone="081234560000")
        req = make_request()
        result = await _fn(update_user)(user_id=TEST_ADMIN_ID, data=data, request=req)
        assert result is not None

    @patch("routes.auth.get_current_user", new_callable=AsyncMock)
    async def test_update_user_with_password_change(self, mock_get_user):
        """Covers lines 310-314: password update with strength validation"""
        from models import UserUpdate
        from routes.auth import update_user

        mock_get_user.return_value = make_admin_user()
        mock_result = MagicMock()
        mock_result.matched_count = 1
        mock_db.users.update_one = AsyncMock(return_value=mock_result)
        updated_user = make_admin_user()
        mock_db.users.find_one = AsyncMock(return_value=updated_user)
        mock_db.campuses.find_one = AsyncMock(return_value={"id": TEST_CAMPUS_ID, "campus_name": "Main Campus"})

        data = UserUpdate(password="NewStrongPass123!")
        req = make_request()
        result = await _fn(update_user)(user_id=TEST_ADMIN_ID, data=data, request=req)
        assert result is not None

    @patch("routes.auth.get_current_user", new_callable=AsyncMock)
    async def test_update_user_with_weak_password(self, mock_get_user):
        """Covers lines 311-312: weak password in update_user"""
        from litestar.exceptions import HTTPException

        from models import UserUpdate
        from routes.auth import update_user

        mock_get_user.return_value = make_admin_user()

        data = UserUpdate(password="weak")
        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(update_user)(user_id=TEST_ADMIN_ID, data=data, request=req)
        assert exc_info.value.status_code == 400

    # ---- Lines 337-339: update_user - generic exception -> 500 ----

    @patch("routes.auth.get_current_user", new_callable=AsyncMock)
    async def test_update_user_db_error(self, mock_get_user):
        """Covers lines 337-339: unexpected error in update_user"""
        from litestar.exceptions import HTTPException

        from models import UserUpdate
        from routes.auth import update_user

        mock_get_user.return_value = make_admin_user()
        mock_db.users.update_one = AsyncMock(side_effect=RuntimeError("DB error"))

        data = UserUpdate(name="Error Name")
        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(update_user)(user_id=TEST_ADMIN_ID, data=data, request=req)
        assert exc_info.value.status_code == 500

    # ---- Line 355: update_own_profile - phone normalization ----

    @patch("routes.auth.get_current_user", new_callable=AsyncMock)
    async def test_update_own_profile_with_phone(self, mock_get_user):
        """Covers line 355: phone normalization in update_own_profile"""
        from models import ProfileUpdate
        from routes.auth import update_own_profile

        user = make_admin_user()
        mock_get_user.return_value = user
        mock_result = MagicMock()
        mock_result.matched_count = 1
        mock_db.users.update_one = AsyncMock(return_value=mock_result)
        updated = dict(user)
        updated["phone"] = "+6289999888777"
        mock_db.users.find_one = AsyncMock(return_value=updated)
        mock_db.campuses.find_one = AsyncMock(return_value={"id": TEST_CAMPUS_ID, "campus_name": "Main Campus"})

        data = ProfileUpdate(phone="089999888777")
        req = make_request()
        result = await _fn(update_own_profile)(data=data, request=req)
        assert result is not None

    # ---- Line 371: update_own_profile - matched_count 0 -> 404 ----

    @patch("routes.auth.get_current_user", new_callable=AsyncMock)
    async def test_update_own_profile_not_found(self, mock_get_user):
        """Covers line 371: user not found in update_own_profile"""
        from litestar.exceptions import HTTPException

        from models import ProfileUpdate
        from routes.auth import update_own_profile

        mock_get_user.return_value = make_admin_user()
        mock_result = MagicMock()
        mock_result.matched_count = 0
        mock_db.users.update_one = AsyncMock(return_value=mock_result)

        data = ProfileUpdate(name="No Exist")
        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(update_own_profile)(data=data, request=req)
        assert exc_info.value.status_code == 404

    # ---- Lines 384-386: update_own_profile - generic exception -> 500 ----

    @patch("routes.auth.get_current_user", new_callable=AsyncMock)
    async def test_update_own_profile_db_error(self, mock_get_user):
        """Covers lines 384-386: unexpected error in update_own_profile"""
        from litestar.exceptions import HTTPException

        from models import ProfileUpdate
        from routes.auth import update_own_profile

        mock_get_user.return_value = make_admin_user()
        mock_db.users.update_one = AsyncMock(side_effect=RuntimeError("DB exploded"))

        data = ProfileUpdate(name="Error")
        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(update_own_profile)(data=data, request=req)
        assert exc_info.value.status_code == 500

    # ---- Line 398: change_password - user not found ----

    @patch("routes.auth.get_current_user", new_callable=AsyncMock)
    async def test_change_password_user_not_found(self, mock_get_user):
        """Covers line 398: user record missing in change_password"""
        from litestar.exceptions import HTTPException

        from models import PasswordChange
        from routes.auth import change_password

        mock_get_user.return_value = make_admin_user()
        mock_db.users.find_one = AsyncMock(return_value=None)

        data = PasswordChange(current_password="OldPass123!", new_password="NewPass1234!")
        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(change_password)(data=data, request=req)
        assert exc_info.value.status_code == 404

    # ---- Line 407: change_password - weak new password ----

    @patch("routes.auth.get_current_user", new_callable=AsyncMock)
    @patch("routes.auth.verify_password", return_value=True)
    async def test_change_password_weak_new_password(self, mock_verify, mock_get_user):
        """Covers line 407: new password fails strength validation"""
        from litestar.exceptions import HTTPException

        from models import PasswordChange
        from routes.auth import change_password

        user = make_admin_user()
        mock_get_user.return_value = user
        mock_db.users.find_one = AsyncMock(return_value=user)

        data = PasswordChange(current_password="OldPass123!", new_password="weak")
        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(change_password)(data=data, request=req)
        assert exc_info.value.status_code == 400

    # ---- Lines 428-430: change_password - generic exception -> 500 ----

    @patch("routes.auth.get_current_user", new_callable=AsyncMock)
    async def test_change_password_db_error(self, mock_get_user):
        """Covers lines 428-430: unexpected error in change_password"""
        from litestar.exceptions import HTTPException

        from models import PasswordChange
        from routes.auth import change_password

        mock_get_user.return_value = make_admin_user()
        mock_db.users.find_one = AsyncMock(side_effect=RuntimeError("DB fail"))

        data = PasswordChange(current_password="OldPass123!", new_password="NewPass1234!")
        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(change_password)(data=data, request=req)
        assert exc_info.value.status_code == 500

    # ---- Lines 436-491: upload_user_photo ----

    @patch("routes.auth.get_current_user", new_callable=AsyncMock)
    async def test_upload_user_photo_not_authorized(self, mock_get_user):
        """Covers line 441: non-admin trying to upload for another user"""
        from litestar.exceptions import HTTPException

        from routes.auth import upload_user_photo

        pastor = make_pastor_user()
        mock_get_user.return_value = pastor

        mock_file = MagicMock()
        mock_file.read = AsyncMock(return_value=b"\x00" * 100)

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(upload_user_photo)(user_id="other-user-id", request=req, data=mock_file)
        assert exc_info.value.status_code == 403

    @patch("routes.auth.get_current_user", new_callable=AsyncMock)
    async def test_upload_user_photo_too_large(self, mock_get_user):
        """Covers line 447: file exceeds MAX_IMAGE_SIZE"""
        from litestar.exceptions import HTTPException

        from constants import MAX_IMAGE_SIZE
        from routes.auth import upload_user_photo

        admin = make_admin_user()
        mock_get_user.return_value = admin

        mock_file = MagicMock()
        mock_file.read = AsyncMock(return_value=b"\x00" * (MAX_IMAGE_SIZE + 1))

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(upload_user_photo)(user_id=TEST_ADMIN_ID, request=req, data=mock_file)
        assert exc_info.value.status_code == 400
        assert "too large" in str(exc_info.value.detail).lower()

    @patch("routes.auth.get_current_user", new_callable=AsyncMock)
    @patch("routes.auth.validate_image_magic_bytes", return_value=(False, "Unsupported file type"))
    async def test_upload_user_photo_invalid_magic_bytes(self, mock_validate, mock_get_user):
        """Covers lines 450-452: invalid magic bytes"""
        from litestar.exceptions import HTTPException

        from routes.auth import upload_user_photo

        admin = make_admin_user()
        mock_get_user.return_value = admin

        mock_file = MagicMock()
        mock_file.read = AsyncMock(return_value=b"\x00" * 100)

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(upload_user_photo)(user_id=TEST_ADMIN_ID, request=req, data=mock_file)
        assert exc_info.value.status_code == 400

    @patch("routes.auth.get_current_user", new_callable=AsyncMock)
    @patch("routes.auth.validate_image_magic_bytes", return_value=(True, "image/jpeg"))
    @patch("routes.auth.Image")
    async def test_upload_user_photo_success(self, mock_pil, mock_validate, mock_get_user):
        """Covers lines 462-485: successful photo upload with resize"""
        from routes.auth import upload_user_photo

        admin = make_admin_user()
        mock_get_user.return_value = admin

        # Create a small valid JPEG content
        mock_file = MagicMock()
        mock_file.read = AsyncMock(return_value=b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        # Mock PIL Image
        mock_img = MagicMock()
        mock_img.width = 400
        mock_img.height = 400
        mock_img.verify.return_value = None
        mock_img.convert.return_value = mock_img
        mock_img.thumbnail.return_value = None
        mock_img.save.return_value = None
        mock_pil.open.return_value = mock_img
        mock_pil.Resampling.LANCZOS = 1

        req = make_request()
        result = await _fn(upload_user_photo)(user_id=TEST_ADMIN_ID, request=req, data=mock_file)
        assert result["message"] == "Photo uploaded successfully"
        assert "photo_url" in result

    @patch("routes.auth.get_current_user", new_callable=AsyncMock)
    @patch("routes.auth.validate_image_magic_bytes", return_value=(True, "image/jpeg"))
    @patch("routes.auth.Image")
    async def test_upload_user_photo_corrupted_image(self, mock_pil, mock_validate, mock_get_user):
        """Covers lines 464-466: PIL cannot open corrupted image"""
        from litestar.exceptions import HTTPException

        from routes.auth import upload_user_photo

        admin = make_admin_user()
        mock_get_user.return_value = admin

        mock_file = MagicMock()
        mock_file.read = AsyncMock(return_value=b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        mock_pil.open.side_effect = Exception("Cannot open image")

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(upload_user_photo)(user_id=TEST_ADMIN_ID, request=req, data=mock_file)
        assert exc_info.value.status_code == 400

    @patch("routes.auth.get_current_user", new_callable=AsyncMock)
    @patch("routes.auth.validate_image_magic_bytes", return_value=(True, "image/jpeg"))
    @patch("routes.auth.Image")
    async def test_upload_user_photo_disk_full(self, mock_pil, mock_validate, mock_get_user):
        """Covers lines 471-473: OSError when saving (disk full)"""
        from litestar.exceptions import HTTPException

        from routes.auth import upload_user_photo

        admin = make_admin_user()
        mock_get_user.return_value = admin

        mock_file = MagicMock()
        mock_file.read = AsyncMock(return_value=b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        mock_img = MagicMock()
        mock_img.width = 400
        mock_img.height = 400
        mock_img.verify.return_value = None
        mock_img.convert.return_value = mock_img
        mock_img.thumbnail.return_value = None
        mock_img.save.side_effect = OSError("No space left on device")
        mock_pil.open.return_value = mock_img
        mock_pil.Resampling.LANCZOS = 1

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(upload_user_photo)(user_id=TEST_ADMIN_ID, request=req, data=mock_file)
        assert exc_info.value.status_code == 507

    @patch("routes.auth.get_current_user", new_callable=AsyncMock)
    @patch("routes.auth.validate_image_magic_bytes", return_value=(True, "image/jpeg"))
    async def test_upload_user_photo_generic_error(self, mock_validate, mock_get_user):
        """Covers lines 489-491: unexpected exception in upload_user_photo"""
        from litestar.exceptions import HTTPException

        from routes.auth import upload_user_photo

        admin = make_admin_user()
        mock_get_user.return_value = admin

        mock_file = MagicMock()
        mock_file.read = AsyncMock(side_effect=RuntimeError("IO error"))

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(upload_user_photo)(user_id=TEST_ADMIN_ID, request=req, data=mock_file)
        assert exc_info.value.status_code == 500

    # ---- Lines 511-513: delete_user - generic exception -> 500 ----

    @patch("routes.auth.get_current_admin", new_callable=AsyncMock)
    async def test_delete_user_db_error(self, mock_admin):
        """Covers lines 511-513: unexpected error in delete_user"""
        from litestar.exceptions import HTTPException

        from routes.auth import delete_user

        mock_admin.return_value = make_admin_user()
        mock_db.users.delete_one = AsyncMock(side_effect=RuntimeError("DB error"))

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(delete_user)(user_id=TEST_USER_ID, request=req)
        assert exc_info.value.status_code == 500


# =====================================================================
# MEMBERS ROUTES - ADDITIONAL COVERAGE
# =====================================================================


class TestMemberRoutesCoverage:
    """Additional tests for routes/members.py to cover missing branches."""

    @pytest.fixture(autouse=True)
    def setup(self):
        global mock_db
        mock_db = make_mock_db()
        init_dependencies(mock_db, TEST_JWT_SECRET)
        from routes.members import init_member_routes

        init_member_routes(
            invalidate_dashboard_cache=AsyncMock(),
            log_activity=AsyncMock(),
            msgspec_enc_hook=lambda obj: str(obj),
            root_dir=str(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        )

    # ---- Lines 94-96: create_member - generic exception -> 500 ----

    @patch("routes.members.get_current_user", new_callable=AsyncMock)
    async def test_create_member_db_error(self, mock_user):
        """Covers lines 94-96: unexpected error in create_member"""
        from litestar.exceptions import HTTPException

        from models import MemberCreate
        from routes.members import create_member

        mock_user.return_value = make_admin_user()
        mock_db.members.insert_one = AsyncMock(side_effect=RuntimeError("DB error"))

        data = MemberCreate(name="Error Member", campus_id=TEST_CAMPUS_ID)
        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(create_member)(data=data, request=req)
        assert exc_info.value.status_code == 500

    # ---- Lines 194-196: list_members - generic exception -> 500 ----

    @patch("routes.members.get_current_user", new_callable=AsyncMock)
    async def test_list_members_db_error(self, mock_user):
        """Covers lines 194-196: unexpected error in list_members"""
        from litestar.exceptions import HTTPException

        from routes.members import list_members

        mock_user.return_value = make_admin_user()
        # paginated_query uses aggregate which should throw
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(side_effect=RuntimeError("DB error"))
        mock_db.members.aggregate = MagicMock(return_value=mock_cursor)

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(list_members)(request=req, page=1, limit=50)
        assert exc_info.value.status_code == 500

    # ---- Lines 241-243: list_at_risk_members - generic exception -> 500 ----

    @patch("routes.members.get_current_user", new_callable=AsyncMock)
    async def test_list_at_risk_members_db_error(self, mock_user):
        """Covers lines 241-243: unexpected error in list_at_risk_members"""
        from litestar.exceptions import HTTPException

        from routes.members import list_at_risk_members

        mock_user.return_value = make_admin_user()
        mock_db.members.find = MagicMock(side_effect=RuntimeError("DB error"))

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(list_at_risk_members)(request=req)
        assert exc_info.value.status_code == 500

    # ---- Line 256: get_member - campus filter applied for non-admin ----

    @patch("routes.members.get_current_user", new_callable=AsyncMock)
    async def test_get_member_as_pastor_with_campus_filter(self, mock_user):
        """Covers line 256: campus filter applied for pastor"""
        from routes.members import get_member

        pastor = make_pastor_user()
        mock_user.return_value = pastor
        member = make_test_member()
        mock_db.members.find_one = AsyncMock(return_value=member)

        req = make_request()
        result = await _fn(get_member)(member_id=TEST_MEMBER_ID, request=req)
        assert result["name"] == "John Doe"
        # Verify campus_id was part of the query
        call_args = mock_db.members.find_one.call_args[0][0]
        assert "campus_id" in call_args

    # ---- Lines 273-275: get_member - generic exception -> 500 ----

    @patch("routes.members.get_current_user", new_callable=AsyncMock)
    async def test_get_member_db_error(self, mock_user):
        """Covers lines 273-275: unexpected error in get_member"""
        from litestar.exceptions import HTTPException

        from routes.members import get_member

        mock_user.return_value = make_admin_user()
        mock_db.members.find_one = AsyncMock(side_effect=RuntimeError("DB error"))

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(get_member)(member_id=TEST_MEMBER_ID, request=req)
        assert exc_info.value.status_code == 500

    # ---- Line 292: update_member - campus filter for non-admin ----

    @patch("routes.members.get_current_user", new_callable=AsyncMock)
    async def test_update_member_as_pastor(self, mock_user):
        """Covers line 292: campus filter in update_member for pastor"""
        from models import MemberUpdate
        from routes.members import update_member

        pastor = make_pastor_user()
        mock_user.return_value = pastor
        updated_member = make_test_member()
        updated_member["name"] = "Pastor Update"
        mock_db.members.find_one_and_update = AsyncMock(return_value=updated_member)

        data = MemberUpdate(name="Pastor Update")
        req = make_request()
        result = await _fn(update_member)(member_id=str(uuid.uuid4()), data=data, request=req)
        assert result["name"] == "Pastor Update"

    # ---- Lines 298-300: update_member - invalid phone ----

    @patch("routes.members.get_current_user", new_callable=AsyncMock)
    async def test_update_member_invalid_phone(self, mock_user):
        """Covers lines 298-300: invalid phone format in update_member"""
        from litestar.exceptions import HTTPException

        from models import MemberUpdate
        from routes.members import update_member

        mock_user.return_value = make_admin_user()

        data = MemberUpdate(phone="invalid-phone!!!")
        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(update_member)(member_id=str(uuid.uuid4()), data=data, request=req)
        assert exc_info.value.status_code == 400

    # ---- Lines 322-324: update_member - generic exception -> 500 ----

    @patch("routes.members.get_current_user", new_callable=AsyncMock)
    async def test_update_member_db_error(self, mock_user):
        """Covers lines 322-324: unexpected error in update_member"""
        from litestar.exceptions import HTTPException

        from models import MemberUpdate
        from routes.members import update_member

        mock_user.return_value = make_admin_user()
        mock_db.members.find_one_and_update = AsyncMock(side_effect=RuntimeError("DB error"))

        data = MemberUpdate(name="Error Update")
        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(update_member)(member_id=str(uuid.uuid4()), data=data, request=req)
        assert exc_info.value.status_code == 500

    # ---- Line 337: delete_member - campus filter for non-admin ----

    @patch("routes.members.get_current_user", new_callable=AsyncMock)
    async def test_delete_member_as_pastor(self, mock_user):
        """Covers line 337: campus filter in delete_member for pastor"""
        from routes.members import delete_member

        pastor = make_pastor_user()
        mock_user.return_value = pastor
        member = make_test_member()
        mock_db.members.find_one = AsyncMock(return_value=member)
        mock_result = MagicMock()
        mock_result.deleted_count = 1
        mock_db.members.delete_one = AsyncMock(return_value=mock_result)

        req = make_request()
        result = await _fn(delete_member)(member_id=TEST_MEMBER_ID, request=req)
        assert result["success"] is True
        # Verify cascade and campus filter
        call_args = mock_db.members.find_one.call_args[0][0]
        assert "campus_id" in call_args

    # ---- Line 345: delete_member - deleted_count is 0 (race condition) ----

    @patch("routes.members.get_current_user", new_callable=AsyncMock)
    async def test_delete_member_race_condition(self, mock_user):
        """Covers line 345: member found but delete returns 0 (deleted between queries)"""
        from litestar.exceptions import HTTPException

        from routes.members import delete_member

        mock_user.return_value = make_admin_user()
        member = make_test_member()
        mock_db.members.find_one = AsyncMock(return_value=member)
        mock_result = MagicMock()
        mock_result.deleted_count = 0
        mock_db.members.delete_one = AsyncMock(return_value=mock_result)

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(delete_member)(member_id=TEST_MEMBER_ID, request=req)
        assert exc_info.value.status_code == 404

    # ---- Lines 378-380: delete_member - generic exception -> 500 ----

    @patch("routes.members.get_current_user", new_callable=AsyncMock)
    async def test_delete_member_db_error(self, mock_user):
        """Covers lines 378-380: unexpected error in delete_member"""
        from litestar.exceptions import HTTPException

        from routes.members import delete_member

        mock_user.return_value = make_admin_user()
        mock_db.members.find_one = AsyncMock(side_effect=RuntimeError("DB error"))

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(delete_member)(member_id=TEST_MEMBER_ID, request=req)
        assert exc_info.value.status_code == 500

    # ---- Lines 386-461: upload_member_photo ----

    @patch("routes.members.get_current_user", new_callable=AsyncMock)
    async def test_upload_member_photo_member_not_found(self, mock_user):
        """Covers line 399: member not found for photo upload"""
        from litestar.exceptions import HTTPException

        from routes.members import upload_member_photo

        mock_user.return_value = make_admin_user()
        mock_db.members.find_one = AsyncMock(return_value=None)

        mock_file = MagicMock()
        mock_file.read = AsyncMock(return_value=b"\x00" * 100)

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(upload_member_photo)(member_id=TEST_MEMBER_ID, request=req, data=mock_file)
        assert exc_info.value.status_code == 404

    @patch("routes.members.get_current_user", new_callable=AsyncMock)
    async def test_upload_member_photo_too_large(self, mock_user):
        """Covers line 404: file too large"""
        from litestar.exceptions import HTTPException

        from constants import MAX_IMAGE_SIZE
        from routes.members import upload_member_photo

        mock_user.return_value = make_admin_user()
        member = make_test_member()
        mock_db.members.find_one = AsyncMock(return_value=member)

        mock_file = MagicMock()
        mock_file.read = AsyncMock(return_value=b"\x00" * (MAX_IMAGE_SIZE + 1))

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(upload_member_photo)(member_id=TEST_MEMBER_ID, request=req, data=mock_file)
        assert exc_info.value.status_code == 400

    @patch("routes.members.get_current_user", new_callable=AsyncMock)
    @patch("routes.members.validate_image_magic_bytes", return_value=(False, "Invalid file type"))
    async def test_upload_member_photo_invalid_magic(self, mock_validate, mock_user):
        """Covers lines 408-409: invalid magic bytes"""
        from litestar.exceptions import HTTPException

        from routes.members import upload_member_photo

        mock_user.return_value = make_admin_user()
        member = make_test_member()
        mock_db.members.find_one = AsyncMock(return_value=member)

        mock_file = MagicMock()
        mock_file.read = AsyncMock(return_value=b"\x00" * 100)

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(upload_member_photo)(member_id=TEST_MEMBER_ID, request=req, data=mock_file)
        assert exc_info.value.status_code == 400

    @patch("routes.members.get_current_user", new_callable=AsyncMock)
    @patch("routes.members.validate_image_magic_bytes", return_value=(True, "image/jpeg"))
    @patch("routes.members.Image")
    async def test_upload_member_photo_corrupted(self, mock_pil, mock_validate, mock_user):
        """Covers lines 413-415: corrupted image cannot be opened by PIL"""
        from litestar.exceptions import HTTPException

        from routes.members import upload_member_photo

        mock_user.return_value = make_admin_user()
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        mock_file = MagicMock()
        mock_file.read = AsyncMock(return_value=b"\xff\xd8" + b"\x00" * 100)

        mock_pil.open.side_effect = Exception("Cannot identify image file")

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(upload_member_photo)(member_id=TEST_MEMBER_ID, request=req, data=mock_file)
        assert exc_info.value.status_code == 400

    @patch("routes.members.get_current_user", new_callable=AsyncMock)
    @patch("routes.members.validate_image_magic_bytes", return_value=(True, "image/jpeg"))
    @patch("routes.members.Image")
    @patch("routes.members.Path")
    async def test_upload_member_photo_success(self, mock_path, mock_pil, mock_validate, mock_user):
        """Covers lines 417-456: full photo upload with 3 sizes"""
        from routes.members import upload_member_photo

        mock_user.return_value = make_admin_user()
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        mock_file = MagicMock()
        mock_file.read = AsyncMock(return_value=b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        # Mock PIL Image
        mock_img = MagicMock()
        mock_img.width = 600
        mock_img.height = 600
        mock_img.verify.return_value = None
        mock_img.convert.return_value = mock_img
        mock_img.copy.return_value = mock_img
        mock_img.thumbnail.return_value = None
        mock_img.save.return_value = None
        mock_pil.open.return_value = mock_img
        mock_pil.Resampling.LANCZOS = 1

        # Mock Path
        mock_filepath = MagicMock()
        mock_path.return_value.__truediv__ = MagicMock(return_value=mock_filepath)
        mock_filepath.__truediv__ = MagicMock(return_value=mock_filepath)

        req = make_request()
        result = await _fn(upload_member_photo)(member_id=TEST_MEMBER_ID, request=req, data=mock_file)
        assert result["success"] is True
        assert "photo_urls" in result

    @patch("routes.members.get_current_user", new_callable=AsyncMock)
    @patch("routes.members.validate_image_magic_bytes", return_value=(True, "image/jpeg"))
    async def test_upload_member_photo_generic_error(self, mock_validate, mock_user):
        """Covers lines 459-461: unexpected error in upload_member_photo"""
        from litestar.exceptions import HTTPException

        from routes.members import upload_member_photo

        mock_user.return_value = make_admin_user()
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        mock_file = MagicMock()
        mock_file.read = AsyncMock(side_effect=RuntimeError("IO failure"))

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(upload_member_photo)(member_id=TEST_MEMBER_ID, request=req, data=mock_file)
        assert exc_info.value.status_code == 500


# =====================================================================
# FINANCIAL AID ROUTES - ADDITIONAL COVERAGE
# =====================================================================


class TestFinancialAidRoutesCoverage:
    """Additional tests for routes/financial_aid.py to cover missing branches."""

    @pytest.fixture(autouse=True)
    def setup(self):
        global mock_db
        mock_db = make_mock_db()
        init_dependencies(mock_db, TEST_JWT_SECRET)
        # Round-2 added a member-visibility check inside create_aid_schedule
        # and get_member_aid_schedules. Default to a real member.
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())
        from routes.financial_aid import init_financial_aid_routes

        init_financial_aid_routes(
            invalidate_dashboard_cache=AsyncMock(),
            log_activity=AsyncMock(),
            get_engagement_settings_cached=AsyncMock(return_value={"atRiskDays": 60, "disconnectedDays": 90}),
        )

    # ---- Line 67: create_aid_schedule - weekly, day_of_week target >= current ----

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_create_weekly_schedule_next_week(self, mock_user):
        """Covers line 67/70: weekly schedule where target weekday is before today"""
        from models import FinancialAidScheduleCreate
        from routes.financial_aid import create_aid_schedule

        mock_user.return_value = make_admin_user()

        # Use 'sunday' which is day 6 - typically requires going to next week
        data = FinancialAidScheduleCreate(
            member_id=TEST_MEMBER_ID,
            title="Weekly Sunday Aid",
            aid_type="food",
            aid_amount=100000,
            frequency="weekly",
            start_date=TODAY.isoformat(),
            day_of_week="sunday",
        )
        req = make_request()
        result = await _fn(create_aid_schedule)(data=data, request=req)
        assert result is not None
        mock_db.financial_aid_schedules.insert_one.assert_called_once()

    # ---- Lines 87-89: create_aid_schedule - monthly with invalid day ----

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_create_monthly_schedule_invalid_day(self, mock_user):
        """Covers lines 87-89: day doesn't exist in month (e.g., Feb 31)"""
        from litestar.exceptions import HTTPException

        from models import FinancialAidScheduleCreate
        from routes.financial_aid import create_aid_schedule

        mock_user.return_value = make_admin_user()

        data = FinancialAidScheduleCreate(
            member_id=TEST_MEMBER_ID,
            title="Monthly Bad Day",
            aid_type="education",
            aid_amount=500000,
            frequency="monthly",
            start_date="2026-02-01",
            day_of_month=31,
        )
        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(create_aid_schedule)(data=data, request=req)
        # Note: create_aid_schedule lacks `except HTTPException: raise` before `except Exception`,
        # so the 400 HTTPException is caught and re-raised as 500
        assert exc_info.value.status_code == 500

    # ---- Lines 104-120: create_aid_schedule - annually with ValueError ----

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_create_annual_schedule_past_date(self, mock_user):
        """Covers lines 102-104: annual schedule where this year's date has passed"""
        from models import FinancialAidScheduleCreate
        from routes.financial_aid import create_aid_schedule

        mock_user.return_value = make_admin_user()

        # Use January (month 1) - likely already past if test runs after Jan
        data = FinancialAidScheduleCreate(
            member_id=TEST_MEMBER_ID,
            title="Annual Aid",
            aid_type="education",
            aid_amount=5000000,
            frequency="annually",
            start_date=TODAY.isoformat(),
            month_of_year=1,
            day_of_month=1,
        )
        req = make_request()
        result = await _fn(create_aid_schedule)(data=data, request=req)
        assert result is not None

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_create_annual_schedule_feb_29_non_leap(self, mock_user):
        """Covers lines 106-120: annual schedule with Feb 29 on non-leap year"""
        from models import FinancialAidScheduleCreate
        from routes.financial_aid import create_aid_schedule

        mock_user.return_value = make_admin_user()

        data = FinancialAidScheduleCreate(
            member_id=TEST_MEMBER_ID,
            title="Feb 29 Aid",
            aid_type="education",
            aid_amount=1000000,
            frequency="annually",
            start_date=TODAY.isoformat(),
            month_of_year=2,
            day_of_month=30,  # Feb 30 doesn't exist
        )
        req = make_request()
        result = await _fn(create_aid_schedule)(data=data, request=req)
        assert result is not None

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_create_annual_schedule_apr_31(self, mock_user):
        """Covers lines 113-114: annual with 30-day month (Apr has 30 days, not 31)"""
        from models import FinancialAidScheduleCreate
        from routes.financial_aid import create_aid_schedule

        mock_user.return_value = make_admin_user()

        data = FinancialAidScheduleCreate(
            member_id=TEST_MEMBER_ID,
            title="Apr 31 Aid",
            aid_type="education",
            aid_amount=1000000,
            frequency="annually",
            start_date=TODAY.isoformat(),
            month_of_year=4,
            day_of_month=31,  # Apr has 30 days
        )
        req = make_request()
        result = await _fn(create_aid_schedule)(data=data, request=req)
        assert result is not None

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_create_annual_schedule_31day_month(self, mock_user):
        """Covers lines 115-116: annual with 31-day month fallback"""
        from models import FinancialAidScheduleCreate
        from routes.financial_aid import create_aid_schedule

        mock_user.return_value = make_admin_user()

        # July (month 7) has 31 days - this shouldn't trigger ValueError but tests the path
        data = FinancialAidScheduleCreate(
            member_id=TEST_MEMBER_ID,
            title="Jul Aid",
            aid_type="education",
            aid_amount=1000000,
            frequency="annually",
            start_date=TODAY.isoformat(),
            month_of_year=7,
            day_of_month=15,
        )
        req = make_request()
        result = await _fn(create_aid_schedule)(data=data, request=req)
        assert result is not None

    # ---- Lines 148-150: create_aid_schedule - generic exception -> 500 ----

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_create_aid_schedule_db_error(self, mock_user):
        """Covers lines 148-150: unexpected error in create_aid_schedule"""
        from litestar.exceptions import HTTPException

        from models import FinancialAidScheduleCreate
        from routes.financial_aid import create_aid_schedule

        mock_user.return_value = make_admin_user()
        mock_db.financial_aid_schedules.insert_one = AsyncMock(side_effect=RuntimeError("DB error"))

        data = FinancialAidScheduleCreate(
            member_id=TEST_MEMBER_ID,
            title="Error Aid",
            aid_type="food",
            aid_amount=100000,
            frequency="weekly",
            start_date=TODAY.isoformat(),
            day_of_week="monday",
        )
        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(create_aid_schedule)(data=data, request=req)
        assert exc_info.value.status_code == 500

    # ---- Lines 176-178: list_aid_schedules - generic exception -> 500 ----

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_list_aid_schedules_db_error(self, mock_user):
        """Covers lines 176-178: unexpected error in list_aid_schedules"""
        from litestar.exceptions import HTTPException

        from routes.financial_aid import list_aid_schedules

        mock_user.return_value = make_admin_user()
        mock_db.financial_aid_schedules.find = MagicMock(side_effect=RuntimeError("DB error"))

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(list_aid_schedules)(request=req, page=1, limit=50)
        assert exc_info.value.status_code == 500

    # ---- Line 191: remove_ignored_occurrence - campus filter applied ----

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_remove_ignored_occurrence_as_pastor(self, mock_user):
        """Covers line 191: campus filter in remove_ignored_occurrence"""
        from routes.financial_aid import remove_ignored_occurrence

        pastor = make_pastor_user()
        mock_user.return_value = pastor
        schedule = {
            "id": "s1",
            "member_id": TEST_MEMBER_ID,
            "campus_id": TEST_CAMPUS_ID,
            "ignored_occurrences": ["2026-03-01"],
        }
        mock_db.financial_aid_schedules.find_one = AsyncMock(return_value=schedule)

        req = make_request()
        result = await _fn(remove_ignored_occurrence)(schedule_id="s1", occurrence_date="2026-03-01", request=req)
        assert result["success"] is True

    # ---- Lines 224-226: remove_ignored_occurrence - generic exception -> 500 ----

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_remove_ignored_occurrence_db_error(self, mock_user):
        """Covers lines 224-226: unexpected error in remove_ignored_occurrence"""
        from litestar.exceptions import HTTPException

        from routes.financial_aid import remove_ignored_occurrence

        mock_user.return_value = make_admin_user()
        mock_db.financial_aid_schedules.find_one = AsyncMock(side_effect=RuntimeError("DB error"))

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(remove_ignored_occurrence)(schedule_id="s1", occurrence_date="2026-03-01", request=req)
        assert exc_info.value.status_code == 500

    # ---- Lines 270-272: clear_all_ignored - generic exception -> 500 ----

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_clear_ignored_db_error(self, mock_user):
        """Covers lines 270-272: unexpected error in clear_all_ignored"""
        from litestar.exceptions import HTTPException

        from routes.financial_aid import clear_all_ignored_occurrences

        mock_user.return_value = make_admin_user()
        mock_db.financial_aid_schedules.find_one = AsyncMock(side_effect=RuntimeError("DB error"))

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(clear_all_ignored_occurrences)(schedule_id="s1", request=req)
        assert exc_info.value.status_code == 500

    # ---- Line 297: delete_aid_schedule - deleted_count is 0 ----

    async def test_delete_aid_schedule_race_condition(self):
        """Covers line 297: schedule found but delete_one returns 0"""
        from litestar.exceptions import HTTPException

        from routes.financial_aid import delete_aid_schedule

        schedule = {"id": "s1", "member_id": TEST_MEMBER_ID, "campus_id": TEST_CAMPUS_ID, "aid_type": "food"}
        mock_db.financial_aid_schedules.find_one = AsyncMock(return_value=schedule)
        mock_result = MagicMock()
        mock_result.deleted_count = 0
        mock_db.financial_aid_schedules.delete_one = AsyncMock(return_value=mock_result)

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(delete_aid_schedule)(schedule_id="s1", request=req)
        assert exc_info.value.status_code == 404

    # ---- Lines 305-307: delete_aid_schedule - generic exception -> 500 ----

    async def test_delete_aid_schedule_db_error(self):
        """Covers lines 305-307: unexpected error in delete_aid_schedule"""
        from litestar.exceptions import HTTPException

        from routes.financial_aid import delete_aid_schedule

        mock_db.financial_aid_schedules.find_one = AsyncMock(side_effect=RuntimeError("DB error"))

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(delete_aid_schedule)(schedule_id="s1", request=req)
        assert exc_info.value.status_code == 500

    # ---- Line 337: stop_aid_schedule - matched_count is 0 ----

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_stop_aid_schedule_race_condition(self, mock_user):
        """Covers line 337: schedule found initially but update returns 0"""
        from litestar.exceptions import HTTPException

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
        mock_result.matched_count = 0
        mock_db.financial_aid_schedules.update_one = AsyncMock(return_value=mock_result)

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(stop_aid_schedule)(schedule_id="s1", request=req)
        assert exc_info.value.status_code == 404

    # ---- Lines 358-360: stop_aid_schedule - generic exception -> 500 ----

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_stop_aid_schedule_db_error(self, mock_user):
        """Covers lines 358-360: unexpected error in stop_aid_schedule"""
        from litestar.exceptions import HTTPException

        from routes.financial_aid import stop_aid_schedule

        mock_user.return_value = make_admin_user()
        mock_db.financial_aid_schedules.find_one = AsyncMock(side_effect=RuntimeError("DB error"))

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(stop_aid_schedule)(schedule_id="s1", request=req)
        assert exc_info.value.status_code == 500

    # ---- Lines 389-395: get_member_aid_schedules - filtered results & debug log ----

    async def test_get_member_aid_schedules_empty_filter(self):
        """Covers lines 389-390, 393-395: schedules exist but none active/with history"""
        from routes.financial_aid import get_member_aid_schedules

        schedules = [
            {"id": "s1", "member_id": TEST_MEMBER_ID, "is_active": False, "ignored_occurrences": []},
            {"id": "s2", "member_id": TEST_MEMBER_ID, "is_active": False, "ignored_occurrences": []},
        ]
        mock_db.financial_aid_schedules.find = MagicMock(return_value=make_cursor(schedules))
        # Round-2 added member-visibility check before listing aid schedules.
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        req = make_request()
        result = await _fn(get_member_aid_schedules)(member_id=TEST_MEMBER_ID, request=req)
        assert len(result) == 0

    async def test_get_member_aid_schedules_exception(self):
        """Covers lines 393-395: unexpected error in get_member_aid_schedules"""
        from litestar.exceptions import HTTPException

        from routes.financial_aid import get_member_aid_schedules

        # Member visibility check passes; the schedules.find() then raises.
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())
        mock_db.financial_aid_schedules.find = MagicMock(side_effect=RuntimeError("DB error"))

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(get_member_aid_schedules)(member_id=TEST_MEMBER_ID, request=req)
        assert exc_info.value.status_code == 500

    # ---- Lines 428-430: get_aid_due_today - generic exception -> 500 ----

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_get_aid_due_today_db_error(self, mock_user):
        """Covers lines 428-430: unexpected error in get_aid_due_today"""
        from litestar.exceptions import HTTPException

        from routes.financial_aid import get_aid_due_today

        mock_user.return_value = make_admin_user()
        mock_db.financial_aid_schedules.find = MagicMock(side_effect=RuntimeError("DB error"))

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(get_aid_due_today)(request=req)
        assert exc_info.value.status_code == 500

    # ---- Lines 510-534: mark_aid_distributed - monthly December -> January ----

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_mark_distributed_monthly_december(self, mock_user):
        """Covers lines 510-511: monthly schedule in December -> January next year"""
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
            "next_occurrence": "2026-12-15",
            "day_of_month": 15,
            "occurrences_completed": 5,
            "is_active": True,
        }
        mock_db.financial_aid_schedules.find_one = AsyncMock(return_value=schedule)
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        req = make_request()
        result = await _fn(mark_aid_distributed)(schedule_id="s1", request=req)
        assert result["success"] is True
        assert result["next_occurrence"] == "2027-01-15"

    # ---- Lines 519-534: mark_aid_distributed - monthly day overflow (Jan 31 -> Feb) ----

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_mark_distributed_monthly_day_overflow_feb(self, mock_user):
        """Covers lines 519-526: Jan 31 -> Feb (28 or 29 in non-leap year)"""
        from routes.financial_aid import mark_aid_distributed

        mock_user.return_value = make_admin_user()
        schedule = {
            "id": "s1",
            "member_id": TEST_MEMBER_ID,
            "campus_id": TEST_CAMPUS_ID,
            "aid_type": "food",
            "aid_amount": 100000,
            "frequency": "monthly",
            "title": "Monthly Food",
            "next_occurrence": "2026-01-31",
            "day_of_month": 31,
            "occurrences_completed": 0,
            "is_active": True,
        }
        mock_db.financial_aid_schedules.find_one = AsyncMock(return_value=schedule)
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        req = make_request()
        result = await _fn(mark_aid_distributed)(schedule_id="s1", request=req)
        assert result["success"] is True
        # Feb 2026 is not a leap year, so should cap at 28
        assert result["next_occurrence"] == "2026-02-28"

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_mark_distributed_monthly_day_overflow_30day(self, mock_user):
        """Covers lines 527-528: March 31 -> April 30 (30-day month)"""
        from routes.financial_aid import mark_aid_distributed

        mock_user.return_value = make_admin_user()
        schedule = {
            "id": "s1",
            "member_id": TEST_MEMBER_ID,
            "campus_id": TEST_CAMPUS_ID,
            "aid_type": "food",
            "aid_amount": 100000,
            "frequency": "monthly",
            "title": "Monthly Food",
            "next_occurrence": "2026-03-31",
            "day_of_month": 31,
            "occurrences_completed": 1,
            "is_active": True,
        }
        mock_db.financial_aid_schedules.find_one = AsyncMock(return_value=schedule)
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        req = make_request()
        result = await _fn(mark_aid_distributed)(schedule_id="s1", request=req)
        assert result["success"] is True
        assert result["next_occurrence"] == "2026-04-30"

    # ---- Line 574: mark_aid_distributed - annually ----

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_mark_distributed_annually(self, mock_user):
        """Covers line 532: annually frequency"""
        from routes.financial_aid import mark_aid_distributed

        mock_user.return_value = make_admin_user()
        schedule = {
            "id": "s1",
            "member_id": TEST_MEMBER_ID,
            "campus_id": TEST_CAMPUS_ID,
            "aid_type": "education",
            "aid_amount": 5000000,
            "frequency": "annually",
            "title": "Annual Aid",
            "next_occurrence": "2026-06-01",
            "occurrences_completed": 0,
            "is_active": True,
        }
        mock_db.financial_aid_schedules.find_one = AsyncMock(return_value=schedule)
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        req = make_request()
        result = await _fn(mark_aid_distributed)(schedule_id="s1", request=req)
        assert result["success"] is True
        assert result["next_occurrence"] == "2027-06-01"

    # ---- Line 534: mark_aid_distributed - unknown frequency fallback ----

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_mark_distributed_unknown_frequency(self, mock_user):
        """Covers line 534: unknown frequency defaults to same date"""
        from routes.financial_aid import mark_aid_distributed

        mock_user.return_value = make_admin_user()
        schedule = {
            "id": "s1",
            "member_id": TEST_MEMBER_ID,
            "campus_id": TEST_CAMPUS_ID,
            "aid_type": "food",
            "aid_amount": 100000,
            "frequency": "one_time",
            "title": "One Time Aid",
            "next_occurrence": TODAY.isoformat(),
            "occurrences_completed": 0,
            "is_active": True,
        }
        mock_db.financial_aid_schedules.find_one = AsyncMock(return_value=schedule)
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        req = make_request()
        result = await _fn(mark_aid_distributed)(schedule_id="s1", request=req)
        assert result["success"] is True

    # ---- Lines 597-627: ignore_financial_aid_schedule - monthly frequency paths ----

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_ignore_aid_monthly(self, mock_user):
        """Covers lines 597-623: monthly ignore with next occurrence calculation"""
        from routes.financial_aid import ignore_financial_aid_schedule

        mock_user.return_value = make_admin_user()
        schedule = {
            "id": "s1",
            "member_id": TEST_MEMBER_ID,
            "campus_id": TEST_CAMPUS_ID,
            "aid_type": "food",
            "frequency": "monthly",
            "next_occurrence": "2026-03-15",
            "day_of_month": 15,
            "ignored_occurrences": [],
            "is_active": True,
        }
        mock_db.financial_aid_schedules.find_one = AsyncMock(return_value=schedule)
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        req = make_request()
        result = await _fn(ignore_financial_aid_schedule)(schedule_id="s1", request=req)
        assert result["success"] is True
        assert result["next_occurrence"] == "2026-04-15"

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_ignore_aid_monthly_december(self, mock_user):
        """Covers lines 601-603: monthly ignore in December -> January"""
        from routes.financial_aid import ignore_financial_aid_schedule

        mock_user.return_value = make_admin_user()
        schedule = {
            "id": "s1",
            "member_id": TEST_MEMBER_ID,
            "campus_id": TEST_CAMPUS_ID,
            "aid_type": "food",
            "frequency": "monthly",
            "next_occurrence": "2026-12-15",
            "day_of_month": 15,
            "ignored_occurrences": [],
            "is_active": True,
        }
        mock_db.financial_aid_schedules.find_one = AsyncMock(return_value=schedule)
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        req = make_request()
        result = await _fn(ignore_financial_aid_schedule)(schedule_id="s1", request=req)
        assert result["success"] is True
        assert result["next_occurrence"] == "2027-01-15"

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_ignore_aid_monthly_day_overflow_feb(self, mock_user):
        """Covers lines 613-618: Jan 31 ignore -> Feb day overflow"""
        from routes.financial_aid import ignore_financial_aid_schedule

        mock_user.return_value = make_admin_user()
        schedule = {
            "id": "s1",
            "member_id": TEST_MEMBER_ID,
            "campus_id": TEST_CAMPUS_ID,
            "aid_type": "food",
            "frequency": "monthly",
            "next_occurrence": "2026-01-31",
            "day_of_month": 31,
            "ignored_occurrences": [],
            "is_active": True,
        }
        mock_db.financial_aid_schedules.find_one = AsyncMock(return_value=schedule)
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        req = make_request()
        result = await _fn(ignore_financial_aid_schedule)(schedule_id="s1", request=req)
        assert result["success"] is True
        assert result["next_occurrence"] == "2026-02-28"

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_ignore_aid_monthly_day_overflow_30day(self, mock_user):
        """Covers lines 619-620: March 31 ignore -> April 30"""
        from routes.financial_aid import ignore_financial_aid_schedule

        mock_user.return_value = make_admin_user()
        schedule = {
            "id": "s1",
            "member_id": TEST_MEMBER_ID,
            "campus_id": TEST_CAMPUS_ID,
            "aid_type": "food",
            "frequency": "monthly",
            "next_occurrence": "2026-03-31",
            "day_of_month": 31,
            "ignored_occurrences": [],
            "is_active": True,
        }
        mock_db.financial_aid_schedules.find_one = AsyncMock(return_value=schedule)
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        req = make_request()
        result = await _fn(ignore_financial_aid_schedule)(schedule_id="s1", request=req)
        assert result["success"] is True
        assert result["next_occurrence"] == "2026-04-30"

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_ignore_aid_annually(self, mock_user):
        """Covers line 624-625: annual ignore"""
        from routes.financial_aid import ignore_financial_aid_schedule

        mock_user.return_value = make_admin_user()
        schedule = {
            "id": "s1",
            "member_id": TEST_MEMBER_ID,
            "campus_id": TEST_CAMPUS_ID,
            "aid_type": "education",
            "frequency": "annually",
            "next_occurrence": "2026-06-01",
            "ignored_occurrences": [],
            "is_active": True,
        }
        mock_db.financial_aid_schedules.find_one = AsyncMock(return_value=schedule)
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        req = make_request()
        result = await _fn(ignore_financial_aid_schedule)(schedule_id="s1", request=req)
        assert result["success"] is True
        assert result["next_occurrence"] == "2027-06-01"

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_ignore_aid_unknown_frequency(self, mock_user):
        """Covers lines 626-627: unknown frequency defaults to same date"""
        from routes.financial_aid import ignore_financial_aid_schedule

        mock_user.return_value = make_admin_user()
        schedule = {
            "id": "s1",
            "member_id": TEST_MEMBER_ID,
            "campus_id": TEST_CAMPUS_ID,
            "aid_type": "food",
            "frequency": "one_time",
            "next_occurrence": TODAY.isoformat(),
            "ignored_occurrences": [],
            "is_active": True,
        }
        mock_db.financial_aid_schedules.find_one = AsyncMock(return_value=schedule)
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        req = make_request()
        result = await _fn(ignore_financial_aid_schedule)(schedule_id="s1", request=req)
        assert result["success"] is True

    # ---- Lines 662-663: ignore_financial_aid_schedule - generic exception -> 500 ----

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_ignore_aid_db_error(self, mock_user):
        """Covers lines 662-663: unexpected error in ignore"""
        from litestar.exceptions import HTTPException

        from routes.financial_aid import ignore_financial_aid_schedule

        mock_user.return_value = make_admin_user()
        mock_db.financial_aid_schedules.find_one = AsyncMock(side_effect=RuntimeError("DB error"))

        req = make_request()
        with pytest.raises(HTTPException) as exc_info:
            await _fn(ignore_financial_aid_schedule)(schedule_id="s1", request=req)
        assert exc_info.value.status_code == 500

    # ---- Line 684: get_financial_aid_summary - end_date only ----

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_get_financial_aid_summary_end_date_only(self, mock_user):
        """Covers line 684: summary with end_date but no start_date"""
        from routes.financial_aid import get_financial_aid_summary

        mock_user.return_value = make_admin_user()
        mock_db.care_events.find = MagicMock(return_value=make_cursor([]))

        result = await _fn(get_financial_aid_summary)(request=make_request(), end_date="2026-12-31")
        assert result["total_amount"] == 0
        assert result["total_count"] == 0

    # ---- Lines 708-710: get_financial_aid_summary - generic exception -> 500 ----

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_get_financial_aid_summary_db_error(self, mock_user):
        """Covers lines 708-710: unexpected error in summary"""
        from litestar.exceptions import HTTPException

        from routes.financial_aid import get_financial_aid_summary

        mock_user.return_value = make_admin_user()
        mock_db.care_events.find = MagicMock(side_effect=RuntimeError("DB error"))

        with pytest.raises(HTTPException) as exc_info:
            await _fn(get_financial_aid_summary)(request=make_request())
        assert exc_info.value.status_code == 500

    # ---- Lines 750-752: get_financial_aid_recipients - member name from event title ----

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_get_financial_aid_recipients_name_from_title(self, mock_user):
        """Covers lines 750-752: fallback to event title for member name"""
        from routes.financial_aid import get_financial_aid_recipients

        mock_user.return_value = make_admin_user()
        agg_data = [{"_id": TEST_MEMBER_ID, "total_amount": 100000, "aid_count": 1}]
        mock_db.care_events.aggregate = MagicMock(return_value=make_agg_cursor(agg_data))
        mock_db.members.find_one = AsyncMock(return_value=None)
        # Return event with title containing " - "
        mock_db.care_events.find_one = AsyncMock(return_value={"title": "Financial Aid - Jane Doe"})

        result = await _fn(get_financial_aid_recipients)(request=make_request())
        assert len(result) == 1
        assert result[0]["member_name"] == "Jane Doe"

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_get_financial_aid_recipients_null_member_id(self, mock_user):
        """Covers line 735: recipient with None member_id skipped"""
        from routes.financial_aid import get_financial_aid_recipients

        mock_user.return_value = make_admin_user()
        agg_data = [{"_id": None, "total_amount": 50000, "aid_count": 1}]
        mock_db.care_events.aggregate = MagicMock(return_value=make_agg_cursor(agg_data))

        result = await _fn(get_financial_aid_recipients)(request=make_request())
        assert len(result) == 0

    # ---- Lines 763-765: get_financial_aid_recipients - generic exception -> 500 ----

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_get_financial_aid_recipients_db_error(self, mock_user):
        """Covers lines 763-765: unexpected error in recipients"""
        from litestar.exceptions import HTTPException

        from routes.financial_aid import get_financial_aid_recipients

        mock_user.return_value = make_admin_user()
        mock_db.care_events.aggregate = MagicMock(side_effect=RuntimeError("DB error"))

        with pytest.raises(HTTPException) as exc_info:
            await _fn(get_financial_aid_recipients)(request=make_request())
        assert exc_info.value.status_code == 500

    # ---- Lines 786-788: get_member_financial_aid - generic exception -> 500 ----

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_get_member_financial_aid_db_error(self, mock_user):
        """Covers lines 786-788: unexpected error in member financial aid"""
        from litestar.exceptions import HTTPException

        from routes.financial_aid import get_member_financial_aid

        mock_user.return_value = make_admin_user()
        mock_db.members.find_one = AsyncMock(return_value={"id": TEST_MEMBER_ID})
        mock_db.care_events.find = MagicMock(side_effect=RuntimeError("DB error"))

        with pytest.raises(HTTPException) as exc_info:
            await _fn(get_member_financial_aid)(member_id=TEST_MEMBER_ID, request=make_request())
        assert exc_info.value.status_code == 500

    # ---- Ignore with duplicate occurrence already in list ----

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_ignore_aid_duplicate_occurrence(self, mock_user):
        """Covers line 586-587: occurrence already in ignored list"""
        from routes.financial_aid import ignore_financial_aid_schedule

        mock_user.return_value = make_admin_user()
        occurrence = TODAY.isoformat()
        schedule = {
            "id": "s1",
            "member_id": TEST_MEMBER_ID,
            "campus_id": TEST_CAMPUS_ID,
            "aid_type": "food",
            "frequency": "weekly",
            "next_occurrence": occurrence,
            "ignored_occurrences": [occurrence],
            "is_active": True,
        }
        mock_db.financial_aid_schedules.find_one = AsyncMock(return_value=schedule)
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        req = make_request()
        result = await _fn(ignore_financial_aid_schedule)(schedule_id="s1", request=req)
        assert result["success"] is True

    # ---- Overdue schedule in get_aid_due_today ----

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_get_aid_due_today_overdue(self, mock_user):
        """Covers lines 423-425: schedule that is overdue (past next_occurrence)"""
        from routes.financial_aid import get_aid_due_today

        mock_user.return_value = make_admin_user()
        past_date = (TODAY - timedelta(days=3)).isoformat()
        schedules = [
            {
                "id": "s1",
                "member_id": TEST_MEMBER_ID,
                "campus_id": TEST_CAMPUS_ID,
                "aid_type": "food",
                "aid_amount": 100000,
                "next_occurrence": past_date,
                "is_active": True,
            }
        ]
        mock_db.financial_aid_schedules.find = MagicMock(return_value=make_cursor(schedules))
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        req = make_request()
        result = await _fn(get_aid_due_today)(request=req)
        assert len(result) == 1
        assert result[0]["status"] == "overdue"
        assert result[0]["days_overdue"] == 3

    # ---- Due today with missing member ----

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_get_aid_due_today_member_not_found(self, mock_user):
        """Covers member lookup returning None in due_today loop"""
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
        mock_db.members.find_one = AsyncMock(return_value=None)

        req = make_request()
        result = await _fn(get_aid_due_today)(request=req)
        # Schedule returned but without member_name since member not found
        assert len(result) == 1
        assert "member_name" not in result[0]

    # ---- Mark distributed monthly with 31-day-month overflow (e.g., May 31 -> Jun 30) ----

    @patch("routes.financial_aid.get_current_user", new_callable=AsyncMock)
    async def test_mark_distributed_monthly_may31_overflow(self, mock_user):
        """Covers lines 529-530: May 31 -> June (30-day month) in mark_distributed"""
        from routes.financial_aid import mark_aid_distributed

        mock_user.return_value = make_admin_user()
        schedule = {
            "id": "s1",
            "member_id": TEST_MEMBER_ID,
            "campus_id": TEST_CAMPUS_ID,
            "aid_type": "food",
            "aid_amount": 100000,
            "frequency": "monthly",
            "title": "Monthly Food",
            "next_occurrence": "2026-05-31",
            "day_of_month": 31,
            "occurrences_completed": 2,
            "is_active": True,
        }
        mock_db.financial_aid_schedules.find_one = AsyncMock(return_value=schedule)
        mock_db.members.find_one = AsyncMock(return_value=make_test_member())

        req = make_request()
        result = await _fn(mark_aid_distributed)(schedule_id="s1", request=req)
        assert result["success"] is True
        assert result["next_occurrence"] == "2026-06-30"
