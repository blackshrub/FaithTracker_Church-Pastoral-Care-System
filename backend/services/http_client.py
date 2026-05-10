"""Shared httpx AsyncClient for connection pooling.

Provides a singleton httpx.AsyncClient that reuses TCP connections
across requests, reducing connection overhead for frequently called
external APIs (WhatsApp gateway, etc.).

Special-purpose calls (sync API with 60s timeout, etc.) should continue
using their own per-request clients with specific timeout requirements.
"""

import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

_client: httpx.AsyncClient | None = None
# Async lock prevents two coroutines that both observe `_client is None`
# from each constructing a new AsyncClient (one would overwrite the other,
# leaking the orphaned client's connection pool + SSL context).
_client_lock = asyncio.Lock()


async def get_http_client() -> httpx.AsyncClient:
    """Get or create the shared httpx AsyncClient.

    The client is configured with:
    - 30s default timeout (matches most usage)
    - 20 max connections / 10 keepalive (reasonable pool)
    - Follow redirects enabled
    """
    global _client
    if _client is not None and not _client.is_closed:
        return _client
    async with _client_lock:
        # Re-check inside the lock — another coroutine may have raced ahead.
        if _client is None or _client.is_closed:
            _client = httpx.AsyncClient(
                timeout=30.0,
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
                follow_redirects=True,
            )
    return _client


async def close_http_client():
    """Close the shared httpx client. Call on application shutdown."""
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None
        logger.info("Shared HTTP client closed")
