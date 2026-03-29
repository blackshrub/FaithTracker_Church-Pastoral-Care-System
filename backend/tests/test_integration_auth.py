"""
Integration tests for FaithTracker authentication and dependencies.

Tests ALL functions in dependencies.py with mocked MongoDB:
- init_dependencies, get_db
- get_current_user, get_current_admin, get_full_admin
- get_campus_filter
- verify_password, get_password_hash, create_access_token
- safe_error_detail, get_client_ip
- check_login_rate_limit, record_failed_login, clear_login_attempts, cleanup_old_login_attempts

Target: 100% coverage of dependencies.py (all 133 statements).
"""

import pytest
import os
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone, timedelta

# Set env vars BEFORE any app imports
os.environ.update({
    'MONGO_URL': 'mongodb://mock:27017',
    'DB_NAME': 'faithtracker_test',
    'JWT_SECRET_KEY': 'test-secret-key-1234567890abcdef1234567890abcdef',
    'ENCRYPTION_KEY': 'dGVzdC1lbmNyeXB0aW9uLWtleS0xMjM0NTY3ODkwYWI=',
    'DRAGONFLY_URL': 'redis://mock:6379',
    'FRONTEND_URL': 'http://localhost:3000',
    'ALLOWED_ORIGINS': 'http://localhost:3000',
    'ENVIRONMENT': 'development',
})

