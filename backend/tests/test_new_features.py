"""
Tests for new features:
- RequestTraceMiddleware (X-Request-ID, X-Response-Time)
- SearchService (Meilisearch integration)
- ChangeStreamWatcher (MongoDB change streams)
"""

import asyncio
import json
import os
import sys
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set required env vars BEFORE importing server.py (needed for middleware tests)
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "faithtracker_test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-unit-tests")

import contextlib

from services.change_stream import (
    _RESUME_TOKEN_KEY,
    ChangeStreamWatcher,
    get_change_stream_watcher,
    is_change_stream_active,
)
from services.search import (
    CARE_EVENTS_CONFIG,
    CARE_EVENTS_INDEX,
    MEMBERS_CONFIG,
    MEMBERS_INDEX,
    SearchService,
    _prepare_care_event_doc,
    _prepare_member_doc,
    get_search_service,
)

# ===================================================================
# Fixtures
# ===================================================================

CAMPUS_ID = "campus-test-001"
CHURCH_ID = "church-test-001"
MEMBER_ID = "member-test-001"


def _make_member(**overrides):
    """Helper to create a sample member dict."""
    defaults = {
        "id": MEMBER_ID,
        "name": "John Doe",
        "phone": "+6281234567890",
        "email": "john@example.com",
        "address": "123 Test Street",
        "notes": "Test member",
        "family_group_name": "Doe Family",
        "campus_id": CAMPUS_ID,
        "engagement_status": "active",
        "gender": "male",
        "category": "youth",
        "photo_url": "/uploads/photo.jpg",
        "created_at": datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC),
    }
    defaults.update(overrides)
    return defaults


def _make_care_event(**overrides):
    """Helper to create a sample care event dict."""
    defaults = {
        "id": "event-test-001",
        "title": "Birthday Celebration",
        "description": "Send birthday wishes",
        "event_type": "birthday",
        "member_id": MEMBER_ID,
        "member_name": "John Doe",
        "campus_id": CAMPUS_ID,
        "event_date": datetime(2025, 5, 15, 0, 0, 0, tzinfo=UTC),
        "completed": False,
        "ignored": False,
        "created_at": datetime(2025, 5, 1, 8, 0, 0, tzinfo=UTC),
    }
    defaults.update(overrides)
    return defaults


def _make_activity_log_document(**overrides):
    """Helper to create a sample activity log document (as stored in MongoDB)."""
    defaults = {
        "id": "activity-001",
        "campus_id": CAMPUS_ID,
        "user_id": "user-001",
        "user_name": "Pastor Smith",
        "user_photo_url": "/uploads/pastor.jpg",
        "action_type": "complete",
        "member_id": MEMBER_ID,
        "member_name": "John Doe",
        "care_event_id": "event-001",
        "event_type": "birthday",
        "notes": "Completed birthday visit",
        "created_at": datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC),
    }
    defaults.update(overrides)
    return defaults


@pytest.fixture
def mock_meili_client():
    """Create a mocked meilisearch.Client with common methods."""
    client = MagicMock()
    client.health.return_value = {"status": "available"}

    # Mock index objects
    members_index = MagicMock()
    care_events_index = MagicMock()

    def _index_side_effect(name):
        if name == MEMBERS_INDEX:
            return members_index
        elif name == CARE_EVENTS_INDEX:
            return care_events_index
        return MagicMock()

    client.index = MagicMock(side_effect=_index_side_effect)
    client.create_index = MagicMock()

    # Store references for test assertions
    client._members_index = members_index
    client._care_events_index = care_events_index

    return client


@pytest.fixture
def search_service(mock_meili_client):
    """Create a SearchService with a mocked Meilisearch client."""
    svc = SearchService()
    svc._client = mock_meili_client
    svc._available = True
    return svc


@pytest.fixture
def mock_redis():
    """Create a mock async Redis client for change stream tests."""
    client = AsyncMock()
    client.get = AsyncMock(return_value=None)
    client.setex = AsyncMock()
    client.publish = AsyncMock()
    client.ping = AsyncMock()
    return client


@pytest.fixture
def mock_db():
    """Create a mock async MongoDB database for change stream tests."""
    db = MagicMock()

    # Mock activity_logs collection
    activity_logs = MagicMock()
    activity_logs.watch = MagicMock()
    db.activity_logs = activity_logs

    # Mock members collection (used by bulk_index_members)
    members_coll = MagicMock()
    db.members = members_coll

    # Mock care_events collection
    care_events_coll = MagicMock()
    db.care_events = care_events_coll

    return db


# ===================================================================
# RequestTraceMiddleware Tests
# ===================================================================


