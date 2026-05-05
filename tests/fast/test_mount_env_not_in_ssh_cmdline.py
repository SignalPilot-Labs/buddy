"""Regression test: mount-related env vars must not appear in SSH cmdline args.

Verifies that run_ssh_command() passes AF_HOST_MOUNTS_JSON, AF_APPTAINER_BINDS,
AF_DOCKER_VOLUMES, AF_RUN_KEY, and AF_HEARTBEAT_TIMEOUT via stdin (not as
command-line arguments), preventing exposure via `ps aux` on shared HPC systems.
"""

from unittest.mock import MagicMock, patch

import pytest


SENSITIVE_ENV_KEYS = [
    "AF_HOST_MOUNTS_JSON",
    "AF_APPTAINER_BINDS",
    "AF_DOCKER_VOLUMES",
    "AF_RUN_KEY",
    "AF_HEARTBEAT_TIMEOUT",
]

SAMPLE_ENV = {
    "AF_RUN_KEY": "run-abc",
    "AF_HOST_MOUNTS_JSON": '[{"host_path": "/data", "container_path": "/mnt/data", "mode": "ro"}]',
    "AF_APPTAINER_BINDS": "-B /data:/mnt/data:ro",
    "AF_DOCKER_VOLUMES": "-v /data:/mnt/data:ro",
    "AF_HEARTBEAT_TIMEOUT": "120",
}


class TestMountEnvNotInSshCmdline:
    """Mount-related env vars must be passed via stdin, not SSH cmdline args."""

    @pytest.mark.asyncio
    async def test_env_not_in_subprocess_args(self) -> None:
        """Captured create_subprocess_exec args must NOT contain env var names or values."""
        captured_args: list[str] = []

        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_process.stdin.write = MagicMock()
        mock_process.stdin.close = MagicMock()

        async def fake_create_subprocess_exec(
            *args: str,
            **kwargs: object,
        ) -> MagicMock:
            captured_args.extend(args)
            return mock_process

        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=fake_create_subprocess_exec,
        ):
            from cli.connector.ssh import run_ssh_command

            await run_ssh_command(
                ssh_target="user@hpc",
                command="srun apptainer run sandbox.sif",
                env=SAMPLE_ENV,
            )

        cmdline_str = " ".join(captured_args)
        for key in SENSITIVE_ENV_KEYS:
            assert key not in cmdline_str, (
                f"{key} must not appear in SSH command-line args — "
                "it would be visible via `ps aux` on shared HPC nodes"
            )
        assert "export" not in cmdline_str, (
            "export statements must not appear in SSH command-line args"
        )
        assert "eval \"$(cat)\"" in cmdline_str or "eval \"$(cat)\"" in cmdline_str, (
            "Command must be wrapped with bash stdin eval pattern"
        )

    @pytest.mark.asyncio
    async def test_env_written_to_stdin(self) -> None:
        """Env vars must be written to the process stdin as export statements."""
        stdin_writes: list[bytes] = []

        mock_stdin = MagicMock()
        mock_stdin.write = MagicMock(side_effect=stdin_writes.append)
        mock_stdin.close = MagicMock()

        mock_process = MagicMock()
        mock_process.stdin = mock_stdin

        async def fake_create_subprocess_exec(
            *args: str,
            **kwargs: object,
        ) -> MagicMock:
            return mock_process

        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=fake_create_subprocess_exec,
        ):
            from cli.connector.ssh import run_ssh_command

            await run_ssh_command(
                ssh_target="user@hpc",
                command="srun apptainer run sandbox.sif",
                env=SAMPLE_ENV,
            )

        stdin_content = b"".join(stdin_writes).decode()
        for key in SENSITIVE_ENV_KEYS:
            assert key in stdin_content, (
                f"{key} must be written to SSH stdin so it reaches the remote process"
            )
        assert "export" in stdin_content, (
            "Stdin must contain export statements for env vars"
        )
        mock_stdin.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_subprocess_uses_stdin_pipe(self) -> None:
        """create_subprocess_exec must be called with stdin=PIPE."""
        import asyncio

        captured_kwargs: dict[str, object] = {}

        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_process.stdin.write = MagicMock()
        mock_process.stdin.close = MagicMock()

        async def fake_create_subprocess_exec(
            *args: str,
            **kwargs: object,
        ) -> MagicMock:
            captured_kwargs.update(kwargs)
            return mock_process

        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=fake_create_subprocess_exec,
        ):
            from cli.connector.ssh import run_ssh_command

            await run_ssh_command(
                ssh_target="user@hpc",
                command="srun apptainer run sandbox.sif",
                env=SAMPLE_ENV,
            )

        assert captured_kwargs.get("stdin") == asyncio.subprocess.PIPE, (
            "run_ssh_command must pass stdin=asyncio.subprocess.PIPE to create_subprocess_exec"
        )

    @pytest.mark.asyncio
    async def test_empty_env_still_uses_bash_wrapper(self) -> None:
        """Even with empty env dict, command must use bash stdin wrapper."""
        captured_args: list[str] = []

        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_process.stdin.write = MagicMock()
        mock_process.stdin.close = MagicMock()

        async def fake_create_subprocess_exec(
            *args: str,
            **kwargs: object,
        ) -> MagicMock:
            captured_args.extend(args)
            return mock_process

        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=fake_create_subprocess_exec,
        ):
            from cli.connector.ssh import run_ssh_command

            await run_ssh_command(
                ssh_target="user@hpc",
                command="scancel 12345",
                env={},
            )

        cmdline_str = " ".join(captured_args)
        assert "bash -c" in cmdline_str, (
            "Even with empty env, command must be wrapped with bash -c for consistency"
        )
        mock_process.stdin.close.assert_called_once()
