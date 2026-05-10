"""
Integration tests for FaithTracker authentication and dependencies.

Tests ALL functions in dependencies.py with mocked MongoDB:
- init_dependencies, get_db
- get_current_user, get_current_admin, get_full_admin
- get_campus_filter
- verify_password, get_password_hash, create_access_token
- safe_error_detail, get_client_ip
- check_login_rate_limit, record_failed_login, clear_login_attempts (DragonflyDB-backed)

Target: 100% coverage of dependencies.py (all 133 statements).
"""

import os
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set env vars BEFORE any app imports
os.environ.update(
    {
        "MONGO_URL": "mongodb://mock:27017",
        "DB_NAME": "faithtracker_test",
        "JWT_SECRET_KEY": "test-secret-key-1234567890abcdef1234567890abcdef",
        "ENCRYPTION_KEY": "dGVzdC1lbmNyeXB0aW9uLWtleS0xMjM0NTY3ODkwYWI=",
        "DRAGONFLY_URL": "redis://mock:6379",
        "FRONTEND_URL": "http://localhost:3000",
        "ALLOWED_ORIGINS": "http://localhost:3000",
        "ENVIRONMENT": "development",
    }
)

# Now import
from dependencies import (
    LOGIN_ATTEMPT_WINDOW_MINUTES,
    LOGIN_MAX_ATTEMPTS,
    check_login_rate_limit,
    clear_login_attempts,
    create_access_token,
    get_campus_filter,
    get_client_ip,
    get_current_admin,
    get_current_user,
    get_db,
    get_full_admin,
    get_password_hash,
    init_dependencies,
    init_redis,
    record_failed_login,
    safe_error_detail,
    verify_password,
)
from enums import UserRole

# ==================== FIXTURES ====================

TEST_SECRET_KEY = "test-secret-key-for-jwt-signing-minimum-length"


@pytest.fixture(autouse=True)
def reset_dependencies():
    """Reset global dependency state before and after each test."""
    import dependencies

    original_db = dependencies._db
    original_secret = dependencies._secret_key
    yield
    dependencies._db = original_db
    dependencies._secret_key = original_secret


@pytest.fixture(autouse=True)
def reset_redis_state():
    """Reset redis state before each test (brute-force is now DragonflyDB-backed)."""
    init_redis(None)
    yield
    init_redis(None)


@pytest.fixture
def mock_db():
    """Create a mock MongoDB database with async collections."""
    db = MagicMock()
    db.users = MagicMock()
    db.users.find_one = AsyncMock(return_value=None)
    return db


@pytest.fixture
def initialized_db(mock_db):
    """Initialize dependencies with the mock DB and return it."""
    init_dependencies(mock_db, TEST_SECRET_KEY)
    return mock_db


@pytest.fixture
def mock_request():
    """Create a mock Litestar Request object."""
    request = MagicMock()
    request.headers = {}
    request.scope = {"client": ("127.0.0.1", 12345)}
    return request


@pytest.fixture
def full_admin_user():
    """A full_admin user dict."""
    return {
        "id": "admin-001",
        "name": "Full Admin",
        "email": "admin@test.com",
        "role": UserRole.FULL_ADMIN.value,
        "campus_id": "campus-001",
        "is_active": True,
    }


@pytest.fixture
def campus_admin_user():
    """A campus_admin user dict."""
    return {
        "id": "campus-admin-001",
        "name": "Campus Admin",
        "email": "campus_admin@test.com",
        "role": UserRole.CAMPUS_ADMIN.value,
        "campus_id": "campus-001",
        "is_active": True,
    }


@pytest.fixture
def pastor_user():
    """A pastor user dict."""
    return {
        "id": "pastor-001",
        "name": "Pastor",
        "email": "pastor@test.com",
        "role": UserRole.PASTOR.value,
        "campus_id": "campus-001",
        "is_active": True,
    }


def make_valid_token(user_id: str = "admin-001", secret: str = TEST_SECRET_KEY) -> str:
    """Helper to create a valid JWT token for testing."""
    import dependencies

    old_secret = dependencies._secret_key
    dependencies._secret_key = secret
    token = create_access_token({"sub": user_id})
    dependencies._secret_key = old_secret
    return token


# ==================== init_dependencies TESTS ====================


