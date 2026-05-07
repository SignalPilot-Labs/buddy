"""Tests for SandboxManager remote backend wiring.

Covers _resolve_backend(), remote SandboxClient construction, and destroy_all()
with mixed local+remote handles.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sandbox_client.models import SandboxInstance
from sandbox_client.manager import SandboxManager


def _make_pool() -> SandboxManager:
    """Create a SandboxManager with mocked DockerLocalBackend and config."""
    with (
        patch("sandbox_client.manager.DockerLocalBackend", return_value=MagicMock()),
        patch("sandbox_client.manager.sandbox_config", return_value={"vm_timeout_sec": 30}),
        patch("sandbox_client.manager.os.environ", {"SANDBOX_INTERNAL_SECRET": "test", "CONNECTOR_URL": "http://localhost:9400", "CONNECTOR_SECRET": "test"}),
    ):
        return SandboxManager()


def _remote_handle(run_key: str, sandbox_id: str) -> SandboxInstance:
    """Build a minimal remote SandboxInstance for testing."""
    return SandboxInstance(
        run_key=run_key,
        url="http://connector:9400/sandboxes/" + run_key,
        sandbox_secret="per-run-secret",
        sandbox_id=sandbox_id,
    )


def _local_handle(run_key: str) -> SandboxInstance:
    """Build a minimal local SandboxInstance for testing."""
    return SandboxInstance(
        run_key=run_key,
        url="http://sandbox:8080",
        sandbox_secret="local-secret",
        sandbox_id=None,
    )


class TestResolveBackendLocal:
    """_resolve_backend returns local Docker for None sandbox_id."""

    @pytest.mark.asyncio
    async def test_resolve_none_returns_docker_local(self) -> None:
        pool = _make_pool()
        result = await pool._resolve_backend(None)
        assert result is pool._docker_local


class TestResolveBackendRemote:
    """_resolve_backend reads DB config and instantiates correct backend."""

    @pytest.mark.asyncio
    async def test_resolve_slurm_backend(self) -> None:
        pool = _make_pool()
        pool._connector_url = "http://connector:9400"
        pool._connector_secret = "connector-secret"

        config = {
            "type": "slurm",
            "ssh_target": "user@hpc.example.com",
            "heartbeat_timeout": 3600,
            "work_dir": "~/scratch",
        }

        with patch(
            "sandbox_client.manager.get_setting_value",
            new=AsyncMock(return_value=json.dumps(config)),
        ):
            with patch("sandbox_client.manager.RemoteBackend") as MockRemote:
                backend_instance = MagicMock()
                MockRemote.return_value = backend_instance
                result = await pool._resolve_backend("sandbox-uuid-1")

        MockRemote.assert_called_once_with(
            connector_url="http://connector:9400",
            connector_secret="connector-secret",
            sandbox_id="sandbox-uuid-1",
            ssh_target="user@hpc.example.com",
            sandbox_type="slurm",
            heartbeat_timeout=3600,
            work_dir="~/scratch",
        )
        assert result is backend_instance

    @pytest.mark.asyncio
    async def test_resolve_docker_remote_backend(self) -> None:
        pool = _make_pool()
        pool._connector_url = "http://connector:9400"
        pool._connector_secret = "connector-secret"

        config = {
            "type": "docker",
            "ssh_target": "user@remote-server.example.com",
            "heartbeat_timeout": 1800,
            "work_dir": "",
        }

        with patch(
            "sandbox_client.manager.get_setting_value",
            new=AsyncMock(return_value=json.dumps(config)),
        ):
            with patch("sandbox_client.manager.RemoteBackend") as MockRemote:
                backend_instance = MagicMock()
                MockRemote.return_value = backend_instance
                result = await pool._resolve_backend("sandbox-uuid-2")

        MockRemote.assert_called_once_with(
            connector_url="http://connector:9400",
            connector_secret="connector-secret",
            sandbox_id="sandbox-uuid-2",
            ssh_target="user@remote-server.example.com",
            sandbox_type="docker",
            heartbeat_timeout=1800,
            work_dir="",
        )
        assert result is backend_instance

    @pytest.mark.asyncio
    async def test_resolve_missing_connector_url_raises(self) -> None:
        pool = _make_pool()
        pool._connector_url = None
        pool._connector_secret = "connector-secret"

        with pytest.raises(RuntimeError, match="CONNECTOR_URL is not set"):
            await pool._resolve_backend("sandbox-uuid-3")

    @pytest.mark.asyncio
    async def test_resolve_missing_connector_secret_raises(self) -> None:
        pool = _make_pool()
        pool._connector_url = "http://connector:9400"
        pool._connector_secret = None

        with pytest.raises(RuntimeError, match="CONNECTOR_SECRET is not set"):
            await pool._resolve_backend("sandbox-uuid-4")

    @pytest.mark.asyncio
    async def test_resolve_missing_config_raises(self) -> None:
        pool = _make_pool()
        pool._connector_url = "http://connector:9400"
        pool._connector_secret = "secret"

        with patch(
            "sandbox_client.manager.get_setting_value",
            new=AsyncMock(return_value=None),
        ):
            with pytest.raises(ValueError, match="No remote sandbox config found"):
                await pool._resolve_backend("unknown-sandbox-uuid")

    @pytest.mark.asyncio
    async def test_resolve_missing_heartbeat_timeout_raises(self) -> None:
        """If heartbeat_timeout is missing from config, KeyError is raised (fail-fast)."""
        pool = _make_pool()
        pool._connector_url = "http://connector:9400"
        pool._connector_secret = "secret"

        config = {"type": "slurm", "ssh_target": "user@hpc"}

        with patch(
            "sandbox_client.manager.get_setting_value",
            new=AsyncMock(return_value=json.dumps(config)),
        ):
            with pytest.raises(KeyError, match="heartbeat_timeout"):
                await pool._resolve_backend("sandbox-uuid-5")


class TestDestroyAllRemote:
    """destroy_all() destroys remote handles before delegating to local."""

    @pytest.mark.asyncio
    async def test_destroy_all_destroys_remote_handles(self) -> None:
        pool = _make_pool()
        pool._connector_url = "http://connector:9400"
        pool._connector_secret = "secret"

        handle = _remote_handle("run-1", "sandbox-uuid-A")
        pool._handles["run-1"] = handle

        mock_backend = MagicMock()
        mock_backend.destroy = AsyncMock()
        pool._docker_local.destroy_all = AsyncMock()

        with patch.object(pool, "_resolve_backend", new=AsyncMock(return_value=mock_backend)):
            await pool.destroy_all()

        mock_backend.destroy.assert_awaited_once_with(handle)
        pool._docker_local.destroy_all.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_destroy_all_skips_local_handles_in_remote_loop(self) -> None:
        """Local handles (sandbox_id=None) are not destroyed in the remote loop."""
        pool = _make_pool()

        local_handle = _local_handle("run-local")
        pool._handles["run-local"] = local_handle

        pool._docker_local.destroy_all = AsyncMock()

        mock_backend = MagicMock()
        mock_backend.destroy = AsyncMock()

        with patch.object(pool, "_resolve_backend", new=AsyncMock(return_value=mock_backend)):
            await pool.destroy_all()

        # destroy() not called on mock_backend because local handle has sandbox_id=None
        mock_backend.destroy.assert_not_awaited()
        pool._docker_local.destroy_all.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_destroy_all_continues_on_remote_error(self) -> None:
        """destroy_all() logs and continues if one remote destroy fails."""
        pool = _make_pool()
        pool._connector_url = "http://connector:9400"
        pool._connector_secret = "secret"

        handle1 = _remote_handle("run-1", "sandbox-A")
        handle2 = _remote_handle("run-2", "sandbox-B")
        pool._handles["run-1"] = handle1
        pool._handles["run-2"] = handle2

        failing_backend = MagicMock()
        failing_backend.destroy = AsyncMock(side_effect=RuntimeError("connector timeout"))
        pool._docker_local.destroy_all = AsyncMock()

        with patch.object(pool, "_resolve_backend", new=AsyncMock(return_value=failing_backend)):
            # Should not raise — errors are logged and swallowed in destroy_all
            await pool.destroy_all()

        pool._docker_local.destroy_all.assert_awaited_once()


class TestRemoteSandboxClientCreation:
    """pool.create() returns a SandboxClient pointed at the connector proxy URL."""

    @pytest.mark.asyncio
    async def test_create_remote_returns_client_with_proxy_url(self) -> None:
        pool = _make_pool()
        pool._connector_url = "http://connector:9400"
        pool._connector_secret = "secret"

        remote_handle = _remote_handle("run-x", "sandbox-Z")
        mock_backend = MagicMock()
        mock_backend.create = AsyncMock(return_value=(remote_handle, []))

        with patch.object(pool, "_resolve_backend", new=AsyncMock(return_value=mock_backend)):
            with patch("sandbox_client.manager.SandboxClient") as MockClient:
                mock_client = MagicMock()
                MockClient.return_value = mock_client
                result_client, result_events = await pool.create(
                    run_key="run-x",
                    sandbox_id="sandbox-Z",
                    host_mounts=None,
                    start_cmd="./start.sh",
                    cancel_event=asyncio.Event(),
                )

        MockClient.assert_called_once_with(
            base_url=remote_handle.url,
            health_timeout=30,
            timeout=30,
            sandbox_secret=remote_handle.sandbox_secret,
            extra_headers=None,
        )
        assert result_client is mock_client
        assert result_events == []
