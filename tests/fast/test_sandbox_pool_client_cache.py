"""Regression tests for SandboxPool client caching.

get_client() was creating a new SandboxClient on every call, leaking the
underlying httpx.AsyncClient. Now it caches by run_key and destroy() closes
the cached client before removing the container.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sandbox_client.pool import SandboxPool


def _make_pool() -> SandboxPool:
    """Instantiate SandboxPool with a mocked Docker client."""
    with patch("sandbox_client.pool.docker.from_env", return_value=MagicMock()):
        with patch("sandbox_client.pool.sandbox_config", return_value={"vm_timeout_sec": 30}):
            return SandboxPool()


class TestSandboxPoolClientCache:
    """Verify get_client() caches and destroy() closes clients."""

    def test_get_client_returns_none_for_unknown_key(self) -> None:
        """get_client() must return None when run_key has no container."""
        pool = _make_pool()
        result = pool.get_client("no-such-key")
        assert result is None

    def test_get_client_returns_same_instance_on_second_call(self) -> None:
        """get_client() must return the cached SandboxClient, not a new one."""
        pool = _make_pool()
        pool._containers["key1"] = "fake-container-id"

        secret = "test-secret"
        with patch.dict(os.environ, {"SANDBOX_INTERNAL_SECRET": secret}):
            client_a = pool.get_client("key1")
            client_b = pool.get_client("key1")

        assert client_a is client_b

    def test_get_client_caches_client_in_dict(self) -> None:
        """After get_client(), _clients must contain the run_key."""
        pool = _make_pool()
        pool._containers["key1"] = "fake-container-id"

        with patch.dict(os.environ, {"SANDBOX_INTERNAL_SECRET": "test-secret"}):
            pool.get_client("key1")

        assert "key1" in pool._clients

    @pytest.mark.asyncio
    async def test_destroy_closes_cached_client(self) -> None:
        """destroy() must call client.close() on the cached client."""
        pool = _make_pool()
        pool._containers["key1"] = "fake-container-id"

        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        pool._clients["key1"] = mock_client

        with patch.object(pool, "_remove_container", new=AsyncMock()):
            with patch.object(pool, "_remove_volume", new=AsyncMock()):
                await pool.destroy("key1")

        mock_client.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_destroy_removes_client_from_cache(self) -> None:
        """destroy() must remove the run_key from _clients."""
        pool = _make_pool()
        pool._containers["key1"] = "fake-container-id"

        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        pool._clients["key1"] = mock_client

        with patch.object(pool, "_remove_container", new=AsyncMock()):
            with patch.object(pool, "_remove_volume", new=AsyncMock()):
                await pool.destroy("key1")

        assert "key1" not in pool._clients

    @pytest.mark.asyncio
    async def test_destroy_unknown_key_no_error(self) -> None:
        """destroy() on an unknown key must silently return."""
        pool = _make_pool()
        # Should not raise
        await pool.destroy("no-such-key")

    @pytest.mark.asyncio
    async def test_destroy_all_closes_all_clients(self) -> None:
        """destroy_all() must close every cached client."""
        pool = _make_pool()
        pool._containers["key1"] = "id1"
        pool._containers["key2"] = "id2"

        mock_client_1 = MagicMock()
        mock_client_1.close = AsyncMock()
        mock_client_2 = MagicMock()
        mock_client_2.close = AsyncMock()
        pool._clients["key1"] = mock_client_1
        pool._clients["key2"] = mock_client_2

        with patch.object(pool, "_remove_container", new=AsyncMock()):
            with patch.object(pool, "_remove_volume", new=AsyncMock()):
                await pool.destroy_all()

        mock_client_1.close.assert_awaited_once()
        mock_client_2.close.assert_awaited_once()
