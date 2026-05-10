"""
Pytest configuration and fixtures for FaithTracker backend tests

Provides:
- Test database setup/teardown
- Authentication fixtures (tokens, users)
- Test data factories
- Async test support
"""

import asyncio
import os
import re
import uuid
from datetime import UTC, datetime

import pytest
from pymongo import AsyncMongoClient

# Test database configuration
TEST_DB_NAME = "faithtracker_test"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")

# ---------------------------------------------------------------------------
# Per-worker DB isolation for pytest-xdist
# ---------------------------------------------------------------------------
# Each xdist worker gets its own MongoDB database (faithtracker_test_gw0,
# gw1, ...). We rewrite MONGO_URL HERE — at conftest import time, before
# any test or server module touches it — so the global `db` in server.py
# (which is derived from MONGO_URL at import time) lands on the same
# per-worker DB the test_db fixture cleans.
#
# Without this, tests insert into faithtracker_test_gw5 via the fixture
# but the SUT reads from faithtracker_test (URL's default) — every read
# returns empty, every write races other workers, ~50 false failures.
_worker_id = os.environ.get("PYTEST_XDIST_WORKER", "master")
if _worker_id != "master" and TEST_DB_NAME in MONGO_URL:
    _per_worker_db = f"{TEST_DB_NAME}_{_worker_id}"
    # Replace `/faithtracker_test` (followed by ? or end of string) with
    # the per-worker variant. Using a regex with lookahead so we don't
    # accidentally rewrite a substring that happens to appear elsewhere.
    MONGO_URL = re.sub(
        rf"/{re.escape(TEST_DB_NAME)}(?=$|\?)",
        f"/{_per_worker_db}",
        MONGO_URL,
        count=1,
    )
    os.environ["MONGO_URL"] = MONGO_URL


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_db_client():
    """MongoDB client for tests (function-scoped for pytest-asyncio compatibility)"""
    client = AsyncMongoClient(MONGO_URL)
    yield client
    await client.close()


@pytest.fixture
async def test_db(test_db_client, worker_id):
    """Clean test database for each test.

    Per-worker DB name (faithtracker_test_gw0, gw1, ...) so xdist parallel
    workers don't share state and race on collection writes. When run
    serially (no -n), worker_id is 'master' and we use the original name
    for back-compat with any tooling that connects to faithtracker_test.
    """
    db_name = TEST_DB_NAME if worker_id == "master" else f"{TEST_DB_NAME}_{worker_id}"
    db = test_db_client[db_name]

    # Clean all collections before test
    collections = await db.list_collection_names()
    for collection in collections:
        await db[collection].delete_many({})

    yield db

    # Clean after test
    collections = await db.list_collection_names()
    for collection in collections:
        await db[collection].delete_many({})


@pytest.fixture
async def test_campus(test_db):
    """Create a test campus"""
    campus_id = str(uuid.uuid4())
    campus = {
        "id": campus_id,
        "campus_name": "Test Campus",
        "location": "Test Location",
        "is_active": True,
        "timezone": "Asia/Jakarta",
        "created_at": datetime.now(UTC).isoformat(),
    }
    await test_db.campuses.insert_one(campus)
    return campus


@pytest.fixture
async def second_campus(test_db):
    """Create a second test campus for multi-tenancy tests"""
    campus_id = str(uuid.uuid4())
    campus = {
        "id": campus_id,
        "campus_name": "Second Campus",
        "location": "Another Location",
        "is_active": True,
        "timezone": "Asia/Jakarta",
        "created_at": datetime.now(UTC).isoformat(),
    }
    await test_db.campuses.insert_one(campus)
    return campus


@pytest.fixture
async def test_admin_user(test_db, test_campus):
    """Create admin user for testing"""
    import bcrypt

    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    user_id = str(uuid.uuid4())

    user = {
        "id": user_id,
        "name": "Test Admin",
        "email": "admin@test.com",
        "password": hash_password("testpass123"),
        "phone": "+6281234567890",
        "campus_id": test_campus["id"],
        "role": "full_admin",
        "is_active": True,
        "created_at": datetime.now(UTC).isoformat(),
    }
    await test_db.users.insert_one(user)
    return user


@pytest.fixture
async def test_pastor_user(test_db, test_campus):
    """Create pastor user for testing"""
    import bcrypt

    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    user_id = str(uuid.uuid4())

    user = {
        "id": user_id,
        "name": "Test Pastor",
        "email": "pastor@test.com",
        "password": hash_password("testpass123"),
        "phone": "+6281234567891",
        "campus_id": test_campus["id"],
        "role": "pastor",
        "is_active": True,
        "created_at": datetime.now(UTC).isoformat(),
    }
    await test_db.users.insert_one(user)
    return user


@pytest.fixture
async def test_member(test_db, test_campus):
    """Create a test member"""
    member_id = str(uuid.uuid4())
    member = {
        "id": member_id,
        "campus_id": test_campus["id"],
        "name": "John Doe",
        "phone": "+6281234567892",
        "email": "john.doe@test.com",
        "engagement_status": "active",
        "days_since_last_contact": 5,
        "last_contact_date": datetime.now(UTC).isoformat(),
        "is_archived": False,
        "created_at": datetime.now(UTC).isoformat(),
    }
    await test_db.members.insert_one(member)
    return member


@pytest.fixture
async def test_member_second_campus(test_db, second_campus):
    """Create a member in second campus for isolation testing"""
    member_id = str(uuid.uuid4())
    member = {
        "id": member_id,
        "campus_id": second_campus["id"],
        "name": "Jane Smith",
        "phone": "+6281234567893",
        "email": "jane.smith@test.com",
        "engagement_status": "active",
        "days_since_last_contact": 3,
        "last_contact_date": datetime.now(UTC).isoformat(),
        "is_archived": False,
        "created_at": datetime.now(UTC).isoformat(),
    }
    await test_db.members.insert_one(member)
    return member


@pytest.fixture
async def test_care_event(test_db, test_campus, test_member):
    """Create a test care event"""
    event_id = str(uuid.uuid4())
    event = {
        "id": event_id,
        "campus_id": test_campus["id"],
        "member_id": test_member["id"],
        "event_type": "birthday",
        "event_date": datetime.now(UTC).date().isoformat(),
        "title": "Birthday Celebration",
        "description": "Send birthday wishes",
        "completed": False,
        "ignored": False,
        "created_at": datetime.now(UTC).isoformat(),
    }
    await test_db.care_events.insert_one(event)
    return event


# Helper functions for tests
def create_test_member_data(campus_id: str, **overrides):
    """Factory function to create test member data"""
    data = {
        "name": "Test Member",
        "phone": f"+628{uuid.uuid4().hex[:10]}",
        "email": f"test{uuid.uuid4().hex[:8]}@example.com",
        "campus_id": campus_id,
    }
    data.update(overrides)
    return data


def create_test_care_event_data(campus_id: str, member_id: str, **overrides):
    """Factory function to create test care event data"""
    data = {
        "campus_id": campus_id,
        "member_id": member_id,
        "event_type": "regular_contact",
        "event_date": datetime.now(UTC).date().isoformat(),
        "title": "Test Event",
        "description": "Test Description",
    }
    data.update(overrides)
    return data


# Export helper functions
pytest.create_test_member_data = create_test_member_data
pytest.create_test_care_event_data = create_test_care_event_data
