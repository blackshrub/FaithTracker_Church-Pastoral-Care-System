"""
FaithTracker Search Service - Meilisearch Integration
Provides typo-tolerant, fast full-text search across members and care events.
Multi-tenant via campus_id filtering on all queries.
Graceful fallback: if Meilisearch is unavailable, returns empty results.
"""

import os
import logging
from typing import Optional, Any

import meilisearch
from meilisearch.errors import MeilisearchError, MeilisearchApiError, MeilisearchCommunicationError

logger = logging.getLogger(__name__)

MEILI_URL = os.environ.get("MEILI_URL", "http://localhost:7700")
MEILI_MASTER_KEY = os.environ.get("MEILI_MASTER_KEY", "faithtracker-search-key")

# Index names
MEMBERS_INDEX = "members"
CARE_EVENTS_INDEX = "care_events"

# Index configurations
MEMBERS_CONFIG = {
    "primaryKey": "id",
    "searchableAttributes": [
        "name",
        "phone",
        "email",
        "address",
        "notes",
        "family_group_name",
    ],
    "filterableAttributes": [
        "campus_id",
        "engagement_status",
        "gender",
        "category",
    ],
    "sortableAttributes": [
        "name",
        "created_at",
    ],
    "displayedAttributes": [
        "id",
        "name",
        "phone",
        "email",
        "engagement_status",
        "photo_url",
        "campus_id",
    ],
}

CARE_EVENTS_CONFIG = {
    "primaryKey": "id",
    "searchableAttributes": [
        "title",
        "description",
        "member_name",
    ],
    "filterableAttributes": [
        "campus_id",
        "event_type",
        "completed",
        "ignored",
    ],
    "sortableAttributes": [
        "event_date",
        "created_at",
    ],
    "displayedAttributes": [
        "id",
        "title",
        "description",
        "event_type",
        "member_id",
        "member_name",
        "event_date",
        "completed",
        "campus_id",
    ],
}


