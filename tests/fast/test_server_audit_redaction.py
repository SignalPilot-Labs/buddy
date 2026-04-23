"""Tests for _scrub_secrets and the five audit/run-finalisation leak surfaces in server.py.

Pins five guarantees:
1. `_scrub_secrets` replaces GIT_TOKEN, CLAUDE_CODE_OAUTH_TOKEN, AGENT_INTERNAL_SECRET,
   SANDBOX_INTERNAL_SECRET, and ANTHROPIC_API_KEY values with `***REDACTED***` and passes
   text through unchanged when no token is set (the `if value:` guard).
2. Site A: `db.log_audit("sandbox_crash")` details.error and details.sandbox_logs are scrubbed.
3. Site B: the `log.error` sandbox tail record does not contain the raw token.
4. Sites C/D/E: traceback log, ActiveRun.error_message, and db.finish_run error_message
   are all scrubbed.
5. Negative control: the CancelledError branch writes the literal "Cancelled" and is NOT
   scrubbed (confirming Sites F/G/H are left alone).
"""

import asyncio
import logging
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# server.py reads AGENT_INTERNAL_SECRET at import time via AgentServer.__init__.
# Set it before the import so the module-level `_server = AgentServer()` succeeds.
os.environ.setdefault("AGENT_INTERNAL_SECRET", "test-secret")
os.environ.setdefault("SANDBOX_INTERNAL_SECRET", "test-sandbox-secret")

# The module-level `_server = AgentServer()` in server.py calls SandboxPool() which
# calls docker.from_env(). Patch it before import so tests can run without Docker.
with patch("docker.from_env", return_value=MagicMock()):
    from server import AgentServer

from utils.constants import ENV_KEY_ANTHROPIC_API, ENV_KEY_CLAUDE_TOKEN, ENV_KEY_GIT_TOKEN, ENV_KEY_INTERNAL_SECRET, ENV_KEY_SANDBOX_SECRET
from utils.models import ActiveRun, StartRequest
from utils.secrets import scrub_secrets

_SECRET_ENV_KEYS: tuple[str, ...] = (
    ENV_KEY_GIT_TOKEN,
    ENV_KEY_CLAUDE_TOKEN,
    ENV_KEY_INTERNAL_SECRET,
    ENV_KEY_SANDBOX_SECRET,
    ENV_KEY_ANTHROPIC_API,
)


def _make_active_run(run_id: str) -> ActiveRun:
    return ActiveRun(run_id=run_id, status="running")


def _make_run_context() -> MagicMock:
    ctx = MagicMock()
    ctx.total_cost = 0.01
    ctx.total_input_tokens = 100
    ctx.total_output_tokens = 50
    ctx.cache_creation_input_tokens = 0
    ctx.cache_read_input_tokens = 0
    return ctx


def _make_server() -> AgentServer:
    """Build an AgentServer instance without calling __init__ (avoids DB + pool setup)."""
    srv = AgentServer.__new__(AgentServer)
    srv._pool = MagicMock()
    srv._exec_timeout = 300
    srv._health_timeout = 30
    srv._clone_timeout = 120
    return srv


