"""Regression test for httpx stream connection leak in RoundRunner._drive_stream.

When a round ends (normally, via cancellation, or via exception), the async
generator `stream_iter` must have `aclose()` called on it. Without this,
the `async with self._http.stream(...)` context in `Session.stream_events()`
is never exited, leaving the httpx connection open.

Fix: `await stream_iter.aclose()` in the `finally` block of `_drive_stream`,
after cancelling the SSE/op/idle tasks.
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


class _SpyAsyncGen:
    """Async generator stand-in that records whether aclose() was awaited."""

    def __init__(self) -> None:
        self.aclose_called = False

    def __aiter__(self) -> "_SpyAsyncGen":
        return self

    async def __anext__(self) -> dict:
        # Block forever so the round only ends via external signal.
        await asyncio.sleep(9999)
        raise StopAsyncIteration

    async def aclose(self) -> None:
        self.aclose_called = True


class TestRunnerStreamCleanup:
    """stream_iter.aclose() must be called when the round ends."""

    @pytest.mark.asyncio
    async def test_aclose_called_on_normal_completion(self) -> None:
        """aclose() is called when the round ends via stream exhaustion (None event)."""
        runner = _make_runner()

        # A spy generator that exhausts immediately (no items) and tracks aclose().
        class _ExhaustedSpyGen:
            def __init__(self) -> None:
                self.aclose_called = False

            def __aiter__(self) -> "_ExhaustedSpyGen":
                return self

            async def __anext__(self) -> dict:
                raise StopAsyncIteration

            async def aclose(self) -> None:
                self.aclose_called = True

        spy = _ExhaustedSpyGen()
        runner._sandbox.session.stream_events = MagicMock(return_value=spy)

        async def _block_forever() -> MagicMock:
            await asyncio.sleep(9999)
            return MagicMock()

        runner._inbox.next_event = _block_forever  # type: ignore[assignment]

        dispatcher = StreamDispatcher(_make_run(), 1, SubagentTracker(_DEFAULT_RUN_CONFIG))
        control = MagicMock()
        control.handle = AsyncMock(return_value=None)

        result = await runner._drive_stream(
            session_id="sess-1",
            dispatcher=dispatcher,
            control=control,
            round_number=1,
        )

        assert result.status == "complete"
        assert spy.aclose_called, "stream_iter.aclose() was not called — httpx connection leaked"

    @pytest.mark.asyncio
    async def test_aclose_called_on_exception(self) -> None:
        """aclose() is called even when an unexpected exception ends the round."""
        runner = _make_runner()
        spy = _SpyAsyncGen()

        runner._sandbox.session.stream_events = MagicMock(return_value=spy)
        runner._inbox.next_event = AsyncMock(side_effect=lambda: asyncio.sleep(9999))

        async def fake_wait(
            tasks: set[asyncio.Task],
            return_when: object,
        ) -> tuple[set[asyncio.Task], set[asyncio.Task]]:
            raise RuntimeError("unexpected failure")

        dispatcher = StreamDispatcher(_make_run(), 1, SubagentTracker(_DEFAULT_RUN_CONFIG))

        with (
            patch("agent_session.runner.asyncio.wait", side_effect=fake_wait),
            pytest.raises(RuntimeError, match="unexpected failure"),
        ):
            await runner._drive_stream(
                session_id="sess-1",
                dispatcher=dispatcher,
                control=MagicMock(),
                round_number=1,
            )

        assert spy.aclose_called, "stream_iter.aclose() was not called after exception — httpx connection leaked"
