"""Tests for health check log filtering.

The sandbox access log filter must suppress GET /health lines
while allowing all other requests through.
"""

import logging

from constants import HealthLogFilter


class TestHealthLogFilter:
    """HealthLogFilter drops health check access log lines."""

    def _make_record(self, msg: str) -> logging.LogRecord:
        return logging.LogRecord(
            name="aiohttp.access",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=msg,
            args=(),
            exc_info=None,
        )

    def test_blocks_health_get(self) -> None:
        f = HealthLogFilter()
        record = self._make_record(
            '127.0.0.1 [15/Apr/2026:18:46:39 +0000] "GET /health HTTP/1.1" 200 202 "-" "curl/8.14.1"',
        )
        assert f.filter(record) is False

    def test_blocks_health_httpx(self) -> None:
        f = HealthLogFilter()
        record = self._make_record(
            '172.18.0.5 [15/Apr/2026:00:53:26 +0000] "GET /health HTTP/1.1" 200 202 "-" "python-httpx/0.28.1"',
        )
        assert f.filter(record) is False

    def test_allows_other_requests(self) -> None:
        f = HealthLogFilter()
        record = self._make_record(
            '127.0.0.1 [15/Apr/2026:18:46:39 +0000] "POST /session/create HTTP/1.1" 200 150',
        )
        assert f.filter(record) is True

    def test_allows_non_access_messages(self) -> None:
        f = HealthLogFilter()
        record = self._make_record("Database connection pool initialized")
        assert f.filter(record) is True
