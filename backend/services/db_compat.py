"""Compatibility shims for the pymongo async API.

pymongo's async API has been migrating methods from coroutine-returning to
direct-return as it stabilises (start_session flipped to sync in 4.16;
watch() may follow). Helpers here detect the shape at runtime so call
sites stay stable across versions and don't break on upgrade with a
TypeError like "object AsyncCollectionChangeStream can't be used in
'await' expression".
"""

import inspect
from contextlib import asynccontextmanager


@asynccontextmanager
async def open_change_stream(target, **watch_kwargs):
    """Open a MongoDB change stream as an async context manager.

    Works whether target.watch() returns a coroutine (current pymongo
    async) or the AsyncChangeStream directly (likely future shape).

    Args:
        target: An AsyncCollection, AsyncDatabase, or AsyncMongoClient.
        **watch_kwargs: Forwarded to target.watch().

    Yields:
        The opened AsyncChangeStream.
    """
    cm = target.watch(**watch_kwargs)
    if inspect.isawaitable(cm):
        cm = await cm
    async with cm as stream:
        yield stream
