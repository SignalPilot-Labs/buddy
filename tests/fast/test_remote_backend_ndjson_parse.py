"""Regression tests for NDJSON parsing in RemoteBackend._start_remote_sandbox().

Verifies that malformed JSON lines are skipped with a warning instead of
crashing the agent.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sandbox_client.backends.remote_backend import RemoteBackend
from sandbox_client.models import SandboxStartError


def _make_backend() -> RemoteBackend:
    """Create a RemoteBackend with dummy connection details."""
    return RemoteBackend(
        connector_url="http://localhost:9999",
        connector_secret="connector-secret",
        sandbox_id="sandbox-uuid-001",
        ssh_target="user@hpc",
        sandbox_type="slurm",
        heartbeat_timeout=60,
        work_dir="~/scratch",
    )


class _AsyncLineIterator:
    """Minimal async iterator over a list of raw strings (connector lines)."""

    def __init__(self, lines: list[str]) -> None:
        self._lines = iter(lines)

    def __aiter__(self) -> "_AsyncLineIterator":
        return self

    async def __anext__(self) -> str:
        try:
            return next(self._lines)
        except StopIteration:
            raise StopAsyncIteration


def _make_mock_http_client(lines: list[str]) -> MagicMock:
    """Build a mock httpx.AsyncClient whose stream yields the given lines."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.aiter_lines = MagicMock(return_value=_AsyncLineIterator(lines))
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    mock_client = MagicMock()
    mock_client.stream = MagicMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


class TestRemoteBackendNdjsonParse:
    """NDJSON parsing in RemoteBackend skips malformed lines gracefully."""

    @pytest.mark.asyncio
    async def test_malformed_json_line_skipped(self) -> None:
        """A malformed JSON line is skipped; valid events before/after are returned."""
        marker_secret = "deadbeef" * 8
        valid_queued = json.dumps({"event": "queued", "backend_id": "slurm-job-99"})
        malformed = "not-json-{{"
        valid_ready = json.dumps(
            {"event": "ready", "host": "compute-1", "port": 8080, "sandbox_secret": marker_secret}
        )
        lines = [valid_queued, malformed, valid_ready]

        backend = _make_backend()
        mock_client = _make_mock_http_client(lines)

        with patch("sandbox_client.backends.remote_backend.httpx.AsyncClient", return_value=mock_client):
            with patch("sandbox_client.backends.remote_backend.log_audit", new_callable=AsyncMock):
                handle, events = await backend.create(
                    run_key="run-ndjson-1",
                    host_mounts=None,
                    start_cmd="start.sh",
                )

        assert handle.sandbox_secret == marker_secret
        # The malformed line was skipped; only valid events collected
        event_types = [e.get("event") for e in events]
        assert "queued" in event_types
        assert "ready" in event_types
        # Malformed line produces no dict in events
        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_all_malformed_lines_results_in_no_ready(self) -> None:
        """When all lines are malformed JSON, create() raises SandboxStartError."""
        lines = ["not-json", "{bad", "also-not-json"]

        backend = _make_backend()
        mock_client = _make_mock_http_client(lines)

        with patch("sandbox_client.backends.remote_backend.httpx.AsyncClient", return_value=mock_client):
            with patch("sandbox_client.backends.remote_backend.log_audit", new_callable=AsyncMock):
                with pytest.raises(SandboxStartError, match="exited without AF_READY"):
                    await backend.create(
                        run_key="run-ndjson-2",
                        host_mounts=None,
                        start_cmd="start.sh",
                    )