class TestRequestTraceMiddleware:
    """Test the ASGI middleware that adds X-Request-ID and X-Response-Time headers."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_response_includes_request_id_header(self):
        """Response should include an auto-generated X-Request-ID header."""
        from server import RequestTraceMiddleware

        sent_messages = []

        async def mock_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"OK"})

        middleware = RequestTraceMiddleware(app=mock_app)

        scope = {"type": "http", "headers": [], "state": {}}

        async def mock_receive():
            return {"type": "http.request", "body": b""}

        async def mock_send(message):
            sent_messages.append(message)

        await middleware(scope, mock_receive, mock_send)

        # Find the http.response.start message
        start_msg = next(m for m in sent_messages if m["type"] == "http.response.start")
        header_dict = dict(start_msg["headers"])

        assert b"x-request-id" in header_dict
        # Should be a valid UUID
        request_id = header_dict[b"x-request-id"].decode()
        uuid.UUID(request_id)  # Raises ValueError if not a valid UUID

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_response_includes_response_time_header(self):
        """Response should include an X-Response-Time header with millisecond format."""
        from server import RequestTraceMiddleware

        sent_messages = []

        async def mock_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"OK"})

        middleware = RequestTraceMiddleware(app=mock_app)

        scope = {"type": "http", "headers": [], "state": {}}

        async def mock_receive():
            return {"type": "http.request", "body": b""}

        async def mock_send(message):
            sent_messages.append(message)

        await middleware(scope, mock_receive, mock_send)

        start_msg = next(m for m in sent_messages if m["type"] == "http.response.start")
        header_dict = dict(start_msg["headers"])

        assert b"x-response-time" in header_dict
        response_time = header_dict[b"x-response-time"].decode()
        # Should match format like "0.1ms" or "12.5ms"
        assert response_time.endswith("ms")
        # The numeric portion should be a valid float
        float(response_time[:-2])

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_client_provided_request_id_is_propagated(self):
        """Client-provided X-Request-ID should be used instead of generating a new one."""
        from server import RequestTraceMiddleware

        sent_messages = []
        client_id = "my-custom-trace-id-12345"

        async def mock_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})

        middleware = RequestTraceMiddleware(app=mock_app)

        scope = {
            "type": "http",
            "headers": [(b"x-request-id", client_id.encode())],
            "state": {},
        }

        async def mock_receive():
            return {"type": "http.request", "body": b""}

        async def mock_send(message):
            sent_messages.append(message)

        await middleware(scope, mock_receive, mock_send)

        start_msg = next(m for m in sent_messages if m["type"] == "http.response.start")
        header_dict = dict(start_msg["headers"])

        assert header_dict[b"x-request-id"].decode() == client_id

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_request_id_stored_in_scope_state(self):
        """Request ID should be stored in scope['state']['request_id'] for logging."""
        from server import RequestTraceMiddleware

        captured_scope = {}

        async def mock_app(scope, receive, send):
            captured_scope.update(scope)
            await send({"type": "http.response.start", "status": 200, "headers": []})

        middleware = RequestTraceMiddleware(app=mock_app)

        scope = {"type": "http", "headers": [], "state": {}}

        async def mock_receive():
            return {"type": "http.request", "body": b""}

        async def mock_send(message):
            pass

        await middleware(scope, mock_receive, mock_send)

        assert "request_id" in scope["state"]
        # Should be a valid UUID when no client header is provided
        uuid.UUID(scope["state"]["request_id"])

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_non_http_scope_passed_through_without_headers(self):
        """Non-HTTP scopes (e.g., websocket) should be passed through without modification."""
        from server import RequestTraceMiddleware

        app_called = False
        sent_messages = []

        async def mock_app(scope, receive, send):
            nonlocal app_called
            app_called = True
            # Simulate a websocket response (no http.response.start)
            await send({"type": "websocket.accept"})

        middleware = RequestTraceMiddleware(app=mock_app)

        scope = {"type": "websocket", "headers": []}

        async def mock_receive():
            return {"type": "websocket.connect"}

        async def mock_send(message):
            sent_messages.append(message)

        await middleware(scope, mock_receive, mock_send)

        assert app_called
        # The websocket message should be passed through unchanged
        assert len(sent_messages) == 1
        assert sent_messages[0]["type"] == "websocket.accept"
        # No trace headers should be added to non-HTTP scopes
        assert "headers" not in sent_messages[0]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_existing_response_headers_are_preserved(self):
        """Existing response headers should not be removed when adding trace headers."""
        from server import RequestTraceMiddleware

        sent_messages = []

        async def mock_app(scope, receive, send):
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"x-custom", b"test-value"),
                    ],
                }
            )

        middleware = RequestTraceMiddleware(app=mock_app)

        scope = {"type": "http", "headers": [], "state": {}}

        async def mock_receive():
            return {"type": "http.request", "body": b""}

        async def mock_send(message):
            sent_messages.append(message)

        await middleware(scope, mock_receive, mock_send)

        start_msg = sent_messages[0]
        header_keys = [h[0] for h in start_msg["headers"]]

        # Original headers preserved
        assert b"content-type" in header_keys
        assert b"x-custom" in header_keys
        # Trace headers added
        assert b"x-request-id" in header_keys
        assert b"x-response-time" in header_keys

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_body_messages_not_modified(self):
        """http.response.body messages should pass through without modification."""
        from server import RequestTraceMiddleware

        sent_messages = []

        async def mock_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"Hello World"})

        middleware = RequestTraceMiddleware(app=mock_app)

        scope = {"type": "http", "headers": [], "state": {}}

        async def mock_receive():
            return {"type": "http.request", "body": b""}

        async def mock_send(message):
            sent_messages.append(message)

        await middleware(scope, mock_receive, mock_send)

        body_msg = next(m for m in sent_messages if m["type"] == "http.response.body")
        assert body_msg["body"] == b"Hello World"
        # Body messages should NOT get headers added
        assert "headers" not in body_msg or body_msg.get("headers") is None


# ===================================================================
# SearchService Tests
# ===================================================================


class TestSearchServiceInitIndexes:
    """Test SearchService.init_indexes() creates and configures Meilisearch indexes."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_init_indexes_creates_both_indexes(self, mock_meili_client):
        """init_indexes should create both 'members' and 'care_events' indexes."""
        svc = SearchService()
        with patch.object(svc, "_connect", return_value=True):
            svc._client = mock_meili_client
            svc._available = True
            result = await svc.init_indexes()

        assert result is True
        # Should call create_index for both indexes
        calls = mock_meili_client.create_index.call_args_list
        index_names = [c[0][0] for c in calls]
        assert MEMBERS_INDEX in index_names
        assert CARE_EVENTS_INDEX in index_names

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_init_indexes_configures_searchable_attributes(self, mock_meili_client):
        """init_indexes should configure searchable attributes on both indexes."""
        svc = SearchService()
        with patch.object(svc, "_connect", return_value=True):
            svc._client = mock_meili_client
            svc._available = True
            await svc.init_indexes()

        members_idx = mock_meili_client._members_index
        members_idx.update_searchable_attributes.assert_called_once_with(MEMBERS_CONFIG["searchableAttributes"])

        events_idx = mock_meili_client._care_events_index
        events_idx.update_searchable_attributes.assert_called_once_with(CARE_EVENTS_CONFIG["searchableAttributes"])

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_init_indexes_returns_false_when_connect_fails(self):
        """init_indexes should return False when Meilisearch is unavailable."""
        svc = SearchService()
        with patch.object(svc, "_connect", return_value=False):
            result = await svc.init_indexes()

        assert result is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_init_indexes_handles_communication_error(self, mock_meili_client):
        """init_indexes should handle MeilisearchCommunicationError gracefully."""
        from meilisearch.errors import MeilisearchCommunicationError

        mock_meili_client.create_index.side_effect = MeilisearchCommunicationError("timeout")

        svc = SearchService()
        with patch.object(svc, "_connect", return_value=True):
            svc._client = mock_meili_client
            svc._available = True
            result = await svc.init_indexes()

        assert result is False
        assert svc._available is False


