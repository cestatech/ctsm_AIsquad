"""Unit tests for Redis-backed per-IP login rate limiting."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from redis.exceptions import ConnectionError

from app.core.exceptions import RateLimitError
from app.services.login_rate_limiter import LoginRateLimiter


@pytest.mark.asyncio
class TestLoginRateLimiter:
    async def test_acquire_returns_reservation_without_exposing_ip_in_key(self):
        redis = AsyncMock()
        redis.eval.return_value = 0
        limiter = LoginRateLimiter(redis, max_attempts=5, window_seconds=900)

        token = await limiter.acquire("203.0.113.42")

        assert token
        key = redis.eval.call_args.args[2]
        assert key.startswith("auth:login-failures:ip:")
        assert "203.0.113.42" not in key

    async def test_acquire_raises_with_retry_after_when_limit_reached(self):
        redis = AsyncMock()
        redis.eval.return_value = 321
        limiter = LoginRateLimiter(redis, max_attempts=5, window_seconds=900)

        with pytest.raises(RateLimitError) as exc_info:
            await limiter.acquire("203.0.113.42")

        assert exc_info.value.retry_after_seconds == 321

    async def test_release_removes_reservation(self):
        redis = AsyncMock()
        limiter = LoginRateLimiter(redis, max_attempts=5, window_seconds=900)

        await limiter.release("203.0.113.42", "reservation")

        redis.eval.assert_awaited_once()
        assert redis.eval.call_args.args[-1] == "reservation"

    async def test_redis_outage_fails_open(self):
        redis = AsyncMock()
        redis.eval.side_effect = ConnectionError("unavailable")
        limiter = LoginRateLimiter(redis, max_attempts=5, window_seconds=900)

        assert await limiter.acquire("203.0.113.42") is None

    async def test_missing_ip_does_not_use_redis(self):
        redis = AsyncMock()
        limiter = LoginRateLimiter(redis, max_attempts=5, window_seconds=900)

        assert await limiter.acquire(None) is None
        redis.eval.assert_not_awaited()
