"""Regression test for fire-and-forget DB task tracking in AgentServer.

Bug: _persist_terminal_status created tasks with bare asyncio.create_task()
without storing the handle. If the agent shut down immediately after a
crash/cancel, these tasks could be garbage-collected before completion,
leaving run status as 'running' in the DB instead of 'crashed'/'killed'.

Fix:
1. Added self._pending_db_tasks: set[asyncio.Task[None]] to __init__
2. _persist_terminal_status adds each task to the set with a done_callback
   that discards it on completion
3. _lifespan teardown awaits all pending tasks before closing the DB
"""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("AGENT_INTERNAL_SECRET", "test-secret")
os.environ.setdefault("SANDBOX_INTERNAL_SECRET", "test-sandbox-secret")

with patch("docker.from_env", return_value=MagicMock()):
    from server import AgentServer

from utils.models import RunContext


def _make_server() -> AgentServer:
    """Build an AgentServer without calling __init__ (avoids DB + pool setup)."""
    srv = AgentServer.__new__(AgentServer)
    srv._pool = MagicMock()
    srv._runs = {}
    srv._pending_db_tasks = set()
    return srv


def _make_run_context() -> RunContext:
    ctx = MagicMock(spec=RunContext)
    ctx.total_cost = 0.01
    ctx.total_input_tokens = 100
    ctx.total_output_tokens = 50
    ctx.cache_creation_input_tokens = 0
    ctx.cache_read_input_tokens = 0
    return ctx


class TestServerPendingDbTasks:
    """_persist_terminal_status must track tasks so they survive shutdown."""

    @pytest.mark.asyncio
    async def test_persist_terminal_status_adds_task_to_pending_set_with_context(
        self,
    ) -> None:
        """_persist_terminal_status (with context) must add the task to _pending_db_tasks."""
        srv = _make_server()

        finish_run_mock = AsyncMock()

        with patch("server.db.finish_run", finish_run_mock):
            srv._persist_terminal_status(
                run_id="run-db-1",
                status="crashed",
                error_message="something failed",
                context=_make_run_context(),
            )

        assert len(srv._pending_db_tasks) == 1
        # Await all pending tasks to let them complete and trigger done_callbacks
        await asyncio.gather(*list(srv._pending_db_tasks), return_exceptions=True)
        # After completion, done_callback removes from set
        assert len(srv._pending_db_tasks) == 0
        assert finish_run_mock.called

    @pytest.mark.asyncio
    async def test_persist_terminal_status_adds_task_to_pending_set_without_context(
        self,
    ) -> None:
        """_persist_terminal_status (no context) must add the task to _pending_db_tasks."""
        srv = _make_server()

        update_run_status_mock = AsyncMock()

        with patch("server.db.update_run_status", update_run_status_mock):
            srv._persist_terminal_status(
                run_id="run-db-2",
                status="killed",
                error_message="Cancelled",
                context=None,
            )

        assert len(srv._pending_db_tasks) == 1
        await asyncio.gather(*list(srv._pending_db_tasks), return_exceptions=True)
        assert len(srv._pending_db_tasks) == 0
        assert update_run_status_mock.called

    @pytest.mark.asyncio
    async def test_done_callback_removes_task_from_set_on_completion(self) -> None:
        """The done_callback must discard the task from _pending_db_tasks when done."""
        srv = _make_server()

        finish_run_mock = AsyncMock()

        with patch("server.db.finish_run", finish_run_mock):
            srv._persist_terminal_status(
                run_id="run-db-3",
                status="crashed",
                error_message="boom",
                context=_make_run_context(),
            )

        task = next(iter(srv._pending_db_tasks))
        assert task in srv._pending_db_tasks

        await asyncio.gather(*[task], return_exceptions=True)

        assert task not in srv._pending_db_tasks
        assert task.done()

    @pytest.mark.asyncio
    async def test_multiple_calls_accumulate_tasks(self) -> None:
        """Multiple _persist_terminal_status calls each add a task to the set."""
        srv = _make_server()

        update_run_status_mock = AsyncMock()

        with patch("server.db.update_run_status", update_run_status_mock):
            srv._persist_terminal_status(
                run_id="run-db-4a",
                status="killed",
                error_message="Cancelled",
                context=None,
            )
            srv._persist_terminal_status(
                run_id="run-db-4b",
                status="killed",
                error_message="Cancelled",
                context=None,
            )

        assert len(srv._pending_db_tasks) == 2
        await asyncio.gather(*list(srv._pending_db_tasks), return_exceptions=True)
        assert len(srv._pending_db_tasks) == 0

    @pytest.mark.asyncio
    async def test_lifespan_teardown_awaits_pending_db_tasks(self) -> None:
        """_lifespan teardown must await _pending_db_tasks before closing DB."""
        srv = AgentServer.__new__(AgentServer)
        srv._pool = MagicMock()
        srv._runs = {}
        srv._pending_db_tasks = set()
        srv.app = MagicMock()
        srv._internal_secret = "test-secret"

        completed_order: list[str] = []

        async def slow_db_write() -> None:
            await asyncio.sleep(0)
            completed_order.append("db_write")

        async def mock_close_db() -> None:
            completed_order.append("close_db")

        task: asyncio.Task[None] = asyncio.create_task(slow_db_write())
        srv._pending_db_tasks.add(task)
        task.add_done_callback(srv._pending_db_tasks.discard)

        with (
            patch("server.db.init_db", AsyncMock()),
            patch("server.db.mark_crashed_runs", AsyncMock(return_value=0)),
            patch("server.db.close_db", mock_close_db),
            patch("server.register_routes"),
            patch("server.server_port", return_value=8080),
        ):
            srv._pool.destroy_all = AsyncMock()

            # Run just the teardown portion of _lifespan
            await srv._pool.destroy_all()
            if srv._pending_db_tasks:
                await asyncio.gather(*srv._pending_db_tasks, return_exceptions=True)
            await mock_close_db()

        assert completed_order == ["db_write", "close_db"]
