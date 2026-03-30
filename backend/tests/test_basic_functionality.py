"""
Test basic CRUD operations and core functionality

Tests for members, care events, and essential operations.
"""

import os
import sys
from datetime import UTC, datetime

import pytest

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.mark.asyncio
async def test_create_member(test_db, test_campus):
    """Test creating a new member"""
    member_data = {
        "id": "new-member-123",
        "campus_id": test_campus["id"],
        "name": "New Member",
        "phone": "+6281234567899",
        "email": "newmember@test.com",
        "created_at": datetime.now(UTC).isoformat(),
    }

    await test_db.members.insert_one(member_data)

    # Verify member was created
    member = await test_db.members.find_one({"id": "new-member-123"})
    assert member is not None
    assert member["name"] == "New Member"
    assert member["campus_id"] == test_campus["id"]


@pytest.mark.asyncio
async def test_update_member(test_db, test_member):
    """Test updating a member"""
    # Update member
    result = await test_db.members.update_one({"id": test_member["id"]}, {"$set": {"name": "Updated Name"}})

    assert result.modified_count == 1

    # Verify update
    member = await test_db.members.find_one({"id": test_member["id"]})
    assert member["name"] == "Updated Name"


@pytest.mark.asyncio
async def test_delete_member(test_db, test_member):
    """Test deleting a member"""
    result = await test_db.members.delete_one({"id": test_member["id"]})
    assert result.deleted_count == 1

    # Verify deletion
    member = await test_db.members.find_one({"id": test_member["id"]})
    assert member is None


@pytest.mark.asyncio
async def test_query_members_by_campus(test_db, test_campus, test_member):
    """Test querying members by campus_id"""
    members = await test_db.members.find({"campus_id": test_campus["id"]}).to_list(None)

    assert len(members) >= 1
    assert all(m["campus_id"] == test_campus["id"] for m in members)


@pytest.mark.asyncio
async def test_create_care_event(test_db, test_campus, test_member):
    """Test creating a care event"""
    event_data = {
        "id": "event-123",
        "campus_id": test_campus["id"],
        "member_id": test_member["id"],
        "event_type": "birthday",
        "event_date": "2024-01-15",
        "title": "Birthday",
        "description": "Send wishes",
        "completed": False,
        "created_at": datetime.now(UTC).isoformat(),
    }

    await test_db.care_events.insert_one(event_data)

    # Verify event was created
    event = await test_db.care_events.find_one({"id": "event-123"})
    assert event is not None
    assert event["member_id"] == test_member["id"]
    assert event["event_type"] == "birthday"


@pytest.mark.asyncio
async def test_complete_care_event(test_db, test_care_event):
    """Test marking a care event as completed"""
    result = await test_db.care_events.update_one(
        {"id": test_care_event["id"]}, {"$set": {"completed": True, "completed_at": datetime.now(UTC).isoformat()}}
    )

    assert result.modified_count == 1

    # Verify completion
    event = await test_db.care_events.find_one({"id": test_care_event["id"]})
    assert event["completed"]


@pytest.mark.asyncio
async def test_query_care_events_by_type(test_db, test_campus, test_member):
    """Test querying care events by type"""
    # Create events of different types
    await test_db.care_events.insert_many(
        [
            {
                "id": "birthday-1",
                "campus_id": test_campus["id"],
                "member_id": test_member["id"],
                "event_type": "birthday",
                "event_date": "2024-01-15",
                "title": "Birthday",
                "completed": False,
            },
            {
                "id": "grief-1",
                "campus_id": test_campus["id"],
                "member_id": test_member["id"],
                "event_type": "grief_loss",
                "event_date": "2024-01-15",
                "title": "Grief Support",
                "completed": False,
            },
        ]
    )

    # Query birthday events
    birthdays = await test_db.care_events.find({"campus_id": test_campus["id"], "event_type": "birthday"}).to_list(None)

    assert len(birthdays) == 1
    assert birthdays[0]["event_type"] == "birthday"


@pytest.mark.asyncio
async def test_query_pending_care_events(test_db, test_campus, test_member):
    """Test querying pending (not completed) care events"""
    # Create completed and pending events
    await test_db.care_events.insert_many(
        [
            {
                "id": "completed-1",
                "campus_id": test_campus["id"],
                "member_id": test_member["id"],
                "event_type": "birthday",
                "event_date": "2024-01-15",
                "completed": True,
            },
            {
                "id": "pending-1",
                "campus_id": test_campus["id"],
                "member_id": test_member["id"],
                "event_type": "birthday",
                "event_date": "2024-01-16",
                "completed": False,
            },
        ]
    )

    # Query pending events
    pending = await test_db.care_events.find({"campus_id": test_campus["id"], "completed": False}).to_list(None)

    assert len(pending) == 1
    assert pending[0]["id"] == "pending-1"


@pytest.mark.asyncio
async def test_member_engagement_status(test_db, test_campus):
    """Test member engagement status tracking"""
    # Create members with different engagement statuses
    await test_db.members.insert_many(
        [
            {
                "id": "active-1",
                "campus_id": test_campus["id"],
                "name": "Active Member",
                "phone": "+6281111111111",
                "engagement_status": "active",
                "days_since_last_contact": 5,
            },
            {
                "id": "at-risk-1",
                "campus_id": test_campus["id"],
                "name": "At Risk Member",
                "phone": "+6282222222222",
                "engagement_status": "at_risk",
                "days_since_last_contact": 65,
            },
            {
                "id": "disconnected-1",
                "campus_id": test_campus["id"],
                "name": "Disconnected Member",
                "phone": "+6283333333333",
                "engagement_status": "disconnected",
                "days_since_last_contact": 95,
            },
        ]
    )

    # Query at-risk members
    at_risk = await test_db.members.find({"campus_id": test_campus["id"], "engagement_status": "at_risk"}).to_list(None)

    assert len(at_risk) == 1
    assert at_risk[0]["name"] == "At Risk Member"


@pytest.mark.asyncio
async def test_user_password_hashed(test_db, test_admin_user):
    """Test that user passwords are properly hashed"""
    user = await test_db.users.find_one({"id": test_admin_user["id"]})

    # Password should be hashed (not plaintext)
    assert user["password"] != "testpass123"
    assert user["password"].startswith("$2b$")  # bcrypt hash prefix


@pytest.mark.asyncio
async def test_campus_activation_status(test_db):
    """Test campus activation/deactivation"""
    # Create active and inactive campuses
    await test_db.campuses.insert_many(
        [
            {"id": "active-campus", "campus_name": "Active Campus", "is_active": True},
            {"id": "inactive-campus", "campus_name": "Inactive Campus", "is_active": False},
        ]
    )

    # Query only active campuses
    active = await test_db.campuses.find({"is_active": True}).to_list(None)

    # Should exclude inactive campus
    campus_ids = [c["id"] for c in active]
    assert "active-campus" in campus_ids
    assert "inactive-campus" not in campus_ids
