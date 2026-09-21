import time
import os
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

class RateLimitStore(ABC):
    @abstractmethod
    def is_rate_limited(self, identifier: str, limit: int, window_seconds: float) -> bool:
        """Returns True if identifier exceeded limit in window_seconds, False otherwise."""
        pass

class InMemoryRateLimitStore(RateLimitStore):
    """In-memory rate limit store with sliding window for dev and tests."""
    def __init__(self):
        self._store: Dict[str, List[float]] = {}

    def is_rate_limited(self, identifier: str, limit: int, window_seconds: float) -> bool:
        now = time.time()
        timestamps = self._store.get(identifier, [])
        valid_timestamps = [t for t in timestamps if now - t < window_seconds]
        if len(valid_timestamps) >= limit:
            self._store[identifier] = valid_timestamps
            return True
        valid_timestamps.append(now)
        self._store[identifier] = valid_timestamps
        return False

class RedisRateLimitStore(RateLimitStore):
    """
    Production-ready distributed rate limiting store compatible with Redis / Upstash / Valkey.
    Uses sliding window log via Redis Sorted Sets (ZADD, ZREMRANGEBYSCORE, ZCARD).
    """
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.environ.get("REDIS_URL")
        self._redis = None
        if self.redis_url:
            try:
                import redis
                self._redis = redis.from_url(self.redis_url)
            except Exception:
                self._redis = None

    def is_rate_limited(self, identifier: str, limit: int, window_seconds: float) -> bool:
        if not self._redis:
            # Fallback to local in-memory if Redis not reachable
            return False
        now = time.time()
        key = f"cleansheet:ratelimit:{identifier}"
        try:
            pipe = self._redis.pipeline()
            pipe.zremrangebyscore(key, 0, now - window_seconds)
            pipe.zcard(key)
            pipe.zadd(key, {str(now): now})
            pipe.expire(key, int(window_seconds) + 10)
            res = pipe.execute()
            count = res[1]
            return count >= limit
        except Exception:
            return False

# Global factory
def get_rate_limit_store() -> RateLimitStore:
    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        return RedisRateLimitStore(redis_url)
    return InMemoryRateLimitStore()

rate_limiter = get_rate_limit_store()
