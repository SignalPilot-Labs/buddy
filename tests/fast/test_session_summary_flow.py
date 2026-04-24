"""Tests for session_summary propagation through the round lifecycle.

Covers:
- StreamSignal carries session_summary from end_round and end_session events
- RoundResult carries session_summary from StreamSignal
- _apply_signal propagates session_summary to RoundResult
- _commit_and_push_round passes session_summary as pr_title to metadata
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_session.runner import RoundRunner
from utils.models import RoundResult, StreamSignal, RunContext
from utils.run_config import RunAgentConfig


def _make_run() -> RunContext:
    return RunContext(
        run_id="test-run-id",
        agent_role="worker",
        branch_name="autofyn/test",
        base_branch="main",
        duration_minutes=0,
        github_repo="owner/repo",
        total_cost=0.0,
        total_input_tokens=0,
        total_output_tokens=0,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
    )


_DEFAULT_RUN_CONFIG = RunAgentConfig(
    max_rounds=128,
    tool_call_timeout_sec=3600,
    session_idle_timeout_sec=120,
    subagent_idle_kill_sec=600,
)


class TestStreamSignalSessionSummary:
    """StreamSignal must carry session_summary."""

    def test_round_complete_with_session_summary(self) -> None:
        signal = StreamSignal(
            kind="round_complete",
            round_summary="Fix auth bug",
            session_summary="Auth hardening",
        )
        assert signal.round_summary == "Fix auth bug"
        assert signal.session_summary == "Auth hardening"

    def test_run_ended_with_session_summary(self) -> None:
        signal = StreamSignal(
            kind="run_ended",
            round_summary="Final cleanup",
            session_summary="Optimize compression to 60%",
        )
        assert signal.session_summary == "Optimize compression to 60%"

    def test_session_summary_defaults_to_none(self) -> None:
        signal = StreamSignal(kind="round_complete", round_summary="done")
        assert signal.session_summary is None


class TestRoundResultSessionSummary:
    """RoundResult must carry session_summary."""

    def test_round_result_with_session_summary(self) -> None:
        result = RoundResult(
            status="complete",
            session_id="sess-1",
            round_summary="Fix auth",
            session_summary="Auth hardening PR",
        )
        assert result.session_summary == "Auth hardening PR"

    def test_round_result_defaults_to_none(self) -> None:
        result = RoundResult(status="complete", session_id="sess-1")
        assert result.session_summary is None


class TestApplySignalPropagation:
    """_apply_signal must propagate session_summary to RoundResult."""

    @pytest.mark.asyncio
    async def test_round_complete_propagates_session_summary(self) -> None:
        runner = RoundRunner(
            sandbox=MagicMock(),
            run=_make_run(),
            inbox=MagicMock(),
            time_lock=MagicMock(),
            run_config=_DEFAULT_RUN_CONFIG,
        )
        signal = StreamSignal(
            kind="round_complete",
            round_summary="Fix auth",
            session_summary="Auth hardening",
        )
        control = MagicMock()
        result = await runner._apply_signal(signal, "sess-1", control, 1)

        assert result is not None
        assert result.round_summary == "Fix auth"
        assert result.session_summary == "Auth hardening"

    @pytest.mark.asyncio
    async def test_run_ended_propagates_session_summary(self) -> None:
        runner = RoundRunner(
            sandbox=MagicMock(),
            run=_make_run(),
            inbox=MagicMock(),
            time_lock=MagicMock(),
            run_config=_DEFAULT_RUN_CONFIG,
        )
        signal = StreamSignal(
            kind="run_ended",
            round_summary="Final round",
            session_summary="Compression optimized to 60%",
        )
        control = MagicMock()
        result = await runner._apply_signal(signal, "sess-1", control, 1)

        assert result is not None
        assert result.status == "ended"
        assert result.session_summary == "Compression optimized to 60%"


class TestCommitAndPushSessionSummary:
    """_commit_and_push_round must pass session_summary as pr_title."""

    @pytest.mark.asyncio
    async def test_session_summary_becomes_pr_title(self) -> None:
        from lifecycle.round_handlers import _commit_and_push_round

        sandbox = MagicMock()
        sandbox.repo.save = AsyncMock(
            return_value=MagicMock(committed=True, pushed=True)
        )
        metadata_store = MagicMock()
        metadata_store.record_round = AsyncMock()

        await _commit_and_push_round(
            sandbox=sandbox,
            run=_make_run(),
            round_number=3,
            metadata_store=metadata_store,
            end_round_summary="Fix unicode regression",
            session_summary="Optimize compression",
            exec_timeout=60,
        )

        metadata_store.record_round.assert_called_once()
        call_kwargs = metadata_store.record_round.call_args
        assert call_kwargs.kwargs["pr_title"] == "Optimize compression"

    @pytest.mark.asyncio
    async def test_none_session_summary_passes_none_pr_title(self) -> None:
        from lifecycle.round_handlers import _commit_and_push_round

        sandbox = MagicMock()
        sandbox.repo.save = AsyncMock(
            return_value=MagicMock(committed=True, pushed=True)
        )
        metadata_store = MagicMock()
        metadata_store.record_round = AsyncMock()

        await _commit_and_push_round(
            sandbox=sandbox,
            run=_make_run(),
            round_number=1,
            metadata_store=metadata_store,
            end_round_summary="Setup env",
            session_summary=None,
            exec_timeout=60,
        )

        call_kwargs = metadata_store.record_round.call_args
        assert call_kwargs.kwargs["pr_title"] is None
