"""
Tests targeting the largest uncovered blocks in server.py to push coverage from 78.2% to 80%+.

Covers:
- perform_member_sync_for_campus() (~430 stmts)
- _compute_monthly_report_data() (~160 stmts)
- sync_members_pull / discover_fields / test_connection (~250 stmts)
- import_from_external_api / import CSV / import JSON / export CSV (~185 stmts)
- process_webhook_member (~115 stmts)
- get_staff_performance() (~50 stmts)
- get_yearly_summary() (~30 stmts)
- overdue writeoff / automation / grief stages / accident followup settings
- notification log endpoints
- PDF report generation
- SSE stream_activity
"""

import pytest
import os
import sys
import uuid
import json
import io
import csv
import hashlib
import hmac as hmac_mod
import asyncio
from datetime import datetime, timezone, timedelta, date
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from enum import Enum

# Set env vars BEFORE any imports that read them
os.environ.update({
    'MONGO_URL': 'mongodb://mock:27017',
    'DB_NAME': 'faithtracker_test',
    'JWT_SECRET_KEY': 'test-secret-key-1234567890abcdef1234567890abcdef',
    'ENCRYPTION_KEY': 'cc7F8DmC4HF2hXLZxWIwZPitOgPS9Ybza0pl2_U0luQ=',
    'DRAGONFLY_URL': 'redis://mock:6379',
    'FRONTEND_URL': 'http://localhost:3000',
    'ALLOWED_ORIGINS': 'http://localhost:3000',
    'ENVIRONMENT': 'development',
})

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bcrypt
import jwt as pyjwt
from bson import ObjectId

# ==================== TEST CONSTANTS ====================

TEST_SECRET = os.environ['JWT_SECRET_KEY']
TEST_CAMPUS_ID = str(uuid.uuid4())
TEST_USER_ID = str(uuid.uuid4())
TEST_MEMBER_ID = str(uuid.uuid4())

HASHED_PASSWORD = bcrypt.hashpw(b"TestPassword123!", bcrypt.gensalt()).decode('utf-8')


# ==================== MOCK HELPERS ====================

def _make_mock_cursor(data=None):
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=data or [])
    cursor.sort = MagicMock(return_value=cursor)
    cursor.skip = MagicMock(return_value=cursor)
    cursor.limit = MagicMock(return_value=cursor)
    return cursor


def _make_mock_agg_cursor(data=None):
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=data or [])
    return cursor


def _make_update_result(matched=1, modified=1):
    result = MagicMock()
    result.matched_count = matched
    result.modified_count = modified
    return result


def _make_delete_result(deleted=1):
    result = MagicMock()
    result.deleted_count = deleted
    return result


def _make_insert_result(inserted_id="mock_id"):
    result = MagicMock()
    result.inserted_id = inserted_id
    return result


def _make_admin_user(**overrides):
    data = {
        "id": TEST_USER_ID,
        "email": "admin@test.com",
        "name": "Test Admin",
        "role": "full_admin",
        "campus_id": TEST_CAMPUS_ID,
        "phone": "+6281234567890",
        "hashed_password": HASHED_PASSWORD,
        "is_active": True,
    }
    data.update(overrides)
    return data


def _make_campus_admin_user(**overrides):
    data = {
        "id": str(uuid.uuid4()),
        "email": "campus_admin@test.com",
        "name": "Campus Admin",
        "role": "campus_admin",
        "campus_id": TEST_CAMPUS_ID,
        "phone": "+6281234567891",
        "hashed_password": HASHED_PASSWORD,
        "is_active": True,
    }
    data.update(overrides)
    return data


def _make_token(user_id=TEST_USER_ID, secret=TEST_SECRET, **extra):
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
        **extra,
    }
    return pyjwt.encode(payload, secret, algorithm="HS256")


def _mock_request(user=None, headers=None, body=None, json_data=None, scope=None):
    """Create a mock Litestar Request."""
    req = MagicMock()
    if user:
        token = _make_token(user["id"])
        h = {"Authorization": f"Bearer {token}"}
    else:
        h = {}
    if headers:
        h.update(headers)
    req.headers = h
    req.body = AsyncMock(return_value=body or b'{}')
    req.json = AsyncMock(return_value=json_data or {})
    req.method = "GET"
    req.url = MagicMock()
    req.url.path = "/api/test"
    req.scope = scope or {"client": ("127.0.0.1", 12345)}
    return req


