"""Regression test: SANDBOX_INTERNAL_SECRET must not appear in SSH env args.

Verifies that stream_start_events() does not include SANDBOX_INTERNAL_SECRET
in the env dict passed to run_ssh_command(). This prevents the secret from
being exposed via /proc/<pid>/cmdline or `ps aux` on shared HPC systems.
"""

from unittest.mock import MagicMock, patch

import pytest


class TestSandboxSecretNotInSshArgs:
    """SANDBOX_INTERNAL_SECRET must not be passed in SSH command-line env."""

    @pytest.mark.asyncio
    async def test_secret_not_in_env_dict(self) -> None:
        """stream_start_events must not put SANDBOX_INTERNAL_SECRET in env dict."""
        captured_env: dict[str, str] | None = None

        async def fake_run_ssh_command(
            ssh_target: str,
            cmd: str,
            env: dict[str, str],
        ) -> MagicMock:
            nonlocal captured_env
            captured_env = dict(env)
            proc = MagicMock()
            proc.stdout = None
            return proc

        with patch(
            "cli.connector.startup.run_ssh_command",
            side_effect=fake_run_ssh_command,
        ):
            from cli.connector.startup import stream_start_events

            await stream_start_events(
                ssh_target="user@hpc",
                start_cmd="start_sandbox.sh",
                run_key="run-001",
                sandbox_type="slurm",
                host_mounts=[],
                heartbeat_timeout=60,
            )

        assert captured_env is not None
        assert "SANDBOX_INTERNAL_SECRET" not in captured_env, (
            "SANDBOX_INTERNAL_SECRET must not appear in SSH env args — "
            "it would be visible via `ps aux` on shared HPC nodes"
        )

    @pytest.mark.asyncio
    async def test_af_run_key_still_present(self) -> None:
        """AF_RUN_KEY must still be passed in the env dict."""
        captured_env: dict[str, str] | None = None

        async def fake_run_ssh_command(
            ssh_target: str,
            cmd: str,
            env: dict[str, str],
        ) -> MagicMock:
            nonlocal captured_env
            captured_env = dict(env)
            proc = MagicMock()
            proc.stdout = None
            return proc

        with patch(
            "cli.connector.startup.run_ssh_command",
            side_effect=fake_run_ssh_command,
        ):
            from cli.connector.startup import stream_start_events

            await stream_start_events(
                ssh_target="user@hpc",
                start_cmd="start_sandbox.sh",
                run_key="run-002",
                sandbox_type="slurm",
                host_mounts=[],
                heartbeat_timeout=60,
            )

        assert captured_env is not None
        assert captured_env["AF_RUN_KEY"] == "run-002"
