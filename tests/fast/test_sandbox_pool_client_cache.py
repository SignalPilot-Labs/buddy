"""Regression tests for DockerLocalBackend client caching.

get_client() was creating a new SandboxClient on every call, leaking the
underlying httpx.AsyncClient. Now it caches by run_key and destroy() closes
the cached client before removing the container.
"""

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
                return DockerLocalBackend()


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

    def test_get_client_returns_same_instance_on_second_call(self) -> None:
        """get_client() must return the cached SandboxClient, not a new one."""
        backend = _make_backend()
        backend._containers["key1"] = "fake-container-id"

        secret = "test-secret"
        with patch.dict(os.environ, {"SANDBOX_INTERNAL_SECRET": secret}):
            client_a = backend.get_client("key1")
            client_b = backend.get_client("key1")

        assert client_a is client_b

    def test_get_client_caches_client_in_dict(self) -> None:
        """After get_client(), _clients must contain the run_key."""
        backend = _make_backend()
        backend._containers["key1"] = "fake-container-id"

        with patch.dict(os.environ, {"SANDBOX_INTERNAL_SECRET": "test-secret"}):
            backend.get_client("key1")

        assert "key1" in backend._clients

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