class TestInitDependencies:
    """Tests for init_dependencies()."""

    def test_sets_db_and_secret_key(self, mock_db):
        """init_dependencies should set the global _db and _secret_key."""
        import dependencies

        init_dependencies(mock_db, "my-secret")
        assert dependencies._db is mock_db
        assert dependencies._secret_key == "my-secret"

    def test_overwrites_previous_values(self, mock_db):
        """Calling init_dependencies again should overwrite previous values."""
        import dependencies

        first_db = MagicMock()
        init_dependencies(first_db, "secret-1")
        assert dependencies._db is first_db

        init_dependencies(mock_db, "secret-2")
        assert dependencies._db is mock_db
        assert dependencies._secret_key == "secret-2"


# ==================== get_db TESTS ====================


class TestGetDb:
    """Tests for get_db()."""

    def test_returns_db_when_initialized(self, initialized_db):
        """get_db should return the database reference after initialization."""
        result = get_db()
        assert result is initialized_db

    def test_raises_runtime_error_when_not_initialized(self):
        """get_db should raise RuntimeError if init_dependencies was never called."""
        import dependencies

        dependencies._db = None
        with pytest.raises(RuntimeError, match="Database not initialized"):
            get_db()


# ==================== get_current_user TESTS ====================


class TestGetCurrentUser:
    """Tests for get_current_user()."""

    async def test_valid_token_returns_user(self, initialized_db, mock_request, full_admin_user):
        """A valid token with an existing user should return the user dict."""
        token = make_valid_token("admin-001")
        mock_request.headers = {"Authorization": f"Bearer {token}"}
        initialized_db.users.find_one = AsyncMock(return_value=full_admin_user)

        result = await get_current_user(mock_request)
        assert result == full_admin_user
        initialized_db.users.find_one.assert_awaited_once_with({"id": "admin-001"}, {"_id": 0})

    async def test_missing_authorization_header(self, initialized_db, mock_request):
        """Missing Authorization header should raise 401."""
        mock_request.headers = {}
        from litestar.exceptions import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request)
        assert exc_info.value.status_code == 401
        assert "Could not validate credentials" in str(exc_info.value.detail)

    async def test_no_bearer_prefix(self, initialized_db, mock_request):
        """Authorization header without 'Bearer ' prefix should raise 401."""
        mock_request.headers = {"Authorization": "Basic some-token"}
        from litestar.exceptions import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request)
        assert exc_info.value.status_code == 401

    async def test_empty_token_after_bearer(self, initialized_db, mock_request):
        """'Bearer ' followed by empty/whitespace-only token should raise 401."""
        mock_request.headers = {"Authorization": "Bearer   "}
        from litestar.exceptions import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request)
        assert exc_info.value.status_code == 401
        # Empty/whitespace token falls through to the generic credentials message.
        assert "Could not validate credentials" in str(exc_info.value.detail)

    async def test_empty_bearer_no_space(self, initialized_db, mock_request):
        """'Bearer' with no token at all (just 7 chars extraction) should raise 401."""
        mock_request.headers = {"Authorization": "Bearer "}
        from litestar.exceptions import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request)
        assert exc_info.value.status_code == 401
        # Empty/whitespace token falls through to the generic credentials message.
        assert "Could not validate credentials" in str(exc_info.value.detail)

    async def test_expired_token(self, initialized_db, mock_request):
        """An expired JWT token should raise 401."""
        import dependencies

        dependencies._secret_key = TEST_SECRET_KEY
        # Create a token that expired 1 hour ago
        expired_token = create_access_token(
            {"sub": "admin-001"},
            expires_delta=timedelta(hours=-1),
        )
        mock_request.headers = {"Authorization": f"Bearer {expired_token}"}
        from litestar.exceptions import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request)
        assert exc_info.value.status_code == 401

    async def test_invalid_token_format(self, initialized_db, mock_request):
        """A malformed JWT should raise 401."""
        mock_request.headers = {"Authorization": "Bearer not-a-valid-jwt-token"}
        from litestar.exceptions import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request)
        assert exc_info.value.status_code == 401

    async def test_token_wrong_secret(self, initialized_db, mock_request):
        """A token signed with a different secret should raise 401."""
        import jwt as pyjwt

        wrong_token = pyjwt.encode(
            {"sub": "admin-001", "exp": datetime.now(UTC) + timedelta(hours=1)},
            "wrong-secret-key",
            algorithm="HS256",
        )
        mock_request.headers = {"Authorization": f"Bearer {wrong_token}"}
        from litestar.exceptions import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request)
        assert exc_info.value.status_code == 401

    async def test_token_missing_sub_claim(self, initialized_db, mock_request):
        """A token without 'sub' claim should raise 401."""
        import jwt as pyjwt

        token_no_sub = pyjwt.encode(
            {"exp": datetime.now(UTC) + timedelta(hours=1)},
            TEST_SECRET_KEY,
            algorithm="HS256",
        )
        mock_request.headers = {"Authorization": f"Bearer {token_no_sub}"}
        from litestar.exceptions import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request)
        assert exc_info.value.status_code == 401
        assert "Could not validate credentials" in str(exc_info.value.detail)

    async def test_user_not_found_in_db(self, initialized_db, mock_request):
        """Valid token but user not found in DB should raise 401."""
        token = make_valid_token("nonexistent-user")
        mock_request.headers = {"Authorization": f"Bearer {token}"}
        initialized_db.users.find_one = AsyncMock(return_value=None)

        from litestar.exceptions import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request)
        assert exc_info.value.status_code == 401


