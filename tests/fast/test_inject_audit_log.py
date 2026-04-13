"""Tests for prompt_injected audit log on inject signals.

Verifies that send_control_signal writes a prompt_injected AuditLog row
when the signal is 'inject', so user feedback persists across page refresh.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock, call

from backend.utils import send_control_signal
from db.models import AuditLog, ControlSignal


def _mock_run(status: str) -> MagicMock:
    """Create a mock Run ORM object with given status."""
    run = MagicMock()
    run.status = status
    return run


def _mock_session_tracking_adds(run: MagicMock | None):
    """Create a mock session that records all .add() calls."""
    session_mock = AsyncMock()
    session_mock.get = AsyncMock(return_value=run)
    session_mock.added = []

    def track_add(obj):
        session_mock.added.append(obj)

    session_mock.add = MagicMock(side_effect=track_add)
    session_mock.commit = AsyncMock()

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def context():
        yield session_mock

    return context, session_mock


class TestInjectWritesAuditLog:
    """send_control_signal must write a prompt_injected AuditLog on inject."""

    @pytest.mark.asyncio
    async def test_inject_creates_audit_log_entry(self):
        """Inject signal must add both ControlSignal and AuditLog rows."""
        run = _mock_run("running")
        context, session_mock = _mock_session_tracking_adds(run)
        with (
            patch("backend.utils.session", context),
            patch("backend.utils.agent_request", new_callable=AsyncMock),
        ):
            await send_control_signal("run-1", "inject", {"running"}, "fix the bug", None)

        added_types = [type(obj).__name__ for obj in session_mock.added]
        assert "ControlSignal" in added_types
        assert "AuditLog" in added_types

    @pytest.mark.asyncio
    async def test_inject_audit_has_correct_event_type(self):
        """The AuditLog entry must have event_type='prompt_injected'."""
        run = _mock_run("running")
        context, session_mock = _mock_session_tracking_adds(run)
        with (
            patch("backend.utils.session", context),
            patch("backend.utils.agent_request", new_callable=AsyncMock),
        ):
            await send_control_signal("run-1", "inject", {"running"}, "fix the bug", None)

        audit_entries = [obj for obj in session_mock.added if isinstance(obj, AuditLog)]
        assert len(audit_entries) == 1
        assert audit_entries[0].event_type == "prompt_injected"

    @pytest.mark.asyncio
    async def test_inject_audit_contains_prompt_text(self):
        """The AuditLog details must include the user's prompt."""
        run = _mock_run("running")
        context, session_mock = _mock_session_tracking_adds(run)
        with (
            patch("backend.utils.session", context),
            patch("backend.utils.agent_request", new_callable=AsyncMock),
        ):
            await send_control_signal(
                "run-1", "inject", {"running"}, "use 10px minimum"
            , None)

        audit_entries = [obj for obj in session_mock.added if isinstance(obj, AuditLog)]
        assert audit_entries[0].details["prompt"] == "use 10px minimum"

    @pytest.mark.asyncio
    async def test_inject_audit_has_correct_run_id(self):
        """The AuditLog entry must reference the correct run."""
        run = _mock_run("running")
        context, session_mock = _mock_session_tracking_adds(run)
        with (
            patch("backend.utils.session", context),
            patch("backend.utils.agent_request", new_callable=AsyncMock),
        ):
            await send_control_signal("run-42", "inject", {"running"}, "hello", None)

        audit_entries = [obj for obj in session_mock.added if isinstance(obj, AuditLog)]
        assert audit_entries[0].run_id == "run-42"

    @pytest.mark.asyncio
    async def test_non_inject_signals_skip_audit_log(self):
        """Pause, resume, stop etc. must NOT create prompt_injected audit entries."""
        for signal in ("pause", "resume", "stop", "kill", "unlock"):
            run = _mock_run("running")
            context, session_mock = _mock_session_tracking_adds(run)
            with (
                patch("backend.utils.session", context),
                patch("backend.utils.agent_request", new_callable=AsyncMock),
            ):
                await send_control_signal("run-1", signal, {"running"}, "payload", None)

            audit_entries = [
                obj for obj in session_mock.added if isinstance(obj, AuditLog)
            ]
            assert (
                len(audit_entries) == 0
            ), f"signal '{signal}' should not create AuditLog"

    @pytest.mark.asyncio
    async def test_inject_with_none_payload_skips_audit(self):
        """Inject with no payload should not create an audit entry."""
        run = _mock_run("running")
        context, session_mock = _mock_session_tracking_adds(run)
        with (
            patch("backend.utils.session", context),
            patch("backend.utils.agent_request", new_callable=AsyncMock),
        ):
            await send_control_signal("run-1", "inject", {"running"}, None, None)

        audit_entries = [obj for obj in session_mock.added if isinstance(obj, AuditLog)]
        assert len(audit_entries) == 0
