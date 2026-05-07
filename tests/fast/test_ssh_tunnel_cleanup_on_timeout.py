"""Regression test: SSH tunnel process is killed when _wait_for_port_ready() times out.

Bug: open_ssh_tunnel() called asyncio.create_subprocess_exec() and then
_wait_for_port_ready().  If _wait_for_port_ready() raised, the subprocess was
left running — an orphaned SSH process.

Fix: Wrapped the _wait_for_port_ready() call in try/except; on exception,
kill_process_group(process) is called before re-raising.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cli.connector.ssh import open_ssh_tunnel


def _fake_process() -> MagicMock:
    """Return a minimal fake asyncio.subprocess.Process."""
    proc = MagicMock(spec=asyncio.subprocess.Process)
    proc.pid = 12345
    proc.returncode = None
    return proc


class TestSshTunnelCleanupOnTimeout:
    """open_ssh_tunnel must kill the subprocess when _wait_for_port_ready raises."""

    @pytest.mark.asyncio
    async def test_process_killed_when_wait_for_port_raises(self) -> None:
        """kill_process_group is called with the process when _wait_for_port_ready raises."""
        fake_proc = _fake_process()
        mock_kill = AsyncMock()

        with (
            patch(
                "cli.connector.ssh.asyncio.create_subprocess_exec",
                new=AsyncMock(return_value=fake_proc),
            ),
            patch(
                "cli.connector.ssh._wait_for_port_ready",
                new=AsyncMock(side_effect=RuntimeError("port not ready after 30s")),
            ),
            patch("cli.connector.ssh.kill_process_group", new=mock_kill),
        ):
            with pytest.raises(RuntimeError):
                await open_ssh_tunnel(
                    ssh_target="user@host",
                    remote_host="127.0.0.1",
                    remote_port=8080,
                    local_port=19000,
                )

        mock_kill.assert_awaited_once_with(fake_proc)

    @pytest.mark.asyncio
    async def test_exception_reraises_after_cleanup(self) -> None:
        """The original RuntimeError propagates unchanged after kill_process_group."""
        fake_proc = _fake_process()
        original_error = RuntimeError("port not ready after 30s")

        with (
            patch(
                "cli.connector.ssh.asyncio.create_subprocess_exec",
                new=AsyncMock(return_value=fake_proc),
            ),
            patch(
                "cli.connector.ssh._wait_for_port_ready",
                new=AsyncMock(side_effect=original_error),
            ),
            patch("cli.connector.ssh.kill_process_group", new=AsyncMock()),
        ):
            with pytest.raises(RuntimeError) as exc_info:
                await open_ssh_tunnel(
                    ssh_target="user@host",
                    remote_host="127.0.0.1",
                    remote_port=8080,
                    local_port=19000,
                )

        assert exc_info.value is original_error

    @pytest.mark.asyncio
    async def test_process_returned_on_success(self) -> None:
        """kill_process_group is NOT called and the process is returned on success."""
        fake_proc = _fake_process()
        mock_kill = AsyncMock()

        with (
            patch(
                "cli.connector.ssh.asyncio.create_subprocess_exec",
                new=AsyncMock(return_value=fake_proc),
            ),
            patch(
                "cli.connector.ssh._wait_for_port_ready",
                new=AsyncMock(return_value=None),
            ),
            patch("cli.connector.ssh.kill_process_group", new=mock_kill),
        ):
            result = await open_ssh_tunnel(
                ssh_target="user@host",
                remote_host="127.0.0.1",
                remote_port=8080,
                local_port=19000,
            )

        mock_kill.assert_not_awaited()
        assert result is fake_proc
