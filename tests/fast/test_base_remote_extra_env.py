"""Regression test: remote backend does NOT send extra_env to connector.

After the /env refactor, secrets are injected via POST /env after sandbox
creation — extra_env is no longer part of the connector request body.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sandbox_client.backends.remote_backend import RemoteBackend


def _make_backend() -> RemoteBackend:
    """Create a RemoteBackend for testing."""
    return RemoteBackend(
        connector_url="http://connector:9400",
        connector_secret="test-secret",
        sandbox_id="test-sandbox-id",
        ssh_target="user@hpc.example.com",
        sandbox_type="slurm",
        heartbeat_timeout=1800,
    )


class _AsyncIterator:
    """Minimal async iterator over a list of strings."""

    def __init__(self, items: list[str]) -> None:
        self._items = iter(items)

    def __aiter__(self) -> "_AsyncIterator":
        return self

    async def __anext__(self) -> str:
        try:
            return next(self._items)
        except StopIteration:
            raise StopAsyncIteration


def _make_mock_http_client(body_capture: dict[str, Any]) -> MagicMock:
    """Build a mock httpx.AsyncClient that captures the POST body."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.aiter_lines = MagicMock(return_value=_AsyncIterator([]))
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    def capture_stream(*args: Any, **kwargs: Any) -> MagicMock:
        body_capture.update(kwargs.get("json", {}))
        return mock_response

    mock_client = MagicMock()
    mock_client.stream = MagicMock(side_effect=capture_stream)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


class TestRemoteBackendNoExtraEnv:
    """extra_env is NOT forwarded to the connector POST body."""

    @pytest.mark.asyncio
    async def test_extra_env_not_in_connector_request(self) -> None:
        """extra_env is no longer sent in the connector request body."""
        backend = _make_backend()
        captured_body: dict[str, Any] = {}
        mock_client = _make_mock_http_client(captured_body)

        with patch("sandbox_client.backends.remote_backend.httpx.AsyncClient", return_value=mock_client):
            async for _ in backend._start_remote_sandbox(
                run_key="run-123",
                start_cmd="./start.sh",
                sandbox_secret="per-run-secret",
                host_mounts=None,
            ):
                pass

        assert "extra_env" not in captured_body