# ==================== get_current_admin TESTS ====================


class TestGetCurrentAdmin:
    """Tests for get_current_admin()."""

    async def test_full_admin_allowed(self, initialized_db, mock_request, full_admin_user):
        """full_admin role should be allowed through."""
        token = make_valid_token(full_admin_user["id"])
        mock_request.headers = {"Authorization": f"Bearer {token}"}
        initialized_db.users.find_one = AsyncMock(return_value=full_admin_user)

        result = await get_current_admin(mock_request)
        assert result["role"] == UserRole.FULL_ADMIN.value

    async def test_campus_admin_allowed(self, initialized_db, mock_request, campus_admin_user):
        """campus_admin role should be allowed through."""
        token = make_valid_token(campus_admin_user["id"])
        mock_request.headers = {"Authorization": f"Bearer {token}"}
        initialized_db.users.find_one = AsyncMock(return_value=campus_admin_user)

        result = await get_current_admin(mock_request)
        assert result["role"] == UserRole.CAMPUS_ADMIN.value

    async def test_pastor_denied(self, initialized_db, mock_request, pastor_user):
        """pastor role should be denied with 403."""
        token = make_valid_token(pastor_user["id"])
        mock_request.headers = {"Authorization": f"Bearer {token}"}
        initialized_db.users.find_one = AsyncMock(return_value=pastor_user)

        from litestar.exceptions import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_current_admin(mock_request)
        assert exc_info.value.status_code == 403
        assert "Admin privileges required" in str(exc_info.value.detail)


# ==================== get_full_admin TESTS ====================


class TestGetFullAdmin:
    """Tests for get_full_admin()."""

    async def test_full_admin_allowed(self, initialized_db, mock_request, full_admin_user):
        """full_admin role should pass."""
        token = make_valid_token(full_admin_user["id"])
        mock_request.headers = {"Authorization": f"Bearer {token}"}
        initialized_db.users.find_one = AsyncMock(return_value=full_admin_user)

        result = await get_full_admin(mock_request)
        assert result["role"] == UserRole.FULL_ADMIN.value

    async def test_campus_admin_denied(self, initialized_db, mock_request, campus_admin_user):
        """campus_admin role should be denied with 403."""
        token = make_valid_token(campus_admin_user["id"])
        mock_request.headers = {"Authorization": f"Bearer {token}"}
        initialized_db.users.find_one = AsyncMock(return_value=campus_admin_user)

        from litestar.exceptions import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_full_admin(mock_request)
        assert exc_info.value.status_code == 403
        assert "Full admin privileges required" in str(exc_info.value.detail)

    async def test_pastor_denied(self, initialized_db, mock_request, pastor_user):
        """pastor role should be denied with 403."""
        token = make_valid_token(pastor_user["id"])
        mock_request.headers = {"Authorization": f"Bearer {token}"}
        initialized_db.users.find_one = AsyncMock(return_value=pastor_user)

        from litestar.exceptions import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_full_admin(mock_request)
        assert exc_info.value.status_code == 403
        assert "Full admin privileges required" in str(exc_info.value.detail)


# ==================== get_campus_filter TESTS ====================


