"""Tests for ConnectorServer._sweep_orphan_dirs — orphaned overlay cleanup."""

from unittest.mock import AsyncMock, patch

import pytest

from cli.connector.server import ConnectorServer

TEST_SECRET = "test-secret"


@pytest.fixture
def server() -> ConnectorServer:
    """Create a ConnectorServer with mocked internals."""
    with patch("cli.connector.server.web.Application"):
        srv = ConnectorServer.__new__(ConnectorServer)
        srv._secret = TEST_SECRET
        srv._port = 0
        srv._states = {}
        srv._heartbeat_tasks = {}
        srv._drain_tasks = {}
        srv._started_runs = {}
        srv._app = None  # type: ignore[assignment]
    return srv


class TestSweepOrphanDirs:
    """Verify _sweep_orphan_dirs only cleans dirs for crashed slurm runs we own."""

    @pytest.mark.asyncio
    async def test_sweeps_crashed_slurm_run(self, server: ConnectorServer) -> None:
        """Orphaned slurm run_key not in _states should get rm -rf."""
        server._started_runs["abc123"] = ("user@hpc", "slurm", "~/scratch")

        with patch("cli.connector.server.run_ssh_command") as mock_ssh:
            proc = AsyncMock()
            proc.communicate = AsyncMock(return_value=(b"", b""))
            mock_ssh.return_value = proc

            await server._sweep_orphan_dirs()

            mock_ssh.assert_called_once()
            cmd = mock_ssh.call_args[0][1]
            assert "rm -rf" in cmd
            assert "abc123" in cmd

    @pytest.mark.asyncio
    async def test_skips_still_tracked_run(self, server: ConnectorServer) -> None:
        """Run still in _states should not be swept."""
        server._started_runs["live1"] = ("user@hpc", "slurm", "~/scratch")
        server._states["live1"] = object()  # type: ignore[assignment]

        with patch("cli.connector.server.run_ssh_command") as mock_ssh:
            await server._sweep_orphan_dirs()
            mock_ssh.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_docker_runs(self, server: ConnectorServer) -> None:
        """Docker runs have no overlay dir — should not be swept."""
        server._started_runs["dock1"] = ("user@remote", "docker", "")

        with patch("cli.connector.server.run_ssh_command") as mock_ssh:
            await server._sweep_orphan_dirs()
            mock_ssh.assert_not_called()

    @pytest.mark.asyncio
    async def test_sweeps_multiple_orphans(self, server: ConnectorServer) -> None:
        """Multiple crashed runs should each get cleaned."""
        server._started_runs["run1"] = ("user@hpc", "slurm", "~/scratch")
        server._started_runs["run2"] = ("user@hpc", "slurm", "~/scratch")
        server._started_runs["run3"] = ("user@hpc", "slurm", "~/scratch")
        server._states["run2"] = object()  # type: ignore[assignment]  # still alive

        with patch("cli.connector.server.run_ssh_command") as mock_ssh:
            proc = AsyncMock()
            proc.communicate = AsyncMock(return_value=(b"", b""))
            mock_ssh.return_value = proc

            await server._sweep_orphan_dirs()

            assert mock_ssh.call_count == 2
            cleaned_keys = [call[0][1] for call in mock_ssh.call_args_list]
            assert any("run1" in cmd for cmd in cleaned_keys)
            assert any("run3" in cmd for cmd in cleaned_keys)
            assert all("run2" not in cmd for cmd in cleaned_keys)

    @pytest.mark.asyncio
    async def test_sweep_failure_does_not_raise(self, server: ConnectorServer) -> None:
        """SSH failure during sweep should be logged, not raised."""
        server._started_runs["fail1"] = ("user@hpc", "slurm", "~/scratch")

        with patch("cli.connector.server.run_ssh_command", side_effect=OSError("ssh failed")):
            await server._sweep_orphan_dirs()  # should not raise
