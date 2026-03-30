"""
Test pastoral notes system

Tests for creating, updating, and managing pastoral care notes and follow-ups.
"""

import os
import sys
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
async def pastoral_note(test_db, test_campus, test_member, test_admin_user):
    """Create a test pastoral note"""
    note_id = str(uuid.uuid4())
    note = {
        "id": note_id,
        "campus_id": test_campus["id"],
        "member_id": test_member["id"],
        "author_id": test_admin_user["id"],
        "author_name": test_admin_user["name"],
        "category": "counseling",
        "title": "Marriage Counseling Session",
        "content": "Initial session discussing communication challenges in marriage.",
        "is_private": False,
        "follow_up_date": (date.today() + timedelta(days=7)).isoformat(),
        "follow_up_completed": False,
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }
    await test_db.pastoral_notes.insert_one(note)
    return note


@pytest.fixture
async def private_note(test_db, test_campus, test_member, test_admin_user):
    """Create a private pastoral note"""
    note_id = str(uuid.uuid4())
    note = {
        "id": note_id,
        "campus_id": test_campus["id"],
        "member_id": test_member["id"],
        "author_id": test_admin_user["id"],
        "author_name": test_admin_user["name"],
        "category": "sensitive",
        "title": "Confidential Discussion",
        "content": "Private pastoral matter requiring discretion.",
        "is_private": True,
        "created_at": datetime.now(UTC).isoformat(),
    }
    await test_db.pastoral_notes.insert_one(note)
    return note


@pytest.mark.asyncio
async def test_create_pastoral_note(test_db, test_campus, test_member, test_admin_user):
    """Test creating a pastoral note"""
    note_data = {
        "id": str(uuid.uuid4()),
        "campus_id": test_campus["id"],
        "member_id": test_member["id"],
        "author_id": test_admin_user["id"],
        "author_name": test_admin_user["name"],
        "category": "visit",
        "title": "Home Visit",
        "content": "Visited member at home to check on recovery.",
        "is_private": False,
        "created_at": datetime.now(UTC).isoformat(),
    }

    await test_db.pastoral_notes.insert_one(note_data)

    note = await test_db.pastoral_notes.find_one({"id": note_data["id"]})
    assert note is not None
    assert note["title"] == "Home Visit"
    assert note["category"] == "visit"


@pytest.mark.asyncio
async def test_update_note_content(test_db, pastoral_note):
    """Test updating note content"""
    new_content = "Updated content with additional observations."

    result = await test_db.pastoral_notes.update_one(
        {"id": pastoral_note["id"]}, {"$set": {"content": new_content, "updated_at": datetime.now(UTC).isoformat()}}
    )

    assert result.modified_count == 1

    note = await test_db.pastoral_notes.find_one({"id": pastoral_note["id"]})
    assert note["content"] == new_content


@pytest.mark.asyncio
async def test_delete_pastoral_note(test_db, pastoral_note):
    """Test deleting a pastoral note"""
    result = await test_db.pastoral_notes.delete_one({"id": pastoral_note["id"]})
    assert result.deleted_count == 1

    note = await test_db.pastoral_notes.find_one({"id": pastoral_note["id"]})
    assert note is None


@pytest.mark.asyncio
async def test_query_notes_by_member(test_db, test_member, pastoral_note):
    """Test querying notes for a specific member"""
    notes = await test_db.pastoral_notes.find({"member_id": test_member["id"]}).sort("created_at", -1).to_list(None)

    assert len(notes) >= 1
    assert all(n["member_id"] == test_member["id"] for n in notes)


@pytest.mark.asyncio
async def test_query_notes_by_category(test_db, test_campus, pastoral_note):
    """Test querying notes by category"""
    notes = await test_db.pastoral_notes.find({"campus_id": test_campus["id"], "category": "counseling"}).to_list(None)

    assert len(notes) >= 1
    assert all(n["category"] == "counseling" for n in notes)


@pytest.mark.asyncio
async def test_private_note_isolation(test_db, test_campus, private_note, test_pastor_user):
    """Test that private notes are only visible to author"""
    all_notes = await test_db.pastoral_notes.find(
        {"campus_id": test_campus["id"], "$or": [{"is_private": False}, {"author_id": test_pastor_user["id"]}]}
    ).to_list(None)

    private_visible = [n for n in all_notes if n.get("is_private") and n["author_id"] != test_pastor_user["id"]]
    assert len(private_visible) == 0


@pytest.mark.asyncio
async def test_set_follow_up_date(test_db, test_campus, test_member, test_admin_user):
    """Test setting a follow-up date on a note"""
    note_data = {
        "id": str(uuid.uuid4()),
        "campus_id": test_campus["id"],
        "member_id": test_member["id"],
        "author_id": test_admin_user["id"],
        "category": "prayer_request",
        "title": "Prayer for healing",
        "content": "Member requested prayer for health issues.",
        "follow_up_date": (date.today() + timedelta(days=14)).isoformat(),
        "follow_up_completed": False,
        "created_at": datetime.now(UTC).isoformat(),
    }

    await test_db.pastoral_notes.insert_one(note_data)

    note = await test_db.pastoral_notes.find_one({"id": note_data["id"]})
    assert note["follow_up_date"] is not None
    assert note["follow_up_completed"] is False


