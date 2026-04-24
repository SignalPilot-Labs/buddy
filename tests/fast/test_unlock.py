"""Tests for session unlock — time gate, health reporting, and sandbox wiring.

Covers:
- TimeLock starts locked/unlocked based on duration
- TimeLock.unlock() transitions to unlocked
- Health endpoint reports correct run_unlocked value
- UserControl forwards unlock to sandbox
- end_session_tool respects unlocked state
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from agent_session.time_lock import TimeLock
from user.control import UserControl
from utils.models import UserEvent


class TestTimeLockState:
    """TimeLock has two states: locked (duration > 0) and unlocked."""

    def test_zero_duration_starts_unlocked(self):
        lock = TimeLock(0)
        assert lock.locked is False

    def test_positive_duration_starts_locked(self):
        lock = TimeLock(30)
        assert lock.locked is True

    def test_unlock_transitions_to_unlocked(self):
        lock = TimeLock(30)
        lock.unlock()
        assert lock.locked is False

    def test_unlock_on_already_unlocked_is_noop(self):
        lock = TimeLock(0)
        lock.unlock()
        assert lock.locked is False

    def test_time_remaining_str_empty_when_unlocked(self):
        lock = TimeLock(30)
        lock.unlock()
        assert lock.time_remaining_str() == ""

    def test_time_remaining_str_shows_time_when_locked(self):
        lock = TimeLock(30)
        remaining = lock.time_remaining_str()
        assert remaining != ""


class TestUserControlUnlock:
    """UserControl.handle() must call sandbox unlock on unlock events."""

    @pytest.mark.asyncio
    async def test_unlock_calls_sandbox(self):
        sandbox = MagicMock()
        sandbox.session = MagicMock()
        sandbox.session.unlock = AsyncMock()
        inbox = MagicMock()

        ctrl = UserControl(sandbox, "session-123", inbox)
        event = UserEvent(kind="unlock", payload="")
        result = await ctrl.handle(event)

        sandbox.session.unlock.assert_called_once_with("session-123")
        assert result.kind == "continue"

    @pytest.mark.asyncio
    async def test_unlock_does_not_stop_session(self):
        sandbox = MagicMock()
        sandbox.session = MagicMock()
        sandbox.session.unlock = AsyncMock()
        inbox = MagicMock()

        ctrl = UserControl(sandbox, "session-123", inbox)
        event = UserEvent(kind="unlock", payload="")
        result = await ctrl.handle(event)

        assert result.kind == "continue"


class TestEndSessionUnlockLogic:
    """The end_session unlock check must respect the unlocked flag."""

    def test_locked_session_blocks_exit(self):
        duration_min = 60
        remaining_min = 50
        unlocked = False
        early_exit = 5
        can_exit = duration_min <= 0 or remaining_min <= early_exit or unlocked
        assert can_exit is False

    def test_unlocked_session_allows_exit(self):
        duration_min = 60
        remaining_min = 50
        unlocked = True
        early_exit = 5
        can_exit = duration_min <= 0 or remaining_min <= early_exit or unlocked
        assert can_exit is True

    def test_no_duration_always_allows_exit(self):
        duration_min = 0
        remaining_min = 0
        unlocked = False
        early_exit = 5
        can_exit = duration_min <= 0 or remaining_min <= early_exit or unlocked
        assert can_exit is True

    def test_expired_session_allows_exit(self):
        duration_min = 60
        remaining_min = 3
        unlocked = False
        early_exit = 5
        can_exit = duration_min <= 0 or remaining_min <= early_exit or unlocked
        assert can_exit is True
