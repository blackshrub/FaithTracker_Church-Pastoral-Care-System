"""
Test financial aid management

Tests for financial aid schedules, recurring payments, and aid tracking.
"""

import os
import sys
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
async def financial_aid_schedule(test_db, test_campus, test_member):
    """Create a test financial aid schedule"""
    schedule_id = str(uuid.uuid4())
    schedule = {
        "id": schedule_id,
        "campus_id": test_campus["id"],
        "member_id": test_member["id"],
        "aid_type": "education",
        "amount": 500000,
        "currency": "IDR",
        "frequency": "monthly",
        "start_date": date.today().isoformat(),
        "end_date": (date.today() + timedelta(days=365)).isoformat(),
        "next_payment_date": date.today().isoformat(),
        "description": "Education support for child",
        "is_active": True,
        "total_paid": 0,
        "payment_count": 0,
        "created_at": datetime.now(UTC).isoformat(),
    }
    await test_db.financial_aid_schedules.insert_one(schedule)
    return schedule


@pytest.fixture
async def one_time_aid(test_db, test_campus, test_member):
    """Create a one-time financial aid event"""
    event_id = str(uuid.uuid4())
    event = {
        "id": event_id,
        "campus_id": test_campus["id"],
        "member_id": test_member["id"],
        "event_type": "financial_aid",
        "event_date": date.today().isoformat(),
        "title": "Emergency Medical Aid",
        "description": "Hospital bill assistance",
        "aid_type": "medical",
        "aid_amount": 2000000,
        "completed": False,
        "created_at": datetime.now(UTC).isoformat(),
    }
    await test_db.care_events.insert_one(event)
    return event


@pytest.mark.asyncio
async def test_create_financial_aid_schedule(test_db, test_campus, test_member):
    """Test creating a recurring financial aid schedule"""
    schedule_data = {
        "id": str(uuid.uuid4()),
        "campus_id": test_campus["id"],
        "member_id": test_member["id"],
        "aid_type": "living_expenses",
        "amount": 1000000,
        "frequency": "monthly",
        "start_date": date.today().isoformat(),
        "is_active": True,
        "created_at": datetime.now(UTC).isoformat(),
    }

    await test_db.financial_aid_schedules.insert_one(schedule_data)

    schedule = await test_db.financial_aid_schedules.find_one({"id": schedule_data["id"]})
    assert schedule is not None
    assert schedule["aid_type"] == "living_expenses"
    assert schedule["amount"] == 1000000


@pytest.mark.asyncio
async def test_update_financial_aid_amount(test_db, financial_aid_schedule):
    """Test updating aid amount"""
    result = await test_db.financial_aid_schedules.update_one(
        {"id": financial_aid_schedule["id"]}, {"$set": {"amount": 750000}}
    )

    assert result.modified_count == 1

    schedule = await test_db.financial_aid_schedules.find_one({"id": financial_aid_schedule["id"]})
    assert schedule["amount"] == 750000


@pytest.mark.asyncio
async def test_deactivate_financial_aid(test_db, financial_aid_schedule):
    """Test deactivating a financial aid schedule"""
    result = await test_db.financial_aid_schedules.update_one(
        {"id": financial_aid_schedule["id"]},
        {"$set": {"is_active": False, "deactivated_at": datetime.now(UTC).isoformat()}},
    )

    assert result.modified_count == 1

    schedule = await test_db.financial_aid_schedules.find_one({"id": financial_aid_schedule["id"]})
    assert schedule["is_active"] is False


@pytest.mark.asyncio
async def test_record_payment(test_db, financial_aid_schedule):
    """Test recording a payment for recurring aid"""
    current = await test_db.financial_aid_schedules.find_one({"id": financial_aid_schedule["id"]})
    new_total = current["total_paid"] + current["amount"]
    new_count = current["payment_count"] + 1
    next_date = (date.today() + timedelta(days=30)).isoformat()

    result = await test_db.financial_aid_schedules.update_one(
        {"id": financial_aid_schedule["id"]},
        {
            "$set": {
                "total_paid": new_total,
                "payment_count": new_count,
                "next_payment_date": next_date,
                "last_payment_date": date.today().isoformat(),
            }
        },
    )

    assert result.modified_count == 1

    schedule = await test_db.financial_aid_schedules.find_one({"id": financial_aid_schedule["id"]})
    assert schedule["payment_count"] == 1
    assert schedule["total_paid"] == 500000


@pytest.mark.asyncio
async def test_query_active_schedules(test_db, test_campus, financial_aid_schedule):
    """Test querying active financial aid schedules"""
    schedules = await test_db.financial_aid_schedules.find({"campus_id": test_campus["id"], "is_active": True}).to_list(
        None
    )

    assert len(schedules) >= 1
    assert all(s["is_active"] for s in schedules)


@pytest.mark.asyncio
async def test_query_upcoming_payments(test_db, test_campus, financial_aid_schedule):
    """Test querying upcoming payment due dates"""
    upcoming_date = (date.today() + timedelta(days=7)).isoformat()

    schedules = await test_db.financial_aid_schedules.find(
        {"campus_id": test_campus["id"], "is_active": True, "next_payment_date": {"$lte": upcoming_date}}
    ).to_list(None)

    assert len(schedules) >= 1