def _make_mock_httpx_response(status_code=200, json_data=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json = MagicMock(return_value=json_data or {})
    resp.text = text
    return resp


@pytest.fixture(autouse=True)
def _reset_caches():
    from utils import invalidate_cache
    invalidate_cache()
    yield


@pytest.fixture
def mock_db():
    db = MagicMock()
    for collection_name in [
        'users', 'members', 'campuses', 'care_events', 'settings',
        'activity_logs', 'notification_logs', 'grief_support',
        'accident_followup', 'financial_aid_schedules', 'sync_configs',
        'sync_logs', 'webhook_logs', 'user_preferences', 'dashboard_cache',
        'pastoral_notes',
    ]:
        coll = MagicMock()
        coll.find_one = AsyncMock(return_value=None)
        coll.insert_one = AsyncMock(return_value=_make_insert_result())
        coll.insert_many = AsyncMock()
        coll.update_one = AsyncMock(return_value=_make_update_result())
        coll.delete_one = AsyncMock(return_value=_make_delete_result())
        coll.delete_many = AsyncMock(return_value=_make_delete_result())
        coll.count_documents = AsyncMock(return_value=0)
        coll.find = MagicMock(return_value=_make_mock_cursor())
        coll.aggregate = MagicMock(return_value=_make_mock_agg_cursor())
        setattr(db, collection_name, coll)
    return db


@pytest.fixture
def setup_server(mock_db):
    """Patch server.db and init dependencies."""
    import server
    from dependencies import init_dependencies

    original_db = server.db
    server.db = mock_db
    init_dependencies(mock_db, TEST_SECRET)
    yield server
    server.db = original_db


# ==================== 1. perform_member_sync_for_campus TESTS ====================

class TestPerformMemberSyncForCampus:
    """Tests for the biggest uncovered function (~430 stmts)."""

    @pytest.mark.asyncio
    async def test_sync_disabled(self, setup_server, mock_db):
        """Sync not configured or not enabled returns error."""
        mock_db.sync_configs.find_one = AsyncMock(return_value=None)
        result = await setup_server.perform_member_sync_for_campus(TEST_CAMPUS_ID)
        assert result["success"] is False
        assert "not configured" in result["error"]

    @pytest.mark.asyncio
    async def test_sync_disabled_flag(self, setup_server, mock_db):
        """Sync config exists but is_enabled=False."""
        mock_db.sync_configs.find_one = AsyncMock(return_value={
            "campus_id": TEST_CAMPUS_ID,
            "is_enabled": False,
        })
        result = await setup_server.perform_member_sync_for_campus(TEST_CAMPUS_ID)
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_sync_login_failure(self, setup_server, mock_db):
        """API login returns non-200."""
        encrypted_pwd = setup_server.encrypt_password("test123")
        mock_db.sync_configs.find_one = AsyncMock(return_value={
            "campus_id": TEST_CAMPUS_ID,
            "is_enabled": True,
            "api_base_url": "https://core.example.com",
            "api_path_prefix": "/api",
            "api_email": "sync@test.com",
            "api_password": encrypted_pwd,
        })
        mock_db.members.find = MagicMock(return_value=_make_mock_cursor([]))

        login_resp = _make_mock_httpx_response(401, text="Unauthorized")

        with patch('httpx.AsyncClient') as mock_httpx:
            mock_client = AsyncMock()
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=login_resp)

            result = await setup_server.perform_member_sync_for_campus(TEST_CAMPUS_ID)
            assert result["success"] is False
            assert "Login failed" in result.get("error", "")

    @pytest.mark.asyncio
    async def test_sync_successful_create_and_update(self, setup_server, mock_db):
        """Successful sync: creates new members, updates existing ones."""
        encrypted_pwd = setup_server.encrypt_password("test123")
        mock_db.sync_configs.find_one = AsyncMock(return_value={
            "campus_id": TEST_CAMPUS_ID,
            "is_enabled": True,
            "api_base_url": "https://core.example.com",
            "api_path_prefix": "/api",
            "api_email": "sync@test.com",
            "api_password": encrypted_pwd,
            "filter_mode": "include",
            "filter_rules": [],
        })

        existing_member = {
            "id": "local-1",
            "external_member_id": "core-1",
            "name": "Existing Member",
            "phone": "+6281111111111",
            "campus_id": TEST_CAMPUS_ID,
            "is_archived": False,
        }
        mock_db.members.find = MagicMock(return_value=_make_mock_cursor([existing_member]))

        core_members = [
            {
                "id": "core-1",
                "full_name": "Existing Member Updated",
                "phone": "+6281111111111",
                "date_of_birth": "1990-05-15",
                "gender": "Male",
                "is_active": True,
            },
            {
                "id": "core-2",
                "full_name": "New Member",
                "phone": "+6282222222222",
                "date_of_birth": "1985-03-20",
                "gender": "Female",
                "is_active": True,
            },
        ]

        login_resp = _make_mock_httpx_response(200, {"access_token": "fake-token"})
        members_resp = _make_mock_httpx_response(200, core_members)

        with patch('httpx.AsyncClient') as mock_httpx:
            mock_client = AsyncMock()
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=login_resp)
            mock_client.get = AsyncMock(return_value=members_resp)

            result = await setup_server.perform_member_sync_for_campus(TEST_CAMPUS_ID)
            assert result["success"] is True
            assert result["stats"]["created"] >= 1

    @pytest.mark.asyncio
    async def test_sync_with_filter_rules(self, setup_server, mock_db):
        """Sync applies dynamic filter rules correctly."""
        encrypted_pwd = setup_server.encrypt_password("test123")
        mock_db.sync_configs.find_one = AsyncMock(return_value={
            "campus_id": TEST_CAMPUS_ID,
            "is_enabled": True,
            "api_base_url": "https://core.example.com",
            "api_path_prefix": "/api",
            "api_email": "sync@test.com",
            "api_password": encrypted_pwd,
            "filter_mode": "include",
            "filter_rules": [
                {"field": "gender", "operator": "equals", "value": "Female"},
            ],
        })
        mock_db.members.find = MagicMock(return_value=_make_mock_cursor([]))

        core_members = [
            {"id": "c1", "full_name": "Male Member", "gender": "Male", "is_active": True},
            {"id": "c2", "full_name": "Female Member", "gender": "Female", "is_active": True},
        ]

        login_resp = _make_mock_httpx_response(200, {"access_token": "fake-token"})
        members_resp = _make_mock_httpx_response(200, core_members)

        with patch('httpx.AsyncClient') as mock_httpx:
            mock_client = AsyncMock()
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=login_resp)
            mock_client.get = AsyncMock(return_value=members_resp)

            result = await setup_server.perform_member_sync_for_campus(TEST_CAMPUS_ID)
            assert result["success"] is True
            assert result["stats"]["created"] == 1

    @pytest.mark.asyncio
    async def test_sync_exclude_filter_mode(self, setup_server, mock_db):
        """Test exclude filter mode."""
        encrypted_pwd = setup_server.encrypt_password("test123")
        mock_db.sync_configs.find_one = AsyncMock(return_value={
            "campus_id": TEST_CAMPUS_ID,
            "is_enabled": True,
            "api_base_url": "https://core.example.com",
            "api_path_prefix": "/api",
            "api_email": "sync@test.com",
            "api_password": encrypted_pwd,
            "filter_mode": "exclude",
            "filter_rules": [
                {"field": "gender", "operator": "equals", "value": "Male"},
            ],
        })
        mock_db.members.find = MagicMock(return_value=_make_mock_cursor([]))

        core_members = [
            {"id": "c1", "full_name": "Male Member", "gender": "Male", "is_active": True},
            {"id": "c2", "full_name": "Female Member", "gender": "Female", "is_active": True},
        ]

        login_resp = _make_mock_httpx_response(200, {"access_token": "fake-token"})
        members_resp = _make_mock_httpx_response(200, core_members)

        with patch('httpx.AsyncClient') as mock_httpx:
            mock_client = AsyncMock()
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=login_resp)
            mock_client.get = AsyncMock(return_value=members_resp)

            result = await setup_server.perform_member_sync_for_campus(TEST_CAMPUS_ID)
            assert result["success"] is True
            assert result["stats"]["created"] == 1

    @pytest.mark.asyncio
    async def test_sync_archives_members_not_in_source(self, setup_server, mock_db):
        """Members in DB but not in API source get archived."""
        encrypted_pwd = setup_server.encrypt_password("test123")
        mock_db.sync_configs.find_one = AsyncMock(return_value={
            "campus_id": TEST_CAMPUS_ID,
            "is_enabled": True,
            "api_base_url": "https://core.example.com",
            "api_path_prefix": "/api",
            "api_email": "sync@test.com",
            "api_password": encrypted_pwd,
            "filter_mode": "include",
            "filter_rules": [],
        })

        existing = {
            "id": "local-orphan",
            "external_member_id": "orphan-id",
            "name": "Orphan Member",
            "campus_id": TEST_CAMPUS_ID,
            "is_archived": False,
        }
        mock_db.members.find = MagicMock(return_value=_make_mock_cursor([existing]))

        login_resp = _make_mock_httpx_response(200, {"access_token": "fake-token"})
        members_resp = _make_mock_httpx_response(200, [])

        with patch('httpx.AsyncClient') as mock_httpx:
            mock_client = AsyncMock()
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=login_resp)
            mock_client.get = AsyncMock(return_value=members_resp)

            result = await setup_server.perform_member_sync_for_campus(TEST_CAMPUS_ID)
            assert result["success"] is True
            assert result["stats"]["archived"] >= 1

    @pytest.mark.asyncio
    async def test_sync_network_error(self, setup_server, mock_db):
        """Network error during sync is handled gracefully."""
        import httpx as httpx_mod
        encrypted_pwd = setup_server.encrypt_password("test123")
        mock_db.sync_configs.find_one = AsyncMock(return_value={
            "campus_id": TEST_CAMPUS_ID,
            "is_enabled": True,
            "api_base_url": "https://core.example.com",
            "api_path_prefix": "/api",
            "api_email": "sync@test.com",
            "api_password": encrypted_pwd,
        })

        with patch('httpx.AsyncClient') as mock_httpx:
            mock_client = AsyncMock()
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(side_effect=httpx_mod.ConnectError("Connection refused"))

            result = await setup_server.perform_member_sync_for_campus(TEST_CAMPUS_ID)
            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_sync_paginated_response(self, setup_server, mock_db):
        """Sync handles paginated API responses (dict with data key)."""
        encrypted_pwd = setup_server.encrypt_password("test123")
        mock_db.sync_configs.find_one = AsyncMock(return_value={
            "campus_id": TEST_CAMPUS_ID,
            "is_enabled": True,
            "api_base_url": "https://core.example.com",
            "api_path_prefix": "/api",
            "api_email": "sync@test.com",
            "api_password": encrypted_pwd,
            "filter_mode": "include",
            "filter_rules": [],
        })
        mock_db.members.find = MagicMock(return_value=_make_mock_cursor([]))

        login_resp = _make_mock_httpx_response(200, {"access_token": "fake-token"})
        page1 = _make_mock_httpx_response(200, {
            "data": [{"id": "c1", "full_name": "Member 1", "is_active": True}],
            "pagination": {"has_more": False}
        })

        with patch('httpx.AsyncClient') as mock_httpx:
            mock_client = AsyncMock()
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=login_resp)
            mock_client.get = AsyncMock(return_value=page1)

            result = await setup_server.perform_member_sync_for_campus(TEST_CAMPUS_ID)
            assert result["success"] is True
            assert result["stats"]["created"] == 1

    @pytest.mark.asyncio
    async def test_sync_with_contains_filter(self, setup_server, mock_db):
        """Test contains filter operator."""
        encrypted_pwd = setup_server.encrypt_password("test123")
        mock_db.sync_configs.find_one = AsyncMock(return_value={
            "campus_id": TEST_CAMPUS_ID,
            "is_enabled": True,
            "api_base_url": "https://core.example.com",
            "api_path_prefix": "/api",
            "api_email": "sync@test.com",
            "api_password": encrypted_pwd,
            "filter_mode": "include",
            "filter_rules": [
                {"field": "name", "operator": "contains", "value": "John"},
            ],
        })
        mock_db.members.find = MagicMock(return_value=_make_mock_cursor([]))

        core_members = [
            {"id": "c1", "full_name": "John Doe", "name": "John Doe", "is_active": True},
            {"id": "c2", "full_name": "Jane Smith", "name": "Jane Smith", "is_active": True},
        ]

        login_resp = _make_mock_httpx_response(200, {"access_token": "fake-token"})
        members_resp = _make_mock_httpx_response(200, core_members)

        with patch('httpx.AsyncClient') as mock_httpx:
            mock_client = AsyncMock()
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=login_resp)
            mock_client.get = AsyncMock(return_value=members_resp)

            result = await setup_server.perform_member_sync_for_campus(TEST_CAMPUS_ID)
            assert result["success"] is True
            assert result["stats"]["created"] == 1

    @pytest.mark.asyncio
    async def test_sync_member_with_photo_url(self, setup_server, mock_db):
        """Sync handles external photo URLs."""
        encrypted_pwd = setup_server.encrypt_password("test123")
        mock_db.sync_configs.find_one = AsyncMock(return_value={
            "campus_id": TEST_CAMPUS_ID,
            "is_enabled": True,
            "api_base_url": "https://core.example.com",
            "api_path_prefix": "/api",
            "api_email": "sync@test.com",
            "api_password": encrypted_pwd,
            "filter_mode": "include",
            "filter_rules": [],
        })
        mock_db.members.find = MagicMock(return_value=_make_mock_cursor([]))

        core_members = [
            {
                "id": "c1",
                "full_name": "Photo Member",
                "photo_url": "https://cdn.example.com/photo.jpg",
                "date_of_birth": "1990-01-01",
                "is_active": True,
            },
        ]

        login_resp = _make_mock_httpx_response(200, {"access_token": "fake-token"})
        members_resp = _make_mock_httpx_response(200, core_members)

        with patch('httpx.AsyncClient') as mock_httpx:
            mock_client = AsyncMock()
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=login_resp)
            mock_client.get = AsyncMock(return_value=members_resp)

            result = await setup_server.perform_member_sync_for_campus(TEST_CAMPUS_ID)
            assert result["success"] is True
            assert result["stats"]["created"] == 1

    @pytest.mark.asyncio
    async def test_sync_archive_inactive_existing_member(self, setup_server, mock_db):
        """Existing member marked inactive in core gets archived locally."""
        encrypted_pwd = setup_server.encrypt_password("test123")
        mock_db.sync_configs.find_one = AsyncMock(return_value={
            "campus_id": TEST_CAMPUS_ID,
            "is_enabled": True,
            "api_base_url": "https://core.example.com",
            "api_path_prefix": "/api",
            "api_email": "sync@test.com",
            "api_password": encrypted_pwd,
            "filter_mode": "include",
            "filter_rules": [],
        })

        existing = {
            "id": "local-1",
            "external_member_id": "core-1",
            "name": "Active Member",
            "campus_id": TEST_CAMPUS_ID,
            "is_archived": False,
        }
        mock_db.members.find = MagicMock(return_value=_make_mock_cursor([existing]))

        core_members = [
            {"id": "core-1", "full_name": "Active Member", "is_active": False},
        ]

        login_resp = _make_mock_httpx_response(200, {"access_token": "fake-token"})
        members_resp = _make_mock_httpx_response(200, core_members)

        with patch('httpx.AsyncClient') as mock_httpx:
            mock_client = AsyncMock()
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=login_resp)
            mock_client.get = AsyncMock(return_value=members_resp)

            result = await setup_server.perform_member_sync_for_campus(TEST_CAMPUS_ID)
            assert result["success"] is True
            assert result["stats"]["archived"] >= 1

    @pytest.mark.asyncio
    async def test_sync_unarchive_reactivated_member(self, setup_server, mock_db):
        """Archived member that becomes active in core gets unarchived."""
        encrypted_pwd = setup_server.encrypt_password("test123")
        mock_db.sync_configs.find_one = AsyncMock(return_value={
            "campus_id": TEST_CAMPUS_ID,
            "is_enabled": True,
            "api_base_url": "https://core.example.com",
            "api_path_prefix": "/api",
            "api_email": "sync@test.com",
            "api_password": encrypted_pwd,
            "filter_mode": "include",
            "filter_rules": [],
        })

        existing = {
            "id": "local-1",
            "external_member_id": "core-1",
            "name": "Archived Member",
            "campus_id": TEST_CAMPUS_ID,
            "is_archived": True,
        }
        mock_db.members.find = MagicMock(return_value=_make_mock_cursor([existing]))

        core_members = [
            {"id": "core-1", "full_name": "Archived Member", "is_active": True},
        ]

        login_resp = _make_mock_httpx_response(200, {"access_token": "fake-token"})
        members_resp = _make_mock_httpx_response(200, core_members)

        with patch('httpx.AsyncClient') as mock_httpx:
            mock_client = AsyncMock()
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=login_resp)
            mock_client.get = AsyncMock(return_value=members_resp)

            result = await setup_server.perform_member_sync_for_campus(TEST_CAMPUS_ID)
            assert result["success"] is True
            assert result["stats"]["unarchived"] >= 1