class TestSearchServiceIndexMember:
    """Test SearchService.index_member() single document indexing."""

    @pytest.mark.unit
    def test_index_member_calls_add_documents(self, search_service, mock_meili_client):
        """index_member should call add_documents with correctly formatted document."""
        member = _make_member()
        result = search_service.index_member(member)

        assert result is True
        mock_meili_client._members_index.add_documents.assert_called_once()
        args = mock_meili_client._members_index.add_documents.call_args[0][0]
        assert len(args) == 1
        doc = args[0]
        assert doc["id"] == MEMBER_ID
        assert doc["name"] == "John Doe"
        assert doc["campus_id"] == CAMPUS_ID

    @pytest.mark.unit
    def test_index_member_returns_false_when_unavailable(self):
        """index_member should return False when service is unavailable."""
        svc = SearchService()
        svc._available = False
        result = svc.index_member(_make_member())
        assert result is False

    @pytest.mark.unit
    def test_index_member_handles_communication_error(self, search_service, mock_meili_client):
        """index_member should handle MeilisearchCommunicationError and mark unavailable."""
        from meilisearch.errors import MeilisearchCommunicationError

        mock_meili_client._members_index.add_documents.side_effect = MeilisearchCommunicationError("timeout")

        result = search_service.index_member(_make_member())

        assert result is False
        assert search_service._available is False


class TestSearchServiceIndexCareEvent:
    """Test SearchService.index_care_event() single document indexing."""

    @pytest.mark.unit
    def test_index_care_event_formats_document_correctly(self, search_service, mock_meili_client):
        """index_care_event should format the document with all required fields."""
        event = _make_care_event()
        result = search_service.index_care_event(event, member_name="John Doe")

        assert result is True
        mock_meili_client._care_events_index.add_documents.assert_called_once()
        args = mock_meili_client._care_events_index.add_documents.call_args[0][0]
        doc = args[0]
        assert doc["id"] == "event-test-001"
        assert doc["title"] == "Birthday Celebration"
        assert doc["member_name"] == "John Doe"
        assert doc["event_type"] == "birthday"
        assert doc["completed"] is False

    @pytest.mark.unit
    def test_index_care_event_uses_event_member_name_as_fallback(self, search_service, mock_meili_client):
        """When member_name is not provided, should fall back to event's member_name field."""
        event = _make_care_event(member_name="Jane From Event")
        result = search_service.index_care_event(event)

        assert result is True
        args = mock_meili_client._care_events_index.add_documents.call_args[0][0]
        assert args[0]["member_name"] == "Jane From Event"

    @pytest.mark.unit
    def test_index_care_event_returns_false_when_unavailable(self):
        """index_care_event should return False when service is unavailable."""
        svc = SearchService()
        svc._available = False
        result = svc.index_care_event(_make_care_event())
        assert result is False


class TestSearchServiceRemove:
    """Test SearchService.remove_member() and remove_care_event()."""

    @pytest.mark.unit
    def test_remove_member_calls_delete_document(self, search_service, mock_meili_client):
        """remove_member should call delete_document with the member ID."""
        result = search_service.remove_member("member-123")
        assert result is True
        mock_meili_client._members_index.delete_document.assert_called_once_with("member-123")

    @pytest.mark.unit
    def test_remove_care_event_calls_delete_document(self, search_service, mock_meili_client):
        """remove_care_event should call delete_document with the event ID."""
        result = search_service.remove_care_event("event-456")
        assert result is True
        mock_meili_client._care_events_index.delete_document.assert_called_once_with("event-456")

    @pytest.mark.unit
    def test_remove_member_returns_false_when_unavailable(self):
        """remove_member should return False when service is unavailable."""
        svc = SearchService()
        svc._available = False
        assert svc.remove_member("member-123") is False

    @pytest.mark.unit
    def test_remove_care_event_returns_false_when_unavailable(self):
        """remove_care_event should return False when service is unavailable."""
        svc = SearchService()
        svc._available = False
        assert svc.remove_care_event("event-456") is False

    @pytest.mark.unit
    def test_remove_member_handles_communication_error(self, search_service, mock_meili_client):
        """remove_member should handle MeilisearchCommunicationError gracefully."""
        from meilisearch.errors import MeilisearchCommunicationError

        mock_meili_client._members_index.delete_document.side_effect = MeilisearchCommunicationError("timeout")
        result = search_service.remove_member("member-123")
        assert result is False
        assert search_service._available is False


