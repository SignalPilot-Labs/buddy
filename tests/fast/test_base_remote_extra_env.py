"""Regression test: base_remote.py passes extra_env to connector.

Before the fix, extra_env was accepted but silently dropped from the
POST body. This verifies it's included in the request.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sandbox_client.slurm_backend import SlurmBackend


def _make_slurm_backend() -> SlurmBackend:
    """Create a SlurmBackend for testing."""
    return SlurmBackend(
        connector_url="http://connector:9400",
        connector_secret="test-secret",
        sandbox_id="test-sandbox-id",
        ssh_target="user@hpc.example.com",
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


class TestBaseRemoteExtraEnv:
    """extra_env is forwarded to the connector POST body."""

    @pytest.mark.asyncio
    async def test_extra_env_included_in_connector_request(self) -> None:
        backend = _make_slurm_backend()
        captured_body: dict[str, Any] = {}
        mock_client = _make_mock_http_client(captured_body)

        extra_env = {"MY_VAR": "my_value", "ANOTHER": "val"}

        with patch("sandbox_client.base_remote.httpx.AsyncClient", return_value=mock_client):
            async for _ in backend._start_remote_sandbox(
                run_key="run-123",
                start_cmd="./start.sh",
                sandbox_secret="per-run-secret",
                host_mounts=None,
                extra_env=extra_env,
            ):
                pass

        assert captured_body.get("extra_env") == extra_env

    @pytest.mark.asyncio
    async def test_extra_env_none_sends_empty_dict(self) -> None:
        """extra_env=None is normalized to {} in the request body."""
        backend = _make_slurm_backend()
        captured_body: dict[str, Any] = {}
        mock_client = _make_mock_http_client(captured_body)

        with patch("sandbox_client.base_remote.httpx.AsyncClient", return_value=mock_client):
            async for _ in backend._start_remote_sandbox(
                run_key="run-456",
                start_cmd="./start.sh",
                sandbox_secret="per-run-secret",
                host_mounts=None,
                extra_env=None,
            ):
                pass

        assert captured_body.get("extra_env") == {}