class SearchService:
    """Meilisearch-backed search service with graceful fallback."""

    def __init__(self):
        self._client: Optional[meilisearch.Client] = None
        self._available = False
        self._db = None

    def set_db(self, db):
        """Set database reference for bulk indexing operations."""
        self._db = db

    def _connect(self) -> bool:
        """Attempt to connect to Meilisearch. Returns True if successful."""
        try:
            self._client = meilisearch.Client(MEILI_URL, MEILI_MASTER_KEY)
            # Test connection with a health check
            health = self._client.health()
            if health.get("status") == "available":
                self._available = True
                logger.info(f"Connected to Meilisearch at {MEILI_URL}")
                return True
            else:
                self._available = False
                logger.warning(f"Meilisearch health check returned unexpected status: {health}")
                return False
        except Exception as e:
            self._available = False
            self._client = None
            logger.warning(f"Meilisearch connection failed: {e}")
            return False

    def _is_available(self) -> bool:
        """Check if Meilisearch is available."""
        if not self._client or not self._available:
            return False
        try:
            health = self._client.health()
            return health.get("status") == "available"
        except Exception:
            self._available = False
            return False

    async def init_indexes(self) -> bool:
        """
        Create and configure Meilisearch indexes on startup.
        Returns True if successful, False if Meilisearch is unavailable.
        """
        if not self._connect():
            logger.warning("Meilisearch unavailable - search features will use MongoDB fallback")
            return False

        try:
            # Create members index
            self._client.create_index(MEMBERS_INDEX, {"primaryKey": MEMBERS_CONFIG["primaryKey"]})
            members_index = self._client.index(MEMBERS_INDEX)
            members_index.update_searchable_attributes(MEMBERS_CONFIG["searchableAttributes"])
            members_index.update_filterable_attributes(MEMBERS_CONFIG["filterableAttributes"])
            members_index.update_sortable_attributes(MEMBERS_CONFIG["sortableAttributes"])
            members_index.update_displayed_attributes(MEMBERS_CONFIG["displayedAttributes"])
            logger.info("Meilisearch 'members' index configured")

            # Create care_events index
            self._client.create_index(CARE_EVENTS_INDEX, {"primaryKey": CARE_EVENTS_CONFIG["primaryKey"]})
            events_index = self._client.index(CARE_EVENTS_INDEX)
            events_index.update_searchable_attributes(CARE_EVENTS_CONFIG["searchableAttributes"])
            events_index.update_filterable_attributes(CARE_EVENTS_CONFIG["filterableAttributes"])
            events_index.update_sortable_attributes(CARE_EVENTS_CONFIG["sortableAttributes"])
            events_index.update_displayed_attributes(CARE_EVENTS_CONFIG["displayedAttributes"])
            logger.info("Meilisearch 'care_events' index configured")

            return True
        except MeilisearchCommunicationError as e:
            self._available = False
            logger.warning(f"Meilisearch communication error during index setup: {e}")
            return False
        except MeilisearchError as e:
            logger.warning(f"Meilisearch error during index setup: {e}")
            return False
        except Exception as e:
            logger.warning(f"Unexpected error during Meilisearch index setup: {e}")
            return False

    # ==================== SINGLE DOCUMENT INDEXING ====================

    def index_member(self, member: dict) -> bool:
        """
        Index a single member document. Call after create/update.
        Returns True if indexed, False on failure.
        """
        if not self._available or not self._client:
            return False

        try:
            doc = _prepare_member_doc(member)
            self._client.index(MEMBERS_INDEX).add_documents([doc])
            return True
        except MeilisearchCommunicationError:
            self._available = False
            logger.warning("Meilisearch unavailable during member indexing")
            return False
        except Exception as e:
            logger.warning(f"Failed to index member {member.get('id')}: {e}")
            return False

    def index_care_event(self, event: dict, member_name: Optional[str] = None) -> bool:
        """
        Index a single care event document. Call after create/update.
        If member_name is not provided, uses event's existing member_name field.
        Returns True if indexed, False on failure.
        """
        if not self._available or not self._client:
            return False

        try:
            doc = _prepare_care_event_doc(event, member_name)
            self._client.index(CARE_EVENTS_INDEX).add_documents([doc])
            return True
        except MeilisearchCommunicationError:
            self._available = False
            logger.warning("Meilisearch unavailable during care event indexing")
            return False
        except Exception as e:
            logger.warning(f"Failed to index care event {event.get('id')}: {e}")
            return False

    def remove_member(self, member_id: str) -> bool:
        """Remove a member from the search index."""
        if not self._available or not self._client:
            return False

        try:
            self._client.index(MEMBERS_INDEX).delete_document(member_id)
            return True
        except MeilisearchCommunicationError:
            self._available = False
            logger.warning("Meilisearch unavailable during member removal")
            return False
        except Exception as e:
            logger.warning(f"Failed to remove member {member_id} from index: {e}")
            return False

    def remove_care_event(self, event_id: str) -> bool:
        """Remove a care event from the search index."""
        if not self._available or not self._client:
            return False

        try:
            self._client.index(CARE_EVENTS_INDEX).delete_document(event_id)
            return True
        except MeilisearchCommunicationError:
            self._available = False
            logger.warning("Meilisearch unavailable during care event removal")
            return False
        except Exception as e:
            logger.warning(f"Failed to remove care event {event_id} from index: {e}")
            return False

    # ==================== BULK INDEXING ====================

    async def bulk_index_members(self, campus_id: Optional[str] = None) -> int:
        """
        Bulk index all members (optionally filtered by campus_id).
        Returns number of documents indexed.
        """
        if not self._available or self._client is None or self._db is None:
            return 0

        try:
            query = {}
            if campus_id:
                query["campus_id"] = campus_id

            cursor = self._db.members.find(query, {"_id": 0})
            batch = []
            total = 0
            batch_size = 500

            async for member in cursor:
                doc = _prepare_member_doc(member)
                batch.append(doc)

                if len(batch) >= batch_size:
                    self._client.index(MEMBERS_INDEX).add_documents(batch)
                    total += len(batch)
                    batch = []

            # Index remaining documents
            if batch:
                self._client.index(MEMBERS_INDEX).add_documents(batch)
                total += len(batch)

            logger.info(f"Bulk indexed {total} members" + (f" for campus {campus_id}" if campus_id else ""))
            return total
        except MeilisearchCommunicationError:
            self._available = False
            logger.warning("Meilisearch unavailable during bulk member indexing")
            return 0
        except Exception as e:
            logger.warning(f"Error during bulk member indexing: {e}")
            return 0

    async def bulk_index_care_events(self, campus_id: Optional[str] = None) -> int:
        """
        Bulk index all care events (optionally filtered by campus_id).
        Enriches events with member names.
        Returns number of documents indexed.
        """
        if not self._available or self._client is None or self._db is None:
            return 0

        try:
            query = {}
            if campus_id:
                query["campus_id"] = campus_id

            # Build member name lookup
            member_names = {}
            async for member in self._db.members.find({}, {"_id": 0, "id": 1, "name": 1}):
                member_names[member["id"]] = member["name"]

            cursor = self._db.care_events.find(query, {"_id": 0})
            batch = []
            total = 0
            batch_size = 500

            async for event in cursor:
                member_name = member_names.get(event.get("member_id"), "Unknown")
                doc = _prepare_care_event_doc(event, member_name)
                batch.append(doc)

                if len(batch) >= batch_size:
                    self._client.index(CARE_EVENTS_INDEX).add_documents(batch)
                    total += len(batch)
                    batch = []

            # Index remaining documents
            if batch:
                self._client.index(CARE_EVENTS_INDEX).add_documents(batch)
                total += len(batch)

            logger.info(f"Bulk indexed {total} care events" + (f" for campus {campus_id}" if campus_id else ""))
            return total
        except MeilisearchCommunicationError:
            self._available = False
            logger.warning("Meilisearch unavailable during bulk care event indexing")
            return 0
        except Exception as e:
            logger.warning(f"Error during bulk care event indexing: {e}")
            return 0

    # ==================== SEARCH ====================

    def search(
        self,
        query: str,
        campus_id: str,
        index: str = MEMBERS_INDEX,
        limit: int = 20,
    ) -> dict:
        """
        Search a single index with campus_id filtering.
        Returns {"hits": [...], "estimatedTotalHits": N, "processingTimeMs": N}
        or empty result on failure.
        """
        if not self._available or not self._client:
            return {"hits": [], "estimatedTotalHits": 0, "processingTimeMs": 0}

        try:
            search_params = {
                "limit": limit,
                "filter": f'campus_id = "{campus_id}"',
            }
            result = self._client.index(index).search(query, search_params)
            return {
                "hits": result.get("hits", []),
                "estimatedTotalHits": result.get("estimatedTotalHits", 0),
                "processingTimeMs": result.get("processingTimeMs", 0),
            }
        except MeilisearchCommunicationError:
            self._available = False
            logger.warning("Meilisearch unavailable during search")
            return {"hits": [], "estimatedTotalHits": 0, "processingTimeMs": 0}
        except Exception as e:
            logger.warning(f"Meilisearch search error: {e}")
            return {"hits": [], "estimatedTotalHits": 0, "processingTimeMs": 0}

    def search_all_campuses(
        self,
        query: str,
        index: str = MEMBERS_INDEX,
        limit: int = 20,
    ) -> dict:
        """
        Search a single index without campus_id filtering (for full_admin).
        Returns {"hits": [...], "estimatedTotalHits": N, "processingTimeMs": N}
        """
        if not self._available or not self._client:
            return {"hits": [], "estimatedTotalHits": 0, "processingTimeMs": 0}

        try:
            search_params = {"limit": limit}
            result = self._client.index(index).search(query, search_params)
            return {
                "hits": result.get("hits", []),
                "estimatedTotalHits": result.get("estimatedTotalHits", 0),
                "processingTimeMs": result.get("processingTimeMs", 0),
            }
        except MeilisearchCommunicationError:
            self._available = False
            logger.warning("Meilisearch unavailable during search")
            return {"hits": [], "estimatedTotalHits": 0, "processingTimeMs": 0}
        except Exception as e:
            logger.warning(f"Meilisearch search error: {e}")
            return {"hits": [], "estimatedTotalHits": 0, "processingTimeMs": 0}

    def multi_search(
        self,
        query: str,
        campus_id: Optional[str] = None,
        limit: int = 10,
    ) -> dict:
        """
        Search across both members and care_events indexes.
        If campus_id is None (full_admin), searches all campuses.
        Returns {"members": [...], "care_events": [...], "processing_time_ms": N}
        """
        if not self._available or not self._client:
            return {"members": [], "care_events": [], "processing_time_ms": 0}

        try:
            filter_str = f'campus_id = "{campus_id}"' if campus_id else None

            queries = [
                {
                    "indexUid": MEMBERS_INDEX,
                    "q": query,
                    "limit": limit,
                },
                {
                    "indexUid": CARE_EVENTS_INDEX,
                    "q": query,
                    "limit": limit,
                },
            ]
            if filter_str:
                queries[0]["filter"] = filter_str
                queries[1]["filter"] = filter_str

            result = self._client.multi_search(queries)
            results_list = result.get("results", [])

            members = []
            care_events = []
            total_time = 0

            for r in results_list:
                total_time += r.get("processingTimeMs", 0)
                if r.get("indexUid") == MEMBERS_INDEX:
                    members = r.get("hits", [])
                elif r.get("indexUid") == CARE_EVENTS_INDEX:
                    care_events = r.get("hits", [])

            return {
                "members": members,
                "care_events": care_events,
                "processing_time_ms": total_time,
            }
        except MeilisearchCommunicationError:
            self._available = False
            logger.warning("Meilisearch unavailable during multi-search")
            return {"members": [], "care_events": [], "processing_time_ms": 0}
        except Exception as e:
            logger.warning(f"Meilisearch multi-search error: {e}")
            return {"members": [], "care_events": [], "processing_time_ms": 0}

    def is_available(self) -> bool:
        """Public check if search service is operational."""
        return self._available


