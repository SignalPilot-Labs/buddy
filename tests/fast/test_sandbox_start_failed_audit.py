"""Tests for sandbox_start_failed audit event emission.

Verifies that when pool.create() raises SandboxStartError, execute_run() emits
a sandbox_start_failed audit event (not sandbox_crash) with scrubbed error and
startup_logs fields, and that the exception is re-raised to the caller.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("AGENT_INTERNAL_SECRET", "test-secret")
os.environ.setdefault("SANDBOX_INTERNAL_SECRET", "test-sandbox-secret")

with patch("docker.from_env", return_value=MagicMock()):
    from server import AgentServer

from sandbox_client.models import SandboxStartError
from utils.constants import ENV_KEY_GIT_TOKEN
from utils.models import ActiveRun
from utils.models_http import StartRequest


def _make_server() -> AgentServer:
    """Build an AgentServer without calling __init__ (avoids DB + pool setup)."""
    srv = AgentServer.__new__(AgentServer)
    srv._pool = MagicMock()
    return srv


def _make_active_run(run_id: str) -> ActiveRun:
    return ActiveRun(run_id=run_id, status="running")


def _make_body(git_token: str) -> StartRequest:
    return StartRequest(
        max_budget_usd=0,
        github_repo="owner/repo",
        prompt="fix it",
        duration_minutes=30,
        env={ENV_KEY_GIT_TOKEN: git_token},
    )


def _make_start_error(message: str, log_lines: list[str]) -> SandboxStartError:
    events: list[dict] = [{"event": "log", "line": line} for line in log_lines]
    return SandboxStartError(message, events)


class TestSandboxStartFailedAudit:
    """execute_run() emits sandbox_start_failed when pool.create() raises SandboxStartError."""

    @pytest.mark.asyncio
    async def test_emits_sandbox_start_failed_not_sandbox_crash(self) -> None:
        """SandboxStartError triggers sandbox_start_failed, not sandbox_crash."""
        srv = _make_server()
        srv._pool.create = AsyncMock(
            side_effect=_make_start_error("Sandbox start failed: timeout", ["startup log"])
        )
        srv._pool.destroy = AsyncMock()
        srv._pool.get_logs = AsyncMock(return_value=[])

        log_audit_mock = AsyncMock()

        with (
            patch("server.log_audit", log_audit_mock),
            patch("server.db.update_run_status", AsyncMock()),
        ):
            active = _make_active_run("run-start-1")
            body = _make_body("ghp_token")
            with pytest.raises(SandboxStartError):
                await srv.execute_run(active, body)

        event_types = [c.args[1] for c in log_audit_mock.call_args_list]
        assert "sandbox_start_failed" in event_types
        assert "sandbox_crash" not in event_types

    @pytest.mark.asyncio
    async def test_audit_payload_contains_error_and_startup_logs(self) -> None:
        """sandbox_start_failed payload has error and startup_logs fields."""
        srv = _make_server()
        srv._pool.create = AsyncMock(
            side_effect=_make_start_error(
                "Sandbox start failed: script exited 1",
                ["Installing deps...", "Error: package not found"],
            )
        )
        srv._pool.destroy = AsyncMock()
        srv._pool.get_logs = AsyncMock(return_value=[])

        log_audit_mock = AsyncMock()

        with (
            patch("server.log_audit", log_audit_mock),
            patch("server.db.update_run_status", AsyncMock()),
        ):
            active = _make_active_run("run-start-2")
            body = _make_body("ghp_token")
            with pytest.raises(SandboxStartError):
                await srv.execute_run(active, body)

        start_fail_call = next(
            c for c in log_audit_mock.call_args_list if c.args[1] == "sandbox_start_failed"
        )
        details: dict = start_fail_call.args[2]
        assert "error" in details
        assert "startup_logs" in details
        assert "script exited 1" in details["error"]
        assert "Installing deps..." in details["startup_logs"]
        assert "Error: package not found" in details["startup_logs"]

    @pytest.mark.asyncio
    async def test_secrets_scrubbed_from_error_and_startup_logs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Secrets are scrubbed from both error and startup_logs fields."""
        sentinel = "GHP_SENTINEL_START_FAIL"
        monkeypatch.setenv(ENV_KEY_GIT_TOKEN, sentinel)

        srv = _make_server()
        srv._pool.create = AsyncMock(
            side_effect=_make_start_error(
                f"Sandbox start failed: token={sentinel} rejected",
                [f"Cloning https://x-access-token:{sentinel}@github.com/o/r.git"],
            )
        )
        srv._pool.destroy = AsyncMock()
        srv._pool.get_logs = AsyncMock(return_value=[])

        log_audit_mock = AsyncMock()

        with (
            patch("server.log_audit", log_audit_mock),
            patch("server.db.update_run_status", AsyncMock()),
        ):
            active = _make_active_run("run-start-3")
            body = _make_body(sentinel)
            with pytest.raises(SandboxStartError):
                await srv.execute_run(active, body)

        start_fail_call = next(
            c for c in log_audit_mock.call_args_list if c.args[1] == "sandbox_start_failed"
        )
        details: dict = start_fail_call.args[2]
        assert sentinel not in details["error"]
        assert "***REDACTED***" in details["error"]
        assert sentinel not in details["startup_logs"]
        assert "***REDACTED***" in details["startup_logs"]

    @pytest.mark.asyncio
    async def test_exception_is_re_raised_after_audit(self) -> None:
        """SandboxStartError propagates to the caller after the audit event is emitted."""
        srv = _make_server()
        exc = _make_start_error("Sandbox start did not emit AF_READY marker", [])
        srv._pool.create = AsyncMock(side_effect=exc)
        srv._pool.destroy = AsyncMock()
        srv._pool.get_logs = AsyncMock(return_value=[])

        log_audit_mock = AsyncMock()

        with (
            patch("server.log_audit", log_audit_mock),
            patch("server.db.update_run_status", AsyncMock()),
        ):
            active = _make_active_run("run-start-4")
            body = _make_body("ghp_token")
            with pytest.raises(SandboxStartError) as exc_info:
                await srv.execute_run(active, body)

        assert exc_info.value is exc
        event_types = [c.args[1] for c in log_audit_mock.call_args_list]
        assert "sandbox_start_failed" in event_types

    @pytest.mark.asyncio
    async def test_only_log_events_included_in_startup_logs(self) -> None:
        """Non-log events (queued, ready, failed) are excluded from startup_logs."""
        srv = _make_server()
        events: list[dict] = [
            {"event": "queued", "backend_id": "abc"},
            {"event": "log", "line": "Starting up"},
            {"event": "failed", "error": "timeout"},
        ]
        srv._pool.create = AsyncMock(
            side_effect=SandboxStartError("Sandbox start failed: timeout", events)
        )
        srv._pool.destroy = AsyncMock()
        srv._pool.get_logs = AsyncMock(return_value=[])

        log_audit_mock = AsyncMock()

        with (
            patch("server.log_audit", log_audit_mock),
            patch("server.db.update_run_status", AsyncMock()),
        ):
            active = _make_active_run("run-start-5")
            body = _make_body("ghp_token")
            with pytest.raises(SandboxStartError):
                await srv.execute_run(active, body)

        start_fail_call = next(
            c for c in log_audit_mock.call_args_list if c.args[1] == "sandbox_start_failed"
        )
        details: dict = start_fail_call.args[2]
        assert "Starting up" in details["startup_logs"]
        assert "queued" not in details["startup_logs"]
        assert "abc" not in details["startup_logs"]

    @pytest.mark.asyncio
    async def test_body_env_secrets_scrubbed_even_if_not_in_osenv(self) -> None:
        """Secrets from body.env must be scrubbed even when not in os.environ."""
        body_only_token = "ghp_body_only_secret_not_in_osenv"

        srv = _make_server()
        srv._pool.create = AsyncMock(
            side_effect=_make_start_error(
                f"Sandbox start failed: token={body_only_token}",
                [f"Token was: {body_only_token}"],
            )
        )
        srv._pool.destroy = AsyncMock()
        srv._pool.get_logs = AsyncMock(return_value=[])

        log_audit_mock = AsyncMock()

        with (
            patch("server.log_audit", log_audit_mock),
            patch("server.db.update_run_status", AsyncMock()),
        ):
            active = _make_active_run("run-body-env")
            body = _make_body(body_only_token)
            with pytest.raises(SandboxStartError):
                await srv.execute_run(active, body)

        start_fail_call = next(
            c for c in log_audit_mock.call_args_list if c.args[1] == "sandbox_start_failed"
        )
        details: dict = start_fail_call.args[2]
        assert body_only_token not in details["error"]
        assert body_only_token not in details["startup_logs"]
        assert "***REDACTED***" in details["error"]
        assert "***REDACTED***" in details["startup_logs"]
