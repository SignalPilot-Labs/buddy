"""Unit tests for AF_READY marker validation.

Both base_backend.parse_ready_marker (local) and connector
startup._parse_marker (remote) must validate that AF_READY contains
the required keys: host, port, secret. Missing keys must produce a
clear error instead of a downstream KeyError.
"""

from __future__ import annotations

import re

import pytest

from cli.connector.startup import MARKER_RE, _parse_marker
from sandbox_client.backends.base_backend import SandboxBackend

SSH_TARGET = "user@hpc"


class TestBaseBackendParseReadyMarker:
    """SandboxBackend.parse_ready_marker must validate required keys."""

    def test_valid_marker_returns_data(self) -> None:
        """Complete AF_READY marker returns parsed dict."""
        line = 'AF_READY {"host": "node01", "port": 8080, "secret": "abc123"}'
        result = SandboxBackend.parse_ready_marker(line)
        assert result is not None
        assert result["host"] == "node01"
        assert result["port"] == 8080
        assert result["secret"] == "abc123"

    def test_missing_host_raises_value_error(self) -> None:
        """AF_READY without host raises ValueError."""
        line = 'AF_READY {"port": 8080, "secret": "abc123"}'
        with pytest.raises(ValueError, match="missing required keys.*host"):
            SandboxBackend.parse_ready_marker(line)

    def test_missing_port_raises_value_error(self) -> None:
        """AF_READY without port raises ValueError."""
        line = 'AF_READY {"host": "node01", "secret": "abc123"}'
        with pytest.raises(ValueError, match="missing required keys.*port"):
            SandboxBackend.parse_ready_marker(line)

    def test_missing_secret_raises_value_error(self) -> None:
        """AF_READY without secret raises ValueError."""
        line = 'AF_READY {"host": "node01", "port": 8080}'
        with pytest.raises(ValueError, match="missing required keys.*secret"):
            SandboxBackend.parse_ready_marker(line)

    def test_missing_all_keys_raises_value_error(self) -> None:
        """AF_READY with empty JSON raises ValueError listing all keys."""
        line = 'AF_READY {}'
        with pytest.raises(ValueError, match="missing required keys"):
            SandboxBackend.parse_ready_marker(line)

    def test_non_marker_line_returns_none(self) -> None:
        """Non-marker line returns None."""
        result = SandboxBackend.parse_ready_marker("INFO: server started")
        assert result is None

    def test_extra_keys_are_preserved(self) -> None:
        """Extra keys in AF_READY (e.g. backend_id) are preserved."""
        line = 'AF_READY {"host": "n1", "port": 80, "secret": "s", "backend_id": "42"}'
        result = SandboxBackend.parse_ready_marker(line)
        assert result is not None
        assert result["backend_id"] == "42"


def _match(line: str) -> re.Match[str]:
    """Run MARKER_RE against line and return the match."""
    m = MARKER_RE.search(line)
    assert m is not None
    return m


class TestConnectorParseMarkerReadyValidation:
    """connector _parse_marker must validate AF_READY required keys."""

    def test_valid_ready_returns_ready_event(self) -> None:
        """Complete AF_READY returns event='ready' with all fields."""
        line = 'AF_READY {"host": "node01", "port": 8080, "secret": "abc"}'
        result = _parse_marker(_match(line), SSH_TARGET)
        assert result["event"] == "ready"
        assert result["host"] == "node01"
        assert result["port"] == 8080
        assert result["sandbox_secret"] == "abc"

    def test_missing_host_returns_log_event(self) -> None:
        """AF_READY without host returns log event, not ready."""
        line = 'AF_READY {"port": 8080, "secret": "abc"}'
        result = _parse_marker(_match(line), SSH_TARGET)
        assert result["event"] == "log"
        assert "missing keys" in result["line"]

    def test_missing_secret_returns_log_event(self) -> None:
        """AF_READY without secret returns log event, not ready."""
        line = 'AF_READY {"host": "node01", "port": 8080}'
        result = _parse_marker(_match(line), SSH_TARGET)
        assert result["event"] == "log"
        assert "missing keys" in result["line"]

    def test_missing_port_returns_log_event(self) -> None:
        """AF_READY without port returns log event, not ready."""
        line = 'AF_READY {"host": "node01", "secret": "abc"}'
        result = _parse_marker(_match(line), SSH_TARGET)
        assert result["event"] == "log"
        assert "missing keys" in result["line"]

    def test_empty_json_returns_log_event(self) -> None:
        """AF_READY with empty JSON returns log event."""
        line = 'AF_READY {}'
        result = _parse_marker(_match(line), SSH_TARGET)
        assert result["event"] == "log"
