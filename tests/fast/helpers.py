"""Shared test helpers for tests/fast."""

from unittest.mock import AsyncMock, MagicMock


def make_server() -> MagicMock:
    """Build a mock AgentServer with pool().resolve_start_cmd wired up.

    Returns a fresh MagicMock each call. Used by any test that exercises
    _restart_terminal_run or other code paths that call
    server.pool().resolve_start_cmd().
    """
    server = MagicMock()
    server.execute_run = AsyncMock()
    server.register_run = MagicMock()
    server.remove_run = MagicMock()
    server.pool.return_value.resolve_start_cmd = AsyncMock(return_value="docker run test")
    return server
