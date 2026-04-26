"""Regression tests for CLI client.py network error handling.

Covers:
- _request() raises httpx.TimeoutException → friendly message + exit(1)
- _request() raises httpx.ConnectError → friendly message + exit(1) (existing behavior)
- stream_sse() raises httpx.ConnectError → friendly message + exit(1)
- stream_sse() raises httpx.TimeoutException → friendly message + exit(1)
"""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from cli.client import AutoFynClient
from cli.constants import HTTP_TIMEOUT_SECONDS


BASE_URL = "http://localhost:3401"


class TestCliClientNetworkErrors:
    """Regression tests for network error handling in AutoFynClient."""

    # ── _request timeout ──────────────────────────────────────────────────────

    def test_request_timeout_exits_with_code_1(self, capsys: pytest.CaptureFixture) -> None:
        """_request() must catch TimeoutException and exit(1), not crash."""
        client = AutoFynClient(BASE_URL)
        with (
            patch.object(client._http, "request", side_effect=httpx.TimeoutException("timed out")),
            pytest.raises(SystemExit) as exc_info,
        ):
            client._request("GET", "/api/runs")
        assert exc_info.value.code == 1

    def test_request_timeout_prints_friendly_message(self, capsys: pytest.CaptureFixture) -> None:
        """_request() must print a timeout error message referencing HTTP_TIMEOUT_SECONDS."""
        client = AutoFynClient(BASE_URL)
        with (
            patch.object(client._http, "request", side_effect=httpx.TimeoutException("timed out")),
            pytest.raises(SystemExit),
        ):
            client._request("GET", "/api/runs")
        captured = capsys.readouterr()
        assert str(HTTP_TIMEOUT_SECONDS) in captured.err
        assert "timed out" in captured.err.lower() or "timeout" in captured.err.lower()

    def test_request_connect_error_exits_with_code_1(self, capsys: pytest.CaptureFixture) -> None:
        """_request() must catch ConnectError and exit(1)."""
        client = AutoFynClient(BASE_URL)
        with (
            patch.object(client._http, "request", side_effect=httpx.ConnectError("refused")),
            pytest.raises(SystemExit) as exc_info,
        ):
            client._request("GET", "/api/runs")
        assert exc_info.value.code == 1

    # ── stream_sse connect error ───────────────────────────────────────────────

    def test_stream_sse_connect_error_exits_with_code_1(self, capsys: pytest.CaptureFixture) -> None:
        """stream_sse() must catch ConnectError and exit(1)."""
        client = AutoFynClient(BASE_URL)
        with (
            patch(
                "cli.client.connect_sse",
                side_effect=httpx.ConnectError("connection refused"),
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            list(client.stream_sse("/api/stream"))
        assert exc_info.value.code == 1

    def test_stream_sse_connect_error_prints_friendly_message(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """stream_sse() must print a connection error message."""
        client = AutoFynClient(BASE_URL)
        with (
            patch(
                "cli.client.connect_sse",
                side_effect=httpx.ConnectError("connection refused"),
            ),
            pytest.raises(SystemExit),
        ):
            list(client.stream_sse("/api/stream"))
        captured = capsys.readouterr()
        assert BASE_URL in captured.err
        assert "connect" in captured.err.lower() or "autofyn" in captured.err.lower()

    # ── stream_sse timeout ─────────────────────────────────────────────────────

    def test_stream_sse_timeout_exits_with_code_1(self, capsys: pytest.CaptureFixture) -> None:
        """stream_sse() must catch TimeoutException and exit(1)."""
        client = AutoFynClient(BASE_URL)
        with (
            patch(
                "cli.client.connect_sse",
                side_effect=httpx.TimeoutException("timed out"),
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            list(client.stream_sse("/api/stream"))
        assert exc_info.value.code == 1

    def test_stream_sse_timeout_prints_friendly_message(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """stream_sse() must print a timeout error message referencing HTTP_TIMEOUT_SECONDS."""
        client = AutoFynClient(BASE_URL)
        with (
            patch(
                "cli.client.connect_sse",
                side_effect=httpx.TimeoutException("timed out"),
            ),
            pytest.raises(SystemExit),
        ):
            list(client.stream_sse("/api/stream"))
        captured = capsys.readouterr()
        assert str(HTTP_TIMEOUT_SECONDS) in captured.err
        assert "timed out" in captured.err.lower() or "timeout" in captured.err.lower()
