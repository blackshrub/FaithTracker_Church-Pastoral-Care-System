"""
Pytest configuration and fixtures for FaithTracker backend tests

Provides:
- Test database setup/teardown
- Authentication fixtures (tokens, users)
- Test data factories
- Async test support
"""

import pytest
import asyncio
import os
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
import uuid
from typing import AsyncGenerator

# Test database configuration
TEST_DB_NAME = 'faithtracker_test'
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_db_client():
    """MongoDB client for tests"""
    client = AsyncIOMotorClient(MONGO_URL)
    yield client
    client.close()


@pytest.fixture
async def test_db(test_db_client):
    """Clean test database for each test"""
    db = test_db_client[TEST_DB_NAME]

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
        "created_at": datetime.now(timezone.utc).isoformat()
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
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await test_db.campuses.insert_one(campus)
    return campus


@pytest.fixture
async def test_admin_user(test_db, test_campus):
    """Create admin user for testing"""
    import bcrypt

    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

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
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await test_db.users.insert_one(user)
    return user


@pytest.fixture
async def test_pastor_user(test_db, test_campus):
    """Create pastor user for testing"""
    import bcrypt

    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

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
        "created_at": datetime.now(timezone.utc).isoformat()
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
        "last_contact_date": datetime.now(timezone.utc).isoformat(),
        "is_archived": False,
        "created_at": datetime.now(timezone.utc).isoformat()
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
        "last_contact_date": datetime.now(timezone.utc).isoformat(),
        "is_archived": False,
        "created_at": datetime.now(timezone.utc).isoformat()
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
        "event_date": datetime.now(timezone.utc).date().isoformat(),
        "title": "Birthday Celebration",
        "description": "Send birthday wishes",
        "completed": False,
        "ignored": False,
        "created_at": datetime.now(timezone.utc).isoformat()
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
        "campus_id": campus_id
    }
    data.update(overrides)
    return data


def create_test_care_event_data(campus_id: str, member_id: str, **overrides):
    """Factory function to create test care event data"""
    data = {
        "campus_id": campus_id,
        "member_id": member_id,
        "event_type": "regular_contact",
        "event_date": datetime.now(timezone.utc).date().isoformat(),
        "title": "Test Event",
        "description": "Test Description"
    }
    data.update(overrides)
    return data


# Export helper functions
pytest.create_test_member_data = create_test_member_data
pytest.create_test_care_event_data = create_test_care_event_data