class TestSearchServiceSearch:
    """Test SearchService.search() single-index search with campus filtering."""

    @pytest.mark.unit
    def test_search_applies_campus_id_filter(self, search_service, mock_meili_client):
        """search() should pass campus_id filter to Meilisearch."""
        mock_meili_client._members_index.search.return_value = {
            "hits": [{"id": "m1", "name": "John"}],
            "estimatedTotalHits": 1,
            "processingTimeMs": 2,
        }

        result = search_service.search("John", campus_id=CAMPUS_ID)

        mock_meili_client._members_index.search.assert_called_once()
        call_args = mock_meili_client._members_index.search.call_args
        assert call_args[0][0] == "John"  # query
        search_params = call_args[0][1]
        assert f'campus_id = "{CAMPUS_ID}"' in search_params["filter"]

        assert len(result["hits"]) == 1
        assert result["estimatedTotalHits"] == 1

    @pytest.mark.unit
    def test_search_returns_empty_when_unavailable(self):
        """search() should return empty results when Meilisearch is unavailable."""
        svc = SearchService()
        svc._available = False
        result = svc.search("test", campus_id=CAMPUS_ID)
        assert result == {"hits": [], "estimatedTotalHits": 0, "processingTimeMs": 0}

    @pytest.mark.unit
    def test_search_handles_communication_error(self, search_service, mock_meili_client):
        """search() should handle MeilisearchCommunicationError and return empty results."""
        from meilisearch.errors import MeilisearchCommunicationError

        mock_meili_client._members_index.search.side_effect = MeilisearchCommunicationError("timeout")
        result = search_service.search("John", campus_id=CAMPUS_ID)
        assert result["hits"] == []
        assert search_service._available is False

    @pytest.mark.unit
    def test_search_respects_limit_parameter(self, search_service, mock_meili_client):
        """search() should pass the limit parameter to Meilisearch."""
        mock_meili_client._members_index.search.return_value = {
            "hits": [],
            "estimatedTotalHits": 0,
            "processingTimeMs": 1,
        }

        search_service.search("test", campus_id=CAMPUS_ID, limit=5)

        call_args = mock_meili_client._members_index.search.call_args
        search_params = call_args[0][1]
        assert search_params["limit"] == 5


class TestSearchServiceMultiSearch:
    """Test SearchService.multi_search() across both indexes."""

    @pytest.mark.unit
    def test_multi_search_searches_both_indexes(self, search_service, mock_meili_client):
        """multi_search should search both members and care_events indexes."""
        mock_meili_client.multi_search.return_value = {
            "results": [
                {
                    "indexUid": MEMBERS_INDEX,
                    "hits": [{"id": "m1", "name": "John"}],
                    "processingTimeMs": 2,
                },
                {
                    "indexUid": CARE_EVENTS_INDEX,
                    "hits": [{"id": "e1", "title": "Birthday"}],
                    "processingTimeMs": 3,
                },
            ]
        }

        result = search_service.multi_search("John", campus_id=CAMPUS_ID)

        assert len(result["members"]) == 1
        assert result["members"][0]["name"] == "John"
        assert len(result["care_events"]) == 1
        assert result["care_events"][0]["title"] == "Birthday"
        assert result["processing_time_ms"] == 5  # Sum of both

    @pytest.mark.unit
    def test_multi_search_applies_campus_filter(self, search_service, mock_meili_client):
        """multi_search should apply campus_id filter when provided."""
        mock_meili_client.multi_search.return_value = {"results": []}

        search_service.multi_search("test", campus_id=CAMPUS_ID)

        call_args = mock_meili_client.multi_search.call_args[0][0]
        # Both queries should have the campus filter
        for query in call_args:
            assert query["filter"] == f'campus_id = "{CAMPUS_ID}"'

    @pytest.mark.unit
    def test_multi_search_without_campus_id_omits_filter(self, search_service, mock_meili_client):
        """multi_search without campus_id (full_admin) should not add filter."""
        mock_meili_client.multi_search.return_value = {"results": []}

        search_service.multi_search("test", campus_id=None)

        call_args = mock_meili_client.multi_search.call_args[0][0]
        for query in call_args:
            assert "filter" not in query

    @pytest.mark.unit
    def test_multi_search_returns_empty_when_unavailable(self):
        """multi_search should return empty results when Meilisearch is unavailable."""
        svc = SearchService()
        svc._available = False
        result = svc.multi_search("test", campus_id=CAMPUS_ID)
        assert result == {"members": [], "care_events": [], "processing_time_ms": 0}

    @pytest.mark.unit
    def test_multi_search_handles_communication_error(self, search_service, mock_meili_client):
        """multi_search should handle MeilisearchCommunicationError gracefully."""
        from meilisearch.errors import MeilisearchCommunicationError

        mock_meili_client.multi_search.side_effect = MeilisearchCommunicationError("timeout")
        result = search_service.multi_search("John", campus_id=CAMPUS_ID)
        assert result["members"] == []
        assert result["care_events"] == []
        assert search_service._available is False


