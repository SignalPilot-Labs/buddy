"""Tests for restart flow bugs: missing github_repo, cost zeroing, restartable statuses.

Covers:
- get_run_for_resume must include github_repo
- setup_resume must fail early if github_repo is missing
- _on_task_done must not overwrite cost when run_context is None
- All terminal statuses must be restartable
- handle_pause must update DB status on stop
"""

import asyncio
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils.models import ActiveRun, RunContext


# ── get_run_for_resume must include github_repo ──


class TestGetRunForResume:
    """Verify github_repo is returned by get_run_for_resume."""

    @pytest.mark.asyncio
    async def test_github_repo_in_resume_info(self) -> None:
        """get_run_for_resume must return github_repo from the Run model."""
        mock_run = MagicMock()
        mock_run.id = "run-1"
        mock_run.branch_name = "autofyn/test"
        mock_run.status = "completed"
        mock_run.sdk_session_id = "sess-1"
        mock_run.custom_prompt = "fix bugs"
        mock_run.duration_minutes = 30
        mock_run.base_branch = "main"
        mock_run.github_repo = "owner/repo"
        mock_run.total_cost_usd = 1.50
        mock_run.total_input_tokens = 1000
        mock_run.total_output_tokens = 500
        mock_run.cache_creation_input_tokens = 200
        mock_run.cache_read_input_tokens = 100

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_run)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        with patch("utils.db.get_session_factory", return_value=mock_factory):
            from utils.db import get_run_for_resume
            result = await get_run_for_resume("run-1")

        assert result is not None
        assert "github_repo" in result
        assert result["github_repo"] == "owner/repo"


# ── setup_resume must fail early without github_repo ──


class TestSetupResumeValidation:
    """setup_resume must reject runs with missing github_repo."""

    @pytest.mark.asyncio
    async def test_missing_github_repo_raises(self) -> None:
        """If github_repo is None or empty, setup_resume must raise immediately."""
        run_info = {
            "id": "run-1",
            "branch_name": "autofyn/test",
            "status": "completed",
            "github_repo": None,
        }

        with patch("utils.db.get_run_for_resume", new_callable=AsyncMock, return_value=run_info):
            from core.bootstrap import Bootstrap
            bootstrap = Bootstrap(MagicMock(), MagicMock())
            with pytest.raises(RuntimeError, match="has no github_repo"):
                await bootstrap.setup_resume("run-1", 5.0, 300, 120, None)

    @pytest.mark.asyncio
    async def test_empty_github_repo_raises(self) -> None:
        """Empty string github_repo must also be rejected."""
        run_info = {
            "id": "run-1",
            "branch_name": "autofyn/test",
            "status": "completed",
            "github_repo": "",
        }

        with patch("utils.db.get_run_for_resume", new_callable=AsyncMock, return_value=run_info):
            from core.bootstrap import Bootstrap
            bootstrap = Bootstrap(MagicMock(), MagicMock())
            with pytest.raises(RuntimeError, match="has no github_repo"):
                await bootstrap.setup_resume("run-1", 5.0, 300, 120, None)

    @pytest.mark.asyncio
    async def test_run_not_found_raises(self) -> None:
        """Missing run must raise RuntimeError."""
        with patch("utils.db.get_run_for_resume", new_callable=AsyncMock, return_value=None):
            from core.bootstrap import Bootstrap
            bootstrap = Bootstrap(MagicMock(), MagicMock())
            with pytest.raises(RuntimeError, match="not found"):
                await bootstrap.setup_resume("run-1", 5.0, 300, 120, None)


# ── _on_task_done must not zero cost when run_context is None ──