# ==================== 2. _compute_monthly_report_data TESTS ====================

class TestComputeMonthlyReportData:
    """Tests for monthly management report data (~160 stmts)."""

    def _setup_empty_db(self, mock_db):
        """Set up mock DB that returns at least 1 member to avoid div-by-zero."""
        members = [{"id": "m1", "engagement_status": "active", "days_since_last_contact": 5,
                     "last_contact_date": datetime.now(timezone.utc).isoformat()}]
        mock_db.members.find = MagicMock(return_value=_make_mock_cursor(members))
        mock_db.care_events.find = MagicMock(return_value=_make_mock_cursor([]))
        mock_db.activity_logs.find = MagicMock(return_value=_make_mock_cursor([]))

    @pytest.mark.asyncio
    async def test_minimal_data(self, setup_server, mock_db):
        """Report with minimal data returns valid structure."""
        user = _make_admin_user()
        self._setup_empty_db(mock_db)

        result = await setup_server._compute_monthly_report_data(user, 2024, 6)

        assert "report_period" in result
        assert result["report_period"]["year"] == 2024
        assert result["report_period"]["month"] == 6
        assert "executive_summary" in result
        assert result["executive_summary"]["total_members"] == 1
        assert "kpis" in result
        assert "insights" in result

    @pytest.mark.asyncio
    async def test_month_with_data(self, setup_server, mock_db):
        """Month with members, events, and activities."""
        user = _make_admin_user()

        members = [
            {"id": "m1", "name": "A", "engagement_status": "active", "days_since_last_contact": 5,
             "last_contact_date": datetime.now(timezone.utc).isoformat(), "gender": "Male", "age": 30},
            {"id": "m2", "name": "B", "engagement_status": "at_risk", "days_since_last_contact": 70,
             "last_contact_date": None, "gender": "Female", "age": 50},
            {"id": "m3", "name": "C", "engagement_status": "disconnected", "days_since_last_contact": 100,
             "last_contact_date": None, "gender": "Male", "age": 40},
        ]

        events = [
            {"id": "e1", "event_type": "birthday", "event_date": "2024-06-15",
             "completed": True, "ignored": False, "member_id": "m1",
             "completed_at": datetime(2024, 6, 15, tzinfo=timezone.utc)},
            {"id": "e2", "event_type": "grief_loss", "event_date": "2024-06-10",
             "completed": False, "ignored": False, "member_id": "m2"},
            {"id": "e3", "event_type": "accident_illness", "event_date": "2024-06-20",
             "completed": True, "ignored": False, "member_id": "m1"},
            {"id": "e4", "event_type": "financial_aid", "event_date": "2024-06-05",
             "completed": True, "ignored": False, "member_id": "m3", "aid_amount": 500000},
        ]

        activities = [
            {"user_id": "u1", "user_name": "Staff A", "action_type": "complete_task",
             "member_id": "m1", "created_at": datetime(2024, 6, 15, tzinfo=timezone.utc)},
            {"user_id": "u1", "user_name": "Staff A", "action_type": "create_care_event",
             "member_id": "m2", "created_at": datetime(2024, 6, 10, tzinfo=timezone.utc)},
        ]

        call_count = [0]
        def mock_events_find(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 2:
                return _make_mock_cursor(events)
            return _make_mock_cursor([])

        mock_db.members.find = MagicMock(return_value=_make_mock_cursor(members))
        mock_db.care_events.find = mock_events_find
        mock_db.activity_logs.find = MagicMock(return_value=_make_mock_cursor(activities))
        mock_db.grief_support.count_documents = AsyncMock(return_value=2)
        mock_db.accident_followup.count_documents = AsyncMock(return_value=1)

        result = await setup_server._compute_monthly_report_data(user, 2024, 6)

        assert result["executive_summary"]["total_members"] == 3
        assert result["executive_summary"]["total_care_events"] == 4
        assert "ministry_highlights" in result
        assert "comparison" in result

    @pytest.mark.asyncio
    async def test_december_boundary(self, setup_server, mock_db):
        """December month correctly computes end date as Jan next year."""
        user = _make_admin_user()
        self._setup_empty_db(mock_db)

        result = await setup_server._compute_monthly_report_data(user, 2024, 12)
        assert result["report_period"]["month"] == 12

    @pytest.mark.asyncio
    async def test_january_boundary(self, setup_server, mock_db):
        """January correctly gets previous month as December of prior year."""
        user = _make_admin_user()
        self._setup_empty_db(mock_db)

        result = await setup_server._compute_monthly_report_data(user, 2024, 1)
        assert result["report_period"]["month"] == 1


# ==================== 3. get_staff_performance_report TESTS ====================

class TestStaffPerformance:
    """Tests for staff performance report (~150 stmts)."""

    @pytest.mark.asyncio
    async def test_staff_report_with_data(self, setup_server, mock_db):
        """Staff performance with multiple action types."""
        user = _make_admin_user()
        request = _mock_request(user=user)

        mock_db.users.find_one = AsyncMock(return_value=user)
        mock_db.users.find = MagicMock(return_value=_make_mock_cursor([
            {"id": "u1", "name": "Staff A", "email": "a@t.com", "role": "pastor", "photo_url": None},
            {"id": "u2", "name": "Staff B", "email": "b@t.com", "role": "pastor", "photo_url": None},
        ]))

        activities = [
            {"user_id": "u1", "user_name": "Staff A", "action_type": "complete_task",
             "member_id": "m1", "event_type": "birthday", "created_at": datetime(2024, 6, 5, tzinfo=timezone.utc)},
            {"user_id": "u1", "user_name": "Staff A", "action_type": "complete_task",
             "member_id": "m2", "event_type": "birthday", "created_at": datetime(2024, 6, 6, tzinfo=timezone.utc)},
            {"user_id": "u1", "user_name": "Staff A", "action_type": "ignore_task",
             "created_at": datetime(2024, 6, 7, tzinfo=timezone.utc)},
            {"user_id": "u1", "user_name": "Staff A", "action_type": "create_care_event",
             "created_at": datetime(2024, 6, 8, tzinfo=timezone.utc)},
            {"user_id": "u1", "user_name": "Staff A", "action_type": "create_member",
             "created_at": datetime(2024, 6, 9, tzinfo=timezone.utc)},
            {"user_id": "u1", "user_name": "Staff A", "action_type": "update_member",
             "created_at": datetime(2024, 6, 10, tzinfo=timezone.utc)},
            {"user_id": "u1", "user_name": "Staff A", "action_type": "send_reminder",
             "created_at": datetime(2024, 6, 11, tzinfo=timezone.utc)},
            # Unknown user in activities (covers the "user not in staff_data" branch)
            {"user_id": "u3", "user_name": "Ghost Staff", "action_type": "complete_task",
             "member_id": "m5", "created_at": "2024-06-12T10:00:00"},
        ]
        mock_db.activity_logs.find = MagicMock(return_value=_make_mock_cursor(activities))

        result = await setup_server.get_staff_performance_report.fn(request=request, year=2024, month=6)

        assert "team_stats" in result
        assert "staff_performance" in result
        assert result["team_stats"]["total_staff"] >= 2
        assert "workload_distribution" in result
        assert "recommendations" in result

    @pytest.mark.asyncio
    async def test_staff_report_empty(self, setup_server, mock_db):
        """Staff performance with no data."""
        user = _make_admin_user()
        request = _mock_request(user=user)
        mock_db.users.find_one = AsyncMock(return_value=user)
        mock_db.users.find = MagicMock(return_value=_make_mock_cursor([]))
        mock_db.activity_logs.find = MagicMock(return_value=_make_mock_cursor([]))

        result = await setup_server.get_staff_performance_report.fn(request=request)
        assert result["team_stats"]["total_staff"] == 0


# ==================== 4. get_yearly_summary_report TESTS ====================

class TestYearlySummary:
    """Tests for yearly summary report."""

    @pytest.mark.asyncio
    async def test_yearly_summary_with_events(self, setup_server, mock_db):
        """Yearly summary with care events across months."""
        user = _make_admin_user()
        request = _mock_request(user=user)
        mock_db.users.find_one = AsyncMock(return_value=user)

        members = [
            {"id": "m1", "engagement_status": "active", "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc)},
        ]

        events = [
            {"event_type": "birthday", "event_date": "2024-01-15", "completed": True},
            {"event_type": "birthday", "event_date": "2024-02-20", "completed": False},
            {"event_type": "financial_aid", "event_date": "2024-03-10", "completed": True, "aid_amount": 1000000},
            {"event_type": "grief_loss", "event_date": "2024-06-01", "completed": True},
        ]

        mock_db.members.find = MagicMock(return_value=_make_mock_cursor(members))
        mock_db.care_events.find = MagicMock(return_value=_make_mock_cursor(events))

        result = await setup_server.get_yearly_summary_report.fn(request=request, year=2024)

        assert result["report_period"]["year"] == 2024
        assert result["yearly_totals"]["total_care_events"] == 4
        assert result["yearly_totals"]["total_financial_aid"] == 1000000
        assert len(result["monthly_breakdown"]) == 12

    @pytest.mark.asyncio
    async def test_yearly_summary_empty(self, setup_server, mock_db):
        """Yearly summary with no data."""
        user = _make_admin_user()
        request = _mock_request(user=user)
        mock_db.users.find_one = AsyncMock(return_value=user)
        mock_db.members.find = MagicMock(return_value=_make_mock_cursor([]))
        mock_db.care_events.find = MagicMock(return_value=_make_mock_cursor([]))

        result = await setup_server.get_yearly_summary_report.fn(request=request, year=2024)
        assert result["yearly_totals"]["total_care_events"] == 0


# ==================== 5. import/export TESTS ====================

class TestImportExport:
    """Tests for import CSV, import JSON, export CSV, import from external API."""

    @pytest.mark.asyncio
    async def test_import_from_external_api_success(self, setup_server, mock_db):
        """Import members from external API."""
        admin = _make_admin_user()
        request = _mock_request(user=admin)
        mock_db.users.find_one = AsyncMock(return_value=admin)

        external_members = [
            {"id": "ext1", "name": "Ext Member 1", "phone": "+621111", "birth_date": "1990-01-01",
             "address": "Addr 1", "membership_status": "baptized", "category": "youth", "gender": "Male"},
            {"id": "ext2", "name": "Ext Member 2", "phone": "+622222"},
        ]

        mock_db.members.find_one = AsyncMock(return_value=None)
        mock_db.members.find = MagicMock(return_value=_make_mock_cursor([]))

        mock_resp = _make_mock_httpx_response(200, external_members)

        with patch('httpx.AsyncClient') as mock_httpx:
            mock_client = AsyncMock()
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_resp)

            result = await setup_server.sync_members_from_external_api.fn(
                api_url="https://api.example.com/members",
                api_key="test-key",
                campus_id=TEST_CAMPUS_ID,
                request=request,
            )
            assert result["success"] is True
            assert result["synced_count"] == 2

    @pytest.mark.asyncio
    async def test_import_from_external_api_update_existing(self, setup_server, mock_db):
        """Import from API updates existing members and un-archives them."""
        admin = _make_admin_user()
        request = _mock_request(user=admin)
        mock_db.users.find_one = AsyncMock(return_value=admin)

        external_members = [
            {"id": "ext1", "name": "Updated Member", "phone": "+621111",
             "birth_date": "1990-01-01", "address": "New Addr", "gender": "Female",
             "membership_status": "baptized", "category": "adult"},
        ]

        mock_db.members.find_one = AsyncMock(return_value={
            "id": "local-1", "external_member_id": "ext1", "name": "Old Name",
            "is_archived": True,
        })
        mock_db.members.find = MagicMock(return_value=_make_mock_cursor([
            {"id": "local-1", "external_member_id": "ext1", "name": "Old Name"},
        ]))

        mock_resp = _make_mock_httpx_response(200, external_members)

        with patch('httpx.AsyncClient') as mock_httpx:
            mock_client = AsyncMock()
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_resp)

            result = await setup_server.sync_members_from_external_api.fn(
                api_url="https://api.example.com/members",
                request=request,
            )
            assert result["success"] is True
            assert result["updated_count"] == 1

    @pytest.mark.asyncio
    async def test_import_from_external_api_error(self, setup_server, mock_db):
        """Import from API handles HTTP error."""
        from litestar.exceptions import HTTPException
        admin = _make_admin_user()
        request = _mock_request(user=admin)
        mock_db.users.find_one = AsyncMock(return_value=admin)

        with patch('httpx.AsyncClient') as mock_httpx:
            mock_client = AsyncMock()
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=Exception("Connection failed"))

            with pytest.raises(HTTPException):
                await setup_server.sync_members_from_external_api.fn(
                    api_url="https://api.example.com/members",
                    request=request,
                )

    @pytest.mark.asyncio
    async def test_import_csv(self, setup_server, mock_db):
        """Import members from CSV file."""
        user = _make_admin_user()
        request = _mock_request(user=user)
        mock_db.users.find_one = AsyncMock(return_value=user)

        csv_content = "name,phone,external_member_id,notes\nJohn Doe,+621111,ext1,Note1\nJane Smith,+622222,,\n"

        mock_file = MagicMock()
        mock_file.read = AsyncMock(return_value=csv_content.encode('utf-8'))

        result = await setup_server.import_members_csv.fn(request=request, data=mock_file)
        assert result["success"] is True
        assert result["imported_count"] == 2

    @pytest.mark.asyncio
    async def test_import_csv_too_large(self, setup_server, mock_db):
        """CSV file exceeding size limit is rejected."""
        from litestar.exceptions import HTTPException
        user = _make_admin_user()
        request = _mock_request(user=user)
        mock_db.users.find_one = AsyncMock(return_value=user)

        mock_file = MagicMock()
        mock_file.read = AsyncMock(return_value=b"x" * (6 * 1024 * 1024))

        with pytest.raises(HTTPException) as exc_info:
            await setup_server.import_members_csv.fn(request=request, data=mock_file)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_import_csv_no_campus(self, setup_server, mock_db):
        """CSV import with no campus assigned."""
        from litestar.exceptions import HTTPException
        user = _make_admin_user(campus_id=None)
        request = _mock_request(user=user)
        mock_db.users.find_one = AsyncMock(return_value=user)

        mock_file = MagicMock()
        mock_file.read = AsyncMock(return_value=b"name,phone\nJohn,+621111\n")

        with pytest.raises(HTTPException) as exc_info:
            await setup_server.import_members_csv.fn(request=request, data=mock_file)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_import_json(self, setup_server, mock_db):
        """Import members from JSON array."""
        user = _make_admin_user()
        request = _mock_request(user=user)
        mock_db.users.find_one = AsyncMock(return_value=user)

        data = [
            {"name": "JSON Member 1", "phone": "+621111"},
            {"name": "JSON Member 2", "phone": "+622222", "external_member_id": "ext1"},
        ]

        result = await setup_server.import_members_json.fn(data=data, request=request)
        assert result["success"] is True
        assert result["imported_count"] == 2

    @pytest.mark.asyncio
    async def test_import_json_no_campus(self, setup_server, mock_db):
        """JSON import with no campus assigned."""
        from litestar.exceptions import HTTPException
        user = _make_admin_user(campus_id=None)
        request = _mock_request(user=user)
        mock_db.users.find_one = AsyncMock(return_value=user)

        with pytest.raises(HTTPException):
            await setup_server.import_members_json.fn(data=[{"name": "Test"}], request=request)

    @pytest.mark.asyncio
    async def test_export_members_csv(self, setup_server, mock_db):
        """Export members to CSV."""
        user = _make_admin_user()
        request = _mock_request(user=user)
        mock_db.users.find_one = AsyncMock(return_value=user)

        members = [
            {"id": "m1", "name": "Member 1", "phone": "+621111",
             "engagement_status": "active", "days_since_last_contact": 5,
             "last_contact_date": datetime.now(timezone.utc).isoformat()},
            {"id": "m2", "name": "Member 2", "phone": "+622222",
             "engagement_status": "disconnected", "days_since_last_contact": 100},
        ]
        mock_db.members.find = MagicMock(return_value=_make_mock_cursor(members))

        result = await setup_server.export_members_csv.fn(request=request)
        assert result.media_type == "text/csv"

    @pytest.mark.asyncio
    async def test_export_care_events_csv(self, setup_server, mock_db):
        """Export care events to CSV."""
        user = _make_admin_user()
        request = _mock_request(user=user)
        mock_db.users.find_one = AsyncMock(return_value=user)

        events = [
            {"id": "e1", "member_id": "m1", "event_type": "birthday",
             "event_date": "2024-06-15", "title": "Birthday", "completed": True},
        ]
        mock_db.care_events.find = MagicMock(return_value=_make_mock_cursor(events))

        result = await setup_server.export_care_events_csv.fn(request=request)
        assert result.media_type == "text/csv"