class TestSearchServiceBulkIndex:
    """Test SearchService.bulk_index_members() bulk indexing."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_bulk_index_members_iterates_and_batches(self, search_service, mock_meili_client):
        """bulk_index_members should iterate the cursor and batch documents."""
        mock_db = MagicMock()
        search_service.set_db(mock_db)

        # Create a mock async cursor that yields 3 members
        members = [
            _make_member(id="m1", name="Alice"),
            _make_member(id="m2", name="Bob"),
            _make_member(id="m3", name="Charlie"),
        ]

        # Simulate an async iterator
        async def async_iter():
            for m in members:
                yield m

        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: async_iter()
        mock_db.members.find.return_value = mock_cursor

        total = await search_service.bulk_index_members()

        assert total == 3
        # All 3 should be in a single batch (< 500)
        mock_meili_client._members_index.add_documents.assert_called_once()
        docs = mock_meili_client._members_index.add_documents.call_args[0][0]
        assert len(docs) == 3

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_bulk_index_members_filters_by_campus_id(self, search_service, mock_meili_client):
        """bulk_index_members with campus_id should filter the query."""
        mock_db = MagicMock()
        search_service.set_db(mock_db)

        async def async_iter():
            return
            yield  # Empty async generator

        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: async_iter()
        mock_db.members.find.return_value = mock_cursor

        await search_service.bulk_index_members(campus_id=CAMPUS_ID)

        # Check that find was called with campus_id filter
        mock_db.members.find.assert_called_once()
        query = mock_db.members.find.call_args[0][0]
        assert query["campus_id"] == CAMPUS_ID

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_bulk_index_members_returns_zero_when_unavailable(self):
        """bulk_index_members should return 0 when Meilisearch is unavailable."""
        svc = SearchService()
        svc._available = False
        total = await svc.bulk_index_members()
        assert total == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_bulk_index_members_returns_zero_when_no_db(self, search_service):
        """bulk_index_members should return 0 when db is not set."""
        # _db is None by default
        search_service._db = None
        total = await search_service.bulk_index_members()
        assert total == 0


class TestSearchServiceIsAvailable:
    """Test SearchService.is_available() public check."""

    @pytest.mark.unit
    def test_is_available_returns_true_when_connected(self, search_service):
        """is_available should return True when service is connected."""
        assert search_service.is_available() is True

    @pytest.mark.unit
    def test_is_available_returns_false_when_not_connected(self):
        """is_available should return False when service is not connected."""
        svc = SearchService()
        assert svc.is_available() is False


class TestSearchServiceConnect:
    """Test SearchService._connect() connection handling."""

    @pytest.mark.unit
    def test_connect_sets_available_on_success(self):
        """_connect should set _available to True when health check passes."""
        svc = SearchService()

        mock_client = MagicMock()
        mock_client.health.return_value = {"status": "available"}

        with patch("services.search.meilisearch.Client", return_value=mock_client):
            result = svc._connect()

        assert result is True
        assert svc._available is True

    @pytest.mark.unit
    def test_connect_handles_communication_error(self):
        """_connect should set _available to False on MeilisearchCommunicationError."""
        from meilisearch.errors import MeilisearchCommunicationError

        svc = SearchService()

        with patch(
            "services.search.meilisearch.Client",
            side_effect=MeilisearchCommunicationError("Connection refused"),
        ):
            result = svc._connect()

        assert result is False
        assert svc._available is False
        assert svc._client is None

    @pytest.mark.unit
    def test_connect_handles_unexpected_health_status(self):
        """_connect should handle non-'available' health status."""
        svc = SearchService()
        mock_client = MagicMock()
        mock_client.health.return_value = {"status": "unhealthy"}

        with patch("services.search.meilisearch.Client", return_value=mock_client):
            result = svc._connect()

        assert result is False
        assert svc._available is False


class TestSearchServiceSingleton:
    """Test get_search_service() module-level singleton."""

    @pytest.mark.unit
    def test_get_search_service_returns_singleton(self):
        """get_search_service() should return the same instance on repeated calls."""
        # Reset the global singleton for a clean test
        import services.search as search_module

        search_module._search_service = None

        svc1 = get_search_service()
        svc2 = get_search_service()

        assert svc1 is svc2

        # Clean up
        search_module._search_service = None


class TestPrepareDocumentHelpers:
    """Test _prepare_member_doc and _prepare_care_event_doc helpers."""

    @pytest.mark.unit
    def test_prepare_member_doc_includes_all_fields(self):
        """_prepare_member_doc should include all expected fields."""
        member = _make_member()
        doc = _prepare_member_doc(member)

        assert doc["id"] == MEMBER_ID
        assert doc["name"] == "John Doe"
        assert doc["phone"] == "+6281234567890"
        assert doc["email"] == "john@example.com"
        assert doc["address"] == "123 Test Street"
        assert doc["campus_id"] == CAMPUS_ID
        assert doc["engagement_status"] == "active"
        assert doc["gender"] == "male"
        assert doc["created_at"] != ""

    @pytest.mark.unit
    def test_prepare_member_doc_handles_missing_fields(self):
        """_prepare_member_doc should default to empty strings for missing fields."""
        doc = _prepare_member_doc({})
        assert doc["id"] == ""
        assert doc["name"] == ""
        assert doc["created_at"] == ""

    @pytest.mark.unit
    def test_prepare_care_event_doc_uses_provided_member_name(self):
        """_prepare_care_event_doc should prefer provided member_name."""
        event = _make_care_event(member_name="Event Name")
        doc = _prepare_care_event_doc(event, member_name="Override Name")
        assert doc["member_name"] == "Override Name"

    @pytest.mark.unit
    def test_prepare_care_event_doc_falls_back_to_event_member_name(self):
        """_prepare_care_event_doc should fall back to event's member_name when None."""
        event = _make_care_event(member_name="From Event")
        doc = _prepare_care_event_doc(event, member_name=None)
        assert doc["member_name"] == "From Event"

    @pytest.mark.unit
    def test_prepare_care_event_doc_serializes_datetime(self):
        """_prepare_care_event_doc should serialize datetime fields to ISO format."""
        event = _make_care_event()
        doc = _prepare_care_event_doc(event)
        assert doc["event_date"] == "2025-05-15T00:00:00+00:00"
        assert doc["created_at"] == "2025-05-01T08:00:00+00:00"


