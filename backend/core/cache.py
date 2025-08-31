# core/cache.py
import time
from typing import Any, Callable, Awaitable, Dict, Tuple


class TTLCache:
    def __init__(self, ttl_seconds: int = 60, maxsize: int = 1000):
        self.ttl = ttl_seconds
        self.maxsize = maxsize
        self._store: Dict[str, Tuple[float, Any]] = {}

    def get(self, key: str):
        rec = self._store.get(key)
        if not rec:
            return None
        exp, val = rec
        if exp < time.time():
            self._store.pop(key, None)
            return None
        return val

    def set(self, key: str, val: Any):
        if len(self._store) >= self.maxsize:
            # simple eviction: pop oldest
            old_key = next(iter(self._store))
            self._store.pop(old_key, None)
        self._store[key] = (time.time() + self.ttl, val)

    async def aget_or_set(self, key: str, creator: Callable[[], Awaitable[Any]]):
        hit = self.get(key)
        if hit is not None:
            return hit
        val = await creator()
        self.set(key, val)
        return val


# one shared cache instance (tune TTL later if needed)
match_cache = TTLCache(ttl_seconds=120)
matrix_cache = TTLCache(ttl_seconds=60)
geom_cache = TTLCache(ttl_seconds=60)
ors_matrix_cache = TTLCache(ttl_seconds=90)
