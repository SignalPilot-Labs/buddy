"""Regression test for time lock grace round.

When a time-locked session expires, the round loop must allow one more
grace round before stopping. This prevents wasting the exploration
investment from round 1 when it overruns the time budget.
"""

from agent_session.time_lock import TimeLock


class TestTimeLockGraceRound:
    """TimeLock tracks grace round state."""

    def test_grace_round_defaults_to_false(self) -> None:
        tl = TimeLock(30)
        assert tl.grace_round_used is False

    def test_grace_round_can_be_set(self) -> None:
        tl = TimeLock(30)
        tl.grace_round_used = True
        assert tl.grace_round_used is True

    def test_unlocked_session_has_grace_round_false(self) -> None:
        tl = TimeLock(0)
        assert tl.grace_round_used is False
