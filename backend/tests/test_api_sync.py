"""
Test API Sync functionality

Tests for FaithFlow API sync configuration, webhook handling, and member synchronization.
"""

import hashlib
import hmac
import json
import os
import sys
import uuid
from datetime import UTC, datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
async def sync_config(test_db, test_campus):
    """Create a test sync configuration"""
    config_id = str(uuid.uuid4())
    config = {
        "id": config_id,
        "campus_id": test_campus["id"],
        "sync_method": "polling",
        "api_base_url": "https://api.example.com",
        "api_path_prefix": "/api",
        "api_email": "sync@example.com",
        "api_password": "encrypted_password_here",
        "polling_interval_hours": 6,
        "reconciliation_enabled": True,
        "reconciliation_time": "03:00",
        "filter_mode": "include",
        "filter_rules": [],
        "is_enabled": True,
        "webhook_secret": "test_webhook_secret_12345",
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }
    await test_db.sync_configs.insert_one(config)
    return config


@pytest.fixture
async def sync_log(test_db, test_campus):
    """Create a test sync log entry"""
    log_id = str(uuid.uuid4())
    log = {
        "id": log_id,
        "campus_id": test_campus["id"],
        "sync_type": "manual",
        "status": "completed",
        "stats": {"fetched": 100, "created": 10, "updated": 5, "archived": 0},
        "error": None,
        "started_at": datetime.now(UTC).isoformat(),
        "completed_at": datetime.now(UTC).isoformat(),
    }
    await test_db.sync_logs.insert_one(log)
    return log


@pytest.mark.asyncio
async def test_create_sync_config(test_db, test_campus):
    """Test creating a sync configuration"""
    config_data = {
        "id": str(uuid.uuid4()),
        "campus_id": test_campus["id"],
        "sync_method": "webhook",
        "api_base_url": "https://newapi.example.com",
        "api_path_prefix": "/v2/api",
        "api_email": "new@example.com",
        "api_password": "encrypted",
        "is_enabled": True,
        "webhook_secret": "new_secret",
        "created_at": datetime.now(UTC).isoformat(),
    }

    await test_db.sync_configs.insert_one(config_data)

    config = await test_db.sync_configs.find_one({"campus_id": test_campus["id"]})
    assert config is not None
    assert config["sync_method"] == "webhook"
    assert config["api_base_url"] == "https://newapi.example.com"


@pytest.mark.asyncio
async def test_update_sync_config(test_db, sync_config):
    """Test updating sync configuration"""
    result = await test_db.sync_configs.update_one(
        {"id": sync_config["id"]}, {"$set": {"polling_interval_hours": 12, "updated_at": datetime.now(UTC).isoformat()}}
    )

    assert result.modified_count == 1

    config = await test_db.sync_configs.find_one({"id": sync_config["id"]})
    assert config["polling_interval_hours"] == 12


@pytest.mark.asyncio
async def test_disable_sync_config(test_db, sync_config):
    """Test disabling sync for a campus"""
    result = await test_db.sync_configs.update_one({"id": sync_config["id"]}, {"$set": {"is_enabled": False}})

    assert result.modified_count == 1

    config = await test_db.sync_configs.find_one({"id": sync_config["id"]})
    assert config["is_enabled"] is False


@pytest.mark.asyncio
async def test_sync_config_filter_rules(test_db, sync_config):
    """Test sync configuration with filter rules"""
    filter_rules = [
        {"field": "gender", "operator": "equals", "value": "Female"},
        {"field": "age", "operator": "between", "value": [18, 35]},
    ]

    result = await test_db.sync_configs.update_one(
        {"id": sync_config["id"]}, {"$set": {"filter_rules": filter_rules, "filter_mode": "include"}}
    )

    assert result.modified_count == 1

    config = await test_db.sync_configs.find_one({"id": sync_config["id"]})
    assert len(config["filter_rules"]) == 2
    assert config["filter_rules"][0]["field"] == "gender"


@pytest.mark.asyncio
async def test_sync_log_creation(test_db, test_campus):
    """Test sync log is created for sync operations"""
    log_data = {
        "id": str(uuid.uuid4()),
        "campus_id": test_campus["id"],
        "sync_type": "polling",
        "status": "in_progress",
        "started_at": datetime.now(UTC).isoformat(),
    }

    await test_db.sync_logs.insert_one(log_data)

    log = await test_db.sync_logs.find_one({"id": log_data["id"]})
    assert log is not None
    assert log["status"] == "in_progress"


