"""Tests for TimeLock — per-run time budget tracker."""

from session.time_lock import TimeLock


class TestTimeLock:
    """Tests for the TimeLock time-budget helper."""

    def test_not_expired_initially(self) -> None:
        lock = TimeLock(30)
        assert not lock.is_expired()

    def test_zero_duration_not_expired(self) -> None:
        lock = TimeLock(0)
        assert not lock.is_expired()

    def test_force_unlock_flag(self) -> None:
        lock = TimeLock(30)
        assert not lock.is_force_unlocked()
        lock.force_unlock()
        assert lock.is_force_unlocked()

    def test_elapsed_minutes_starts_near_zero(self) -> None:
        lock = TimeLock(30)
        elapsed = lock.elapsed_minutes()
        assert 0 <= elapsed < 1

    def test_remaining_minutes_positive(self) -> None:
        lock = TimeLock(30)
        remaining = lock.remaining_minutes()
        assert 29 <= remaining <= 30

    def test_time_remaining_str_has_minute_suffix(self) -> None:
        lock = TimeLock(30)
        assert "m" in lock.time_remaining_str()

    def test_time_remaining_str_empty_for_zero_duration(self) -> None:
        lock = TimeLock(0)
        assert lock.time_remaining_str() == ""