class TestGetCampusFilter:
    """Tests for get_campus_filter()."""

    def test_full_admin_returns_empty_filter(self, full_admin_user):
        """full_admin should get empty filter (access to everything)."""
        result = get_campus_filter(full_admin_user)
        assert result == {}

    def test_campus_admin_returns_scoped_filter(self, campus_admin_user):
        """campus_admin should get filter scoped to their campus."""
        result = get_campus_filter(campus_admin_user)
        assert result == {"campus_id": "campus-001"}

    def test_pastor_returns_scoped_filter(self, pastor_user):
        """pastor should get filter scoped to their campus."""
        result = get_campus_filter(pastor_user)
        assert result == {"campus_id": "campus-001"}

    def test_user_without_campus_id_returns_impossible_filter(self):
        """User with no campus_id and non-full_admin role gets impossible filter."""
        user_no_campus = {
            "id": "orphan-001",
            "role": UserRole.PASTOR.value,
            # No campus_id key at all
        }
        result = get_campus_filter(user_no_campus)
        assert result == {"campus_id": {"$exists": False, "$eq": "IMPOSSIBLE_VALUE"}}

    def test_user_with_none_campus_id(self):
        """User with campus_id=None and non-full_admin should get impossible filter."""
        user_none_campus = {
            "id": "orphan-002",
            "role": UserRole.CAMPUS_ADMIN.value,
            "campus_id": None,
        }
        result = get_campus_filter(user_none_campus)
        # campus_id is None, which is falsy, so falls through to impossible filter
        assert result == {"campus_id": {"$exists": False, "$eq": "IMPOSSIBLE_VALUE"}}

    def test_user_with_empty_string_campus_id(self):
        """User with campus_id='' and non-full_admin should get impossible filter."""
        user_empty_campus = {
            "id": "orphan-003",
            "role": UserRole.PASTOR.value,
            "campus_id": "",
        }
        result = get_campus_filter(user_empty_campus)
        # empty string is falsy, so falls through to impossible filter
        assert result == {"campus_id": {"$exists": False, "$eq": "IMPOSSIBLE_VALUE"}}


# ==================== verify_password TESTS ====================


class TestVerifyPassword:
    """Tests for verify_password()."""

    def test_correct_password(self):
        """verify_password should return True for correct password."""
        hashed = get_password_hash("my-secure-password")
        assert verify_password("my-secure-password", hashed) is True

    def test_wrong_password(self):
        """verify_password should return False for wrong password."""
        hashed = get_password_hash("my-secure-password")
        assert verify_password("wrong-password", hashed) is False

    def test_empty_password_mismatch(self):
        """Empty password should not match a real hash."""
        hashed = get_password_hash("something")
        assert verify_password("", hashed) is False

    def test_unicode_password(self):
        """Unicode passwords should work correctly."""
        hashed = get_password_hash("p@$$w\u00f6rd\u2603")
        assert verify_password("p@$$w\u00f6rd\u2603", hashed) is True
        assert verify_password("p@$$word", hashed) is False


# ==================== get_password_hash TESTS ====================


class TestGetPasswordHash:
    """Tests for get_password_hash()."""

    def test_returns_bcrypt_hash(self):
        """get_password_hash should return a valid bcrypt hash string."""
        hashed = get_password_hash("test-password")
        assert isinstance(hashed, str)
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")

    def test_different_salts_produce_different_hashes(self):
        """Two calls with the same password should produce different hashes (random salt)."""
        hash1 = get_password_hash("same-password")
        hash2 = get_password_hash("same-password")
        assert hash1 != hash2

    def test_hash_is_verifiable(self):
        """The produced hash should be verifiable with verify_password."""
        password = "test123"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True


# ==================== create_access_token TESTS ====================


