"""Regression tests for DockerLocalBackend client caching.

get_client() returns cached clients populated by create(). destroy()
closes the cached client before removing the container.
"""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sandbox_client.backends.local_backend import DockerLocalBackend
from sandbox_client.models import SandboxInstance


def _make_backend() -> DockerLocalBackend:
    """Instantiate DockerLocalBackend with a mocked Docker client."""
    with patch("sandbox_client.backends.local_backend.docker.from_env", return_value=MagicMock()):
        with patch("sandbox_client.backends.local_backend.sandbox_config", return_value={"vm_timeout_sec": 30, "health_timeout_sec": 5}):
            with patch.dict(os.environ, {"AF_IMAGE_TAG": "test"}):
                return DockerLocalBackend(asyncio.Event())


def _make_handle(run_key: str) -> SandboxInstance:
    """Build a minimal SandboxInstance for testing."""
    return SandboxInstance(
        run_key=run_key,
        url="",
        sandbox_secret="",
        sandbox_id=None,
    )


class TestSandboxPoolClientCache:
    """Verify get_client() caches and destroy() closes clients."""

    def test_get_client_returns_none_for_unknown_key(self) -> None:
        """get_client() must return None when run_key has no container."""
        backend = _make_backend()
        result = backend.get_client("no-such-key")
        assert result is None

    def test_get_client_returns_cached_client(self) -> None:
        """get_client() must return the client populated by create()."""
        backend = _make_backend()
        mock_client = MagicMock()
        backend._clients["key1"] = mock_client

        assert backend.get_client("key1") is mock_client

    def test_get_client_returns_none_when_no_client_cached(self) -> None:
        """get_client() returns None even if container exists but client wasn't created."""
        backend = _make_backend()
        backend._containers["key1"] = "fake-container-id"

        assert backend.get_client("key1") is None

    @pytest.mark.asyncio
    async def test_destroy_closes_cached_client(self) -> None:
        """destroy() must call client.close() on the cached client."""
        backend = _make_backend()
        backend._containers["key1"] = "fake-container-id"

        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        backend._clients["key1"] = mock_client

        handle = _make_handle("key1")
        with patch.object(backend, "_remove_container", new=AsyncMock()):
            with patch.object(backend, "_remove_volume", new=AsyncMock()):
                await backend.destroy(handle)

        mock_client.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_destroy_removes_client_from_cache(self) -> None:
        """destroy() must remove the run_key from _clients."""
        backend = _make_backend()
        backend._containers["key1"] = "fake-container-id"

        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        backend._clients["key1"] = mock_client

        handle = _make_handle("key1")
        with patch.object(backend, "_remove_container", new=AsyncMock()):
            with patch.object(backend, "_remove_volume", new=AsyncMock()):
                await backend.destroy(handle)

        assert "key1" not in backend._clients

    @pytest.mark.asyncio
    async def test_destroy_unknown_key_no_error(self) -> None:
        """destroy() on an unknown key must silently return."""
        backend = _make_backend()
        handle = _make_handle("no-such-key")
        await backend.destroy(handle)

    @pytest.mark.asyncio
    async def test_destroy_all_closes_all_clients(self) -> None:
        """destroy_all() must close every cached client."""
        backend = _make_backend()
        backend._containers["key1"] = "id1"
        backend._containers["key2"] = "id2"

        mock_client_1 = MagicMock()
        mock_client_1.close = AsyncMock()
        mock_client_2 = MagicMock()
        mock_client_2.close = AsyncMock()
        backend._clients["key1"] = mock_client_1
        backend._clients["key2"] = mock_client_2

        with patch.object(backend, "_remove_container", new=AsyncMock()):
            with patch.object(backend, "_remove_volume", new=AsyncMock()):
                await backend.destroy_all()

        mock_client_1.close.assert_awaited_once()
        mock_client_2.close.assert_awaited_once()