# ==================== 6. webhook processing TESTS ====================

class TestWebhookProcessing:
    """Tests for receive_sync_webhook and process_webhook_member (~115 stmts)."""

    @pytest.mark.asyncio
    async def test_webhook_missing_signature(self, setup_server, mock_db):
        """Webhook without signature is rejected."""
        from litestar.exceptions import HTTPException
        request = MagicMock()
        request.body = AsyncMock(return_value=b'{"event_type": "test"}')
        request.json = AsyncMock(return_value={"event_type": "test"})
        request.headers = {}
        request.scope = {"client": ("127.0.0.1", 12345)}

        with pytest.raises(HTTPException) as exc_info:
            await setup_server.receive_sync_webhook.fn(request)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_webhook_invalid_signature(self, setup_server, mock_db):
        """Webhook with invalid signature is rejected."""
        from litestar.exceptions import HTTPException
        payload = {"event_type": "member.created", "campus_id": TEST_CAMPUS_ID, "member_id": "m1"}
        body = json.dumps(payload).encode()

        mock_db.sync_configs.find_one = AsyncMock(return_value={
            "campus_id": TEST_CAMPUS_ID,
            "is_enabled": True,
            "webhook_secret": "real-secret",
        })

        request = MagicMock()
        request.body = AsyncMock(return_value=body)
        request.json = AsyncMock(return_value=payload)
        request.headers = {"X-Webhook-Signature": "wrong-signature"}
        request.scope = {"client": ("127.0.0.1", 12345)}

        with pytest.raises(HTTPException) as exc_info:
            await setup_server.receive_sync_webhook.fn(request)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_webhook_test_event(self, setup_server, mock_db):
        """Test/ping webhook event returns success."""
        payload = {"event_type": "test", "campus_id": TEST_CAMPUS_ID}
        body = json.dumps(payload).encode()
        secret = "test-webhook-secret"

        sig = hmac_mod.new(secret.encode(), body, hashlib.sha256).hexdigest()

        mock_db.sync_configs.find_one = AsyncMock(return_value={
            "campus_id": TEST_CAMPUS_ID,
            "is_enabled": True,
            "webhook_secret": secret,
        })

        request = MagicMock()
        request.body = AsyncMock(return_value=body)
        request.json = AsyncMock(return_value=payload)
        request.headers = {"X-Webhook-Signature": sig}
        request.scope = {"client": ("127.0.0.1", 12345)}

        result = await setup_server.receive_sync_webhook.fn(request)
        assert result["success"] is True
        assert "test successful" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_webhook_member_created(self, setup_server, mock_db):
        """Webhook creates a new member."""
        payload = {"event_type": "member.created", "campus_id": TEST_CAMPUS_ID, "member_id": "core-m1"}
        body = json.dumps(payload).encode()
        secret = "test-secret"
        sig = hmac_mod.new(secret.encode(), body, hashlib.sha256).hexdigest()

        encrypted_pwd = setup_server.encrypt_password("test123")
        config = {
            "campus_id": TEST_CAMPUS_ID,
            "is_enabled": True,
            "webhook_secret": secret,
            "api_base_url": "https://core.example.com",
            "api_path_prefix": "/api",
            "api_email": "sync@test.com",
            "api_password": encrypted_pwd,
        }
        mock_db.sync_configs.find_one = AsyncMock(return_value=config)
        mock_db.members.find_one = AsyncMock(return_value=None)

        request = MagicMock()
        request.body = AsyncMock(return_value=body)
        request.json = AsyncMock(return_value=payload)
        request.headers = {"X-Webhook-Signature": sig}
        request.scope = {"client": ("127.0.0.1", 12345)}

        member_resp = _make_mock_httpx_response(200, {
            "full_name": "New Webhook Member",
            "phone": "+621111",
            "date_of_birth": "1990-01-01",
            "gender": "Male",
            "member_status": "youth",
            "is_active": True,
            "photo_url": "https://cdn.example.com/photo.jpg",
        })
        login_resp = _make_mock_httpx_response(200, {"access_token": "fake-token"})

        setup_server._core_api_token_cache.clear()

        with patch('httpx.AsyncClient') as mock_httpx:
            mock_client = AsyncMock()
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=login_resp)
            mock_client.get = AsyncMock(return_value=member_resp)

            result = await setup_server.receive_sync_webhook.fn(request)
            assert result["success"] is True
            assert "created" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_webhook_member_updated(self, setup_server, mock_db):
        """Webhook updates an existing member."""
        payload = {"event_type": "member.updated", "campus_id": TEST_CAMPUS_ID, "member_id": "core-m1"}
        body = json.dumps(payload).encode()
        secret = "test-secret"
        sig = hmac_mod.new(secret.encode(), body, hashlib.sha256).hexdigest()

        encrypted_pwd = setup_server.encrypt_password("test123")
        config = {
            "campus_id": TEST_CAMPUS_ID,
            "is_enabled": True,
            "webhook_secret": secret,
            "api_base_url": "https://core.example.com",
            "api_path_prefix": "/api",
            "api_email": "sync@test.com",
            "api_password": encrypted_pwd,
        }
        mock_db.sync_configs.find_one = AsyncMock(return_value=config)
        mock_db.members.find_one = AsyncMock(return_value={
            "id": "local-1", "external_member_id": "core-m1", "name": "Old Name",
        })

        request = MagicMock()
        request.body = AsyncMock(return_value=body)
        request.json = AsyncMock(return_value=payload)
        request.headers = {"X-Webhook-Signature": sig}
        request.scope = {"client": ("127.0.0.1", 12345)}

        member_resp = _make_mock_httpx_response(200, {
            "full_name": "Updated Member",
            "phone": "+621111",
            "is_active": True,
        })
        login_resp = _make_mock_httpx_response(200, {"access_token": "fake-token"})
        setup_server._core_api_token_cache.clear()

        with patch('httpx.AsyncClient') as mock_httpx:
            mock_client = AsyncMock()
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=login_resp)
            mock_client.get = AsyncMock(return_value=member_resp)

            result = await setup_server.receive_sync_webhook.fn(request)
            assert result["success"] is True
            assert "updated" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_webhook_member_deleted(self, setup_server, mock_db):
        """Webhook archives (deletes) a member."""
        payload = {"event_type": "member.deleted", "campus_id": TEST_CAMPUS_ID, "member_id": "core-m1"}
        body = json.dumps(payload).encode()
        secret = "test-secret"
        sig = hmac_mod.new(secret.encode(), body, hashlib.sha256).hexdigest()

        encrypted_pwd = setup_server.encrypt_password("test123")
        config = {
            "campus_id": TEST_CAMPUS_ID,
            "is_enabled": True,
            "webhook_secret": secret,
            "api_base_url": "https://core.example.com",
            "api_path_prefix": "/api",
            "api_email": "sync@test.com",
            "api_password": encrypted_pwd,
        }
        mock_db.sync_configs.find_one = AsyncMock(return_value=config)

        request = MagicMock()
        request.body = AsyncMock(return_value=body)
        request.json = AsyncMock(return_value=payload)
        request.headers = {"X-Webhook-Signature": sig}
        request.scope = {"client": ("127.0.0.1", 12345)}

        login_resp = _make_mock_httpx_response(200, {"access_token": "fake-token"})
        setup_server._core_api_token_cache.clear()

        with patch('httpx.AsyncClient') as mock_httpx:
            mock_client = AsyncMock()
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=login_resp)

            result = await setup_server.receive_sync_webhook.fn(request)
            assert result["success"] is True
            assert "archived" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_webhook_missing_campus_id(self, setup_server, mock_db):
        """Webhook without campus_id in payload."""
        from litestar.exceptions import HTTPException
        payload = {"event_type": "test"}
        body = json.dumps(payload).encode()

        request = MagicMock()
        request.body = AsyncMock(return_value=body)
        request.json = AsyncMock(return_value=payload)
        request.headers = {"X-Webhook-Signature": "some-sig"}
        request.scope = {"client": ("127.0.0.1", 12345)}

        with pytest.raises(HTTPException) as exc_info:
            await setup_server.receive_sync_webhook.fn(request)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_webhook_no_config(self, setup_server, mock_db):
        """Webhook for campus with no sync config."""
        from litestar.exceptions import HTTPException
        payload = {"event_type": "test", "campus_id": TEST_CAMPUS_ID}
        body = json.dumps(payload).encode()

        mock_db.sync_configs.find_one = AsyncMock(return_value=None)

        request = MagicMock()
        request.body = AsyncMock(return_value=body)
        request.json = AsyncMock(return_value=payload)
        request.headers = {"X-Webhook-Signature": "some-sig"}
        request.scope = {"client": ("127.0.0.1", 12345)}

        with pytest.raises(HTTPException) as exc_info:
            await setup_server.receive_sync_webhook.fn(request)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_webhook_sync_disabled(self, setup_server, mock_db):
        """Webhook for campus with sync disabled."""
        from litestar.exceptions import HTTPException
        payload = {"event_type": "test", "campus_id": TEST_CAMPUS_ID}
        body = json.dumps(payload).encode()

        mock_db.sync_configs.find_one = AsyncMock(return_value={
            "campus_id": TEST_CAMPUS_ID,
            "is_enabled": False,
            "webhook_secret": "s",
        })

        request = MagicMock()
        request.body = AsyncMock(return_value=body)
        request.json = AsyncMock(return_value=payload)
        request.headers = {"X-Webhook-Signature": "some-sig"}
        request.scope = {"client": ("127.0.0.1", 12345)}

        with pytest.raises(HTTPException) as exc_info:
            await setup_server.receive_sync_webhook.fn(request)
        assert exc_info.value.status_code == 403


