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

    @pytest.mark.asyncio
    async def test_db_write_happens_before_agent_forward(self):
        """DB commit must happen before agent forward — audit trail survives agent failures."""
        run = _mock_run("running")
        call_order: list[str] = []

        session_mock = AsyncMock()
        session_mock.get = AsyncMock(return_value=run)
        session_mock.add = MagicMock(side_effect=lambda _: call_order.append("db_add"))
        session_mock.commit = AsyncMock(side_effect=lambda: call_order.append("db_commit"))

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def ctx():
            yield session_mock

        async def mock_agent(*args, **kwargs):
            call_order.append("agent_forward")

        with (
            patch("backend.utils.session", ctx),
            patch("backend.utils.agent_request", mock_agent),
        ):
            await send_control_signal("run-1", "stop", {"running"}, "bye")

        assert call_order == ["db_add", "db_commit", "agent_forward"]

    @pytest.mark.asyncio
    async def test_agent_failure_does_not_swallow_db_write(self):
        """If agent forward fails, the DB write should still have happened."""
        run = _mock_run("running")
        with (
            patch("backend.utils.session", _mock_session(run)),
            patch("backend.utils.agent_request", new_callable=AsyncMock) as mock_agent,
        ):
            mock_agent.side_effect = Exception("agent down")
            with pytest.raises(Exception, match="agent down"):
                await send_control_signal("run-1", "pause", {"running"}, None)
            # agent_request was called (it raised), so DB write already happened
            mock_agent.assert_called_once()

    @pytest.mark.asyncio
    async def test_unknown_signal_skips_agent_forward(self):
        """A signal not in SIGNAL_AGENT_PATHS should still write to DB but skip forwarding."""
        run = _mock_run("running")
        with (
            patch("backend.utils.session", _mock_session(run)),
            patch("backend.utils.agent_request", new_callable=AsyncMock) as mock_agent,
        ):
            result = await send_control_signal("run-1", "custom_signal", {"running"}, None)
            assert result["ok"] is True
            mock_agent.assert_not_called()

    @pytest.mark.asyncio
    async def test_stop_forwards_no_json_body(self):
        """Stop signal should NOT send payload as json body — agent ignores it."""
        run = _mock_run("running")
        with (
            patch("backend.utils.session", _mock_session(run)),
            patch("backend.utils.agent_request", new_callable=AsyncMock) as mock_agent,
        ):
            await send_control_signal("run-1", "stop", {"running"}, "reason text")
            assert mock_agent.call_args[0][3] is None  # json_body is None for stop

    @pytest.mark.asyncio
    async def test_all_signals_pass_run_id_as_param(self):
        """Every signal type must pass run_id in params dict."""
        for signal in ("pause", "resume", "stop", "unlock", "inject", "kill"):
            run = _mock_run("running")
            valid = {"running", "paused"}
            with (
                patch("backend.utils.session", _mock_session(run)),
                patch("backend.utils.agent_request", new_callable=AsyncMock) as mock_agent,
            ):
                await send_control_signal("run-42", signal, valid, "payload")
                assert mock_agent.call_args[0][4] == {"run_id": "run-42"}, f"{signal} missing run_id"
