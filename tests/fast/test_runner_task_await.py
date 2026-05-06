"""Regression test: all cancelled tasks must be awaited in RoundRunner._drive_stream.

When a round ends (normally, via cancellation, or via exception), the finally block
must cancel AND await op_task and idle_task, not just sse_task.

Without awaiting them, Python emits:
    RuntimeWarning: coroutine '...' was never awaited

Fix: add await blocks for op_task and idle_task (with idle_task is not None guard)
after the existing await sse_task block in the finally clause.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_session.runner import RoundRunner
from agent_session.stream import StreamDispatcher
from agent_session.tracker import SubagentTracker
from utils.models import RunContext
from utils.run_config import RunAgentConfig

_DEFAULT_RUN_CONFIG = RunAgentConfig(
    max_rounds=128,
    tool_call_timeout_sec=3600,
    session_idle_timeout_sec=120,
    subagent_idle_kill_sec=600,
)


def _make_run() -> RunContext:
    return RunContext(
        run_id="abcd1234-0000-0000-0000-000000000099",
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
    return RoundRunner(
        sandbox=MagicMock(),
        run=_make_run(),
        inbox=MagicMock(),
        time_lock=MagicMock(),
        run_config=_DEFAULT_RUN_CONFIG,
    )


class _ExhaustedGen:
    """Async generator that raises StopAsyncIteration immediately (empty stream)."""

    def __init__(self) -> None:
        self.aclose_called = False

    def __aiter__(self) -> "_ExhaustedGen":
        return self

    async def __anext__(self) -> dict:
        raise StopAsyncIteration

    async def aclose(self) -> None:
        self.aclose_called = True


class TestRunnerTaskAwait:
    """All three tasks (sse_task, op_task, idle_task) must be awaited in the finally block."""

    @pytest.mark.asyncio
    async def test_op_task_awaited_on_normal_completion(self) -> None:
        """op_task must be awaited when the round ends via stream exhaustion."""
        runner = _make_runner()
        spy_gen = _ExhaustedGen()
        runner._sandbox.session.stream_events = MagicMock(return_value=spy_gen)

        awaited_tasks: list[str] = []

        async def _blocking_inbox() -> MagicMock:
            try:
                await asyncio.sleep(9999)
                return MagicMock()
            except asyncio.CancelledError:
                awaited_tasks.append("op_task")
                raise

        runner._inbox.next_event = _blocking_inbox  # type: ignore[assignment]

        dispatcher = StreamDispatcher(_make_run(), 1, SubagentTracker(_DEFAULT_RUN_CONFIG))
        control = MagicMock()
        control.handle = AsyncMock(return_value=None)

        result = await runner._drive_stream(
            session_id="sess-await-1",
            dispatcher=dispatcher,
            control=control,
            round_number=1,
        )

        assert result.status == "complete"
        assert "op_task" in awaited_tasks, (
            "op_task was cancelled but never awaited — RuntimeWarning would be emitted"
        )

    @pytest.mark.asyncio
    async def test_idle_task_awaited_on_normal_completion(self) -> None:
        """idle_task must be awaited when the round ends via stream exhaustion."""
        runner = _make_runner()
        spy_gen = _ExhaustedGen()
        runner._sandbox.session.stream_events = MagicMock(return_value=spy_gen)

        idle_awaited: list[bool] = []
        original_sleep = asyncio.sleep

        async def _spy_sleep(delay: float) -> None:
            try:
                await original_sleep(delay)
            except asyncio.CancelledError:
                idle_awaited.append(True)
                raise

        async def _blocking_inbox() -> MagicMock:
            await asyncio.sleep(9999)
            return MagicMock()

        runner._inbox.next_event = _blocking_inbox  # type: ignore[assignment]

        dispatcher = StreamDispatcher(_make_run(), 1, SubagentTracker(_DEFAULT_RUN_CONFIG))
        control = MagicMock()
        control.handle = AsyncMock(return_value=None)

        with patch("agent_session.runner.asyncio.sleep", side_effect=_spy_sleep):
            result = await runner._drive_stream(
                session_id="sess-await-2",
                dispatcher=dispatcher,
                control=control,
                round_number=1,
            )

        assert result.status == "complete"
        # idle_task wraps asyncio.sleep — if awaited after cancel, CancelledError propagates
        assert idle_awaited, (
            "idle_task was cancelled but never awaited — RuntimeWarning would be emitted"
        )

    @pytest.mark.asyncio
    async def test_tasks_done_after_exception(self) -> None:
        """op_task and idle_task must be done (cancelled) after an exception kills the round.

        If a task is cancelled but not awaited, it remains pending, which causes
        RuntimeWarning: coroutine '...' was never awaited when it is GC'd.
        Verifying task.done() after the drive loop confirms that awaiting happened.
        """
        runner = _make_runner()

        class _BlockingGen:
            def __init__(self) -> None:
                self.aclose_called = False

            def __aiter__(self) -> "_BlockingGen":
                return self

            async def __anext__(self) -> dict:
                await asyncio.sleep(9999)
                raise StopAsyncIteration

            async def aclose(self) -> None:
                self.aclose_called = True

        spy_gen = _BlockingGen()
        runner._sandbox.session.stream_events = MagicMock(return_value=spy_gen)

        captured_tasks: dict[str, asyncio.Task] = {}
        original_create_task = asyncio.create_task

        call_count = 0

        def spy_create_task(coro, **kwargs):  # type: ignore[no-untyped-def]
            nonlocal call_count
            task = original_create_task(coro, **kwargs)
            call_count += 1
            if call_count == 1:
                captured_tasks["sse_task"] = task
            elif call_count == 2:
                captured_tasks["op_task"] = task
            elif call_count == 3:
                captured_tasks["idle_task"] = task
            return task

        async def _blocking_inbox() -> MagicMock:
            await asyncio.sleep(9999)
            return MagicMock()

        runner._inbox.next_event = _blocking_inbox  # type: ignore[assignment]

        async def fake_wait(
            tasks: set[asyncio.Task],
            return_when: object,
        ) -> tuple[set[asyncio.Task], set[asyncio.Task]]:
            # Yield control so the tasks can start executing before we raise.
            await asyncio.sleep(0)
            raise RuntimeError("simulated fatal error")

        dispatcher = StreamDispatcher(_make_run(), 1, SubagentTracker(_DEFAULT_RUN_CONFIG))

        with (
            patch("agent_session.runner.asyncio.create_task", side_effect=spy_create_task),
            patch("agent_session.runner.asyncio.wait", side_effect=fake_wait),
            pytest.raises(RuntimeError, match="simulated fatal error"),
        ):
            await runner._drive_stream(
                session_id="sess-await-3",
                dispatcher=dispatcher,
                control=MagicMock(),
                round_number=1,
            )

        # After _drive_stream raises, all tasks must be done (cancelled+awaited).
        # A task that was cancelled but not awaited is still "pending" until the
        # event loop processes the cancellation on the next iteration.
        assert "op_task" in captured_tasks, "op_task was not captured"
        assert "idle_task" in captured_tasks, "idle_task was not captured"
        op_task = captured_tasks["op_task"]
        idle_task = captured_tasks["idle_task"]
        assert op_task.done(), "op_task not done — it was cancelled but never awaited"
        assert idle_task.done(), "idle_task not done — it was cancelled but never awaited"
