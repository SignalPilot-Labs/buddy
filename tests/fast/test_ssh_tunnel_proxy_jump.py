"""Regression test: SSH tunnel uses ProxyJump for Slurm sandboxes.

Slurm jobs run on compute nodes separate from the login node. The SSH
tunnel must ProxyJump through the login node to reach the compute node,
allowing the sandbox to bind securely to 127.0.0.1.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSshTunnelProxyJump:
    """SSH tunnel uses ProxyJump when connecting to Slurm compute nodes."""

    @pytest.mark.asyncio
    async def test_slurm_uses_proxy_jump(self) -> None:
        """Slurm sandboxes: -J flag present, -L target is 127.0.0.1."""
        captured_cmd: list[str] | None = None

        async def fake_subprocess_exec(*args: str, **kwargs: object) -> MagicMock:
            nonlocal captured_cmd
            captured_cmd = list(args)
            proc = MagicMock()
            proc.pid = 12345
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=fake_subprocess_exec):
            with patch("cli.connector.ssh._wait_for_port_ready", new_callable=AsyncMock):
                from cli.connector.ssh import open_ssh_tunnel
                await open_ssh_tunnel(
                    ssh_target="user@login.hpc.edu",
                    remote_host="compute-node-01",
                    remote_port=8080,
                    local_port=50123,
                    sandbox_type="slurm",
                )

        assert captured_cmd is not None
        assert "-J" in captured_cmd, "Slurm must use ProxyJump"
        j_idx = captured_cmd.index("-J")
        assert captured_cmd[j_idx + 1] == "user@login.hpc.edu"

        # -L should forward to 127.0.0.1 on the compute node
        l_idx = captured_cmd.index("-L")
        l_spec = captured_cmd[l_idx + 1]
        assert l_spec == "127.0.0.1:50123:127.0.0.1:8080", (
            f"Expected -L 127.0.0.1:50123:127.0.0.1:8080, got {l_spec}"
        )

        # Final arg should be the compute node
        assert captured_cmd[-1] == "compute-node-01"

    @pytest.mark.asyncio
    async def test_docker_uses_direct_tunnel(self) -> None:
        """Docker sandboxes: no -J flag, standard -L to remote_host."""
        captured_cmd: list[str] | None = None

        async def fake_subprocess_exec(*args: str, **kwargs: object) -> MagicMock:
            nonlocal captured_cmd
            captured_cmd = list(args)
            proc = MagicMock()
            proc.pid = 12346
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=fake_subprocess_exec):
            with patch("cli.connector.ssh._wait_for_port_ready", new_callable=AsyncMock):
                from cli.connector.ssh import open_ssh_tunnel
                await open_ssh_tunnel(
                    ssh_target="user@gpu-server",
                    remote_host="gpu-server",
                    remote_port=8080,
                    local_port=50124,
                    sandbox_type="docker",
                )

        assert captured_cmd is not None
        assert "-J" not in captured_cmd, "Docker should not use ProxyJump"

        # -L should forward to remote_host
        l_idx = captured_cmd.index("-L")
        l_spec = captured_cmd[l_idx + 1]
        assert l_spec == "127.0.0.1:50124:gpu-server:8080"

        # Final arg should be ssh_target
        assert captured_cmd[-1] == "user@gpu-server"
