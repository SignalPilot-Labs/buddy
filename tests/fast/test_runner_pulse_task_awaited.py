"""Regression test: RoundRunner.run() awaits cancelled pulse task.

Bug: pulse task was cancelled but not awaited in the finally block of
RoundRunner.run() (line 108), leaving a zombie task that could emit
ResourceWarning messages.

Fix: After pulse.cancel(), await the task and swallow CancelledError,
matching the pattern from DockerLocalBackend._destroy_by_key() (Round 4)
and ConnectorServer._destroy() (Round 5).
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_session.runner import RoundRunner
from utils.models import RoundResult, RunContext
from utils.run_config import RunAgentConfig


_RUN_CONFIG = RunAgentConfig(
    max_rounds=128,
    tool_call_timeout_sec=3600,
    session_idle_timeout_sec=120,
    subagent_idle_kill_sec=600,
)


def _make_run() -> RunContext:
    """Minimal RunContext for testing."""
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
    """Build a RoundRunner with fully mocked dependencies."""
    sandbox = MagicMock()
    sandbox.session.start = AsyncMock(return_value="sess-001")
    sandbox.session.stop = AsyncMock()
    sandbox.session.delete = AsyncMock()

    inbox = MagicMock()
    inbox.next_event = AsyncMock(side_effect=asyncio.CancelledError)

    time_lock = MagicMock()
    time_lock.elapsed_minutes = MagicMock(return_value=0.5)

    return RoundRunner(
        sandbox=sandbox,
        run=_make_run(),
        inbox=inbox,
        time_lock=time_lock,
        run_config=_RUN_CONFIG,
    )


class TestRunnerPulseTaskAwaited:
    """Verify that RoundRunner.run() awaits the cancelled pulse task."""

    @pytest.mark.asyncio
    async def test_pulse_task_is_done_after_run_completes(self) -> None:
        """Pulse task must be done (not pending) when run() returns."""
        runner = _make_runner()

        captured_tasks: list[asyncio.Task] = []

        # Intercept asyncio.create_task to track the pulse task specifically.
        # The pulse task is the first create_task call inside run().
        original_create_task = asyncio.create_task
        call_count = 0

        def _tracking_create_task(coro, **kwargs):  # type: ignore[no-untyped-def]
            nonlocal call_count
            task = original_create_task(coro, **kwargs)
            call_count += 1
            if call_count == 1:
                # First create_task in run() is the pulse task.
                captured_tasks.append(task)
            return task

        async def _immediate_return(*args: object, **kwargs: object) -> RoundResult:
            """Stub _drive_stream to return immediately (normal completion)."""
            return RoundResult(status="complete", session_id="sess-001")

        with (
            patch.object(runner, "_drive_stream", new=_immediate_return),
            patch("agent_session.runner.asyncio.create_task", side_effect=_tracking_create_task),
            patch("agent_session.runner.log_audit", new=AsyncMock()),
        ):
            result = await runner.run(options={}, initial_prompt="Go.", round_number=1)

        assert result.status == "complete"
        assert len(captured_tasks) == 1, "Expected exactly one captured pulse task"
        pulse_task = captured_tasks[0]
        assert pulse_task.done(), "Pulse task must be done (cancelled+awaited) after run() returns"

    @pytest.mark.asyncio
    async def test_pulse_task_is_done_after_exception(self) -> None:
        """Pulse task must be done even when _drive_stream raises an exception."""
        runner = _make_runner()

        captured_tasks: list[asyncio.Task] = []
        original_create_task = asyncio.create_task
        call_count = 0

        def _tracking_create_task(coro, **kwargs):  # type: ignore[no-untyped-def]
            nonlocal call_count
            task = original_create_task(coro, **kwargs)
            call_count += 1
            if call_count == 1:
                captured_tasks.append(task)
            return task

        async def _raise_on_drive(*args: object, **kwargs: object) -> RoundResult:
            """Stub _drive_stream to raise a generic error."""
            raise RuntimeError("simulated fatal error")

        with (
            patch.object(runner, "_drive_stream", new=_raise_on_drive),
            patch("agent_session.runner.asyncio.create_task", side_effect=_tracking_create_task),
            patch("agent_session.runner.log_audit", new=AsyncMock()),
        ):
            result = await runner.run(options={}, initial_prompt="Go.", round_number=1)

        assert result.status == "error"
        assert len(captured_tasks) == 1
        pulse_task = captured_tasks[0]
        assert pulse_task.done(), "Pulse task must be done after exception in run()"

    @pytest.mark.asyncio
    async def test_pulse_task_is_cancelled_not_just_requested(self) -> None:
        """Verify the pulse task's cancel() was actually invoked (task is cancelled)."""
        runner = _make_runner()

        long_running_started = asyncio.Event()

        async def _long_pulse(*args: object, **kwargs: object) -> None:
            """Simulate a long-running pulse watchdog."""
            long_running_started.set()
            await asyncio.sleep(60)

        pulse_task_ref: list[asyncio.Task] = []
        original_create_task = asyncio.create_task
        call_count = 0

        def _tracking_create_task(coro, **kwargs):  # type: ignore[no-untyped-def]
            nonlocal call_count
            task = original_create_task(coro, **kwargs)
            call_count += 1
            if call_count == 1:
                pulse_task_ref.append(task)
            return task

        async def _immediate_return(*args: object, **kwargs: object) -> RoundResult:
            await long_running_started.wait()
            return RoundResult(status="complete", session_id="sess-001")

        with (
            patch.object(runner, "_drive_stream", new=_immediate_return),
            patch("agent_session.runner.asyncio.create_task", side_effect=_tracking_create_task),
            patch("agent_session.runner.PulseWatchdog") as mock_wd_cls,
            patch("agent_session.runner.log_audit", new=AsyncMock()),
        ):
            mock_wd = MagicMock()
            mock_wd.run = _long_pulse
            mock_wd_cls.return_value = mock_wd

            result = await runner.run(options={}, initial_prompt="Go.", round_number=1)

        assert result.status == "complete"
        assert len(pulse_task_ref) == 1
        pulse_task = pulse_task_ref[0]
        assert pulse_task.done(), "Pulse task must be done after run() returns"
        assert pulse_task.cancelled(), "Pulse task must be in cancelled state"