class TestServerAuditRedaction:
    """_scrub_secrets helper and each of the five audit/finalisation boundaries."""

    # ── Helper-direct (4) ─────────────────────────────────────────────

    def test_scrubs_git_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ENV_KEY_GIT_TOKEN, "GHP_SENTINEL_AUDIT_GIT_A")
        result = scrub_secrets(
            "git clone https://x-access-token:GHP_SENTINEL_AUDIT_GIT_A@github.com/o/r.git failed",
            [os.environ.get(k) for k in _SECRET_ENV_KEYS],
        )
        assert "GHP_SENTINEL_AUDIT_GIT_A" not in result
        assert "***REDACTED***" in result

    def test_scrubs_claude_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ENV_KEY_CLAUDE_TOKEN, "sk-ant-SENTINEL_CLAUDE_B")
        result = scrub_secrets(
            "sdk error: token=sk-ant-SENTINEL_CLAUDE_B expired",
            [os.environ.get(k) for k in _SECRET_ENV_KEYS],
        )
        assert "sk-ant-SENTINEL_CLAUDE_B" not in result
        assert "***REDACTED***" in result

    def test_scrubs_internal_secret(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ENV_KEY_INTERNAL_SECRET, "INT_SENTINEL_C")
        result = scrub_secrets(
            "auth failed INT_SENTINEL_C in header",
            [os.environ.get(k) for k in _SECRET_ENV_KEYS],
        )
        assert "INT_SENTINEL_C" not in result
        assert "***REDACTED***" in result

    def test_scrubs_sandbox_secret(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ENV_KEY_SANDBOX_SECRET, "SBX_SENTINEL_D")
        result = scrub_secrets(
            "auth failed SBX_SENTINEL_D in header",
            [os.environ.get(k) for k in _SECRET_ENV_KEYS],
        )
        assert "SBX_SENTINEL_D" not in result
        assert "***REDACTED***" in result

    def test_no_tokens_in_env_passthrough(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(ENV_KEY_GIT_TOKEN, raising=False)
        monkeypatch.delenv(ENV_KEY_CLAUDE_TOKEN, raising=False)
        monkeypatch.delenv(ENV_KEY_INTERNAL_SECRET, raising=False)
        monkeypatch.delenv(ENV_KEY_SANDBOX_SECRET, raising=False)
        monkeypatch.delenv(ENV_KEY_ANTHROPIC_API, raising=False)
        text = "benign traceback text"
        result = scrub_secrets(text, [os.environ.get(k) for k in _SECRET_ENV_KEYS])
        assert result == text
        assert "***REDACTED***" not in result

    # ── Integration — one per distinct boundary ────────────────────────

    @pytest.mark.asyncio
    async def test_sandbox_crash_audit_scrubs_error_and_logs(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Site A: db.log_audit sandbox_crash details must not contain raw token."""
        sentinel = "GHP_SENTINEL_AUDIT_GIT_A"
        monkeypatch.setenv(ENV_KEY_GIT_TOKEN, sentinel)

        srv = _make_server()
        pool = srv._pool
        pool.get_sandbox_logs = AsyncMock(
            return_value=[
                f"line1 https://x-access-token:{sentinel}@github.com/o/r.git fatal",
                "line2",
            ]
        )
        pool.create = AsyncMock(return_value=MagicMock(close=AsyncMock()))
        pool.destroy = AsyncMock()

        log_audit_mock = AsyncMock()

        with (
            patch("server.bootstrap_run", side_effect=RuntimeError(f"boom {sentinel}")),
            patch("server.db.log_audit", log_audit_mock),
        ):
            active = _make_active_run("run-a")
            body = StartRequest(
                github_repo="owner/repo",
                prompt="fix it",
                duration_minutes=30,
                env={ENV_KEY_GIT_TOKEN: sentinel},
            )
            with pytest.raises(RuntimeError):
                await srv.execute_run(active, body)

        crash_call = next(
            c for c in log_audit_mock.call_args_list if c.args[1] == "sandbox_crash"
        )
        details: dict = crash_call.args[2]
        assert sentinel not in details["error"]
        assert "***REDACTED***" in details["error"]
        assert sentinel not in details["sandbox_logs"]
        assert "***REDACTED***" in details["sandbox_logs"]

    @pytest.mark.asyncio
    async def test_sandbox_crash_log_record_scrubs_tail(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Site B: log.error sandbox tail must not contain raw token."""
        sentinel = "GHP_SENTINEL_AUDIT_GIT_A"
        monkeypatch.setenv(ENV_KEY_GIT_TOKEN, sentinel)

        srv = _make_server()
        pool = srv._pool
        pool.get_sandbox_logs = AsyncMock(
            return_value=[
                f"line1 https://x-access-token:{sentinel}@github.com/o/r.git fatal",
                "line2",
            ]
        )
        pool.create = AsyncMock(return_value=MagicMock(close=AsyncMock()))
        pool.destroy = AsyncMock()

        with (
            patch("server.bootstrap_run", side_effect=RuntimeError(f"boom {sentinel}")),
            patch("server.db.log_audit", AsyncMock()),
            caplog.at_level(logging.ERROR, logger="server"),
        ):
            active = _make_active_run("run-b")
            body = StartRequest(
                github_repo="owner/repo",
                prompt="fix it",
                duration_minutes=30,
                env={ENV_KEY_GIT_TOKEN: sentinel},
            )
            with pytest.raises(RuntimeError):
                await srv.execute_run(active, body)

        assert sentinel not in caplog.text
        assert "***REDACTED***" in caplog.text

    @pytest.mark.asyncio
    async def test_on_task_done_scrubs_traceback_and_error_message(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Sites C/D/E: traceback log, ActiveRun.error_message, and db.finish_run
        error_message are all scrubbed from the crash exception."""
        sentinel = "GHP_SENTINEL_AUDIT_GIT_A"
        monkeypatch.setenv(ENV_KEY_GIT_TOKEN, sentinel)

        srv = _make_server()
        active = _make_active_run("run-c")
        active.run_context = _make_run_context()

        exc = RuntimeError(
            f"connect failed https://x-access-token:{sentinel}@github.com/o/r.git"
        )

        task: asyncio.Task = MagicMock(spec=asyncio.Task)
        task.exception.return_value = exc

        finish_run_mock = AsyncMock()

        with (
            patch("server.db.finish_run", finish_run_mock),
            patch("server.asyncio.create_task", side_effect=lambda coro: asyncio.ensure_future(coro)),
            caplog.at_level(logging.ERROR, logger="server"),
        ):
            srv.on_task_done(active, task)
            # Allow the create_task coroutine to complete
            await asyncio.sleep(0)

        # Site C: traceback log
        assert sentinel not in caplog.text
        assert "***REDACTED***" in caplog.text

        # Site D: in-memory error_message
        assert active.error_message is not None
        assert sentinel not in active.error_message
        assert "***REDACTED***" in active.error_message

        # Site E: db.finish_run error_message argument
        assert finish_run_mock.called
        call_kwargs = finish_run_mock.call_args
        # error_message is the 7th positional arg (index 6)
        error_message_arg: str | None = call_kwargs.args[6]
        assert error_message_arg is not None
        assert sentinel not in error_message_arg
        assert "***REDACTED***" in error_message_arg

    @pytest.mark.asyncio
    async def test_cancelled_path_error_message_unchanged(self) -> None:
        """Negative control: CancelledError branch writes literal 'Cancelled' unchanged."""
        srv = _make_server()
        active = _make_active_run("run-d")
        active.run_context = _make_run_context()

        task: asyncio.Task = MagicMock(spec=asyncio.Task)
        task.exception.side_effect = asyncio.CancelledError()

        finish_run_mock = AsyncMock()

        with (
            patch("server.db.finish_run", finish_run_mock),
            patch("server.asyncio.create_task", side_effect=lambda coro: asyncio.ensure_future(coro)),
        ):
            srv.on_task_done(active, task)
            await asyncio.sleep(0)

        assert active.error_message == "Cancelled"

        assert finish_run_mock.called
        call_kwargs = finish_run_mock.call_args
        # error_message is the 7th positional arg (index 6)
        error_message_arg: str | None = call_kwargs.args[6]
        assert error_message_arg == "Cancelled"
