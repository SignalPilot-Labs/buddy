"""Unit tests for SessionGate — end_round and end_session MCP tools."""

import time
from unittest.mock import AsyncMock, patch

import pytest

from session.gate import SessionGate


def _make_gate(
    duration_minutes: float,
    elapsed_minutes: float,
    unlocked: bool,
) -> tuple[SessionGate, list[dict], list[bool]]:
    """Create a SessionGate, call build_mcp, return gate + captures."""
    emitted: list[dict] = []
    ended: list[bool] = []
    gate = SessionGate(
        run_id="run-1",
        emit=emitted.append,
        mark_ended=lambda: ended.append(True),
        is_unlocked=lambda: unlocked,
    )
    config = {
        "duration_minutes": duration_minutes,
        "start_time": time.time() - (elapsed_minutes * 60),
    }
    gate.build_mcp(config)
    return gate, emitted, ended


class TestEndRound:
    """end_round must mark session ended and emit event."""

    @pytest.mark.asyncio
    async def test_end_round_marks_ended(self) -> None:
        gate, emitted, ended = _make_gate(60, 10, False)
        result = await gate._end_round.handler({"round_summary": "round done", "session_summary": "Test PR"})

        assert len(ended) == 1
        assert emitted[-1]["event"] == "end_round"
        assert emitted[-1]["data"]["round_summary"] == "round done"
        assert emitted[-1]["data"]["session_summary"] == "Test PR"
        assert result["content"][0]["text"] == "Round ended."


class TestEndSessionLocked:
    """end_session must be denied while time lock is active."""

    @pytest.mark.asyncio
    async def test_denied_with_time_remaining(self) -> None:
        gate, emitted, ended = _make_gate(60, 10, False)

        with patch("session.gate.log_audit", new_callable=AsyncMock):
            result = await gate._end_session.handler({"round_summary": "all done", "session_summary": "PR title"})

        assert len(ended) == 0
        assert "SESSION LOCKED" in result["content"][0]["text"]
        assert emitted[-1]["event"] == "end_session_denied"

    @pytest.mark.asyncio
    async def test_allowed_when_time_expired(self) -> None:
        gate, emitted, ended = _make_gate(60, 58, False)

        with patch("session.gate.log_audit", new_callable=AsyncMock):
            result = await gate._end_session.handler({"round_summary": "done", "session_summary": "PR title"})

        assert len(ended) == 1
        assert emitted[-1]["event"] == "end_session"
        assert result["content"][0]["text"] == "Session ended."

    @pytest.mark.asyncio
    async def test_allowed_when_unlocked(self) -> None:
        gate, emitted, ended = _make_gate(60, 10, True)

        with patch("session.gate.log_audit", new_callable=AsyncMock):
            await gate._end_session.handler({"round_summary": "forced", "session_summary": "PR title"})

        assert len(ended) == 1
        assert emitted[-1]["event"] == "end_session"

    @pytest.mark.asyncio
    async def test_allowed_when_zero_duration(self) -> None:
        gate, emitted, ended = _make_gate(0, 0, False)

        with patch("session.gate.log_audit", new_callable=AsyncMock):
            await gate._end_session.handler({"round_summary": "no lock", "session_summary": "PR title"})

        assert len(ended) == 1
