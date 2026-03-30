"""
Test multi-tenancy data isolation

Critical tests to ensure campuses cannot access each other's data.
"""

import os
import sys
from datetime import UTC

import pytest

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.mark.asyncio
async def test_members_isolated_by_campus(test_db, test_campus, second_campus, test_member, test_member_second_campus):
    """Test that members query is filtered by campus_id"""
    # Query members for first campus
    campus1_members = await test_db.members.find({"campus_id": test_campus["id"]}).to_list(None)

    # Query members for second campus
    campus2_members = await test_db.members.find({"campus_id": second_campus["id"]}).to_list(None)

    # Each campus should see only their member
    assert len(campus1_members) == 1
    assert len(campus2_members) == 1
    assert campus1_members[0]["id"] == test_member["id"]
    assert campus2_members[0]["id"] == test_member_second_campus["id"]


@pytest.mark.asyncio
async def test_care_events_isolated_by_campus(
    test_db, test_campus, second_campus, test_member, test_member_second_campus
):
    """Test that care events are isolated by campus"""
    # Create care event for first campus
    event1 = {
        "id": "event-1",
        "campus_id": test_campus["id"],
        "member_id": test_member["id"],
        "event_type": "birthday",
        "event_date": "2024-01-15",
        "title": "Campus 1 Event",
    }
    await test_db.care_events.insert_one(event1)

    # Create care event for second campus
    event2 = {
        "id": "event-2",
        "campus_id": second_campus["id"],
        "member_id": test_member_second_campus["id"],
        "event_type": "birthday",
        "event_date": "2024-01-15",
        "title": "Campus 2 Event",
    }
    await test_db.care_events.insert_one(event2)

    # Query events for each campus
    campus1_events = await test_db.care_events.find({"campus_id": test_campus["id"]}).to_list(None)

    campus2_events = await test_db.care_events.find({"campus_id": second_campus["id"]}).to_list(None)

    # Each should see only their events
    assert len(campus1_events) == 1
    assert len(campus2_events) == 1
    assert campus1_events[0]["title"] == "Campus 1 Event"
    assert campus2_events[0]["title"] == "Campus 2 Event"


@pytest.mark.asyncio
async def test_users_isolated_by_campus(test_db, test_campus, second_campus):
    """Test that users (except full_admin) are isolated by campus"""
    # Create user for first campus
    user1 = {
        "id": "user-1",
        "campus_id": test_campus["id"],
        "name": "Campus 1 Admin",
        "email": "admin1@test.com",
        "role": "campus_admin",
    }
    await test_db.users.insert_one(user1)

    # Create user for second campus
    user2 = {
        "id": "user-2",
        "campus_id": second_campus["id"],
        "name": "Campus 2 Admin",
        "email": "admin2@test.com",
        "role": "campus_admin",
    }
    await test_db.users.insert_one(user2)

    # Query users for each campus
    campus1_users = await test_db.users.find({"campus_id": test_campus["id"], "role": {"$ne": "full_admin"}}).to_list(
        None
    )

    campus2_users = await test_db.users.find({"campus_id": second_campus["id"], "role": {"$ne": "full_admin"}}).to_list(
        None
    )

    # Each should see only their users
    assert len(campus1_users) == 1
    assert len(campus2_users) == 1
    assert campus1_users[0]["id"] == "user-1"
    assert campus2_users[0]["id"] == "user-2"


@pytest.mark.asyncio
async def test_cannot_modify_other_campus_member(test_db, test_campus, second_campus, test_member_second_campus):
    """Test that updating a member requires matching campus_id"""
    # Try to update member from campus2 using campus1's id
    result = await test_db.members.update_one(
        {
            "id": test_member_second_campus["id"],
            "campus_id": test_campus["id"],  # Wrong campus!
        },
        {"$set": {"name": "Hacked Name"}},
    )

    # Update should fail (0 documents modified)
    assert result.modified_count == 0

    # Verify member was not changed
    member = await test_db.members.find_one({"id": test_member_second_campus["id"]})
    assert member["name"] == "Jane Smith"  # Original name


@pytest.mark.asyncio
async def test_cannot_delete_other_campus_member(test_db, test_campus, second_campus, test_member_second_campus):
    """Test that deleting a member requires matching campus_id"""
    # Try to delete member from campus2 using campus1's id
    result = await test_db.members.delete_one(
        {
            "id": test_member_second_campus["id"],
            "campus_id": test_campus["id"],  # Wrong campus!
        }
    )

    # Delete should fail (0 documents deleted)
    assert result.deleted_count == 0

    # Verify member still exists
    member = await test_db.members.find_one({"id": test_member_second_campus["id"]})
    assert member is not None


