"""Tests for resume_run logic — the pause/resume bug regression guard.

The root bug: resuming a paused run with a prompt sent only an 'inject' signal,
never a 'resume' signal. The agent's wait_for_resume_or_stop() queued the inject
but blocked forever waiting for 'resume'. The fix: always send 'resume' after
optional 'inject'.

These tests mock at the send_control_signal level and call resume_run through
a patched import to avoid the auth module's /data/api.key requirement.
"""

import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager

from fastapi import HTTPException


def _mock_run(status: str, github_repo: str = "org/repo") -> MagicMock:
    """Create a mock Run ORM object with given status."""
    run = MagicMock()
    run.status = status
    run.github_repo = github_repo
    run.error_message = None
    return run


def _mock_session(run: MagicMock | None):
    """Create a mock async session context manager."""
    session_mock = AsyncMock()
    session_mock.get = AsyncMock(return_value=run)
    session_mock.add = MagicMock()
    session_mock.commit = AsyncMock()

    @asynccontextmanager
    async def context():
        yield session_mock

    return context


@pytest.fixture(autouse=True)
def _patch_auth():
    """Stub out backend.auth so importing endpoints doesn't need /data/api.key."""
    fake_auth = MagicMock()
    fake_auth.verify_api_key = AsyncMock()
    sys.modules.setdefault("backend.auth", fake_auth)
    yield


def _import_resume_run():
    """Import resume_run after auth is patched."""
    from backend.endpoints.runs import resume_run

    return resume_run


def _make_body(payload: str | None = None):
    """Create a ControlSignalRequest."""
    from backend.models import ControlSignalRequest

    return ControlSignalRequest(payload=payload)


