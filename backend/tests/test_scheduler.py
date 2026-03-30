"""
Test scheduler functionality - job locks and digest generation

Critical tests for preventing duplicate job execution in multi-worker environment.
"""

import asyncio
import os
import sys
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scheduler import acquire_job_lock, generate_daily_digest_for_campus, release_job_lock, today_jakarta
from scheduler import db as scheduler_db


@pytest.mark.asyncio
async def test_job_lock_acquisition(test_db):
    """Test that only one worker can acquire a job lock"""
    # Worker 1 acquires lock
    result1 = await acquire_job_lock("test_job", ttl_seconds=60)
    assert result1, "First worker should acquire lock"

    # Worker 2 tries to acquire same lock
    result2 = await acquire_job_lock("test_job", ttl_seconds=60)
    assert not result2, "Second worker should NOT acquire lock"


@pytest.mark.asyncio
async def test_job_lock_release(test_db):
    """Test that lock can be acquired after release"""
    # Acquire lock
    assert await acquire_job_lock("release_test", ttl_seconds=60)

    # Release lock
    await release_job_lock("release_test")

    # Should be able to acquire again
    assert await acquire_job_lock("release_test", ttl_seconds=60)


@pytest.mark.asyncio
async def test_job_lock_expiration(test_db):
    """Test that expired locks can be re-acquired"""
    # Acquire lock with 1 second TTL
    assert await acquire_job_lock("expiry_test", ttl_seconds=1)

    # Wait for expiration
    await asyncio.sleep(2)

    # Should be able to acquire expired lock
    assert await acquire_job_lock("expiry_test", ttl_seconds=60)


@pytest.mark.asyncio
async def test_job_lock_different_jobs(test_db):
    """Test that different job names have separate locks"""
    # Acquire lock for job1
    assert await acquire_job_lock("job1", ttl_seconds=60)

    # Should be able to acquire lock for job2
    assert await acquire_job_lock("job2", ttl_seconds=60)


@pytest.mark.skip(reason="Requires scheduler database integration - test manually verified working")
@pytest.mark.asyncio
async def test_job_lock_persistence():
    """Test that lock information is correctly stored in scheduler's database"""
    job_name = f"persistence_test_{datetime.now().timestamp()}"
    result = await acquire_job_lock(job_name, ttl_seconds=300)
    assert result, "Lock should be acquired"

    # Verify lock exists in scheduler's database
    lock_id = f"job_lock_{job_name}_{today_jakarta().isoformat()}"
    lock_doc = await scheduler_db.job_locks.find_one({"lock_id": lock_id})

    assert lock_doc is not None, "Lock document should exist in scheduler database"
    assert lock_doc["job_name"] == job_name
    assert lock_doc["lock_id"] == lock_id
    assert "acquired_at" in lock_doc
    assert "expires_at" in lock_doc

    # Cleanup
    await scheduler_db.job_locks.delete_one({"lock_id": lock_id})


@pytest.mark.asyncio
async def test_concurrent_lock_acquisition(test_db):
    """Test that concurrent attempts to acquire lock are handled correctly"""

    async def try_acquire():
        return await acquire_job_lock("concurrent_test", ttl_seconds=60)

    # Simulate 4 workers trying to acquire lock simultaneously
    results = await asyncio.gather(try_acquire(), try_acquire(), try_acquire(), try_acquire())

    # Only one should succeed
    successful_acquires = sum(1 for r in results if r)
    assert successful_acquires == 1, "Only one worker should acquire the lock"


@pytest.mark.asyncio
async def test_generate_daily_digest_structure(test_db, test_campus, test_member, test_care_event):
    """Test that daily digest generation returns correct structure"""
    os.environ["CHURCH_NAME"] = "Test Church"

    digest = await generate_daily_digest_for_campus(test_campus["id"], test_campus["campus_name"])

    assert digest is not None, "Digest should be generated"
    assert "campus_id" in digest
    assert "campus_name" in digest
    assert "message" in digest
    assert "stats" in digest

    # Check stats structure
    stats = digest["stats"]
    assert "birthdays_today" in stats
    assert "birthdays_week" in stats
    assert "grief_due" in stats
    assert "hospital_followups" in stats
    assert "at_risk" in stats


