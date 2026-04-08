"""Tests for parallel run signal isolation.

Verifies that control signals sent to different run IDs are routed
independently — pausing run-1 does not affect run-2, and each signal
carries the correct run_id in its params.
"""

import pytest
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import AsyncContextManager
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from backend.utils import send_control_signal


def _mock_run(status: str) -> MagicMock:
    """Create a mock Run ORM object with given status."""
    run = MagicMock()
    run.status = status
    return run


def _mock_session_multi(
    runs_by_id: dict[str, MagicMock],
) -> Callable[[], AsyncContextManager[AsyncMock]]:
    """Create a mock async session context manager backed by a dict of runs.

    session.get(Model, run_id) returns the run for that ID, or None if not found.
    """
    session_mock = AsyncMock()
    session_mock.get = AsyncMock(side_effect=lambda _model, rid: runs_by_id.get(rid))
    session_mock.add = MagicMock()
    session_mock.commit = AsyncMock()

    @asynccontextmanager
    async def ctx():
        yield session_mock

    return ctx


class TestParallelSignalIsolation:
    """Control signals to different run_ids must be routed independently."""

    @pytest.mark.asyncio
    async def test_pause_targets_specific_run(self) -> None:
        """Pause run-1 — agent_request must receive run_id=run-1, not run-2."""
        run1 = _mock_run("running")
        run2 = _mock_run("running")
        runs = {"run-1": run1, "run-2": run2}

        with (
            patch("backend.utils.session", _mock_session_multi(runs)),
            patch("backend.utils.agent_request", new_callable=AsyncMock) as mock_agent,
        ):
            result = await send_control_signal("run-1", "pause", {"running"}, None)

        assert result["ok"] is True
        mock_agent.assert_called_once()
        args = mock_agent.call_args[0]
        assert args[1] == "/pause"
        assert args[4] == {"run_id": "run-1"}

    @pytest.mark.asyncio
    async def test_stop_one_run_leaves_other_running(self) -> None:
        """Stop run-1 (status transitions to stopped). Pause run-2 should still succeed."""
        run1 = _mock_run("running")
        run2 = _mock_run("running")
        runs = {"run-1": run1, "run-2": run2}

        with (
            patch("backend.utils.session", _mock_session_multi(runs)),
            patch("backend.utils.agent_request", new_callable=AsyncMock),
        ):
            stop_result = await send_control_signal("run-1", "stop", {"running"}, None)

        assert stop_result["ok"] is True

        # run-2 is still running — pause should succeed independently
        with (
            patch("backend.utils.session", _mock_session_multi(runs)),
            patch("backend.utils.agent_request", new_callable=AsyncMock) as mock_agent,
        ):
            pause_result = await send_control_signal("run-2", "pause", {"running"}, None)

        assert pause_result["ok"] is True
        args = mock_agent.call_args[0]
        assert args[4] == {"run_id": "run-2"}

    @pytest.mark.asyncio
    async def test_inject_to_each_run_independently(self) -> None:
        """Inject different payloads to run-1 and run-2; each call carries correct run_id and payload."""
        run1 = _mock_run("running")
        run2 = _mock_run("running")
        runs = {"run-1": run1, "run-2": run2}

        with (
            patch("backend.utils.session", _mock_session_multi(runs)),
            patch("backend.utils.agent_request", new_callable=AsyncMock) as mock_agent,
        ):
            await send_control_signal("run-1", "inject", {"running"}, "focus on tests")

        first_call = mock_agent.call_args[0]
        assert first_call[1] == "/inject"
        assert first_call[3] == {"payload": "focus on tests"}
        assert first_call[4] == {"run_id": "run-1"}

        with (
            patch("backend.utils.session", _mock_session_multi(runs)),
            patch("backend.utils.agent_request", new_callable=AsyncMock) as mock_agent,
        ):
            await send_control_signal("run-2", "inject", {"running"}, "write more docs")

        second_call = mock_agent.call_args[0]
        assert second_call[1] == "/inject"
        assert second_call[3] == {"payload": "write more docs"}
        assert second_call[4] == {"run_id": "run-2"}

    @pytest.mark.asyncio
    async def test_signal_to_wrong_run_id_returns_404(self) -> None:
        """Pause to a run_id that doesn't exist in the DB must raise HTTPException 404."""
        run1 = _mock_run("running")
        runs = {"run-1": run1}

        with patch("backend.utils.session", _mock_session_multi(runs)):
            with pytest.raises(HTTPException) as exc_info:
                await send_control_signal("nonexistent-run", "pause", {"running"}, None)

        assert exc_info.value.status_code == 404
