"""Regression test for truthiness check on round_cost skipping zero-cost rebasing.

Previously `if round_cost:` used Python truthiness, so `0.0` (falsy) caused
the rebasing block to be skipped entirely. The fix uses `if round_cost is not None:`
so zero-cost results still trigger cost correction and token baseline rebasing.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from tests.fast.conftest import _make_dispatcher


class TestStreamZeroCostRebase:
    """StreamDispatcher must rebase cost even when SDK reports zero total_cost_usd."""

    @pytest.mark.asyncio
    async def test_zero_cost_triggers_rebase(self) -> None:
        """result event with total_cost_usd=0.0 must set total_cost to cost_baseline."""
        dispatcher, _ = _make_dispatcher()

        # Simulate some accumulated cost from token counting before result arrives
        dispatcher._run.total_cost = 0.05
        dispatcher._cost_baseline = 0.0  # baseline at round start was 0

        with patch("agent_session.stream.db.save_session_id", new=AsyncMock()):
            with patch("agent_session.stream.db.update_run_cost", new=AsyncMock()):
                await dispatcher.dispatch(
                    {
                        "event": "result",
                        "data": {
                            "session_id": "session-abc",
                            "total_cost_usd": 0.0,
                        },
                    }
                )

        # cost_baseline (0.0) + round_cost (0.0) = 0.0, not the accumulated 0.05
        assert dispatcher._run.total_cost == 0.0, (
            "total_cost must be rebased to cost_baseline + 0.0, not left at accumulated estimate"
        )

    @pytest.mark.asyncio
    async def test_none_cost_does_not_rebase(self) -> None:
        """result event with no total_cost_usd must NOT overwrite accumulated estimate."""
        dispatcher, _ = _make_dispatcher()

        # Simulate accumulated cost estimate
        dispatcher._run.total_cost = 0.05
        dispatcher._cost_baseline = 0.0

        with patch("agent_session.stream.db.save_session_id", new=AsyncMock()):
            with patch("agent_session.stream.db.update_run_cost", new=AsyncMock()):
                await dispatcher.dispatch(
                    {
                        "event": "result",
                        "data": {
                            "session_id": "session-abc",
                            # total_cost_usd absent — SDK didn't report cost
                        },
                    }
                )

        # No rebase: accumulated estimate is preserved
        assert dispatcher._run.total_cost == 0.05, (
            "total_cost must not change when total_cost_usd is absent from result"
        )

    @pytest.mark.asyncio
    async def test_nonzero_cost_still_rebases(self) -> None:
        """result event with total_cost_usd=0.12 must correctly rebase total_cost."""
        dispatcher, _ = _make_dispatcher()

        dispatcher._run.total_cost = 0.05
        dispatcher._cost_baseline = 0.0

        with patch("agent_session.stream.db.save_session_id", new=AsyncMock()):
            with patch("agent_session.stream.db.update_run_cost", new=AsyncMock()):
                await dispatcher.dispatch(
                    {
                        "event": "result",
                        "data": {
                            "session_id": "session-abc",
                            "total_cost_usd": 0.12,
                        },
                    }
                )

        assert dispatcher._run.total_cost == pytest.approx(0.12)