# ==================== 7. test_connection / discover_fields TESTS ====================

class TestSyncTestConnection:
    """Tests for test_sync_connection and discover_fields."""

    @pytest.mark.asyncio
    async def test_connection_success(self, setup_server, mock_db):
        """Successful connection test."""
        user = _make_campus_admin_user()
        request = _mock_request(user=user)
        mock_db.users.find_one = AsyncMock(return_value=user)

        from models import SyncConfigCreate
        data = SyncConfigCreate(
            api_base_url="https://core.example.com",
            api_email="sync@test.com",
            api_password="test123",
            api_path_prefix="/api",
        )

        login_resp = _make_mock_httpx_response(200, {"access_token": "fake-token"})
        page1 = _make_mock_httpx_response(200, [{"id": "m1", "name": "Member 1"}])

        with patch('httpx.AsyncClient') as mock_httpx:
            mock_client = AsyncMock()
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=login_resp)
            mock_client.get = AsyncMock(return_value=page1)

            result = await setup_server.test_sync_connection.fn(data=data, request=request)
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_connection_login_failure(self, setup_server, mock_db):
        """Connection test with login failure."""
        user = _make_campus_admin_user()
        request = _mock_request(user=user)
        mock_db.users.find_one = AsyncMock(return_value=user)

        from models import SyncConfigCreate
        data = SyncConfigCreate(
            api_base_url="https://core.example.com",
            api_email="sync@test.com",
            api_password="wrong-pass",
            api_path_prefix="/api",
        )

        login_resp = _make_mock_httpx_response(401, {"detail": "Invalid credentials"}, text="Invalid credentials")

        with patch('httpx.AsyncClient') as mock_httpx:
            mock_client = AsyncMock()
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=login_resp)

            result = await setup_server.test_sync_connection.fn(data=data, request=request)
            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_connection_no_token_returned(self, setup_server, mock_db):
        """Login succeeds but no token returned."""
        user = _make_campus_admin_user()
        request = _mock_request(user=user)
        mock_db.users.find_one = AsyncMock(return_value=user)

        from models import SyncConfigCreate
        data = SyncConfigCreate(
            api_base_url="https://core.example.com",
            api_email="sync@test.com",
            api_password="test123",
        )

        login_resp = _make_mock_httpx_response(200, {})

        with patch('httpx.AsyncClient') as mock_httpx:
            mock_client = AsyncMock()
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=login_resp)

            result = await setup_server.test_sync_connection.fn(data=data, request=request)
            assert result["success"] is False
            assert "No access token" in result["message"]

    @pytest.mark.asyncio
    async def test_connection_timeout(self, setup_server, mock_db):
        """Connection test with timeout."""
        import httpx as httpx_mod
        user = _make_campus_admin_user()
        request = _mock_request(user=user)
        mock_db.users.find_one = AsyncMock(return_value=user)

        from models import SyncConfigCreate
        data = SyncConfigCreate(
            api_base_url="https://core.example.com",
            api_email="sync@test.com",
            api_password="test123",
        )

        with patch('httpx.AsyncClient') as mock_httpx:
            mock_client = AsyncMock()
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(side_effect=httpx_mod.TimeoutException("Timeout"))

            result = await setup_server.test_sync_connection.fn(data=data, request=request)
            assert result["success"] is False
            assert "timeout" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_connection_with_masked_password(self, setup_server, mock_db):
        """Connection test with masked password fetches from DB."""
        user = _make_campus_admin_user()
        request = _mock_request(user=user)
        mock_db.users.find_one = AsyncMock(return_value=user)

        encrypted_pwd = setup_server.encrypt_password("stored-pass")
        mock_db.sync_configs.find_one = AsyncMock(return_value={
            "campus_id": TEST_CAMPUS_ID,
            "api_password": encrypted_pwd,
        })

        from models import SyncConfigCreate
        data = SyncConfigCreate(
            api_base_url="https://core.example.com",
            api_email="sync@test.com",
            api_password="********",
        )

        login_resp = _make_mock_httpx_response(200, {"access_token": "fake-token"})
        members_resp = _make_mock_httpx_response(200, [])

        with patch('httpx.AsyncClient') as mock_httpx:
            mock_client = AsyncMock()
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=login_resp)
            mock_client.get = AsyncMock(return_value=members_resp)

            result = await setup_server.test_sync_connection.fn(data=data, request=request)
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_discover_fields_success(self, setup_server, mock_db):
        """Discover fields from external API."""
        user = _make_campus_admin_user()
        request = _mock_request(user=user)
        mock_db.users.find_one = AsyncMock(return_value=user)

        from models import SyncConfigCreate
        data = SyncConfigCreate(
            api_base_url="https://core.example.com",
            api_email="sync@test.com",
            api_password="test123",
            api_path_prefix="/api",
        )

        login_resp = _make_mock_httpx_response(200, {"access_token": "fake-token"})
        members_resp = _make_mock_httpx_response(200, [
            {"name": "John", "gender": "Male", "age": 30, "birth_date": "1990-01-01",
             "is_active": True, "category": "adult"},
            {"name": "Jane", "gender": "Female", "age": 25, "birth_date": "1995-05-15",
             "is_active": False, "category": "youth"},
        ])

        with patch('httpx.AsyncClient') as mock_httpx:
            mock_client = AsyncMock()
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=login_resp)
            mock_client.get = AsyncMock(return_value=members_resp)

            result = await setup_server.discover_fields_from_core.fn(data=data, request=request)
            assert len(result["fields"]) > 0
            assert result["sample_count"] == 2
            field_names = [f["name"] for f in result["fields"]]
            assert "name" in field_names
            assert "gender" in field_names

    @pytest.mark.asyncio
    async def test_discover_fields_empty(self, setup_server, mock_db):
        """Discover fields with no members returns empty."""
        user = _make_campus_admin_user()
        request = _mock_request(user=user)
        mock_db.users.find_one = AsyncMock(return_value=user)

        from models import SyncConfigCreate
        data = SyncConfigCreate(
            api_base_url="https://core.example.com",
            api_email="sync@test.com",
            api_password="test123",
        )

        login_resp = _make_mock_httpx_response(200, {"access_token": "fake-token"})
        # Use a proper MagicMock response whose .json() returns a real list
        members_resp = MagicMock()
        members_resp.status_code = 200
        members_resp.json = MagicMock(return_value=[])

        with patch('httpx.AsyncClient') as mock_httpx:
            mock_client = AsyncMock()
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=login_resp)
            mock_client.get = AsyncMock(return_value=members_resp)

            result = await setup_server.discover_fields_from_core.fn(data=data, request=request)
            assert len(result["fields"]) == 0