# ==================== MODULE-LEVEL SINGLETON ====================

_search_service: Optional[SearchService] = None


def get_search_service() -> SearchService:
    """Get the global SearchService instance."""
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
    return _search_service


# ==================== DOCUMENT PREPARATION HELPERS ====================

def _prepare_member_doc(member: dict) -> dict:
    """Prepare a member document for Meilisearch indexing."""
    return {
        "id": member.get("id", ""),
        "name": member.get("name", ""),
        "phone": member.get("phone", ""),
        "email": member.get("email", ""),
        "address": member.get("address", ""),
        "notes": member.get("notes", ""),
        "family_group_name": member.get("family_group_name", ""),
        "campus_id": member.get("campus_id", ""),
        "engagement_status": member.get("engagement_status", ""),
        "gender": member.get("gender", ""),
        "category": member.get("category", ""),
        "photo_url": member.get("photo_url", ""),
        "created_at": _serialize_datetime(member.get("created_at")),
    }


def _prepare_care_event_doc(event: dict, member_name: Optional[str] = None) -> dict:
    """Prepare a care event document for Meilisearch indexing."""
    return {
        "id": event.get("id", ""),
        "title": event.get("title", ""),
        "description": event.get("description", ""),
        "event_type": event.get("event_type", ""),
        "member_id": event.get("member_id", ""),
        "member_name": member_name or event.get("member_name", ""),
        "campus_id": event.get("campus_id", ""),
        "event_date": _serialize_datetime(event.get("event_date")),
        "completed": event.get("completed", False),
        "ignored": event.get("ignored", False),
        "created_at": _serialize_datetime(event.get("created_at")),
    }


def _serialize_datetime(value) -> str:
    """Safely serialize a datetime or date to ISO string for Meilisearch."""
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)