class TestCreateAccessToken:
    """Tests for create_access_token()."""

    def test_default_expiry(self, initialized_db):
        """Token with default expiry should have expected hours from JWT_TOKEN_EXPIRE_HOURS."""
        import jwt as pyjwt

        from constants import JWT_TOKEN_EXPIRE_HOURS

        token = create_access_token({"sub": "user-001"})
        payload = pyjwt.decode(token, TEST_SECRET_KEY, algorithms=["HS256"])
        assert payload["sub"] == "user-001"
        assert "exp" in payload

        # Check expiry is approximately JWT_TOKEN_EXPIRE_HOURS from now
        exp_dt = datetime.fromtimestamp(payload["exp"], tz=UTC)
        expected = datetime.now(UTC) + timedelta(hours=JWT_TOKEN_EXPIRE_HOURS)
        # Allow 5-second tolerance
        assert abs((exp_dt - expected).total_seconds()) < 5

    def test_custom_expiry(self, initialized_db):
        """Token with custom expires_delta should use the given duration."""
        import jwt as pyjwt

        custom_delta = timedelta(minutes=30)
        token = create_access_token({"sub": "user-002"}, expires_delta=custom_delta)
        payload = pyjwt.decode(token, TEST_SECRET_KEY, algorithms=["HS256"])

        exp_dt = datetime.fromtimestamp(payload["exp"], tz=UTC)
        expected = datetime.now(UTC) + custom_delta
        assert abs((exp_dt - expected).total_seconds()) < 5

    def test_token_preserves_extra_data(self, initialized_db):
        """Extra data in the payload should be preserved in the token."""
        import jwt as pyjwt

        token = create_access_token({"sub": "user-003", "role": "admin", "campus": "c1"})
        payload = pyjwt.decode(token, TEST_SECRET_KEY, algorithms=["HS256"])
        assert payload["sub"] == "user-003"
        assert payload["role"] == "admin"
        assert payload["campus"] == "c1"

    def test_original_data_not_mutated(self, initialized_db):
        """create_access_token should not mutate the original data dict."""
        original = {"sub": "user-004"}
        create_access_token(original)
        assert "exp" not in original

    def test_token_is_string(self, initialized_db):
        """The returned token should be a string."""
        token = create_access_token({"sub": "user-005"})
        assert isinstance(token, str)


# ==================== safe_error_detail TESTS ====================


class TestSafeErrorDetail:
    """Tests for safe_error_detail()."""

    def test_development_mode_returns_full_error(self):
        """In development mode, the full error message should be returned."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            error = ValueError("Detailed internal error info")
            result = safe_error_detail(error, 500)
            assert result == "Detailed internal error info"

    def test_production_mode_returns_generic_500(self):
        """In production mode, a generic 500 message should be returned."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            error = ValueError("SECRET: database connection string exposed")
            result = safe_error_detail(error, 500)
            assert result == "An internal error occurred. Please try again later."
            assert "SECRET" not in result

    def test_production_mode_returns_generic_400(self):
        """In production mode, a generic 400 message should be returned."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            error = ValueError("Bad input details")
            result = safe_error_detail(error, 400)
            assert result == "Invalid request"

    def test_production_mode_returns_generic_401(self):
        """In production mode, a generic 401 message should be returned."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            error = ValueError("Token expired details")
            result = safe_error_detail(error, 401)
            assert result == "Authentication required"

    def test_production_mode_returns_generic_403(self):
        """In production mode, a generic 403 message should be returned."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            error = ValueError("Forbidden details")
            result = safe_error_detail(error, 403)
            assert result == "Access denied"

    def test_production_mode_returns_generic_404(self):
        """In production mode, a generic 404 message should be returned."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            error = ValueError("Not found details")
            result = safe_error_detail(error, 404)
            assert result == "Resource not found"

    def test_production_mode_unknown_status_code(self):
        """In production mode, an unknown status code should return fallback."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            error = ValueError("Some error")
            result = safe_error_detail(error, 418)
            assert result == "An error occurred"

    def test_development_mode_with_custom_status_code(self):
        """In development mode, the full error should be returned regardless of status."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            error = RuntimeError("Custom 503 error details")
            result = safe_error_detail(error, 503)
            assert result == "Custom 503 error details"


# ==================== get_client_ip TESTS ====================