@pytest.mark.asyncio
async def test_complete_follow_up(test_db, pastoral_note):
    """Test marking a follow-up as completed"""
    result = await test_db.pastoral_notes.update_one(
        {"id": pastoral_note["id"]},
        {"$set": {"follow_up_completed": True, "follow_up_completed_at": datetime.now(UTC).isoformat()}},
    )

    assert result.modified_count == 1

    note = await test_db.pastoral_notes.find_one({"id": pastoral_note["id"]})
    assert note["follow_up_completed"] is True


@pytest.mark.asyncio
async def test_query_pending_follow_ups(test_db, test_campus, pastoral_note):
    """Test querying notes with pending follow-ups"""
    pending = await test_db.pastoral_notes.find(
        {"campus_id": test_campus["id"], "follow_up_date": {"$exists": True, "$ne": None}, "follow_up_completed": False}
    ).to_list(None)

    assert len(pending) >= 1
    assert all(not n.get("follow_up_completed") for n in pending)


@pytest.mark.asyncio
async def test_query_overdue_follow_ups(test_db, test_campus, test_member, test_admin_user):
    """Test querying overdue follow-ups"""
    overdue_note = {
        "id": str(uuid.uuid4()),
        "campus_id": test_campus["id"],
        "member_id": test_member["id"],
        "author_id": test_admin_user["id"],
        "category": "visit",
        "title": "Overdue follow-up",
        "content": "This follow-up is overdue.",
        "follow_up_date": (date.today() - timedelta(days=5)).isoformat(),
        "follow_up_completed": False,
        "created_at": datetime.now(UTC).isoformat(),
    }
    await test_db.pastoral_notes.insert_one(overdue_note)

    overdue = await test_db.pastoral_notes.find(
        {
            "campus_id": test_campus["id"],
            "follow_up_date": {"$lt": date.today().isoformat()},
            "follow_up_completed": False,
        }
    ).to_list(None)

    assert len(overdue) >= 1


@pytest.mark.asyncio
async def test_note_categories():
    """Test valid note categories"""
    valid_categories = [
        "counseling",
        "visit",
        "prayer_request",
        "phone_call",
        "spiritual_growth",
        "family_matter",
        "health",
        "sensitive",
        "other",
    ]

    assert len(valid_categories) > 0
    assert "counseling" in valid_categories
    assert "sensitive" in valid_categories


@pytest.mark.asyncio
async def test_notes_by_author(test_db, test_campus, test_admin_user, pastoral_note):
    """Test querying notes by author"""
    notes = await test_db.pastoral_notes.find(
        {"campus_id": test_campus["id"], "author_id": test_admin_user["id"]}
    ).to_list(None)

    assert len(notes) >= 1
    assert all(n["author_id"] == test_admin_user["id"] for n in notes)


@pytest.mark.asyncio
async def test_search_notes_content(test_db, test_campus, pastoral_note):
    """Test searching notes by content"""
    notes = await test_db.pastoral_notes.find(
        {
            "campus_id": test_campus["id"],
            "$or": [
                {"title": {"$regex": "counseling", "$options": "i"}},
                {"content": {"$regex": "communication", "$options": "i"}},
            ],
        }
    ).to_list(None)

    assert len(notes) >= 1


@pytest.mark.asyncio
async def test_note_with_attachments(test_db, test_campus, test_member, test_admin_user):
    """Test note with file attachments metadata"""
    note_data = {
        "id": str(uuid.uuid4()),
        "campus_id": test_campus["id"],
        "member_id": test_member["id"],
        "author_id": test_admin_user["id"],
        "category": "visit",
        "title": "Hospital Visit with Photos",
        "content": "Visited member in hospital.",
        "attachments": [{"filename": "visit_photo.jpg", "type": "image/jpeg", "size": 1024000}],
        "created_at": datetime.now(UTC).isoformat(),
    }

    await test_db.pastoral_notes.insert_one(note_data)

    note = await test_db.pastoral_notes.find_one({"id": note_data["id"]})
    assert len(note["attachments"]) == 1
    assert note["attachments"][0]["filename"] == "visit_photo.jpg"


@pytest.mark.asyncio
async def test_notes_count_by_member(test_db, test_member, pastoral_note, private_note):
    """Test counting notes per member"""
    count = await test_db.pastoral_notes.count_documents({"member_id": test_member["id"]})

    assert count >= 2


@pytest.mark.asyncio
async def test_recent_notes_for_campus(test_db, test_campus, pastoral_note):
    """Test getting recent notes for dashboard"""
    recent = (
        await test_db.pastoral_notes.find({"campus_id": test_campus["id"]})
        .sort("created_at", -1)
        .limit(10)
        .to_list(None)
    )

    assert len(recent) >= 1