# ==================== 8. sync_members_pull TESTS ====================

class TestSyncMembersPull:
    """Tests for the sync_members_from_core endpoint."""

    @pytest.mark.asyncio
    async def test_pull_success(self, setup_server, mock_db):
        """Successful pull delegates to perform_member_sync_for_campus."""
        user = _make_campus_admin_user()
        request = _mock_request(user=user)
        mock_db.users.find_one = AsyncMock(return_value=user)

        with patch.object(setup_server, 'perform_member_sync_for_campus',
                          new_callable=AsyncMock) as mock_sync:
            mock_sync.return_value = {"success": True, "stats": {}, "duration_seconds": 1.5}
            result = await setup_server.sync_members_from_core.fn(request)
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_pull_fails(self, setup_server, mock_db):
        """Pull sync failure raises HTTPException."""
        from litestar.exceptions import HTTPException
        user = _make_campus_admin_user()
        request = _mock_request(user=user)
        mock_db.users.find_one = AsyncMock(return_value=user)

        with patch.object(setup_server, 'perform_member_sync_for_campus',
                          new_callable=AsyncMock) as mock_sync:
            mock_sync.return_value = {"success": False, "error": "Config missing"}
            with pytest.raises(HTTPException):
                await setup_server.sync_members_from_core.fn(request)

    @pytest.mark.asyncio
    async def test_pull_no_campus(self, setup_server, mock_db):
        """Pull with no campus_id raises error."""
        from litestar.exceptions import HTTPException
        user = _make_campus_admin_user(campus_id=None)
        request = _mock_request(user=user)
        mock_db.users.find_one = AsyncMock(return_value=user)

        with pytest.raises(HTTPException) as exc_info:
            await setup_server.sync_members_from_core.fn(request)
        assert exc_info.value.status_code == 400


