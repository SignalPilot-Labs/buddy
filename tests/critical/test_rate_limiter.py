"""Tests for the server rate limiter."""

import time

import pytest
from fastapi import HTTPException

from utils.constants import START_RATE_LIMIT_MAX, START_RATE_LIMIT_WINDOW_SEC


class TestRateLimiter:
    """Tests for sliding-window rate limiter logic."""

    def _make_limiter(self):
        """Create a minimal limiter matching server.py logic."""
        timestamps: list[float] = []

        def check() -> None:
            now = time.monotonic()
            timestamps[:] = [t for t in timestamps if now - t < START_RATE_LIMIT_WINDOW_SEC]
            if len(timestamps) >= START_RATE_LIMIT_MAX:
                raise HTTPException(status_code=429, detail="Too many start requests.")
            timestamps.append(now)

        return check, timestamps

    def test_allows_up_to_limit(self):
        check, _ = self._make_limiter()
        for _ in range(START_RATE_LIMIT_MAX):
            check()

    def test_rejects_over_limit(self):
        check, _ = self._make_limiter()
        for _ in range(START_RATE_LIMIT_MAX):
            check()
        with pytest.raises(HTTPException) as exc_info:
            check()
        assert exc_info.value.status_code == 429

    def test_allows_after_window_expires(self):
        check, timestamps = self._make_limiter()
        old = time.monotonic() - START_RATE_LIMIT_WINDOW_SEC - 1
        for _ in range(START_RATE_LIMIT_MAX):
            timestamps.append(old)
        check()  # should not raise — old timestamps expired
