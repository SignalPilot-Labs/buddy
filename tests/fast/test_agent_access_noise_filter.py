"""Tests for agent-side AccessNoiseFilter.

The agent access log filter must suppress GET /health, GET /logs, and
/diff lines while allowing all other requests through.
"""

import logging

from utils.constants import AccessNoiseFilter


class TestAgentAccessNoiseFilter:
    """AccessNoiseFilter drops health, logs, and diff access log lines."""

    def _make_record(self, msg: str) -> logging.LogRecord:
        return logging.LogRecord(
            name="uvicorn.access",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=msg,
            args=(),
            exc_info=None,
        )

    def test_blocks_health(self) -> None:
        f = AccessNoiseFilter()
        record = self._make_record('GET /health HTTP/1.1" 200 OK')
        assert f.filter(record) is False

    def test_blocks_logs(self) -> None:
        f = AccessNoiseFilter()
        record = self._make_record('GET /logs?run_id=abc HTTP/1.1" 200 OK')
        assert f.filter(record) is False

    def test_blocks_diff_repo(self) -> None:
        f = AccessNoiseFilter()
        record = self._make_record('GET /diff/repo?run_id=abc HTTP/1.1" 200 OK')
        assert f.filter(record) is False

    def test_blocks_diff_tmp(self) -> None:
        f = AccessNoiseFilter()
        record = self._make_record('GET /diff/tmp?run_id=abc HTTP/1.1" 200 OK')
        assert f.filter(record) is False

    def test_blocks_diff_stats(self) -> None:
        f = AccessNoiseFilter()
        record = self._make_record('GET /diff/repo/stats?run_id=abc HTTP/1.1" 200 OK')
        assert f.filter(record) is False

    def test_allows_other_requests(self) -> None:
        f = AccessNoiseFilter()
        record = self._make_record('POST /start HTTP/1.1" 200 OK')
        assert f.filter(record) is True

    def test_allows_non_access_messages(self) -> None:
        f = AccessNoiseFilter()
        record = self._make_record("Run abc started")
        assert f.filter(record) is True