# ==================== 9. Settings endpoints TESTS ====================

class TestSettingsEndpoints:
    """Tests for overdue writeoff, automation, grief stages, accident followup."""

    @pytest.mark.asyncio
    async def test_update_overdue_writeoff_settings(self, setup_server, mock_db):
        """Update overdue writeoff settings."""
        admin = _make_admin_user()
        request = _mock_request(user=admin)
        mock_db.users.find_one = AsyncMock(return_value=admin)

        from models import OverdueWriteoffSettingsUpdate
        data = OverdueWriteoffSettingsUpdate(days=30, enabled=True)

        result = await setup_server.update_overdue_writeoff_settings.fn(data=data, request=request)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_update_automation_settings(self, setup_server, mock_db):
        """Update automation settings with valid time."""
        admin = _make_admin_user()
        request = _mock_request(user=admin)
        mock_db.users.find_one = AsyncMock(return_value=admin)

        from models import AutomationSettingsUpdate
        data = AutomationSettingsUpdate(digestTime="09:00", whatsappGateway="https://wa.api", enabled=True)

        with patch('scheduler.schedule_daily_digest') as mock_sched:
            result = await setup_server.update_automation_settings.fn(data=data, request=request)
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_update_automation_settings_invalid_time(self, setup_server, mock_db):
        """Update automation settings with invalid time format."""
        from litestar.exceptions import HTTPException
        admin = _make_admin_user()
        request = _mock_request(user=admin)
        mock_db.users.find_one = AsyncMock(return_value=admin)

        from models import AutomationSettingsUpdate
        data = AutomationSettingsUpdate(digestTime="25:00", whatsappGateway="", enabled=True)

        with pytest.raises(HTTPException) as exc_info:
            await setup_server.update_automation_settings.fn(data=data, request=request)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_update_grief_stages(self, setup_server, mock_db):
        """Update grief stages."""
        admin = _make_admin_user()
        request = _mock_request(user=admin)
        mock_db.users.find_one = AsyncMock(return_value=admin)

        data = [{"stage": "1_week", "days": 7, "name": "1 Week After"}]
        result = await setup_server.update_grief_stages.fn(data=data, request=request)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_update_accident_followup(self, setup_server, mock_db):
        """Update accident followup settings."""
        admin = _make_admin_user()
        request = _mock_request(user=admin)
        mock_db.users.find_one = AsyncMock(return_value=admin)

        data = [{"stage": "first_followup", "days": 3, "name": "First Follow-up"}]
        result = await setup_server.update_accident_followup.fn(data=data, request=request)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_update_user_preferences(self, setup_server, mock_db):
        """Update user preferences."""
        user = _make_admin_user()
        request = _mock_request(user=user)
        mock_db.users.find_one = AsyncMock(return_value=user)

        from models import UserPreferencesUpdate
        data = UserPreferencesUpdate(email_notifications=False, whatsapp_notifications=True)

        result = await setup_server.update_user_preferences.fn(user_id=user["id"], data=data, request=request)
        assert result["success"] is True


# ==================== 10. Notification logs TESTS ====================

class TestNotificationLogs:
    """Tests for notification log endpoint."""

    @pytest.mark.asyncio
    async def test_get_notification_logs_with_status_filter(self, setup_server, mock_db):
        """Get notification logs with status filter."""
        user = _make_admin_user()
        request = _mock_request(user=user)
        mock_db.users.find_one = AsyncMock(return_value=user)

        mock_db.notification_logs.find = MagicMock(return_value=_make_mock_cursor([]))

        from enums import NotificationStatus
        result = await setup_server.get_notification_logs.fn(request=request, limit=50, status=NotificationStatus.SENT)
        assert isinstance(result, list)


# ==================== 11. PDF report generation TESTS ====================

class TestPdfReport:
    """Tests for PDF report export."""

    @pytest.mark.asyncio
    async def test_export_pdf_success(self, setup_server, mock_db):
        """Export monthly report as PDF."""
        user = _make_admin_user()
        request = _mock_request(user=user)
        mock_db.users.find_one = AsyncMock(return_value=user)
        mock_db.campuses.find_one = AsyncMock(return_value={"campus_name": "Test Campus"})

        # Need at least 1 member to avoid div-by-zero in report
        members = [{"id": "m1", "engagement_status": "active", "days_since_last_contact": 5,
                     "last_contact_date": datetime.now(timezone.utc).isoformat()}]
        mock_db.members.find = MagicMock(return_value=_make_mock_cursor(members))
        mock_db.care_events.find = MagicMock(return_value=_make_mock_cursor([]))
        mock_db.activity_logs.find = MagicMock(return_value=_make_mock_cursor([]))

        mock_pdf_generator = MagicMock(return_value=b"%PDF-1.4 fake pdf content")

        with patch.object(setup_server, 'get_pdf_generator', return_value=mock_pdf_generator):
            result = await setup_server.export_monthly_report_pdf.fn(request=request, year=2024, month=6)
            assert result.media_type == "application/pdf"


# ==================== 12. sync_logs endpoint TESTS ====================

class TestSyncLogs:
    """Tests for sync log listing."""

    @pytest.mark.asyncio
    async def test_get_sync_logs(self, setup_server, mock_db):
        """Get sync history logs."""
        user = _make_campus_admin_user()
        request = _mock_request(user=user)
        mock_db.users.find_one = AsyncMock(return_value=user)
        mock_db.sync_logs.count_documents = AsyncMock(return_value=2)

        logs = [
            {"id": "sl1", "status": "success", "members_fetched": 50},
            {"id": "sl2", "status": "error", "error_message": "Timeout"},
        ]
        mock_db.sync_logs.find = MagicMock(return_value=_make_mock_cursor(logs))

        result = await setup_server.get_sync_logs.fn(request=request)
        assert result["total"] == 2
        assert len(result["logs"]) == 2