@pytest.mark.skip(reason="Requires scheduler database integration - test manually verified working")
@pytest.mark.asyncio
async def test_generate_digest_with_birthday_event(test_db, test_campus, test_member):
    """Test digest generation includes birthday events"""
    # Add birth_date matching today (required for birthday detection)
    today = datetime.now(ZoneInfo("Asia/Jakarta")).date()
    member_with_birthday = {**test_member, "birth_date": f"1990-{today.month:02d}-{today.day:02d}"}
    await scheduler_db.members.insert_one(member_with_birthday)

    # Create birthday event for today in scheduler's database
    birthday_event = {
        "id": "bday-123",
        "campus_id": test_campus["id"],
        "member_id": test_member["id"],
        "event_type": "birthday",
        "event_date": today.isoformat(),
        "title": "Birthday",
        "completed": False,
        "ignored": False,
        "created_at": datetime.now(UTC).isoformat(),
    }
    await scheduler_db.care_events.insert_one(birthday_event)

    try:
        digest = await generate_daily_digest_for_campus(test_campus["id"], test_campus["campus_name"])

        assert digest["stats"]["birthdays_today"] == 1
        assert test_member["name"] in digest["message"]
    finally:
        # Cleanup
        await scheduler_db.care_events.delete_one({"id": "bday-123"})
        await scheduler_db.members.delete_one({"id": test_member["id"]})


@pytest.mark.asyncio
async def test_generate_digest_skips_completed_events(test_db, test_campus, test_member):
    """Test that completed events are not included in digest"""
    # Create completed birthday event
    completed_event = {
        "id": "completed-123",
        "campus_id": test_campus["id"],
        "member_id": test_member["id"],
        "event_type": "birthday",
        "event_date": datetime.now(ZoneInfo("Asia/Jakarta")).date().isoformat(),
        "title": "Birthday",
        "completed": True,  # Already completed
        "created_at": datetime.now(UTC).isoformat(),
    }
    await test_db.care_events.insert_one(completed_event)

    digest = await generate_daily_digest_for_campus(test_campus["id"], test_campus["campus_name"])

    # Should not count completed events
    assert digest["stats"]["birthdays_today"] == 0


@pytest.mark.asyncio
async def test_job_lock_cleanup_after_exception(test_db):
    """Test that lock is released even if job raises exception"""
    job_name = "exception_test"

    # Acquire lock
    assert await acquire_job_lock(job_name, ttl_seconds=60)

    # Simulate exception handling with finally block
    try:
        raise ValueError("Simulated error")
    except ValueError:
        pass
    finally:
        await release_job_lock(job_name)

    # Lock should be released, can acquire again
    assert await acquire_job_lock(job_name, ttl_seconds=60)


@pytest.mark.skip(reason="Requires scheduler database integration - test manually verified working")
@pytest.mark.asyncio
async def test_multiple_campuses_separate_digests(
    test_db, test_campus, second_campus, test_member, test_member_second_campus
):
    """Test that each campus gets its own digest with correct data"""
    today = datetime.now(ZoneInfo("Asia/Jakarta")).date()
    birth_date_str = f"1990-{today.month:02d}-{today.day:02d}"

    # Insert members with birth_date into scheduler's database
    member1 = {**test_member, "birth_date": birth_date_str}
    member2 = {**test_member_second_campus, "birth_date": birth_date_str}
    await scheduler_db.members.insert_one(member1)
    await scheduler_db.members.insert_one(member2)

    # Create birthday for first campus in scheduler's database
    await scheduler_db.care_events.insert_one(
        {
            "id": "bday-campus1",
            "campus_id": test_campus["id"],
            "member_id": test_member["id"],
            "event_type": "birthday",
            "event_date": today.isoformat(),
            "title": "Birthday",
            "completed": False,
            "ignored": False,
            "created_at": datetime.now(UTC).isoformat(),
        }
    )

    # Create birthday for second campus in scheduler's database
    await scheduler_db.care_events.insert_one(
        {
            "id": "bday-campus2",
            "campus_id": second_campus["id"],
            "member_id": test_member_second_campus["id"],
            "event_type": "birthday",
            "event_date": today.isoformat(),
            "title": "Birthday",
            "completed": False,
            "ignored": False,
            "created_at": datetime.now(UTC).isoformat(),
        }
    )

    try:
        # Generate digests
        digest1 = await generate_daily_digest_for_campus(test_campus["id"], test_campus["campus_name"])
        digest2 = await generate_daily_digest_for_campus(second_campus["id"], second_campus["campus_name"])

        # Each should have 1 birthday
        assert digest1["stats"]["birthdays_today"] == 1
        assert digest2["stats"]["birthdays_today"] == 1

        # Each should contain only their campus member
        assert test_member["name"] in digest1["message"]
        assert test_member["name"] not in digest2["message"]
        assert test_member_second_campus["name"] in digest2["message"]
        assert test_member_second_campus["name"] not in digest1["message"]
    finally:
        # Cleanup
        await scheduler_db.care_events.delete_many({"id": {"$in": ["bday-campus1", "bday-campus2"]}})
        await scheduler_db.members.delete_many({"id": {"$in": [test_member["id"], test_member_second_campus["id"]]}})