class TestGetClientIp:
    """Tests for get_client_ip()."""

    def test_x_forwarded_for_single_ip(self, mock_request):
        """X-Forwarded-For with a single IP should return that IP."""
        mock_request.headers = {"x-forwarded-for": "203.0.113.50"}
        result = get_client_ip(mock_request)
        assert result == "203.0.113.50"

    def test_x_forwarded_for_multiple_ips(self, mock_request):
        """X-Forwarded-For with multiple IPs should return the first (client) IP."""
        mock_request.headers = {"x-forwarded-for": "203.0.113.50, 70.41.3.18, 150.172.238.178"}
        result = get_client_ip(mock_request)
        assert result == "203.0.113.50"

    def test_x_forwarded_for_with_spaces(self, mock_request):
        """X-Forwarded-For values should be stripped of whitespace."""
        mock_request.headers = {"x-forwarded-for": "  10.0.0.1  , 192.168.1.1"}
        result = get_client_ip(mock_request)
        assert result == "10.0.0.1"

    def test_x_real_ip(self, mock_request):
        """X-Real-IP should be used when X-Forwarded-For is absent."""
        mock_request.headers = {"x-real-ip": "198.51.100.42"}
        result = get_client_ip(mock_request)
        assert result == "198.51.100.42"

    def test_x_real_ip_with_whitespace(self, mock_request):
        """X-Real-IP should be stripped of whitespace."""
        mock_request.headers = {"x-real-ip": "  198.51.100.42  "}
        result = get_client_ip(mock_request)
        assert result == "198.51.100.42"

    def test_x_forwarded_for_takes_precedence_over_x_real_ip(self, mock_request):
        """X-Forwarded-For should take precedence over X-Real-IP."""
        mock_request.headers = {
            "x-forwarded-for": "203.0.113.50",
            "x-real-ip": "198.51.100.42",
        }
        result = get_client_ip(mock_request)
        assert result == "203.0.113.50"

    def test_direct_connection_ip(self, mock_request):
        """When no proxy headers are present, direct connection IP should be used."""
        mock_request.headers = {}
        mock_request.scope = {"client": ("192.168.1.100", 54321)}
        result = get_client_ip(mock_request)
        assert result == "192.168.1.100"

    def test_no_client_in_scope(self, mock_request):
        """When there is no client in scope, 'unknown' should be returned."""
        mock_request.headers = {}
        mock_request.scope = {}
        result = get_client_ip(mock_request)
        assert result == "unknown"

    def test_client_is_none(self, mock_request):
        """When client is None, 'unknown' should be returned."""
        mock_request.headers = {}
        mock_request.scope = {"client": None}
        result = get_client_ip(mock_request)
        assert result == "unknown"

    def test_empty_x_forwarded_for_falls_through(self, mock_request):
        """Empty X-Forwarded-For should fall through to X-Real-IP or direct."""
        mock_request.headers = {"x-forwarded-for": ""}
        mock_request.scope = {"client": ("10.0.0.5", 9999)}
        result = get_client_ip(mock_request)
        # Empty string is falsy, so falls through
        assert result == "10.0.0.5"

    def test_empty_x_real_ip_falls_through(self, mock_request):
        """Empty X-Real-IP should fall through to direct connection."""
        mock_request.headers = {"x-real-ip": ""}
        mock_request.scope = {"client": ("10.0.0.6", 8888)}
        result = get_client_ip(mock_request)
        assert result == "10.0.0.6"


# ==================== BRUTE FORCE PROTECTION TESTS (DragonflyDB-backed) ====================


