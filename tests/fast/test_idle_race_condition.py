"""Regression test for idle timeout race condition in RoundRunner._drive_stream.

When both SSE task and idle task complete simultaneously (both in the asyncio.wait
`done` set), the SSE branch replaces `idle_task` with a new task before the idle
check runs. Without the `fired_idle` snapshot, the check `if idle_task in done`
would test the NEW task (not in `done`), silently skipping idle timeout handling.

Fix: capture `fired_idle = idle_task` before the SSE branch.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_session.runner import RoundRunner
from agent_session.stream import StreamDispatcher
from agent_session.tracker import SubagentTracker
from utils.models import RoundResult, RunContext
from utils.run_config import RunAgentConfig

_DEFAULT_RUN_CONFIG = RunAgentConfig(
    max_rounds=128,
    tool_call_timeout_sec=3600,
    session_idle_timeout_sec=120,
    subagent_idle_kill_sec=600,
)


def _make_run() -> RunContext:
    """Create a minimal RunContext for testing."""
    return RunContext(
        run_id="abcd1234-0000-0000-0000-000000000000",
        agent_role="worker",
        github_repo="org/repo",
        branch_name="fix/test",
        base_branch="main",
        duration_minutes=60,
        total_cost=0,
        total_input_tokens=0,
        total_output_tokens=0,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
    )


def _make_runner() -> RoundRunner:
    """Create a RoundRunner with mock dependencies."""
    return RoundRunner(
        sandbox=MagicMock(),
        run=_make_run(),
        inbox=MagicMock(),
        time_lock=MagicMock(),
        run_config=_DEFAULT_RUN_CONFIG,
    )


class TestIdleRaceCondition:
    """Idle timeout must fire even when SSE completes simultaneously."""

    @pytest.mark.asyncio
    async def test_idle_fires_when_sse_and_idle_complete_simultaneously(self) -> None:
        """_handle_idle_timeout is called even when both SSE and idle complete at once.

        Simulates the race by making asyncio.wait return a done set containing
        both the SSE task and the idle task in the first iteration. Verifies that
        _handle_idle_timeout is called despite the SSE branch replacing idle_task.
        """
        runner = _make_runner()

        # Track which handlers were called.
        idle_handle_calls: list[int] = []
        sse_handle_calls: list[int] = []
        iteration = 0

        # On first call: return both tasks as done (race condition scenario).
        # On second call: raise to escape the while True loop.
        async def fake_wait(
            tasks: set[asyncio.Task],
            return_when: object,
        ) -> tuple[set[asyncio.Task], set[asyncio.Task]]:
            nonlocal iteration
            iteration += 1
            if iteration == 1:
                return set(tasks), set()
            raise RuntimeError("stop loop")

        terminal_from_idle = RoundResult(status="complete", session_id="sess-1")

        async def fake_handle_idle_timeout(
            round_number: int,
            nudge_count: int,
            idle_since: float,
            session_id: str,
        ) -> tuple[RoundResult | None, int, asyncio.Task | None]:
            idle_handle_calls.append(1)
            return terminal_from_idle, nudge_count + 1, None

        async def fake_handle_sse_event(
            sse_task: asyncio.Task,
            stream_iter: object,
            dispatcher: object,
            control: object,
            session_id: str,
            round_number: int,
            is_rate_limited: bool,
        ) -> tuple[asyncio.Task, RoundResult | None, bool]:
            sse_handle_calls.append(1)
            # Replace the SSE task (as the real code does) — the new task is NOT in done.
            sse_task.cancel()
            new_task: asyncio.Task[None] = asyncio.create_task(asyncio.sleep(9999))
            return new_task, None, is_rate_limited

        async def fake_handle_user_event(
            op_task: asyncio.Task,
            control: object,
            session_id: str,
        ) -> tuple[asyncio.Task, RoundResult | None]:
            op_task.cancel()
            new_op: asyncio.Task[None] = asyncio.create_task(asyncio.sleep(9999))
            return new_op, None

        stream_mock = MagicMock()
        stream_mock.__aiter__ = MagicMock(return_value=stream_mock)
        stream_mock.aclose = AsyncMock()
        runner._sandbox.session.stream_events = MagicMock(return_value=stream_mock)
        # next_event must return a coroutine (runner wraps it in create_task).
        runner._inbox.next_event = AsyncMock(side_effect=lambda: asyncio.sleep(9999))

        dispatcher = StreamDispatcher(_make_run(), 1, SubagentTracker(_DEFAULT_RUN_CONFIG))

        with (
            patch("agent_session.runner.asyncio.wait", side_effect=fake_wait),
            patch.object(runner, "_handle_idle_timeout", side_effect=fake_handle_idle_timeout),
            patch.object(runner, "_handle_sse_event", side_effect=fake_handle_sse_event),
            patch.object(runner, "_handle_user_event", side_effect=fake_handle_user_event),
        ):
            try:
                await runner._drive_stream(
                    session_id="sess-1",
                    dispatcher=dispatcher,
                    control=MagicMock(),
                    round_number=1,
                )
            except RuntimeError as exc:
                if "stop loop" not in str(exc):
                    raise

        assert len(sse_handle_calls) >= 1, "SSE handler should have been called"
        assert len(idle_handle_calls) >= 1, (
            "_handle_idle_timeout was not called — idle timeout race condition not fixed"
        )