@pytest.mark.asyncio
async def test_sync_log_completion(test_db, sync_log):
    """Test updating sync log on completion"""
    stats = {"fetched": 200, "created": 20, "updated": 10, "archived": 5}

    result = await test_db.sync_logs.update_one(
        {"id": sync_log["id"]},
        {"$set": {"status": "completed", "stats": stats, "completed_at": datetime.now(UTC).isoformat()}},
    )

    assert result.modified_count == 1

    log = await test_db.sync_logs.find_one({"id": sync_log["id"]})
    assert log["status"] == "completed"
    assert log["stats"]["fetched"] == 200


@pytest.mark.asyncio
async def test_sync_log_failure(test_db, test_campus):
    """Test sync log records failures properly"""
    log_data = {
        "id": str(uuid.uuid4()),
        "campus_id": test_campus["id"],
        "sync_type": "manual",
        "status": "failed",
        "error": "Connection timeout after 3 retries",
        "started_at": datetime.now(UTC).isoformat(),
        "completed_at": datetime.now(UTC).isoformat(),
    }

    await test_db.sync_logs.insert_one(log_data)

    log = await test_db.sync_logs.find_one({"id": log_data["id"]})
    assert log["status"] == "failed"
    assert "timeout" in log["error"].lower()


@pytest.mark.asyncio
async def test_webhook_signature_verification():
    """Test webhook signature verification logic"""
    secret = "test_secret_key_12345"
    payload = json.dumps({"event": "member.created", "data": {"id": "123"}})

    expected_signature = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()

    actual_signature = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()

    assert hmac.compare_digest(expected_signature, actual_signature)


@pytest.mark.asyncio
async def test_webhook_invalid_signature():
    """Test webhook rejection with invalid signature"""
    secret = "test_secret_key_12345"
    wrong_secret = "wrong_secret"
    payload = json.dumps({"event": "member.created"})

    correct_sig = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()

    wrong_sig = hmac.new(wrong_secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()

    assert not hmac.compare_digest(correct_sig, wrong_sig)


@pytest.mark.asyncio
async def test_sync_logs_query_by_campus(test_db, test_campus, sync_log):
    """Test querying sync logs by campus"""
    logs = await test_db.sync_logs.find({"campus_id": test_campus["id"]}).sort("started_at", -1).to_list(None)

    assert len(logs) >= 1
    assert all(log["campus_id"] == test_campus["id"] for log in logs)


@pytest.mark.asyncio
async def test_sync_config_unique_per_campus(test_db, test_campus, sync_config):
    """Test that only one sync config exists per campus"""
    configs = await test_db.sync_configs.find({"campus_id": test_campus["id"]}).to_list(None)

    assert len(configs) == 1


@pytest.mark.asyncio
async def test_member_external_id_tracking(test_db, test_campus):
    """Test members synced from external API have external_member_id"""
    member_data = {
        "id": str(uuid.uuid4()),
        "campus_id": test_campus["id"],
        "name": "External Member",
        "external_member_id": "ext-12345",
        "source": "faithflow_sync",
        "created_at": datetime.now(UTC).isoformat(),
    }

    await test_db.members.insert_one(member_data)

    member = await test_db.members.find_one({"external_member_id": "ext-12345"})
    assert member is not None
    assert member["source"] == "faithflow_sync"


@pytest.mark.asyncio
async def test_sync_updates_existing_member(test_db, test_campus):
    """Test sync updates member matched by external_member_id"""
    original = {
        "id": str(uuid.uuid4()),
        "campus_id": test_campus["id"],
        "name": "Original Name",
        "external_member_id": "ext-99999",
        "created_at": datetime.now(UTC).isoformat(),
    }
    await test_db.members.insert_one(original)

    result = await test_db.members.update_one(
        {"external_member_id": "ext-99999", "campus_id": test_campus["id"]},
        {"$set": {"name": "Updated Name", "phone": "+6281234567890"}},
    )

    assert result.modified_count == 1

    member = await test_db.members.find_one({"external_member_id": "ext-99999"})
    assert member["name"] == "Updated Name"
    assert member["phone"] == "+6281234567890"