class TestBruteForceRedis:
    """Tests for DragonflyDB-backed brute force protection."""

    @pytest.fixture(autouse=True)
    def setup_redis_mock(self):
        """Set up a mock redis client for each test."""
        self.redis_store = {}
        self.mock_redis = AsyncMock()

        async def mock_get(key):
            return self.redis_store.get(key)

        async def mock_set(key, value, ex=None):
            self.redis_store[key] = value

        async def mock_delete(key):
            self.redis_store.pop(key, None)

        self.mock_redis.get = AsyncMock(side_effect=mock_get)
        self.mock_redis.set = AsyncMock(side_effect=mock_set)
        self.mock_redis.delete = AsyncMock(side_effect=mock_delete)
        init_redis(self.mock_redis)
        yield
        init_redis(None)

    @pytest.mark.asyncio
    async def test_first_attempt_allowed(self):
        """First login attempt from a new IP/email should be allowed."""
        allowed, msg = await check_login_rate_limit("1.2.3.4", "user@test.com")
        assert allowed is True
        assert msg is None

    @pytest.mark.asyncio
    async def test_no_redis_fails_open(self):
        """If redis is None, always allow login."""
        init_redis(None)
        allowed, _msg = await check_login_rate_limit("1.2.3.4", "user@test.com")
        assert allowed is True

    @pytest.mark.asyncio
    async def test_record_and_check_below_max(self):
        """Attempts below max should still be allowed."""
        for _i in range(LOGIN_MAX_ATTEMPTS - 1):
            await record_failed_login("1.2.3.4", "user@test.com")
        allowed, _msg = await check_login_rate_limit("1.2.3.4", "user@test.com")
        assert allowed is True

    @pytest.mark.asyncio
    async def test_lockout_after_max_attempts(self):
        """Account should be locked after max failed attempts."""
        for _i in range(LOGIN_MAX_ATTEMPTS):
            await record_failed_login("1.2.3.4", "lock@test.com")
        allowed, msg = await check_login_rate_limit("1.2.3.4", "lock@test.com")
        assert allowed is False
        assert "locked" in msg.lower()

    @pytest.mark.asyncio
    async def test_lockout_shows_remaining_minutes(self):
        """Locked message should include remaining minutes."""
        for _i in range(LOGIN_MAX_ATTEMPTS):
            await record_failed_login("1.2.3.4", "time@test.com")
        # Trigger lockout
        await check_login_rate_limit("1.2.3.4", "time@test.com")
        # Check again - should show remaining time
        allowed, msg = await check_login_rate_limit("1.2.3.4", "time@test.com")
        assert allowed is False
        assert "minutes" in msg

    @pytest.mark.asyncio
    async def test_expired_lockout_allows_login(self):
        """Expired lockout should allow login and clear the key."""
        import json as json_mod

        key = "ft:login:1.2.3.4:expired@test.com"
        past = (datetime.now(UTC) - timedelta(minutes=30)).isoformat()
        self.redis_store[key] = json_mod.dumps(
            {
                "attempts": 10,
                "last_attempt": past,
                "locked_until": past,  # Already expired
            }
        )
        allowed, _msg = await check_login_rate_limit("1.2.3.4", "expired@test.com")
        assert allowed is True
        assert key not in self.redis_store  # Key should be deleted

    @pytest.mark.asyncio
    async def test_email_case_insensitive(self):
        """Email should be case-insensitive in key."""
        await record_failed_login("1.2.3.4", "User@Test.COM")
        key = "ft:login:1.2.3.4:user@test.com"
        assert key in self.redis_store

    @pytest.mark.asyncio
    async def test_different_ips_separate(self):
        """Different IPs should have separate attempt counters."""
        for _i in range(LOGIN_MAX_ATTEMPTS):
            await record_failed_login("1.1.1.1", "user@test.com")
        # Lock the first IP
        await check_login_rate_limit("1.1.1.1", "user@test.com")
        # Second IP should still be allowed
        allowed, _ = await check_login_rate_limit("2.2.2.2", "user@test.com")
        assert allowed is True

    @pytest.mark.asyncio
    async def test_clear_login_attempts_removes_key(self):
        """clear_login_attempts should delete the redis key."""
        await record_failed_login("1.2.3.4", "clear@test.com")
        key = "ft:login:1.2.3.4:clear@test.com"
        assert key in self.redis_store
        await clear_login_attempts("1.2.3.4", "clear@test.com")
        assert key not in self.redis_store

    @pytest.mark.asyncio
    async def test_clear_nonexistent_key_no_error(self):
        """Clearing a non-existent key should not raise."""
        await clear_login_attempts("9.9.9.9", "noone@test.com")

    @pytest.mark.asyncio
    async def test_record_resets_outside_window(self):
        """Attempts outside the window should reset the counter."""
        import json as json_mod

        key = "ft:login:1.2.3.4:window@test.com"
        old_time = (datetime.now(UTC) - timedelta(minutes=LOGIN_ATTEMPT_WINDOW_MINUTES + 1)).isoformat()
        self.redis_store[key] = json_mod.dumps(
            {"attempts": LOGIN_MAX_ATTEMPTS - 1, "last_attempt": old_time, "locked_until": None}
        )
        await record_failed_login("1.2.3.4", "window@test.com")
        record = json_mod.loads(self.redis_store[key])
        assert record["attempts"] == 1  # Reset, not incremented

    @pytest.mark.asyncio
    async def test_redis_error_fails_open(self):
        """Redis errors should fail open (allow login)."""
        self.mock_redis.get = AsyncMock(side_effect=Exception("Redis down"))
        allowed, _msg = await check_login_rate_limit("1.2.3.4", "err@test.com")
        assert allowed is True

    @pytest.mark.asyncio
    async def test_full_lockout_and_recovery_flow(self):
        """Full flow: fail max times → lockout → clear → allowed."""
        ip, email = "10.0.0.1", "flow@test.com"
        for _i in range(LOGIN_MAX_ATTEMPTS):
            await record_failed_login(ip, email)
        allowed, _ = await check_login_rate_limit(ip, email)
        assert allowed is False
        # Clear attempts (simulates successful login from admin)
        await clear_login_attempts(ip, email)
        allowed, _ = await check_login_rate_limit(ip, email)
        assert allowed is True
