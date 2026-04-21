"""Regression test: mark_crashed_runs emits agent_restarted audit events.

When the agent container restarts, in-flight runs are marked as crashed.
Previously the error only appeared in Run.error_message (run tab sidebar).
Now an agent_restarted audit event is emitted per run so the feed shows it too.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils.db import mark_crashed_runs


def _mock_session(run_ids: list[str]) -> MagicMock:
    """Build a mock async session that returns the given run IDs from SELECT."""
    session = AsyncMock()
    # SELECT returns rows of (run_id,)
    select_result = MagicMock()
    select_result.all.return_value = [(rid,) for rid in run_ids]
    session.execute = AsyncMock(side_effect=[select_result, MagicMock()])
    session.add = MagicMock()
    session.commit = AsyncMock()
    return session


class TestMarkCrashedRunsAudit:
    """mark_crashed_runs must emit agent_restarted audit events."""

    @pytest.mark.asyncio
    async def test_emits_audit_event_per_crashed_run(self) -> None:
        run_ids = ["run-1", "run-2"]
        session = _mock_session(run_ids)
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=session)
        ctx.__aexit__ = AsyncMock(return_value=False)
        factory = MagicMock(return_value=ctx)

        with patch("utils.db.get_session_factory", return_value=factory):
            count = await mark_crashed_runs()

        assert count == 2
        # One audit event per run
        assert session.add.call_count == 2
        for call in session.add.call_args_list:
            audit = call[0][0]
            assert audit.event_type == "agent_restarted"
            assert "error" in audit.details

    @pytest.mark.asyncio
    async def test_no_runs_returns_zero(self) -> None:
        session = _mock_session([])
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=session)
        ctx.__aexit__ = AsyncMock(return_value=False)
        factory = MagicMock(return_value=ctx)

        with patch("utils.db.get_session_factory", return_value=factory):
            count = await mark_crashed_runs()

        assert count == 0
        session.add.assert_not_called()