# ===================================================================
# ChangeStreamWatcher Tests
# ===================================================================


class TestChangeStreamWatcherCheckReplicaSet:
    """Test ChangeStreamWatcher._check_replica_set() replica set detection."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_false_on_standalone_mongodb(self, mock_db):
        """Should return False when MongoDB is standalone (no replica set)."""
        # Simulate the watch() context manager raising an error
        mock_watch_cm = AsyncMock()
        mock_watch_cm.__aenter__ = AsyncMock(side_effect=Exception("not supported: replica set"))
        mock_watch_cm.__aexit__ = AsyncMock(return_value=False)
        # PyMongo async: collection.watch() is now a coroutine that
        # resolves to the async context manager.
        mock_db.activity_logs.watch = AsyncMock(return_value=mock_watch_cm)

        watcher = ChangeStreamWatcher(mock_db)
        result = await watcher._check_replica_set()

        assert result is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_true_when_change_streams_work(self, mock_db):
        """Should return True when change streams are available."""
        # Simulate successful watch context manager
        mock_watch_cm = AsyncMock()
        mock_watch_cm.__aenter__ = AsyncMock()
        mock_watch_cm.__aexit__ = AsyncMock(return_value=False)
        # PyMongo async: collection.watch() is now a coroutine that
        # resolves to the async context manager.
        mock_db.activity_logs.watch = AsyncMock(return_value=mock_watch_cm)

        watcher = ChangeStreamWatcher(mock_db)
        result = await watcher._check_replica_set()

        assert result is True

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_false_on_not_allowed_error(self, mock_db):
        """Should return False when error contains 'not allowed'."""
        mock_watch_cm = AsyncMock()
        mock_watch_cm.__aenter__ = AsyncMock(side_effect=Exception("Operation not allowed on standalone"))
        mock_watch_cm.__aexit__ = AsyncMock(return_value=False)
        # PyMongo async: collection.watch() is now a coroutine that
        # resolves to the async context manager.
        mock_db.activity_logs.watch = AsyncMock(return_value=mock_watch_cm)

        watcher = ChangeStreamWatcher(mock_db)
        result = await watcher._check_replica_set()

        assert result is False


class TestChangeStreamWatcherExtractActivityData:
    """Test ChangeStreamWatcher._extract_activity_data() field extraction."""

    @pytest.mark.unit
    def test_extracts_correct_fields(self, mock_db):
        """Should extract all expected fields from the document."""
        watcher = ChangeStreamWatcher(mock_db)
        doc = _make_activity_log_document()

        result = watcher._extract_activity_data(doc)

        assert result["id"] == "activity-001"
        assert result["campus_id"] == CAMPUS_ID
        assert result["user_id"] == "user-001"
        assert result["user_name"] == "Pastor Smith"
        assert result["user_photo_url"] == "/uploads/pastor.jpg"
        assert result["action_type"] == "complete"
        assert result["member_id"] == MEMBER_ID
        assert result["member_name"] == "John Doe"
        assert result["care_event_id"] == "event-001"
        assert result["event_type"] == "birthday"
        assert result["notes"] == "Completed birthday visit"

    @pytest.mark.unit
    def test_handles_enum_action_type(self, mock_db):
        """Should extract .value from enum action_type."""
        watcher = ChangeStreamWatcher(mock_db)

        # Create a mock enum-like object
        mock_enum = MagicMock()
        mock_enum.value = "create_event"

        doc = _make_activity_log_document(action_type=mock_enum)
        result = watcher._extract_activity_data(doc)

        assert result["action_type"] == "create_event"

    @pytest.mark.unit
    def test_handles_enum_event_type(self, mock_db):
        """Should extract .value from enum event_type."""
        watcher = ChangeStreamWatcher(mock_db)

        mock_enum = MagicMock()
        mock_enum.value = "grief"

        doc = _make_activity_log_document(event_type=mock_enum)
        result = watcher._extract_activity_data(doc)

        assert result["event_type"] == "grief"

    @pytest.mark.unit
    def test_handles_datetime_created_at(self, mock_db):
        """Should serialize datetime created_at to ISO format."""
        watcher = ChangeStreamWatcher(mock_db)
        ts = datetime(2025, 6, 15, 14, 30, 0, tzinfo=UTC)
        doc = _make_activity_log_document(created_at=ts)

        result = watcher._extract_activity_data(doc)

        assert result["timestamp"] == "2025-06-15T14:30:00+00:00"

    @pytest.mark.unit
    def test_handles_string_created_at(self, mock_db):
        """Should use string representation for non-datetime created_at."""
        watcher = ChangeStreamWatcher(mock_db)
        doc = _make_activity_log_document(created_at="2025-06-15T14:30:00Z")

        result = watcher._extract_activity_data(doc)

        assert result["timestamp"] == "2025-06-15T14:30:00Z"

    @pytest.mark.unit
    def test_handles_missing_created_at(self, mock_db):
        """Should generate a current timestamp when created_at is missing."""
        watcher = ChangeStreamWatcher(mock_db)
        doc = _make_activity_log_document(created_at=None)

        result = watcher._extract_activity_data(doc)

        # Should be a valid ISO timestamp (generated from datetime.now)
        assert result["timestamp"] != ""
        assert "T" in result["timestamp"]

    @pytest.mark.unit
    def test_handles_missing_fields_gracefully(self, mock_db):
        """Should return empty strings/None for missing fields without raising."""
        watcher = ChangeStreamWatcher(mock_db)
        doc = {}  # Completely empty document

        result = watcher._extract_activity_data(doc)

        assert result["id"] == ""
        assert result["campus_id"] == ""
        assert result["user_id"] == ""
        assert result["member_id"] is None
        assert result["action_type"] == ""


class TestChangeStreamWatcherPublishActivity:
    """Test ChangeStreamWatcher._publish_activity() publishing."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_publishes_to_correct_redis_channel(self, mock_db, mock_redis):
        """Should publish to the ft:{campus_id}:activity channel in DragonflyDB."""
        watcher = ChangeStreamWatcher(mock_db, redis_client=mock_redis)
        activity_data = {"id": "act-1", "action_type": "complete"}

        await watcher._publish_activity(CAMPUS_ID, activity_data)

        mock_redis.publish.assert_called_once()
        args = mock_redis.publish.call_args
        assert args[0][0] == f"ft:{CAMPUS_ID}:activity"
        published_data = json.loads(args[0][1])
        assert published_data["id"] == "act-1"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_falls_back_to_in_memory_when_redis_unavailable(self, mock_db):
        """Should fall back to in-memory broadcast when DragonflyDB is unavailable."""
        watcher = ChangeStreamWatcher(mock_db, redis_client=None)

        mock_broadcast = AsyncMock()
        # Patch _get_redis_client to return None (no Redis) and mock the
        # fallback import of server.broadcast_activity
        with patch.object(watcher, "_get_redis_client", return_value=None):
            # Patch the import of broadcast_activity inside _publish_activity
            mock_server_module = MagicMock()
            mock_server_module.broadcast_activity = mock_broadcast
            with patch.dict("sys.modules", {"server": mock_server_module}):
                await watcher._publish_activity(CAMPUS_ID, {"id": "act-1"})
                mock_broadcast.assert_called_once_with(CAMPUS_ID, {"id": "act-1"})

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_falls_back_when_redis_publish_fails(self, mock_db, mock_redis):
        """Should fall back to in-memory when Redis publish raises an exception."""
        mock_redis.publish.side_effect = Exception("Redis connection lost")
        watcher = ChangeStreamWatcher(mock_db, redis_client=mock_redis)

        mock_broadcast = AsyncMock()
        mock_server_module = MagicMock()
        mock_server_module.broadcast_activity = mock_broadcast
        with patch.dict("sys.modules", {"server": mock_server_module}):
            await watcher._publish_activity(CAMPUS_ID, {"id": "act-1"})
            mock_broadcast.assert_called_once_with(CAMPUS_ID, {"id": "act-1"})


