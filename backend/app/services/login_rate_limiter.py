"""Redis-backed per-IP login failure rate limiting."""

from __future__ import annotations

import hashlib
import logging
import time
from collections.abc import Awaitable
from functools import lru_cache
from typing import Any, cast
from uuid import uuid4

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.core.exceptions import RateLimitError

log = logging.getLogger(__name__)

_ACQUIRE_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local token = ARGV[4]

redis.call("ZREMRANGEBYSCORE", key, "-inf", now - window)
local count = redis.call("ZCARD", key)
if count >= limit then
    local oldest = redis.call("ZRANGE", key, 0, 0, "WITHSCORES")
    local retry_after = math.ceil(window - (now - tonumber(oldest[2])))
    return math.max(retry_after, 1)
end

redis.call("ZADD", key, now, token)
redis.call("EXPIRE", key, math.ceil(window))
return 0
"""

_RELEASE_SCRIPT = """
redis.call("ZREM", KEYS[1], ARGV[1])
if redis.call("ZCARD", KEYS[1]) == 0 then
    redis.call("DEL", KEYS[1])
end
return 1
"""


class LoginRateLimiter:
    """Limit retained failed-login reservations per client IP."""

    def __init__(
        self,
        redis: Redis,
        *,
        max_attempts: int,
        window_seconds: int,
    ) -> None:
        self._redis = redis
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds

    @staticmethod
    def _key(ip_address: str) -> str:
        ip_hash = hashlib.sha256(ip_address.encode("utf-8")).hexdigest()
        return f"auth:login-failures:ip:{ip_hash}"

    async def acquire(self, ip_address: str | None) -> str | None:
        """
        Reserve a login attempt.

        Call ``release`` when the attempt succeeds or fails for a reason other
        than invalid credentials. Credential failures retain the reservation.
        """
        if not ip_address:
            return None

        token = uuid4().hex
        try:
            # redis-py types eval() as `Awaitable[str] | str` because the stub
            # is shared with the sync client; the asyncio client always awaits.
            retry_after = await cast(
                "Awaitable[Any]",
                self._redis.eval(
                    _ACQUIRE_SCRIPT,
                    1,
                    self._key(ip_address),
                    str(time.time()),
                    str(self._window_seconds),
                    str(self._max_attempts),
                    token,
                ),
            )
        except RedisError:
            log.exception("Redis unavailable; allowing login attempt without IP limit")
            return None

        if int(retry_after):
            raise RateLimitError(retry_after_seconds=int(retry_after))
        return token

    async def release(self, ip_address: str | None, token: str | None) -> None:
        """Release a reservation that should not count as a failed login."""
        if not ip_address or not token:
            return
        try:
            await cast(
                "Awaitable[Any]",
                self._redis.eval(
                    _RELEASE_SCRIPT,
                    1,
                    self._key(ip_address),
                    token,
                ),
            )
        except RedisError:
            log.exception("Redis unavailable while releasing login reservation")


@lru_cache
def get_login_rate_limiter() -> LoginRateLimiter:
    settings = get_settings()
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return LoginRateLimiter(
        redis,
        max_attempts=settings.AUTH_IP_MAX_FAILED_ATTEMPTS,
        window_seconds=settings.AUTH_IP_WINDOW_MINUTES * 60,
    )
