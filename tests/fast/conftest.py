"""Shared helpers and constants for tests/fast test suite."""

from unittest.mock import AsyncMock, MagicMock

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
    """Create a minimal RunContext for the dispatcher."""
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


def _make_dispatcher() -> tuple[StreamDispatcher, SubagentTracker]:
    """Create a dispatcher and its tracker for testing."""
    tracker = SubagentTracker(_DEFAULT_RUN_CONFIG)
    dispatcher = StreamDispatcher(run=_make_run(), round_number=1, tracker=tracker)
    return dispatcher, tracker


def _make_sandbox(read_return: str | None) -> MagicMock:
    """Build a minimal mock SandboxClient whose file_system.read() returns read_return."""
    sandbox = MagicMock()
    sandbox.file_system.read = AsyncMock(return_value=read_return)
    return sandbox