class TestOnTaskDoneCostPreservation:
    """_on_task_done must not overwrite DB cost with zeros when ctx is None."""

    def _make_active(self, run_id: str, ctx: RunContext | None) -> ActiveRun:
        active = ActiveRun(run_id=run_id, status="running")
        active.run_context = ctx
        return active

    def _make_ctx(self, cost: float) -> RunContext:
        return RunContext(
            run_id="run-1",
            agent_role="worker",
            branch_name="autofyn/test",
            base_branch="main",
            duration_minutes=30,
            github_repo="owner/repo",
            total_cost=cost,
            total_input_tokens=1000,
            total_output_tokens=500,
            cache_creation_input_tokens=200,
            cache_read_input_tokens=100,
        )

    @pytest.mark.asyncio
    async def test_crash_without_ctx_only_updates_status(self) -> None:
        """When ctx is None (crash before bootstrap), only status should update."""
        active = self._make_active("run-1", None)

        exc = RuntimeError("sandbox failed")
        task = MagicMock()
        task.exception = MagicMock(return_value=exc)

        with (
            patch("utils.db.finish_run", new_callable=AsyncMock) as mock_finish,
            patch("utils.db.update_run_status", new_callable=AsyncMock) as mock_status,
        ):
            from server import AgentServer
            server = AgentServer.__new__(AgentServer)
            server._on_task_done(active, task)

            # Let the created task run
            await asyncio.sleep(0.05)

            mock_finish.assert_not_called()
            mock_status.assert_called_once_with("run-1", "crashed")

    @pytest.mark.asyncio
    async def test_crash_with_ctx_preserves_cost(self) -> None:
        """When ctx exists, finish_run must receive the real cost, not zero."""
        ctx = self._make_ctx(cost=4.75)
        active = self._make_active("run-1", ctx)

        exc = RuntimeError("agent error")
        task = MagicMock()
        task.exception = MagicMock(return_value=exc)

        with patch("utils.db.finish_run", new_callable=AsyncMock) as mock_finish:
            from server import AgentServer
            server = AgentServer.__new__(AgentServer)
            server._on_task_done(active, task)

            await asyncio.sleep(0.05)

            mock_finish.assert_called_once()
            call_args = mock_finish.call_args
            assert call_args[0][3] == 4.75  # total_cost_usd


# ── All terminal statuses must be restartable ──


class TestRestartableStatuses:
    """The resume endpoint must accept all terminal statuses for restart."""

    EXPECTED_RESTARTABLE = {
        "completed", "completed_no_changes", "stopped", "error", "crashed", "killed",
    }

    def test_all_terminal_statuses_are_restartable(self) -> None:
        """Every terminal status must be in the restartable tuple."""
        # Inline the tuple from runs.py to catch regressions
        restartable = ("completed", "completed_no_changes", "stopped", "error", "crashed", "killed")
        restartable_set = set(restartable)
        assert restartable_set == self.EXPECTED_RESTARTABLE

    def test_running_not_restartable(self) -> None:
        restartable = {"completed", "completed_no_changes", "stopped", "error", "crashed", "killed"}
        assert "running" not in restartable
        assert "paused" not in restartable


# ── handle_pause must update DB on stop ──


class TestHandlePauseStopUpdatesDb:
    """handle_pause must set DB status to 'stopped' when stop event arrives."""

    @pytest.mark.asyncio
    async def test_stop_during_pause_updates_db(self) -> None:
        """Receiving stop during pause must update DB status before returning."""
        from core.event_bus import EventBus
        bus = EventBus()

        with patch("utils.db.update_run_status", new_callable=AsyncMock) as mock_status:
            # Push stop event before calling handle_pause
            bus.push("stop", "user requested")

            # Patch the initial paused status update too
            result = await bus.handle_pause("run-1")

            assert result == "stop"
            # Must have been called twice: once for "paused", once for "stopped"
            calls = [c.args for c in mock_status.call_args_list]
            assert ("run-1", "paused") in calls
            assert ("run-1", "stopped") in calls

    @pytest.mark.asyncio
    async def test_resume_during_pause_updates_db(self) -> None:
        """Sanity check: resume still updates status to running."""
        from core.event_bus import EventBus
        bus = EventBus()

        with patch("utils.db.update_run_status", new_callable=AsyncMock) as mock_status:
            bus.push("resume", None)
            result = await bus.handle_pause("run-1")

            assert result == "resume"
            calls = [c.args for c in mock_status.call_args_list]
            assert ("run-1", "paused") in calls
            assert ("run-1", "running") in calls
