"""
TTL-based in-memory cache using cachetools.TTLCache behind an asyncio lock.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from cachetools import TTLCache

from app.config import settings


class AsyncTTLCache:
    def __init__(self, maxsize: int, ttl: int) -> None:
        self._cache: TTLCache = TTLCache(maxsize=maxsize, ttl=ttl)
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            return self._cache.get(key)

    async def set(self, key: str, value: Any) -> None:
        async with self._lock:
            self._cache[key] = value

    async def invalidate(self, key: str) -> None:
        async with self._lock:
            self._cache.pop(key, None)


meters_cache = AsyncTTLCache(maxsize=500, ttl=settings.cache_ttl_meters)
readings_cache = AsyncTTLCache(maxsize=500, ttl=settings.cache_ttl_readings)
transformers_cache = AsyncTTLCache(maxsize=100, ttl=settings.cache_ttl_transformers)