class TestResumePausedRun:
    """Resume on a paused run must always send a 'resume' signal to unblock the agent."""

    @pytest.mark.asyncio
    async def test_resume_paused_no_prompt_sends_resume_signal(self):
        """Resuming a paused run with no prompt sends exactly one 'resume' signal."""
        resume_run = _import_resume_run()
        run = _mock_run("paused")
        with (
            patch("backend.endpoints.runs.session", _mock_session(run)),
            patch(
                "backend.endpoints.runs.send_control_signal", new_callable=AsyncMock
            ) as mock_signal,
        ):
            mock_signal.return_value = {"ok": True, "signal": "resume", "run_id": "r-1"}
            result = await resume_run(
                "00000000-0000-0000-0000-000000000001", _make_body()
            )

            assert result["ok"] is True
            mock_signal.assert_called_once_with(
                "00000000-0000-0000-0000-000000000001",
                "resume",
                {"paused"},
                None,
                None,
            )

    @pytest.mark.asyncio
    async def test_resume_paused_with_prompt_sends_inject_then_resume(self):
        """Resuming a paused run with a prompt must send inject AND resume.

        This is the exact regression: the old code sent only 'inject' and the
        agent's wait_for_resume_or_stop() never unblocked.
        """
        resume_run = _import_resume_run()
        run = _mock_run("paused")
        signals_sent: list[str] = []

        async def track_signal(run_id, signal, valid_statuses, payload, extra_body):
            signals_sent.append(signal)
            return {"ok": True, "signal": signal, "run_id": run_id}

        with (
            patch("backend.endpoints.runs.session", _mock_session(run)),
            patch(
                "backend.endpoints.runs.send_control_signal", side_effect=track_signal
            ),
        ):
            await resume_run(
                "00000000-0000-0000-0000-000000000001",
                _make_body("continue with tests"),
            )

            assert signals_sent == ["inject", "resume"], (
                f"Expected ['inject', 'resume'] but got {signals_sent}. "
                "If only 'inject' is sent, the agent stays stuck in pause forever."
            )

    @pytest.mark.asyncio
    async def test_resume_paused_with_whitespace_only_sends_resume_only(self):
        """Whitespace-only prompt should be treated as no prompt."""
        resume_run = _import_resume_run()
        run = _mock_run("paused")
        with (
            patch("backend.endpoints.runs.session", _mock_session(run)),
            patch(
                "backend.endpoints.runs.send_control_signal", new_callable=AsyncMock
            ) as mock_signal,
        ):
            mock_signal.return_value = {"ok": True, "signal": "resume", "run_id": "r-1"}
            await resume_run("00000000-0000-0000-0000-000000000001", _make_body("   "))

            mock_signal.assert_called_once_with(
                "00000000-0000-0000-0000-000000000001",
                "resume",
                {"paused"},
                None,
                None,
            )

    @pytest.mark.asyncio
    async def test_resume_completed_run_calls_restart(self):
        """Terminal status routes to _resume_completed_run, not send_control_signal."""
        resume_run = _import_resume_run()
        run = _mock_run("completed")
        session_mock = AsyncMock()
        session_mock.get = AsyncMock(return_value=run)
        session_mock.commit = AsyncMock()

        @asynccontextmanager
        async def context():
            yield session_mock

        with (
            patch("backend.endpoints.runs.session", context),
            patch(
                "backend.endpoints.runs._resume_completed_run",
                new_callable=AsyncMock,
            ) as mock_restart,
        ):
            mock_restart.return_value = {"ok": True, "resumed": True}
            result = await resume_run(
                "00000000-0000-0000-0000-000000000001",
                _make_body("fix the bug"),
            )

            assert result["ok"] is True
            mock_restart.assert_called_once()
            assert mock_restart.call_args[0][2] == "fix the bug"

    @pytest.mark.asyncio
    async def test_resume_running_run_returns_409(self):
        """Cannot resume a run that is already running."""
        resume_run = _import_resume_run()
        run = _mock_run("running")
        with patch("backend.endpoints.runs.session", _mock_session(run)):
            with pytest.raises(HTTPException) as exc_info:
                await resume_run("00000000-0000-0000-0000-000000000001", _make_body())
            assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_resume_rate_limited_injects_not_restarts(self):
        """Rate-limited run should inject the prompt, not restart the run."""
        resume_run = _import_resume_run()
        run = _mock_run("rate_limited")
        signals_sent: list[str] = []

        async def track_signal(run_id, signal, valid_statuses, payload, extra_body):
            signals_sent.append(signal)
            return {"ok": True, "signal": signal, "run_id": run_id}

        with (
            patch("backend.endpoints.runs.session", _mock_session(run)),
            patch("backend.endpoints.runs.send_control_signal", side_effect=track_signal),
            patch("backend.endpoints.runs._resume_completed_run", new_callable=AsyncMock) as mock_restart,
        ):
            result = await resume_run(
                "00000000-0000-0000-0000-000000000001",
                _make_body("keep going"),
            )

            assert result["ok"] is True
            assert signals_sent == ["inject"]
            mock_restart.assert_not_called()

    @pytest.mark.asyncio
    async def test_resume_rate_limited_no_prompt_returns_ok(self):
        """Rate-limited run with no prompt should return ok without sending signals."""
        resume_run = _import_resume_run()
        run = _mock_run("rate_limited")
        with (
            patch("backend.endpoints.runs.session", _mock_session(run)),
            patch("backend.endpoints.runs.send_control_signal", new_callable=AsyncMock) as mock_signal,
        ):
            result = await resume_run(
                "00000000-0000-0000-0000-000000000001",
                _make_body(),
            )

            assert result["ok"] is True
            mock_signal.assert_not_called()

    @pytest.mark.asyncio
    async def test_resume_missing_run_returns_404(self):
        """Resuming a nonexistent run returns 404."""
        resume_run = _import_resume_run()
        with patch("backend.endpoints.runs.session", _mock_session(None)):
            with pytest.raises(HTTPException) as exc_info:
                await resume_run("00000000-0000-0000-0000-000000000001", _make_body())
            assert exc_info.value.status_code == 404
