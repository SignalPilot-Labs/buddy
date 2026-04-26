"""Regression test for spurious idle nudge race condition in RoundRunner._drive_stream.

When both sse_task and idle_task complete in the same asyncio.wait() cycle, the
idle timeout handler must NOT fire if SSE activity has already replaced idle_task.

Root cause: fired_idle was captured before SSE handling, which could cancel and
replace idle_task. The stale fired_idle reference still appeared in `done`, causing
a spurious _handle_idle_timeout call that incremented nudge_count from 0 to 1.

Fix: add identity check `idle_task is fired_idle` so that a replaced idle_task
does not trigger the idle handler.
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

_INBOX_CORO_NAME = "_block_forever"


def _make_run() -> RunContext:
    return RunContext(
        run_id="abcd1234-0000-0000-0000-000000000001",
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


class _SingleEventGen:
    """Async generator that yields one SSE event then blocks indefinitely."""

    def __init__(self, event: dict) -> None:
        self._event = event
        self._yielded = False
        self.aclose_called = False

    def __aiter__(self) -> "_SingleEventGen":
        return self

    async def __anext__(self) -> dict:
        if not self._yielded:
            self._yielded = True
            return self._event
        await asyncio.sleep(9999)
        raise StopAsyncIteration

    async def aclose(self) -> None:
        self.aclose_called = True


async def _block_forever() -> MagicMock:
    """Coroutine that never returns naturally — used as inbox.next_event mock."""
    await asyncio.sleep(9999)
    return MagicMock()


def _is_op_task(task: asyncio.Task) -> bool:
    """Return True if this task wraps the _block_forever inbox coroutine."""
    coro = task.get_coro()
    return hasattr(coro, "__qualname__") and _INBOX_CORO_NAME in coro.__qualname__


class TestRunnerIdleNudgeRace:
    """Idle nudge_count must stay 0 when SSE activity and idle timer fire simultaneously."""

    @pytest.mark.asyncio
    async def test_no_spurious_nudge_when_sse_and_idle_complete_together(self) -> None:
        """nudge_count must not increment when SSE replaces idle_task in the same cycle.

        Simulates the race: asyncio.wait() returns both sse_task and idle_task in
        the done set during the same iteration. After SSE handling creates a new
        idle_task, the old fired_idle must not trigger the idle handler because
        `idle_task is fired_idle` is now False.
        """
        runner = _make_runner()

        # SSE stream yields a text_delta event (non-terminal), then blocks.
        sse_event = {"type": "text_delta", "text": "hello"}
        spy_gen = _SingleEventGen(sse_event)
        runner._sandbox.session.stream_events = MagicMock(return_value=spy_gen)

        # Inbox blocks forever so op_task is never in the done set.
        runner._inbox.next_event = _block_forever  # type: ignore[assignment]

        # Track calls to _handle_idle_timeout by spying on the method.
        nudge_count_calls: list[int] = []
        original_handle = runner._handle_idle_timeout

        async def spy_handle_idle(
            round_number: int,
            nudge_count: int,
            idle_since: float,
            session_id: str,
        ) -> object:
            nudge_count_calls.append(nudge_count)
            return await original_handle(round_number, nudge_count, idle_since, session_id)

        runner._handle_idle_timeout = spy_handle_idle  # type: ignore[method-assign]

        original_wait = asyncio.wait
        call_count = 0

        async def patched_wait(
            tasks: set[asyncio.Task],
            return_when: object,
        ) -> tuple[set[asyncio.Task], set[asyncio.Task]]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Let real wait complete so sse_task finishes (spy_gen yields immediately).
                done_real, pending = await original_wait(
                    tasks, return_when=asyncio.FIRST_COMPLETED
                )
                # Identify op_task (wraps _block_forever) and exclude it from done.
                # Return sse_task AND idle_task as done to simulate the race condition.
                op_task_set = {t for t in tasks if _is_op_task(t)}
                non_op_tasks = tasks - op_task_set
                return non_op_tasks, op_task_set
            # Second iteration: stop the loop.
            raise asyncio.CancelledError

        dispatcher = StreamDispatcher(_make_run(), 1, SubagentTracker(_DEFAULT_RUN_CONFIG))
        control = MagicMock()
        control.handle = AsyncMock(return_value=None)

        with (
            patch("agent_session.runner.asyncio.wait", side_effect=patched_wait),
            pytest.raises(asyncio.CancelledError),
        ):
            await runner._drive_stream(
                session_id="sess-race",
                dispatcher=dispatcher,
                control=control,
                round_number=1,
            )

        # The idle handler must NOT have been called — SSE activity replaced idle_task,
        # so the identity check `idle_task is fired_idle` should be False, skipping
        # the spurious nudge.
        assert nudge_count_calls == [], (
            f"_handle_idle_timeout was called spuriously with nudge_counts={nudge_count_calls}; "
            "SSE activity should have replaced idle_task, skipping the idle handler"
        )
