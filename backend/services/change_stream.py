"""
MongoDB Change Streams service for real-time event propagation.

Watches the activity_logs collection and broadcasts new activities to SSE
subscribers via DragonflyDB pub/sub, decoupling real-time broadcasting from
business logic.

Architecture:
    [log_activity()] -> insert into activity_logs
                              |
                  [ChangeStreamWatcher] (watches collection via change stream)
                              |
                  [DragonflyDB pub/sub] (publishes to ft:{campus_id}:activity)
                              |
                  [SSE endpoint] (subscribes and streams to clients)

NOTE: MongoDB Change Streams require a replica set or sharded cluster.
Standalone MongoDB (e.g., default docker-compose setup) does NOT support
change streams. This service detects the topology at startup and gracefully
falls back to a no-op if replica set is unavailable. In that case, the
existing manual broadcast in log_activity() remains the active path.

When a replica set IS available, this service becomes the sole producer of
SSE events via DragonflyDB pub/sub, and the manual broadcast in log_activity()
can be disabled.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Resume token key in DragonflyDB for crash recovery
_RESUME_TOKEN_KEY = "ft:change_stream:resume_token"

# Exponential backoff constants for reconnection
_INITIAL_BACKOFF_SECONDS = 1.0
_MAX_BACKOFF_SECONDS = 60.0
_BACKOFF_MULTIPLIER = 2.0


class ChangeStreamWatcher:
    """Watches the activity_logs collection for new inserts and publishes
    to DragonflyDB pub/sub channels for SSE delivery.

    The watcher runs as a background asyncio task and supports:
    - Resume tokens for reconnection after transient failures
    - Exponential backoff on connection errors
    - Graceful shutdown via stop()
    - Automatic detection of replica set availability
    """

    def __init__(self, db, redis_client=None):
        """
        Args:
            db: Motor database instance (AsyncIOMotorDatabase)
            redis_client: Optional redis.asyncio.Redis client for DragonflyDB pub/sub.
                          If None, the watcher will attempt to get it from services.cache.
        """
        self._db = db
        self._redis_client = redis_client
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._replica_set_available = False

    async def _check_replica_set(self) -> bool:
        """Check if MongoDB is running as a replica set (required for change streams).

        Returns True if change streams are supported, False otherwise.
        """
        try:
            # Try to open a change stream briefly to verify support.
            # This is the most reliable detection method since it tests
            # the actual capability rather than inferring from topology.
            async with self._db.activity_logs.watch(
                pipeline=[{"$match": {"operationType": "insert"}}],
                max_await_time_ms=100,
            ) as stream:
                # If we got here without error, change streams are supported
                pass
            return True
        except Exception as e:
            error_str = str(e).lower()
            if "replica set" in error_str or "not supported" in error_str or "not allowed" in error_str:
                logger.info(
                    "MongoDB change streams not available (standalone mode). "
                    "The manual broadcast path in log_activity() will be used. "
                    "To enable change streams, configure MongoDB as a replica set."
                )
            else:
                logger.warning(f"Change stream check failed with unexpected error: {e}")
            return False

    def _get_redis_client(self):
        """Get redis client, either from constructor arg or from cache service."""
        if self._redis_client is not None:
            return self._redis_client
        try:
            from services.cache import get_redis_client
            return get_redis_client()
        except Exception:
            return None

    async def _load_resume_token(self) -> Optional[dict]:
        """Load the last resume token from DragonflyDB for crash recovery.

        Resume tokens allow the watcher to pick up where it left off after
        a restart, avoiding missed events.
        """
        redis = self._get_redis_client()
        if not redis:
            return None
        try:
            data = await redis.get(_RESUME_TOKEN_KEY)
            if data:
                token = json.loads(data)
                logger.info("Loaded change stream resume token from DragonflyDB")
                return token
        except Exception as e:
            logger.debug(f"Could not load resume token: {e}")
        return None

    async def _save_resume_token(self, token: dict) -> None:
        """Persist the resume token to DragonflyDB.

        Token is stored with a 24-hour TTL. MongoDB oplog entries older than
        the oplog window cannot be resumed from anyway, so stale tokens are
        useless and should expire.
        """
        redis = self._get_redis_client()
        if not redis:
            return
        try:
            await redis.setex(
                _RESUME_TOKEN_KEY,
                86400,  # 24 hour TTL
                json.dumps(token, default=str),
            )
        except Exception as e:
            logger.debug(f"Could not save resume token: {e}")

    async def _publish_activity(self, campus_id: str, activity_data: dict) -> None:
        """Publish an activity event to the DragonflyDB pub/sub channel.

        Falls back to in-memory broadcast if DragonflyDB is unavailable.
        """
        redis = self._get_redis_client()
        if redis:
            try:
                channel = f"ft:{campus_id}:activity"
                await redis.publish(channel, json.dumps(activity_data, default=str))
                return
            except Exception as e:
                logger.debug(f"DragonflyDB publish from change stream failed: {e}")

        # Fallback: in-memory broadcast (import here to avoid circular dependency)
        try:
            from server import broadcast_activity
            await broadcast_activity(campus_id, activity_data)
        except Exception as e:
            logger.debug(f"In-memory broadcast from change stream failed: {e}")

    def _extract_activity_data(self, full_document: dict) -> dict:
        """Extract the fields needed for SSE broadcast from a change stream document.

        Transforms the raw MongoDB document into the same format that
        _broadcast_activity_safe() uses, ensuring SSE consumers see
        consistent data regardless of the broadcast path.
        """
        # Handle enum values that may be stored as strings or enum objects
        action_type = full_document.get("action_type", "")
        if hasattr(action_type, "value"):
            action_type = action_type.value

        event_type = full_document.get("event_type")
        if event_type and hasattr(event_type, "value"):
            event_type = event_type.value

        created_at = full_document.get("created_at")
        if isinstance(created_at, datetime):
            timestamp = created_at.isoformat()
        elif created_at:
            timestamp = str(created_at)
        else:
            timestamp = datetime.now(timezone.utc).isoformat()

        return {
            "id": full_document.get("id", ""),
            "campus_id": full_document.get("campus_id", ""),
            "user_id": full_document.get("user_id", ""),
            "user_name": full_document.get("user_name", ""),
            "user_photo_url": full_document.get("user_photo_url"),
            "action_type": action_type,
            "member_id": full_document.get("member_id"),
            "member_name": full_document.get("member_name"),
            "care_event_id": full_document.get("care_event_id"),
            "event_type": event_type,
            "notes": full_document.get("notes"),
            "timestamp": timestamp,
        }

    async def _watch_loop(self) -> None:
        """Main watch loop with reconnection and exponential backoff.

        This loop runs continuously while self._running is True. On each
        iteration it opens a change stream cursor on the activity_logs
        collection and processes insert events. If the cursor fails (e.g.,
        network error, cursor invalidation), the loop reconnects with
        exponential backoff.
        """
        backoff = _INITIAL_BACKOFF_SECONDS
        resume_token = await self._load_resume_token()

        while self._running:
            try:
                # Build the change stream pipeline: only process inserts,
                # and project only the fields we need to keep bandwidth low.
                pipeline = [
                    {"$match": {"operationType": "insert"}},
                    {
                        "$project": {
                            "operationType": 1,
                            "fullDocument.id": 1,
                            "fullDocument.campus_id": 1,
                            "fullDocument.user_id": 1,
                            "fullDocument.user_name": 1,
                            "fullDocument.user_photo_url": 1,
                            "fullDocument.action_type": 1,
                            "fullDocument.member_id": 1,
                            "fullDocument.member_name": 1,
                            "fullDocument.care_event_id": 1,
                            "fullDocument.event_type": 1,
                            "fullDocument.notes": 1,
                            "fullDocument.created_at": 1,
                        }
                    },
                ]

                watch_kwargs = {
                    "pipeline": pipeline,
                    "full_document": "updateLookup",
                    "max_await_time_ms": 1000,  # Poll interval for getMore
                }
                if resume_token:
                    watch_kwargs["resume_after"] = resume_token

                logger.info("Opening change stream on activity_logs collection")

                async with self._db.activity_logs.watch(**watch_kwargs) as stream:
                    # Reset backoff on successful connection
                    backoff = _INITIAL_BACKOFF_SECONDS

                    async for change in stream:
                        if not self._running:
                            break

                        # Save resume token for crash recovery
                        token = change.get("_id")
                        if token:
                            resume_token = token
                            # Save periodically (not on every event to reduce writes)
                            await self._save_resume_token(token)

                        full_doc = change.get("fullDocument")
                        if not full_doc:
                            continue

                        campus_id = full_doc.get("campus_id", "")
                        if not campus_id:
                            continue

                        activity_data = self._extract_activity_data(full_doc)
                        await self._publish_activity(campus_id, activity_data)

            except asyncio.CancelledError:
                logger.info("Change stream watcher cancelled")
                break
            except Exception as e:
                if not self._running:
                    break
                logger.warning(
                    f"Change stream error (reconnecting in {backoff:.1f}s): {e}"
                )
                try:
                    await asyncio.sleep(backoff)
                except asyncio.CancelledError:
                    break
                backoff = min(backoff * _BACKOFF_MULTIPLIER, _MAX_BACKOFF_SECONDS)

        logger.info("Change stream watcher stopped")

    async def start(self) -> bool:
        """Start the change stream watcher as a background task.

        Returns True if the watcher was started successfully, False if
        change streams are not available (standalone MongoDB).
        """
        if self._task and not self._task.done():
            logger.warning("Change stream watcher is already running")
            return self._replica_set_available

        # Detect replica set support
        self._replica_set_available = await self._check_replica_set()
        if not self._replica_set_available:
            logger.info(
                "Change stream watcher not started (replica set not available). "
                "Manual broadcast in log_activity() will handle SSE delivery."
            )
            return False

        self._running = True
        self._task = asyncio.create_task(self._watch_loop())
        # Prevent unhandled exception warnings if the task fails
        self._task.add_done_callback(self._on_task_done)
        logger.info("Change stream watcher started successfully")
        return True

    def _on_task_done(self, task: asyncio.Task) -> None:
        """Callback for when the background task completes (normally or with error)."""
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            logger.error(f"Change stream watcher task failed: {exc}")

    async def stop(self) -> None:
        """Gracefully stop the change stream watcher."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            logger.info("Change stream watcher stopped gracefully")

    @property
    def is_running(self) -> bool:
        """Whether the watcher is currently active."""
        return self._running and self._task is not None and not self._task.done()

    @property
    def is_replica_set_available(self) -> bool:
        """Whether the MongoDB deployment supports change streams."""
        return self._replica_set_available


# Module-level singleton for convenience
_watcher: Optional[ChangeStreamWatcher] = None


async def start_change_stream_watcher(db, redis_client=None) -> Optional[ChangeStreamWatcher]:
    """Initialize and start the global change stream watcher.

    Args:
        db: Motor database instance
        redis_client: Optional DragonflyDB redis client

    Returns:
        The ChangeStreamWatcher instance, or None if change streams are unavailable.
    """
    global _watcher
    _watcher = ChangeStreamWatcher(db, redis_client)
    started = await _watcher.start()
    if started:
        return _watcher
    # Return the watcher even if not started so callers can check status
    return _watcher


async def stop_change_stream_watcher() -> None:
    """Stop the global change stream watcher."""
    global _watcher
    if _watcher:
        await _watcher.stop()
        _watcher = None


def get_change_stream_watcher() -> Optional[ChangeStreamWatcher]:
    """Get the global change stream watcher instance."""
    return _watcher


def is_change_stream_active() -> bool:
    """Check if the change stream watcher is actively processing events.

    When True, the change stream handles SSE broadcasting and the manual
    broadcast in log_activity() can be skipped. When False, log_activity()
    should continue to broadcast manually via _broadcast_activity_safe().
    """
    return _watcher is not None and _watcher.is_running
