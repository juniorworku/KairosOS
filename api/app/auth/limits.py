"""Atomic Redis rate limits; tests may explicitly inject an isolated in-memory limiter."""

import time
from typing import Protocol

from redis.asyncio import Redis


class Limiter(Protocol):
    async def allow(self, key: str, limit: int, seconds: int) -> bool: ...


class RedisLimiter:
    def __init__(self, url: str) -> None:
        self.url = url

    async def allow(self, key: str, limit: int, seconds: int) -> bool:
        script = """
        local count = redis.call('INCR', KEYS[1])
        if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
        return count
        """
        bucket = int(time.time()) // seconds
        async with Redis.from_url(self.url) as redis:
            count = await redis.eval(script, 1, f"auth:{key}:{seconds}:{bucket}", seconds)
            return int(count) <= limit


class MemoryLimiter:
    """For isolated tests only. Production never falls back when Redis is unavailable."""

    def __init__(self) -> None:
        self.counters: dict[tuple[str, int, int], int] = {}

    async def allow(self, key: str, limit: int, seconds: int) -> bool:
        bucket = (key, seconds, int(time.time()) // seconds)
        self.counters[bucket] = self.counters.get(bucket, 0) + 1
        return self.counters[bucket] <= limit
