"""Tests for reconcile_orphaned_agent_calls.

Verifies:
- Agent tool calls with pre but no post get a synthesized post record
- Agent tool calls that already have post are left alone
- Non-Agent tool calls are ignored
- Returns count of reconciled orphans
- Zero orphans returns 0
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils.db import reconcile_orphaned_agent_calls


def _make_tool_call(tool_use_id: str, phase: str, tool_name: str) -> MagicMock:
    """Build a mock ToolCall row."""
    tc = MagicMock()
    tc.tool_use_id = tool_use_id
    tc.tool_name = tool_name
    tc.phase = phase
    tc.session_id = "sess-1"
    tc.agent_id = "agent-1"
    tc.agent_role = "worker"
    return tc


def _mock_session(pre_tuids: list[str], post_tuids: list[str], orphan_records: list) -> AsyncMock:
    """Build a mock session that returns pre/post tool_use_ids and orphan records."""
    session = AsyncMock()

    pre_result = MagicMock()
    pre_result.all.return_value = [(t,) for t in pre_tuids]

    post_result = MagicMock()
    post_result.all.return_value = [(t,) for t in post_tuids]

    orphan_result = MagicMock()
    orphan_result.scalars.return_value.all.return_value = orphan_records

    session.execute = AsyncMock(side_effect=[pre_result, post_result, orphan_result])
    session.add = MagicMock()
    session.commit = AsyncMock()
    return session


class TestReconcileOrphanedAgentCalls:
    """reconcile_orphaned_agent_calls synthesizes missing post events."""

    @pytest.mark.asyncio
    async def test_synthesizes_post_for_orphan(self) -> None:
        orphan = _make_tool_call("tuid-1", "pre", "Agent")
        session = _mock_session(
            pre_tuids=["tuid-1", "tuid-2"],
            post_tuids=["tuid-2"],
            orphan_records=[orphan],
        )
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=session)
        ctx.__aexit__ = AsyncMock(return_value=False)
        factory = MagicMock(return_value=ctx)

        with patch("utils.db.get_session_factory", return_value=factory):
            count = await reconcile_orphaned_agent_calls("run-1")

        assert count == 1
        assert session.add.call_count == 1
        added = session.add.call_args[0][0]
        assert added.phase == "post"
        assert added.tool_use_id == "tuid-1"
        assert added.output_data == {"reconciled": True}

    @pytest.mark.asyncio
    async def test_no_orphans_returns_zero(self) -> None:
        session = AsyncMock()
        pre_result = MagicMock()
        pre_result.all.return_value = [("tuid-1",)]
        post_result = MagicMock()
        post_result.all.return_value = [("tuid-1",)]
        session.execute = AsyncMock(side_effect=[pre_result, post_result])
        session.add = MagicMock()

        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=session)
        ctx.__aexit__ = AsyncMock(return_value=False)
        factory = MagicMock(return_value=ctx)

        with patch("utils.db.get_session_factory", return_value=factory):
            count = await reconcile_orphaned_agent_calls("run-1")

        assert count == 0
        session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_pre_records_returns_zero(self) -> None:
        session = AsyncMock()
        pre_result = MagicMock()
        pre_result.all.return_value = []
        session.execute = AsyncMock(side_effect=[pre_result])

        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=session)
        ctx.__aexit__ = AsyncMock(return_value=False)
        factory = MagicMock(return_value=ctx)

        with patch("utils.db.get_session_factory", return_value=factory):
            count = await reconcile_orphaned_agent_calls("run-1")

        assert count == 0