class TestChangeStreamWatcherResumeToken:
    """Test ChangeStreamWatcher resume token persistence."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_load_resume_token_returns_none_when_no_token(self, mock_db, mock_redis):
        """Should return None when no resume token is stored."""
        mock_redis.get.return_value = None
        watcher = ChangeStreamWatcher(mock_db, redis_client=mock_redis)

        token = await watcher._load_resume_token()

        assert token is None
        mock_redis.get.assert_called_once_with(_RESUME_TOKEN_KEY)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_load_resume_token_returns_stored_token(self, mock_db, mock_redis):
        """Should deserialize and return a stored resume token."""
        stored_token = {"_data": "resume-token-data-123"}
        mock_redis.get.return_value = json.dumps(stored_token)
        watcher = ChangeStreamWatcher(mock_db, redis_client=mock_redis)

        token = await watcher._load_resume_token()

        assert token == stored_token

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_load_resume_token_returns_none_on_redis_error(self, mock_db, mock_redis):
        """Should return None if Redis raises an error."""
        mock_redis.get.side_effect = Exception("Redis down")
        watcher = ChangeStreamWatcher(mock_db, redis_client=mock_redis)

        token = await watcher._load_resume_token()

        assert token is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_load_resume_token_returns_none_when_no_redis(self, mock_db):
        """Should return None when redis client is not available."""
        watcher = ChangeStreamWatcher(mock_db, redis_client=None)

        with patch.object(watcher, "_get_redis_client", return_value=None):
            token = await watcher._load_resume_token()

        assert token is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_save_resume_token_stores_with_ttl(self, mock_db, mock_redis):
        """Should store the token in Redis with a 24-hour TTL."""
        watcher = ChangeStreamWatcher(mock_db, redis_client=mock_redis)
        token = {"_data": "my-resume-token"}

        await watcher._save_resume_token(token)

        mock_redis.setex.assert_called_once()
        args = mock_redis.setex.call_args
        assert args[0][0] == _RESUME_TOKEN_KEY
        assert args[0][1] == 86400  # 24 hours
        stored_data = json.loads(args[0][2])
        assert stored_data["_data"] == "my-resume-token"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_save_resume_token_handles_redis_error(self, mock_db, mock_redis):
        """Should not raise when Redis save fails (logs debug instead)."""
        mock_redis.setex.side_effect = Exception("Redis write error")
        watcher = ChangeStreamWatcher(mock_db, redis_client=mock_redis)

        # Should not raise
        await watcher._save_resume_token({"_data": "token"})

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_save_resume_token_noop_when_no_redis(self, mock_db):
        """Should silently do nothing when Redis is not available."""
        watcher = ChangeStreamWatcher(mock_db, redis_client=None)

        with patch.object(watcher, "_get_redis_client", return_value=None):
            # Should not raise
            await watcher._save_resume_token({"_data": "token"})


class TestChangeStreamWatcherStartStop:
    """Test ChangeStreamWatcher.start() and stop() lifecycle."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_start_detects_standalone_and_does_not_start(self, mock_db):
        """start() should return False and not create a task when no replica set."""
        watcher = ChangeStreamWatcher(mock_db)

        with patch.object(watcher, "_check_replica_set", new_callable=AsyncMock, return_value=False):
            result = await watcher.start()

        assert result is False
        assert watcher._task is None
        assert watcher._running is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_start_creates_task_when_replica_set_available(self, mock_db):
        """start() should create a background task when replica set is available."""
        watcher = ChangeStreamWatcher(mock_db)

        with (
            patch.object(watcher, "_check_replica_set", new_callable=AsyncMock, return_value=True),
            patch.object(watcher, "_watch_loop", new_callable=AsyncMock),
        ):
            result = await watcher.start()

        assert result is True
        assert watcher._running is True
        assert watcher._task is not None

        # Clean up the background task
        await watcher.stop()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_stop_cancels_task_gracefully(self, mock_db):
        """stop() should cancel the background task and set _running to False."""
        watcher = ChangeStreamWatcher(mock_db)

        # Manually set up a running state
        async def fake_loop():
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.sleep(999)

        watcher._running = True
        watcher._task = asyncio.create_task(fake_loop())

        await watcher.stop()

        assert watcher._running is False
        assert watcher._task.done()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_stop_is_safe_when_not_started(self, mock_db):
        """stop() should not raise when called on an unstarted watcher."""
        watcher = ChangeStreamWatcher(mock_db)

        # Should not raise
        await watcher.stop()

        assert watcher._running is False


