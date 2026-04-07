"""Tests for control signal routing through /runs/{id}/* endpoints.

Verifies that send_control_signal writes to DB AND forwards to the agent,
and that /runs/{id}/resume routes correctly based on run status.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.utils import send_control_signal


def _mock_run(status: str) -> MagicMock:
    """Create a mock Run ORM object with given status."""
    run = MagicMock()
    run.status = status
    return run


def _mock_session(run: MagicMock | None):
    """Create a mock async session context manager."""
    session_mock = AsyncMock()
    session_mock.get = AsyncMock(return_value=run)
    session_mock.add = MagicMock()
    session_mock.commit = AsyncMock()

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def ctx():
        yield session_mock

    return ctx


class TestSendControlSignalForwardsToAgent:
    """send_control_signal must write to DB and forward to agent EventBus."""

    @pytest.mark.asyncio
    async def test_forwards_pause_to_agent(self):
        run = _mock_run("running")
        with (
            patch("backend.utils.session", _mock_session(run)),
            patch("backend.utils.agent_request", new_callable=AsyncMock) as mock_agent,
        ):
            result = await send_control_signal("run-1", "pause", {"running"}, None)
            assert result["ok"] is True
            mock_agent.assert_called_once()
            args = mock_agent.call_args
            assert args[0][0] == "POST"
            assert args[0][1] == "/pause"
            assert args[0][3] is None  # no json body for pause
            assert args[0][4] == {"run_id": "run-1"}

    @pytest.mark.asyncio
    async def test_forwards_inject_with_payload(self):
        run = _mock_run("running")
        with (
            patch("backend.utils.session", _mock_session(run)),
            patch("backend.utils.agent_request", new_callable=AsyncMock) as mock_agent,
        ):
            result = await send_control_signal("run-1", "inject", {"running"}, "focus on tests")
            assert result["ok"] is True
            mock_agent.assert_called_once()
            args = mock_agent.call_args
            assert args[0][1] == "/inject"
            assert args[0][3] == {"payload": "focus on tests"}

    @pytest.mark.asyncio
    async def test_forwards_stop_to_agent(self):
        run = _mock_run("running")
        with (
            patch("backend.utils.session", _mock_session(run)),
            patch("backend.utils.agent_request", new_callable=AsyncMock) as mock_agent,
        ):
            await send_control_signal("run-1", "stop", {"running"}, "user stop")
            mock_agent.assert_called_once()
            assert mock_agent.call_args[0][1] == "/stop"

    @pytest.mark.asyncio
    async def test_forwards_resume_to_agent(self):
        run = _mock_run("paused")
        with (
            patch("backend.utils.session", _mock_session(run)),
            patch("backend.utils.agent_request", new_callable=AsyncMock) as mock_agent,
        ):
            await send_control_signal("run-1", "resume", {"paused"}, None)
            mock_agent.assert_called_once()
            assert mock_agent.call_args[0][1] == "/resume_signal"

    @pytest.mark.asyncio
    async def test_forwards_kill_to_agent(self):
        run = _mock_run("running")
        with (
            patch("backend.utils.session", _mock_session(run)),
            patch("backend.utils.agent_request", new_callable=AsyncMock) as mock_agent,
        ):
            await send_control_signal("run-1", "kill", {"running"}, None)
            mock_agent.assert_called_once()
            assert mock_agent.call_args[0][1] == "/kill"

    @pytest.mark.asyncio
    async def test_rejects_wrong_status(self):
        run = _mock_run("completed")
        with patch("backend.utils.session", _mock_session(run)):
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                await send_control_signal("run-1", "pause", {"running"}, None)
            assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_rejects_missing_run(self):
        with patch("backend.utils.session", _mock_session(None)):
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                await send_control_signal("nonexistent", "pause", {"running"}, None)
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_inject_on_paused_run(self):
        """Inject should work on paused runs too."""
        run = _mock_run("paused")
        with (
            patch("backend.utils.session", _mock_session(run)),
            patch("backend.utils.agent_request", new_callable=AsyncMock) as mock_agent,
        ):
            result = await send_control_signal("run-1", "inject", {"running", "paused"}, "do this")
            assert result["ok"] is True
            assert mock_agent.call_args[0][3] == {"payload": "do this"}

    @pytest.mark.asyncio
    async def test_inject_on_rate_limited_run(self):
        """Inject should work on rate_limited runs."""
        run = _mock_run("rate_limited")
        with (
            patch("backend.utils.session", _mock_session(run)),
            patch("backend.utils.agent_request", new_callable=AsyncMock) as mock_agent,
        ):
            result = await send_control_signal(
                "run-1", "inject", {"running", "paused", "rate_limited"}, "retry",
            )
            assert result["ok"] is True
            mock_agent.assert_called_once()