# ==================== 13. save_sync_config TESTS ====================

class TestSaveSyncConfig:
    """Tests for saving sync configuration."""

    @pytest.mark.asyncio
    async def test_save_new_config(self, setup_server, mock_db):
        """Save a new sync config."""
        user = _make_campus_admin_user()
        request = _mock_request(user=user)
        mock_db.users.find_one = AsyncMock(return_value=user)
        mock_db.sync_configs.find_one = AsyncMock(return_value=None)

        from models import SyncConfigCreate
        data = SyncConfigCreate(
            api_base_url="https://core.example.com",
            api_email="sync@test.com",
            api_password="test123",
            sync_method="polling",
            api_path_prefix="/api",
        )

        login_resp = _make_mock_httpx_response(200, {
            "access_token": "t",
            "user": {"church_id": "church-123"}
        })

        with patch('httpx.AsyncClient') as mock_httpx:
            mock_client = AsyncMock()
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=login_resp)

            result = await setup_server.save_sync_config.fn(data=data, request=request)
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_save_config_masked_password(self, setup_server, mock_db):
        """Save config with masked password uses existing stored password."""
        user = _make_campus_admin_user()
        request = _mock_request(user=user)
        mock_db.users.find_one = AsyncMock(return_value=user)

        encrypted_pwd = setup_server.encrypt_password("stored-pass")
        mock_db.sync_configs.find_one = AsyncMock(return_value={
            "id": "existing-config-id",
            "campus_id": TEST_CAMPUS_ID,
            "api_password": encrypted_pwd,
        })

        from models import SyncConfigCreate
        data = SyncConfigCreate(
            api_base_url="https://core.example.com",
            api_email="sync@test.com",
            api_password="********",
            sync_method="polling",
        )

        login_resp = _make_mock_httpx_response(200, {"access_token": "t"})

        with patch('httpx.AsyncClient') as mock_httpx:
            mock_client = AsyncMock()
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=login_resp)

            result = await setup_server.save_sync_config.fn(data=data, request=request)
            assert result["success"] is True


# ==================== 14. get_cached_core_token TESTS ====================

class TestGetCachedCoreToken:
    """Tests for core API token caching."""

    @pytest.mark.asyncio
    async def test_cached_token_returned(self, setup_server, mock_db):
        """Cached valid token is returned without API call."""
        setup_server._core_api_token_cache["camp-1"] = {
            "token": "cached-token",
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=1)
        }

        config = {
            "api_base_url": "https://core.example.com",
            "api_path_prefix": "/api",
            "api_email": "sync@test.com",
            "api_password": setup_server.encrypt_password("pwd"),
        }

        token = await setup_server.get_cached_core_token("camp-1", config)
        assert token == "cached-token"

    @pytest.mark.asyncio
    async def test_expired_token_refreshed(self, setup_server, mock_db):
        """Expired token triggers new login."""
        setup_server._core_api_token_cache["camp-2"] = {
            "token": "old-token",
            "expires_at": datetime.now(timezone.utc) - timedelta(hours=1)
        }

        config = {
            "api_base_url": "https://core.example.com",
            "api_path_prefix": "/api",
            "api_email": "sync@test.com",
            "api_password": setup_server.encrypt_password("pwd"),
        }

        login_resp = _make_mock_httpx_response(200, {"access_token": "new-token"})

        with patch('httpx.AsyncClient') as mock_httpx:
            mock_client = AsyncMock()
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=login_resp)

            token = await setup_server.get_cached_core_token("camp-2", config)
            assert token == "new-token"


# ==================== 15. SSE stream_activity TESTS ====================

class TestStreamActivity:
    """Tests for SSE stream activity endpoint."""

    @pytest.mark.asyncio
    async def test_stream_activity_with_header_auth(self, setup_server, mock_db):
        """Stream activity with valid JWT in header."""
        user = _make_admin_user()
        request = _mock_request(user=user)
        mock_db.users.find_one = AsyncMock(return_value=user)

        with patch.object(setup_server, 'subscribe_to_activities', new_callable=AsyncMock) as mock_sub:
            mock_sub.return_value = asyncio.Queue()
            result = await setup_server.stream_activity.fn(request=request, token=None)
            assert result is not None

    @pytest.mark.asyncio
    async def test_stream_activity_with_query_token(self, setup_server, mock_db):
        """Stream activity with JWT in query parameter."""
        user = _make_admin_user()
        request = MagicMock()
        request.headers = {}
        request.scope = {"client": ("127.0.0.1", 12345)}

        token = _make_token(user["id"])
        mock_db.users.find_one = AsyncMock(return_value=user)

        with patch.object(setup_server, 'subscribe_to_activities', new_callable=AsyncMock) as mock_sub:
            mock_sub.return_value = asyncio.Queue()
            result = await setup_server.stream_activity.fn(request=request, token=token)
            assert result is not None

    @pytest.mark.asyncio
    async def test_stream_activity_no_auth(self, setup_server, mock_db):
        """Stream activity with no auth raises 401."""
        from litestar.exceptions import HTTPException
        request = MagicMock()
        request.headers = {}
        request.scope = {"client": ("127.0.0.1", 12345)}
        mock_db.users.find_one = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await setup_server.stream_activity.fn(request=request, token=None)
        assert exc_info.value.status_code == 401


# ==================== 16. connection test with paginated response formats ====================

class TestConnectionPaginatedFormats:
    """Test sync connection with various paginated response formats."""

    @pytest.mark.asyncio
    async def test_connection_with_pagination_metadata(self, setup_server, mock_db):
        """Connection test with response containing pagination.total."""
        user = _make_campus_admin_user()
        request = _mock_request(user=user)
        mock_db.users.find_one = AsyncMock(return_value=user)

        from models import SyncConfigCreate
        data = SyncConfigCreate(
            api_base_url="https://core.example.com",
            api_email="sync@test.com",
            api_password="test123",
        )

        login_resp = _make_mock_httpx_response(200, {"access_token": "fake-token"})
        members_resp = _make_mock_httpx_response(200, {
            "pagination": {"total": 150},
            "data": [{"id": "m1"}],
        })

        with patch('httpx.AsyncClient') as mock_httpx:
            mock_client = AsyncMock()
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=login_resp)
            mock_client.get = AsyncMock(return_value=members_resp)

            result = await setup_server.test_sync_connection.fn(data=data, request=request)
            assert result["success"] is True
            assert result["member_count"] == 150

    @pytest.mark.asyncio
    async def test_connection_with_data_key_no_pagination(self, setup_server, mock_db):
        """Connection test with dict response having data key but no pagination metadata."""
        user = _make_campus_admin_user()
        request = _mock_request(user=user)
        mock_db.users.find_one = AsyncMock(return_value=user)

        from models import SyncConfigCreate
        data = SyncConfigCreate(
            api_base_url="https://core.example.com",
            api_email="sync@test.com",
            api_password="test123",
        )

        login_resp = _make_mock_httpx_response(200, {"access_token": "fake-token"})
        members_resp = _make_mock_httpx_response(200, {
            "data": [{"id": "m1"}, {"id": "m2"}]
        })

        with patch('httpx.AsyncClient') as mock_httpx:
            mock_client = AsyncMock()
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=login_resp)
            mock_client.get = AsyncMock(return_value=members_resp)

            result = await setup_server.test_sync_connection.fn(data=data, request=request)
            assert result["success"] is True
            assert result["member_count"] == 2


# ==================== 17. monthly report endpoint TESTS ====================

class TestMonthlyReportEndpoint:
    """Test the monthly report route handler."""

    @pytest.mark.asyncio
    async def test_get_monthly_report(self, setup_server, mock_db):
        """Get monthly report via endpoint."""
        user = _make_admin_user()
        request = _mock_request(user=user)
        mock_db.users.find_one = AsyncMock(return_value=user)

        members = [{"id": "m1", "engagement_status": "active", "days_since_last_contact": 5,
                     "last_contact_date": datetime.now(timezone.utc).isoformat()}]
        mock_db.members.find = MagicMock(return_value=_make_mock_cursor(members))
        mock_db.care_events.find = MagicMock(return_value=_make_mock_cursor([]))
        mock_db.activity_logs.find = MagicMock(return_value=_make_mock_cursor([]))

        result = await setup_server.get_monthly_management_report.fn(request=request, year=2024, month=6)
        assert result["report_period"]["year"] == 2024


# ==================== 18. run_reminders_now TESTS ====================

class TestRunRemindersNow:
    """Test manual reminder trigger."""

    @pytest.mark.asyncio
    async def test_run_reminders(self, setup_server, mock_db):
        """Trigger daily reminders manually."""
        admin = _make_admin_user()
        request = _mock_request(user=admin)
        mock_db.users.find_one = AsyncMock(return_value=admin)

        with patch.object(setup_server, 'daily_reminder_job', new_callable=AsyncMock) as mock_job:
            mock_job.return_value = None
            result = await setup_server.run_reminders_now.fn(request=request)
            assert result["success"] is True