class TestChangeStreamWatcherIsRunning:
    """Test ChangeStreamWatcher.is_running property."""

    @pytest.mark.unit
    def test_is_running_false_by_default(self, mock_db):
        """is_running should be False on a fresh watcher."""
        watcher = ChangeStreamWatcher(mock_db)
        assert watcher.is_running is False

    @pytest.mark.unit
    def test_is_running_false_when_task_is_none(self, mock_db):
        """is_running should be False when _task is None even if _running is True."""
        watcher = ChangeStreamWatcher(mock_db)
        watcher._running = True
        watcher._task = None
        assert watcher.is_running is False

    @pytest.mark.unit
    def test_is_running_false_when_task_is_done(self, mock_db):
        """is_running should be False when the task has completed."""
        watcher = ChangeStreamWatcher(mock_db)
        watcher._running = True
        mock_task = MagicMock()
        mock_task.done.return_value = True
        watcher._task = mock_task
        assert watcher.is_running is False

    @pytest.mark.unit
    def test_is_running_true_when_active(self, mock_db):
        """is_running should be True when _running=True and task is not done."""
        watcher = ChangeStreamWatcher(mock_db)
        watcher._running = True
        mock_task = MagicMock()
        mock_task.done.return_value = False
        watcher._task = mock_task
        assert watcher.is_running is True


class TestChangeStreamWatcherIsReplicaSetAvailable:
    """Test ChangeStreamWatcher.is_replica_set_available property."""

    @pytest.mark.unit
    def test_is_replica_set_available_default_false(self, mock_db):
        """is_replica_set_available should default to False."""
        watcher = ChangeStreamWatcher(mock_db)
        assert watcher.is_replica_set_available is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_is_replica_set_available_after_start(self, mock_db):
        """is_replica_set_available should reflect detection result after start()."""
        watcher = ChangeStreamWatcher(mock_db)

        with (
            patch.object(watcher, "_check_replica_set", new_callable=AsyncMock, return_value=True),
            patch.object(watcher, "_watch_loop", new_callable=AsyncMock),
        ):
            await watcher.start()

        assert watcher.is_replica_set_available is True

        # Clean up
        await watcher.stop()


# ===================================================================
# Module-level function tests
# ===================================================================


class TestModuleLevelFunctions:
    """Test module-level convenience functions."""

    @pytest.mark.unit
    def test_is_change_stream_active_returns_false_when_no_watcher(self):
        """is_change_stream_active() should return False when no watcher exists."""
        import services.change_stream as cs_module

        original = cs_module._watcher
        try:
            cs_module._watcher = None
            assert is_change_stream_active() is False
        finally:
            cs_module._watcher = original

    @pytest.mark.unit
    def test_is_change_stream_active_returns_false_when_not_running(self, mock_db):
        """is_change_stream_active() should return False when watcher is not running."""
        import services.change_stream as cs_module

        original = cs_module._watcher
        try:
            watcher = ChangeStreamWatcher(mock_db)
            watcher._running = False
            cs_module._watcher = watcher
            assert is_change_stream_active() is False
        finally:
            cs_module._watcher = original

    @pytest.mark.unit
    def test_is_change_stream_active_returns_true_when_running(self, mock_db):
        """is_change_stream_active() should return True when watcher is actively running."""
        import services.change_stream as cs_module

        original = cs_module._watcher
        try:
            watcher = ChangeStreamWatcher(mock_db)
            watcher._running = True
            mock_task = MagicMock()
            mock_task.done.return_value = False
            watcher._task = mock_task
            cs_module._watcher = watcher
            assert is_change_stream_active() is True
        finally:
            cs_module._watcher = original

    @pytest.mark.unit
    def test_get_change_stream_watcher_returns_none_initially(self):
        """get_change_stream_watcher() should return None when not initialized."""
        import services.change_stream as cs_module

        original = cs_module._watcher
        try:
            cs_module._watcher = None
            assert get_change_stream_watcher() is None
        finally:
            cs_module._watcher = original

    @pytest.mark.unit
    def test_get_search_service_returns_search_service_instance(self):
        """get_search_service() should return a SearchService instance."""
        import services.search as search_module

        search_module._search_service = None
        svc = get_search_service()
        assert isinstance(svc, SearchService)
        # Clean up
        search_module._search_service = None