# Now import
from dependencies import (
    init_dependencies, get_db, get_current_user, get_current_admin,
    get_full_admin, get_campus_filter, verify_password, get_password_hash,
    create_access_token, safe_error_detail, get_client_ip,
    check_login_rate_limit, record_failed_login, clear_login_attempts,
    cleanup_old_login_attempts, _login_attempts,
    LOGIN_MAX_ATTEMPTS, LOGIN_LOCKOUT_MINUTES, LOGIN_ATTEMPT_WINDOW_MINUTES,
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
def clear_login_attempts_dict():
    """Clear the login attempts dict before each test."""
    _login_attempts.clear()
    yield
    _login_attempts.clear()


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
        initialized_db.users.find_one.assert_awaited_once_with(
            {"id": "admin-001"}, {"_id": 0}
        )

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
        assert "Token is empty or invalid" in str(exc_info.value.detail)

    async def test_empty_bearer_no_space(self, initialized_db, mock_request):
        """'Bearer' with no token at all (just 7 chars extraction) should raise 401."""
        mock_request.headers = {"Authorization": "Bearer "}
        from litestar.exceptions import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request)
        assert exc_info.value.status_code == 401
        assert "Token is empty or invalid" in str(exc_info.value.detail)

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
            {"sub": "admin-001", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
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
            {"exp": datetime.now(timezone.utc) + timedelta(hours=1)},
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
        exp_dt = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        expected = datetime.now(timezone.utc) + timedelta(hours=JWT_TOKEN_EXPIRE_HOURS)
        # Allow 5-second tolerance
        assert abs((exp_dt - expected).total_seconds()) < 5

    def test_custom_expiry(self, initialized_db):
        """Token with custom expires_delta should use the given duration."""
        import jwt as pyjwt

        custom_delta = timedelta(minutes=30)
        token = create_access_token({"sub": "user-002"}, expires_delta=custom_delta)
        payload = pyjwt.decode(token, TEST_SECRET_KEY, algorithms=["HS256"])

        exp_dt = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        expected = datetime.now(timezone.utc) + custom_delta
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


# ==================== check_login_rate_limit TESTS ====================

class TestCheckLoginRateLimit:
    """Tests for check_login_rate_limit()."""

    def test_first_attempt_allowed(self):
        """First login attempt from a new IP/email should be allowed."""
        allowed, msg = check_login_rate_limit("1.2.3.4", "user@test.com")
        assert allowed is True
        assert msg is None

    def test_allowed_when_below_max_attempts(self):
        """Login should be allowed when attempts are below the max."""
        # Record some failed attempts but stay below the limit
        for i in range(LOGIN_MAX_ATTEMPTS - 1):
            record_failed_login("1.2.3.4", "user@test.com")

        allowed, msg = check_login_rate_limit("1.2.3.4", "user@test.com")
        assert allowed is True
        assert msg is None

    def test_locked_after_max_attempts(self):
        """Login should be blocked after max failed attempts within the window."""
        ip = "1.2.3.4"
        email = "locked@test.com"

        # Record max failed attempts
        for i in range(LOGIN_MAX_ATTEMPTS):
            record_failed_login(ip, email)

        # This check should trigger lockout
        allowed, msg = check_login_rate_limit(ip, email)
        assert allowed is False
        assert "Too many failed attempts" in msg
        assert str(LOGIN_LOCKOUT_MINUTES) in msg

    def test_locked_account_returns_remaining_minutes(self):
        """A locked account should report remaining lockout time."""
        ip = "5.6.7.8"
        email = "locked2@test.com"
        key = f"{ip}:{email}"

        # Set up a lock that expires in 10 minutes
        now = datetime.now(timezone.utc)
        _login_attempts[key] = {
            "attempts": LOGIN_MAX_ATTEMPTS,
            "last_attempt": now,
            "locked_until": now + timedelta(minutes=10),
        }

        allowed, msg = check_login_rate_limit(ip, email)
        assert allowed is False
        assert "Account temporarily locked" in msg
        assert "minutes" in msg

    def test_lockout_expired_allows_login(self):
        """After lockout expires, login should be allowed again."""
        ip = "9.10.11.12"
        email = "expired@test.com"
        key = f"{ip}:{email}"

        # Set up an expired lock
        now = datetime.now(timezone.utc)
        _login_attempts[key] = {
            "attempts": LOGIN_MAX_ATTEMPTS,
            "last_attempt": now - timedelta(minutes=20),
            "locked_until": now - timedelta(minutes=5),  # Expired 5 min ago
        }

        allowed, msg = check_login_rate_limit(ip, email)
        assert allowed is True
        assert msg is None
        # Record should have been cleared
        assert key not in _login_attempts

    def test_email_case_insensitive(self):
        """Rate limiting should treat emails case-insensitively."""
        ip = "1.1.1.1"
        record_failed_login(ip, "User@Test.COM")

        key_lower = f"{ip}:user@test.com"
        assert key_lower in _login_attempts
        assert _login_attempts[key_lower]["attempts"] == 1

    def test_different_ips_tracked_separately(self):
        """Different IPs with the same email should be tracked separately."""
        email = "user@test.com"
        for _ in range(LOGIN_MAX_ATTEMPTS):
            record_failed_login("1.1.1.1", email)

        # Different IP should still be allowed
        allowed, msg = check_login_rate_limit("2.2.2.2", email)
        assert allowed is True
        assert msg is None

    def test_different_emails_tracked_separately(self):
        """Different emails from the same IP should be tracked separately."""
        ip = "1.1.1.1"
        for _ in range(LOGIN_MAX_ATTEMPTS):
            record_failed_login(ip, "user1@test.com")

        # Different email should still be allowed
        allowed, msg = check_login_rate_limit(ip, "user2@test.com")
        assert allowed is True
        assert msg is None

    def test_within_window_but_under_limit(self):
        """Attempts within the time window but under the limit should be allowed."""
        ip = "3.3.3.3"
        email = "within@test.com"
        key = f"{ip}:{email}"

        now = datetime.now(timezone.utc)
        _login_attempts[key] = {
            "attempts": 2,
            "last_attempt": now - timedelta(minutes=1),  # Recent, within window
            "locked_until": None,
        }

        allowed, msg = check_login_rate_limit(ip, email)
        assert allowed is True
        assert msg is None

    def test_attempts_outside_window_allowed(self):
        """Attempts outside the time window should not count (record exists but old)."""
        ip = "4.4.4.4"
        email = "old@test.com"
        key = f"{ip}:{email}"

        now = datetime.now(timezone.utc)
        _login_attempts[key] = {
            "attempts": LOGIN_MAX_ATTEMPTS,  # At max, but old
            "last_attempt": now - timedelta(minutes=LOGIN_ATTEMPT_WINDOW_MINUTES + 1),
            "locked_until": None,
        }

        # Outside window, so attempts don't count
        allowed, msg = check_login_rate_limit(ip, email)
        assert allowed is True
        assert msg is None


# ==================== record_failed_login TESTS ====================

class TestRecordFailedLogin:
    """Tests for record_failed_login()."""

    def test_first_attempt_creates_record(self):
        """First failed login should create a new record with attempts=1."""
        ip = "10.0.0.1"
        email = "new@test.com"
        key = f"{ip}:{email}"

        record_failed_login(ip, email)

        assert key in _login_attempts
        record = _login_attempts[key]
        assert record["attempts"] == 1
        assert record["locked_until"] is None
        assert isinstance(record["last_attempt"], datetime)

    def test_subsequent_attempts_increment(self):
        """Subsequent failed logins within the window should increment attempts."""
        ip = "10.0.0.2"
        email = "repeat@test.com"
        key = f"{ip}:{email}"

        record_failed_login(ip, email)
        assert _login_attempts[key]["attempts"] == 1

        record_failed_login(ip, email)
        assert _login_attempts[key]["attempts"] == 2

        record_failed_login(ip, email)
        assert _login_attempts[key]["attempts"] == 3

    def test_outside_window_resets_counter(self):
        """If the last attempt was outside the window, counter should reset to 1."""
        ip = "10.0.0.3"
        email = "reset@test.com"
        key = f"{ip}:{email}"

        now = datetime.now(timezone.utc)
        _login_attempts[key] = {
            "attempts": 4,
            "last_attempt": now - timedelta(minutes=LOGIN_ATTEMPT_WINDOW_MINUTES + 1),
            "locked_until": None,
        }

        record_failed_login(ip, email)

        record = _login_attempts[key]
        assert record["attempts"] == 1
        # last_attempt should be updated to now
        assert (now - record["last_attempt"]).total_seconds() < 2

    def test_updates_last_attempt_timestamp(self):
        """Each failed login should update the last_attempt timestamp."""
        ip = "10.0.0.4"
        email = "timestamp@test.com"

        record_failed_login(ip, email)
        first_time = _login_attempts[f"{ip}:{email}"]["last_attempt"]

        record_failed_login(ip, email)
        second_time = _login_attempts[f"{ip}:{email}"]["last_attempt"]

        assert second_time >= first_time

    def test_email_lowercased_in_key(self):
        """The email should be lowercased in the key for consistency."""
        ip = "10.0.0.5"
        record_failed_login(ip, "UPPER@TEST.COM")
        assert f"{ip}:upper@test.com" in _login_attempts


# ==================== clear_login_attempts TESTS ====================

class TestClearLoginAttempts:
    """Tests for clear_login_attempts()."""

    def test_clears_existing_record(self):
        """clear_login_attempts should remove the record for the IP/email combination."""
        ip = "20.0.0.1"
        email = "clear@test.com"
        key = f"{ip}:{email}"

        _login_attempts[key] = {
            "attempts": 3,
            "last_attempt": datetime.now(timezone.utc),
            "locked_until": None,
        }

        clear_login_attempts(ip, email)
        assert key not in _login_attempts

    def test_handles_missing_record_gracefully(self):
        """Clearing a non-existent record should not raise an error."""
        # Should not raise any exception
        clear_login_attempts("99.99.99.99", "nonexistent@test.com")

    def test_email_case_insensitive(self):
        """clear_login_attempts should use lowercase email for the key."""
        ip = "20.0.0.2"
        email_lower = "case@test.com"
        key = f"{ip}:{email_lower}"

        _login_attempts[key] = {
            "attempts": 2,
            "last_attempt": datetime.now(timezone.utc),
            "locked_until": None,
        }

        # Clear with mixed-case email
        clear_login_attempts(ip, "Case@Test.COM")
        assert key not in _login_attempts

    def test_only_clears_specified_key(self):
        """Clearing one record should not affect other records."""
        ip = "20.0.0.3"
        email1 = "keep@test.com"
        email2 = "remove@test.com"

        now = datetime.now(timezone.utc)
        _login_attempts[f"{ip}:{email1}"] = {
            "attempts": 1,
            "last_attempt": now,
            "locked_until": None,
        }
        _login_attempts[f"{ip}:{email2}"] = {
            "attempts": 2,
            "last_attempt": now,
            "locked_until": None,
        }

        clear_login_attempts(ip, email2)
        assert f"{ip}:{email1}" in _login_attempts
        assert f"{ip}:{email2}" not in _login_attempts


# ==================== cleanup_old_login_attempts TESTS ====================

class TestCleanupOldLoginAttempts:
    """Tests for cleanup_old_login_attempts()."""

    def test_removes_expired_unlocked_records(self):
        """Old unlocked records past the expiry window should be removed."""
        now = datetime.now(timezone.utc)
        expiry_time = LOGIN_LOCKOUT_MINUTES + LOGIN_ATTEMPT_WINDOW_MINUTES

        # Old record - should be cleaned
        _login_attempts["old:old@test.com"] = {
            "attempts": 2,
            "last_attempt": now - timedelta(minutes=expiry_time + 5),
            "locked_until": None,
        }
        # Recent record - should be kept
        _login_attempts["recent:recent@test.com"] = {
            "attempts": 1,
            "last_attempt": now - timedelta(minutes=1),
            "locked_until": None,
        }

        cleanup_old_login_attempts()

        assert "old:old@test.com" not in _login_attempts
        assert "recent:recent@test.com" in _login_attempts

    def test_removes_expired_locked_records(self):
        """Locked records whose lockout has expired should be removed."""
        now = datetime.now(timezone.utc)

        # Expired lock - should be cleaned
        _login_attempts["expired:exp@test.com"] = {
            "attempts": LOGIN_MAX_ATTEMPTS,
            "last_attempt": now - timedelta(minutes=20),
            "locked_until": now - timedelta(minutes=1),  # Lock expired 1 min ago
        }
        # Active lock - should be kept
        _login_attempts["active:act@test.com"] = {
            "attempts": LOGIN_MAX_ATTEMPTS,
            "last_attempt": now,
            "locked_until": now + timedelta(minutes=10),  # Still locked
        }

        cleanup_old_login_attempts()

        assert "expired:exp@test.com" not in _login_attempts
        assert "active:act@test.com" in _login_attempts

    def test_keeps_recent_unlocked_records(self):
        """Recent unlocked records should not be removed."""
        now = datetime.now(timezone.utc)

        _login_attempts["recent:r@test.com"] = {
            "attempts": 3,
            "last_attempt": now - timedelta(minutes=2),
            "locked_until": None,
        }

        cleanup_old_login_attempts()
        assert "recent:r@test.com" in _login_attempts

    def test_empty_dict_no_error(self):
        """Cleanup on an empty dict should not raise an error."""
        _login_attempts.clear()
        cleanup_old_login_attempts()
        assert len(_login_attempts) == 0

    def test_keeps_records_with_locked_until_none_but_recent(self):
        """Records with no lockout but recent last_attempt should be kept."""
        now = datetime.now(timezone.utc)

        _login_attempts["keep:k@test.com"] = {
            "attempts": 4,
            "last_attempt": now,
            "locked_until": None,
        }

        cleanup_old_login_attempts()
        assert "keep:k@test.com" in _login_attempts

    def test_removes_multiple_expired_records(self):
        """Multiple expired records should all be removed in one call."""
        now = datetime.now(timezone.utc)
        expiry_time = LOGIN_LOCKOUT_MINUTES + LOGIN_ATTEMPT_WINDOW_MINUTES

        for i in range(5):
            _login_attempts[f"old{i}:o{i}@test.com"] = {
                "attempts": 1,
                "last_attempt": now - timedelta(minutes=expiry_time + 10 + i),
                "locked_until": None,
            }

        # Add one fresh record to keep
        _login_attempts["fresh:f@test.com"] = {
            "attempts": 1,
            "last_attempt": now,
            "locked_until": None,
        }

        cleanup_old_login_attempts()

        assert len(_login_attempts) == 1
        assert "fresh:f@test.com" in _login_attempts


# ==================== INTEGRATION: Full login flow ====================

class TestLoginFlowIntegration:
    """Integration tests combining multiple rate-limiting functions."""

    def test_full_lockout_and_recovery_flow(self):
        """Test complete flow: attempts -> lockout -> expiry -> recovery."""
        ip = "100.0.0.1"
        email = "flow@test.com"

        # Step 1: Verify first attempt is allowed
        allowed, msg = check_login_rate_limit(ip, email)
        assert allowed is True

        # Step 2: Record max failed attempts
        for i in range(LOGIN_MAX_ATTEMPTS):
            record_failed_login(ip, email)

        # Step 3: Next check triggers lockout
        allowed, msg = check_login_rate_limit(ip, email)
        assert allowed is False
        assert "Too many failed attempts" in msg

        # Step 4: Simulate lockout expiry by backdating locked_until
        key = f"{ip}:{email}"
        _login_attempts[key]["locked_until"] = datetime.now(timezone.utc) - timedelta(minutes=1)

        # Step 5: Should be allowed again (lock expired)
        allowed, msg = check_login_rate_limit(ip, email)
        assert allowed is True
        assert key not in _login_attempts

    def test_successful_login_clears_attempts(self):
        """After a successful login, attempts should be cleared."""
        ip = "100.0.0.2"
        email = "success@test.com"
        key = f"{ip}:{email}"

        # Record some failed attempts
        for _ in range(3):
            record_failed_login(ip, email)

        assert key in _login_attempts
        assert _login_attempts[key]["attempts"] == 3

        # Successful login clears attempts
        clear_login_attempts(ip, email)
        assert key not in _login_attempts

        # Should be able to fail again from 0
        record_failed_login(ip, email)
        assert _login_attempts[key]["attempts"] == 1

    def test_cleanup_after_lockout_and_expiry(self):
        """Cleanup should remove records after lockout expires."""
        ip = "100.0.0.3"
        email = "cleanup@test.com"
        key = f"{ip}:{email}"
        now = datetime.now(timezone.utc)

        # Create an expired lockout record
        _login_attempts[key] = {
            "attempts": LOGIN_MAX_ATTEMPTS,
            "last_attempt": now - timedelta(minutes=30),
            "locked_until": now - timedelta(minutes=5),
        }

        cleanup_old_login_attempts()
        assert key not in _login_attempts


# ==================== Edge cases and robustness ====================

class TestEdgeCases:
    """Edge case tests for robustness."""

    async def test_get_current_user_propagates_db_error(self, initialized_db, mock_request):
        """If DB raises an unexpected error, it should propagate (not be caught)."""
        token = make_valid_token("user-edge")
        mock_request.headers = {"Authorization": f"Bearer {token}"}
        initialized_db.users.find_one = AsyncMock(side_effect=Exception("DB connection lost"))

        with pytest.raises(Exception, match="DB connection lost"):
            await get_current_user(mock_request)

    def test_get_campus_filter_with_no_role_key(self):
        """User dict without a role key should get impossible filter."""
        user_no_role = {"id": "norole-001", "campus_id": "campus-001"}
        result = get_campus_filter(user_no_role)
        # role is None, which != FULL_ADMIN, and campus_id exists, so scoped filter
        assert result == {"campus_id": "campus-001"}

    def test_get_campus_filter_empty_dict(self):
        """An empty user dict should get impossible filter."""
        result = get_campus_filter({})
        assert result == {"campus_id": {"$exists": False, "$eq": "IMPOSSIBLE_VALUE"}}

    def test_verify_password_with_special_characters(self):
        """Passwords with special characters should work."""
        password = "p@$$w0rd!#%^&*()_+-=[]{}|;':\",./<>?"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True

    def test_create_access_token_with_zero_expiry(self, initialized_db):
        """Token with zero timedelta should expire immediately."""
        import jwt as pyjwt

        token = create_access_token({"sub": "zero"}, expires_delta=timedelta(seconds=0))
        # Token should be valid (just barely)
        payload = pyjwt.decode(token, TEST_SECRET_KEY, algorithms=["HS256"],
                               options={"verify_exp": False})
        assert payload["sub"] == "zero"

    def test_rate_limit_with_special_chars_in_email(self):
        """Emails with special characters should be handled correctly."""
        ip = "50.0.0.1"
        email = "user+tag@sub.domain.com"
        record_failed_login(ip, email)
        assert f"{ip}:{email}" in _login_attempts

    def test_concurrent_rate_limit_scenario(self):
        """Multiple IPs hitting the same email should each have independent tracking."""
        email = "popular@test.com"
        ips = [f"10.0.{i}.1" for i in range(10)]

        # Each IP records 3 failed attempts
        for ip in ips:
            for _ in range(3):
                record_failed_login(ip, email)

        # All should still be allowed (under limit)
        for ip in ips:
            allowed, msg = check_login_rate_limit(ip, email)
            assert allowed is True

        # Now push one IP over the limit
        for _ in range(2):
            record_failed_login(ips[0], email)

        allowed, msg = check_login_rate_limit(ips[0], email)
        assert allowed is False

        # Others should still be fine
        for ip in ips[1:]:
            allowed, msg = check_login_rate_limit(ip, email)
            assert allowed is True