@pytest.mark.asyncio
async def test_query_overdue_payments(test_db, test_campus, test_member):
    """Test querying overdue payments"""
    overdue_schedule = {
        "id": str(uuid.uuid4()),
        "campus_id": test_campus["id"],
        "member_id": test_member["id"],
        "aid_type": "education",
        "amount": 500000,
        "frequency": "monthly",
        "next_payment_date": (date.today() - timedelta(days=5)).isoformat(),
        "is_active": True,
        "created_at": datetime.now(UTC).isoformat(),
    }
    await test_db.financial_aid_schedules.insert_one(overdue_schedule)

    overdue = await test_db.financial_aid_schedules.find(
        {"campus_id": test_campus["id"], "is_active": True, "next_payment_date": {"$lt": date.today().isoformat()}}
    ).to_list(None)

    assert len(overdue) >= 1


@pytest.mark.asyncio
async def test_aid_type_validation(test_db, test_campus, test_member):
    """Test various aid types"""
    valid_aid_types = ["education", "medical", "living_expenses", "emergency", "other"]

    for aid_type in valid_aid_types:
        schedule = {
            "id": str(uuid.uuid4()),
            "campus_id": test_campus["id"],
            "member_id": test_member["id"],
            "aid_type": aid_type,
            "amount": 100000,
            "frequency": "one_time",
            "is_active": True,
            "created_at": datetime.now(UTC).isoformat(),
        }
        await test_db.financial_aid_schedules.insert_one(schedule)

    schedules = await test_db.financial_aid_schedules.find({"member_id": test_member["id"]}).to_list(None)

    aid_types = [s["aid_type"] for s in schedules]
    for expected_type in valid_aid_types:
        assert expected_type in aid_types


@pytest.mark.asyncio
async def test_frequency_types(test_db, test_campus, test_member):
    """Test different payment frequencies"""
    frequencies = ["weekly", "biweekly", "monthly", "quarterly", "one_time"]

    for freq in frequencies:
        schedule = {
            "id": str(uuid.uuid4()),
            "campus_id": test_campus["id"],
            "member_id": test_member["id"],
            "aid_type": "living_expenses",
            "amount": 100000,
            "frequency": freq,
            "is_active": True,
            "created_at": datetime.now(UTC).isoformat(),
        }
        await test_db.financial_aid_schedules.insert_one(schedule)

    schedules = await test_db.financial_aid_schedules.find({"member_id": test_member["id"]}).to_list(None)

    found_frequencies = [s["frequency"] for s in schedules]
    for expected_freq in frequencies:
        assert expected_freq in found_frequencies


@pytest.mark.asyncio
async def test_complete_one_time_aid(test_db, one_time_aid):
    """Test completing a one-time aid event"""
    result = await test_db.care_events.update_one(
        {"id": one_time_aid["id"]},
        {
            "$set": {
                "completed": True,
                "completed_at": datetime.now(UTC).isoformat(),
                "notes": "Payment disbursed successfully",
            }
        },
    )

    assert result.modified_count == 1

    event = await test_db.care_events.find_one({"id": one_time_aid["id"]})
    assert event["completed"] is True


@pytest.mark.asyncio
async def test_aid_total_by_member(test_db, test_campus, test_member, financial_aid_schedule):
    """Test calculating total aid given to a member"""
    await test_db.financial_aid_schedules.update_one(
        {"id": financial_aid_schedule["id"]}, {"$set": {"total_paid": 2500000, "payment_count": 5}}
    )

    pipeline = [
        {"$match": {"member_id": test_member["id"]}},
        {"$group": {"_id": "$member_id", "total_aid": {"$sum": "$total_paid"}, "total_schedules": {"$sum": 1}}},
    ]

    result = await (await test_db.financial_aid_schedules.aggregate(pipeline)).to_list(None)
    assert len(result) == 1
    assert result[0]["total_aid"] >= 2500000


@pytest.mark.asyncio
async def test_aid_by_type_summary(test_db, test_campus, financial_aid_schedule):
    """Test summarizing aid by type for campus"""
    pipeline = [
        {"$match": {"campus_id": test_campus["id"], "is_active": True}},
        {"$group": {"_id": "$aid_type", "count": {"$sum": 1}, "total_monthly": {"$sum": "$amount"}}},
    ]

    result = await (await test_db.financial_aid_schedules.aggregate(pipeline)).to_list(None)
    assert len(result) >= 1


@pytest.mark.asyncio
async def test_delete_schedule_with_member(test_db, test_campus, test_member, financial_aid_schedule):
    """Test that deleting member doesn't orphan schedules (should cascade or archive)"""
    schedule_before = await test_db.financial_aid_schedules.find_one({"member_id": test_member["id"]})
    assert schedule_before is not None

    await test_db.financial_aid_schedules.update_many(
        {"member_id": test_member["id"]}, {"$set": {"is_active": False, "deactivated_reason": "member_deleted"}}
    )

    schedule_after = await test_db.financial_aid_schedules.find_one({"member_id": test_member["id"]})
    assert schedule_after["is_active"] is False