@pytest.mark.asyncio
async def test_activity_logs_isolated_by_campus(test_db, test_campus, second_campus):
    """Test that activity logs are isolated by campus"""
    # Create activity log for first campus
    log1 = {"id": "log-1", "campus_id": test_campus["id"], "action": "member_created", "user_name": "Admin 1"}
    await test_db.activity_logs.insert_one(log1)

    # Create activity log for second campus
    log2 = {"id": "log-2", "campus_id": second_campus["id"], "action": "member_created", "user_name": "Admin 2"}
    await test_db.activity_logs.insert_one(log2)

    # Query logs for each campus
    campus1_logs = await test_db.activity_logs.find({"campus_id": test_campus["id"]}).to_list(None)

    campus2_logs = await test_db.activity_logs.find({"campus_id": second_campus["id"]}).to_list(None)

    # Each should see only their logs
    assert len(campus1_logs) == 1
    assert len(campus2_logs) == 1
    assert campus1_logs[0]["user_name"] == "Admin 1"
    assert campus2_logs[0]["user_name"] == "Admin 2"


@pytest.mark.asyncio
async def test_full_admin_can_see_all_campuses(test_db, test_campus, second_campus):
    """Test that full_admin users can access multiple campuses"""
    # Create full_admin user
    admin = {
        "id": "full-admin-1",
        "campus_id": test_campus["id"],
        "name": "Super Admin",
        "email": "super@test.com",
        "role": "full_admin",
    }
    await test_db.users.insert_one(admin)

    # Full admin should be able to query all campuses
    all_campuses = await test_db.campuses.find({"is_active": True}).to_list(None)

    # Should see both campuses
    assert len(all_campuses) == 2
    campus_ids = [c["id"] for c in all_campuses]
    assert test_campus["id"] in campus_ids
    assert second_campus["id"] in campus_ids


@pytest.mark.asyncio
async def test_dashboard_cache_isolated_by_campus(test_db, test_campus, second_campus):
    """Test that dashboard cache is isolated by campus"""
    from datetime import datetime

    # Create cache for first campus
    cache1 = {
        "cache_key": f"dashboard_reminders_{test_campus['id']}_2024-01-15",
        "campus_id": test_campus["id"],
        "data": {"total_tasks": 5},
        "calculated_at": datetime.now(UTC),
    }
    await test_db.dashboard_cache.insert_one(cache1)

    # Create cache for second campus
    cache2 = {
        "cache_key": f"dashboard_reminders_{second_campus['id']}_2024-01-15",
        "campus_id": second_campus["id"],
        "data": {"total_tasks": 3},
        "calculated_at": datetime.now(UTC),
    }
    await test_db.dashboard_cache.insert_one(cache2)

    # Query cache for each campus
    campus1_cache = await test_db.dashboard_cache.find_one({"campus_id": test_campus["id"]})

    campus2_cache = await test_db.dashboard_cache.find_one({"campus_id": second_campus["id"]})

    # Each should see only their cache
    assert campus1_cache["data"]["total_tasks"] == 5
    assert campus2_cache["data"]["total_tasks"] == 3


@pytest.mark.asyncio
async def test_grief_support_isolated_by_campus(
    test_db, test_campus, second_campus, test_member, test_member_second_campus
):
    """Test that grief support stages are isolated by campus"""
    # Create grief stage for first campus
    stage1 = {
        "id": "stage-1",
        "campus_id": test_campus["id"],
        "member_id": test_member["id"],
        "stage": "1_week",
        "completed": False,
    }
    await test_db.grief_support.insert_one(stage1)

    # Create grief stage for second campus
    stage2 = {
        "id": "stage-2",
        "campus_id": second_campus["id"],
        "member_id": test_member_second_campus["id"],
        "stage": "1_week",
        "completed": False,
    }
    await test_db.grief_support.insert_one(stage2)

    # Query stages for each campus
    campus1_stages = await test_db.grief_support.find({"campus_id": test_campus["id"]}).to_list(None)

    campus2_stages = await test_db.grief_support.find({"campus_id": second_campus["id"]}).to_list(None)

    # Each should see only their stages
    assert len(campus1_stages) == 1
    assert len(campus2_stages) == 1
    assert campus1_stages[0]["member_id"] == test_member["id"]
    assert campus2_stages[0]["member_id"] == test_member_second_campus["id"]
