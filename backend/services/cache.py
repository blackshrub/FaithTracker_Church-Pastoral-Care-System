import json
import logging
import os
from typing import Any

import redis.asyncio as redis

logger = logging.getLogger(__name__)

DRAGONFLY_URL = os.environ.get("DRAGONFLY_URL", "redis://localhost:6379/0")

_redis_client: redis.Redis | None = None


class CacheService:
    DEFAULT_TTL = 300
    DASHBOARD_TTL = 600
    SETTINGS_TTL = 3600
    STATIC_TTL = 86400

    KEY_PREFIX = "ft:"

    KEY_DASHBOARD_STATS = "dashboard:stats"
    KEY_CAMPUSES = "campuses:list"
    KEY_ENGAGEMENT_SETTINGS = "settings:engagement"
    KEY_WRITEOFF_SETTINGS = "settings:writeoff"
    KEY_AUTOMATION_SETTINGS = "settings:automation"

    def __init__(self, client: redis.Redis):
        self._client = client

    def _make_key(self, key: str, church_id: str | None = None) -> str:
        if church_id:
            return f"{self.KEY_PREFIX}{church_id}:{key}"
        return f"{self.KEY_PREFIX}{key}"

    async def get(self, key: str, church_id: str | None = None) -> Any | None:
        full_key = self._make_key(key, church_id)
        try:
            data = await self._client.get(full_key)
            if data:
                return json.loads(data)
            return None
        except redis.RedisError as e:
            logger.warning(f"Cache get error for {full_key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int = DEFAULT_TTL, church_id: str | None = None) -> bool:
        full_key = self._make_key(key, church_id)
        try:
            serialized = json.dumps(value, default=str)
            await self._client.setex(full_key, ttl, serialized)
            return True
        except redis.RedisError as e:
            logger.warning(f"Cache set error for {full_key}: {e}")
            return False

    async def delete(self, key: str, church_id: str | None = None) -> bool:
        full_key = self._make_key(key, church_id)
        try:
            await self._client.delete(full_key)
            return True
        except redis.RedisError as e:
            logger.warning(f"Cache delete error for {full_key}: {e}")
            return False

    async def invalidate_pattern(self, pattern: str, church_id: str | None = None) -> int:
        full_pattern = self._make_key(pattern, church_id)
        try:
            cursor = 0
            deleted = 0
            while True:
                cursor, keys = await self._client.scan(cursor=cursor, match=full_pattern, count=100)
                if keys:
                    deleted += await self._client.delete(*keys)
                if cursor == 0:
                    break
            return deleted
        except redis.RedisError as e:
            logger.warning(f"Cache invalidate_pattern error for {full_pattern}: {e}")
            return 0

    async def get_dashboard_stats(self, church_id: str) -> dict | None:
        return await self.get(self.KEY_DASHBOARD_STATS, church_id)

    async def set_dashboard_stats(self, church_id: str, stats: dict) -> bool:
        return await self.set(self.KEY_DASHBOARD_STATS, stats, ttl=self.DASHBOARD_TTL, church_id=church_id)

    async def invalidate_dashboard(self, church_id: str) -> bool:
        return await self.delete(self.KEY_DASHBOARD_STATS, church_id)

    async def get_campuses(self) -> list | None:
        return await self.get(self.KEY_CAMPUSES)

    async def set_campuses(self, campuses: list) -> bool:
        return await self.set(self.KEY_CAMPUSES, campuses, ttl=self.SETTINGS_TTL)

    async def invalidate_campuses(self) -> bool:
        return await self.delete(self.KEY_CAMPUSES)

    async def get_settings(self, key: str, church_id: str) -> dict | None:
        return await self.get(key, church_id)

    async def set_settings(self, key: str, church_id: str, settings: dict) -> bool:
        return await self.set(key, settings, ttl=self.SETTINGS_TTL, church_id=church_id)

    async def invalidate_settings(self, key: str, church_id: str) -> bool:
        return await self.delete(key, church_id)

    # Lua script: atomic INCR + EXPIRE-on-first. A non-atomic pipeline
    # could leave the key without a TTL if the client crashes between
    # INCR and EXPIRE, producing a permanent counter that an attacker
    # could exploit to lock out a victim forever.
    _INCR_TTL_SCRIPT = (
        "local n = redis.call('incr', KEYS[1]) "
        "if n == 1 then redis.call('expire', KEYS[1], ARGV[1]) end "
        "return n"
    )

    async def incr_rate_limit(self, key: str, window_seconds: int = 60) -> int:
        full_key = self._make_key(f"ratelimit:{key}")
        try:
            return int(
                await self._client.eval(self._INCR_TTL_SCRIPT, 1, full_key, window_seconds)
            )
        except redis.RedisError as e:
            logger.warning(f"Rate limit incr error for {full_key}: {e}")
            return 0

    async def health_check(self) -> bool:
        try:
            await self._client.ping()
            return True
        except redis.RedisError:
            return False


async def init_cache() -> CacheService:
    global _redis_client

    _redis_client = redis.from_url(
        DRAGONFLY_URL,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
    )

    try:
        await _redis_client.ping()
        logger.info(f"Connected to DragonflyDB at {DRAGONFLY_URL}")
    except redis.RedisError as e:
        logger.warning(f"DragonflyDB connection failed: {e}. Cache will be disabled.")

    return CacheService(_redis_client)


async def close_cache() -> None:
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None
        logger.info("DragonflyDB connection closed")


def get_cache() -> CacheService | None:
    if _redis_client:
        return CacheService(_redis_client)
    return None


def get_redis_client() -> redis.Redis | None:
    """Get the raw redis client for direct operations (e.g., login rate limiting)"""
    return _redis_client
