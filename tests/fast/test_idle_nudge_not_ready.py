"""Regression test: idle nudge skips gracefully when session client not ready.

Previously, if the sandbox returned 503 on interrupt (client not yet initialized),
the error propagated as HTTPStatusError and killed the round. Now the runner
catches SessionNotReadyError and skips the nudge.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sandbox_client.handlers.session import SessionNotReadyError


class TestIdleNudgeNotReady:
    """_handle_idle_timeout must skip the nudge when interrupt raises SessionNotReadyError."""

    @pytest.mark.asyncio
    async def test_idle_nudge_skipped_on_not_ready(self) -> None:
        """When interrupt raises SessionNotReadyError, nudge is skipped and round continues."""
        from agent_session.runner import RoundRunner

        sandbox = MagicMock()
        sandbox.session = MagicMock()
        sandbox.session.interrupt = AsyncMock(
            side_effect=SessionNotReadyError("abc123 client not ready")
        )

        run_ctx = MagicMock()
        run_ctx.run_id = "test-run-id-00000000"
        inbox = MagicMock()
        inbox.push = MagicMock()
        time_lock = MagicMock()
        run_config = MagicMock()
        run_config.session_idle_timeout_sec = 1

        runner = RoundRunner(sandbox, run_ctx, inbox, time_lock, run_config)

        terminal, nudge_count, idle_task = await runner._handle_idle_timeout(
            round_number=1,
            nudge_count=0,
            idle_since=asyncio.get_event_loop().time() - 10,
            session_id="abc123",
        )

        # Round must NOT terminate
        assert terminal is None
        # Nudge count incremented (so we still track attempts)
        assert nudge_count == 1
        # New idle task must be created for backoff
        assert idle_task is not None
        idle_task.cancel()
        # Inject must NOT be pushed (nudge was skipped)
        inbox.push.assert_not_called()

    @pytest.mark.asyncio
    async def test_idle_nudge_proceeds_normally_when_ready(self) -> None:
        """When interrupt succeeds, the nudge inject is pushed."""
        from agent_session.runner import RoundRunner

        sandbox = MagicMock()
        sandbox.session = MagicMock()
        sandbox.session.interrupt = AsyncMock(return_value=None)

        run_ctx = MagicMock()
        run_ctx.run_id = "test-run-id-00000000"
        inbox = MagicMock()
        inbox.push = MagicMock()
        time_lock = MagicMock()
        run_config = MagicMock()
        run_config.session_idle_timeout_sec = 1

        runner = RoundRunner(sandbox, run_ctx, inbox, time_lock, run_config)

        with patch("agent_session.runner.log_audit", new_callable=AsyncMock):
            with patch("agent_session.runner.render_idle_nudge", return_value="nudge text"):
                terminal, nudge_count, idle_task = await runner._handle_idle_timeout(
                    round_number=1,
                    nudge_count=0,
                    idle_since=asyncio.get_event_loop().time() - 10,
                    session_id="abc123",
                )

        assert terminal is None
        assert nudge_count == 1
        assert idle_task is not None
        idle_task.cancel()
        # Inject MUST be pushed when interrupt succeeds
        inbox.push.assert_called_once()
