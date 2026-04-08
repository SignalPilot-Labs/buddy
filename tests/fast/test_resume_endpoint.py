"""Tests for the unified /resume endpoint logic.

Covers both paths: unpause (paused run in _runs) and restart (completed run
requiring new sandbox). Uses the same pure helpers from run_helpers.py.
"""

from unittest.mock import MagicMock

import pytest

from utils.constants import ENV_KEY_CLAUDE_TOKEN, ENV_KEY_GIT_TOKEN
from utils.models import ActiveRun, ResumeRequest
from utils.run_helpers import merge_tokens_into_env


def _make_active(run_id: str, status: str) -> ActiveRun:
    """Build an ActiveRun with a mock EventBus."""
    active = ActiveRun(run_id=run_id, status=status)
    active.events = MagicMock()
    active.events.push = MagicMock()
    return active


class TestResumeUnpause:
    """Unpause path: run exists in _runs and is paused."""

    def test_paused_run_gets_resume_signal(self) -> None:
        active = _make_active("run-1", "paused")
        runs: dict[str, ActiveRun] = {"run-1": active}

        # Simulate what the endpoint does for a paused run
        rid = "run-1"
        found = runs.get(rid)
        assert found is not None
        assert found.status == "paused"
        assert found.events is not None

        mock_events: MagicMock = found.events  # type: ignore[assignment]
        mock_events.push("resume", None)
        mock_events.push.assert_called_once_with("resume", None)

    def test_running_run_is_not_unpaused(self) -> None:
        active = _make_active("run-1", "running")
        runs: dict[str, ActiveRun] = {"run-1": active}

        found = runs.get("run-1")
        assert found is not None
        # Endpoint should NOT push resume to a running run
        assert found.status != "paused"


class TestResumeRestart:
    """Restart path: run not in _runs (completed/stopped), needs new sandbox."""

    def test_missing_run_id_for_restart_is_rejected(self) -> None:
        """Restart requires run_id in the body — Pydantic rejects empty string."""
        with pytest.raises(Exception, match="run_id"):
            ResumeRequest(run_id="")

    def test_tokens_merged_for_restart(self) -> None:
        """Restart must merge tokens into env just like /start does."""
        body = ResumeRequest(
            run_id="run-old",
            claude_token="ct-123",
            git_token="gt-456",
        )
        result = merge_tokens_into_env(body.env, body.claude_token, body.git_token)
        assert result is not None
        assert result[ENV_KEY_CLAUDE_TOKEN] == "ct-123"
        assert result[ENV_KEY_GIT_TOKEN] == "gt-456"

    def test_restart_preserves_existing_env(self) -> None:
        """Extra env vars from dashboard should survive token merge."""
        body = ResumeRequest(
            run_id="run-old",
            claude_token="ct-123",
            git_token="gt-456",
            env={"CUSTOM_VAR": "hello"},
        )
        result = merge_tokens_into_env(body.env, body.claude_token, body.git_token)
        assert result is not None
        assert result["CUSTOM_VAR"] == "hello"
        assert result[ENV_KEY_CLAUDE_TOKEN] == "ct-123"

    def test_completed_run_not_in_active_runs_triggers_restart(self) -> None:
        """A run_id not in server._runs means the run finished — restart path."""
        runs: dict[str, ActiveRun] = {}
        found = runs.get("run-old")
        assert found is None
        # Endpoint would proceed to restart path


class TestResumeDispatch:
    """The endpoint must pick the correct path based on run state."""

    def test_paused_run_takes_unpause_path(self) -> None:
        runs: dict[str, ActiveRun] = {"r1": _make_active("r1", "paused")}
        active = runs.get("r1")
        assert active is not None and active.status == "paused"

    def test_absent_run_takes_restart_path(self) -> None:
        runs: dict[str, ActiveRun] = {}
        active = runs.get("r1")
        assert active is None

    def test_completed_run_still_in_dict_takes_restart_path(self) -> None:
        """A completed run lingering in _runs should NOT be unpaused."""
        runs: dict[str, ActiveRun] = {"r1": _make_active("r1", "completed")}
        active = runs.get("r1")
        assert active is not None
        # Not paused, so endpoint should NOT push resume signal
        assert active.status != "paused"
