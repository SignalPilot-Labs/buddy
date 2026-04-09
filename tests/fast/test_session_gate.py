"""Tests for SessionGate time lock logic."""

from tools.session import SessionGate
from utils.models import RunContext


class TestSessionGate:
    """Tests for SessionGate time lock logic."""

    def _make_gate(self, duration_minutes: float) -> SessionGate:
        ctx = RunContext(
            run_id="test-run", agent_role="worker",
            branch_name="test-branch", base_branch="main",
            duration_minutes=duration_minutes, github_repo="owner/repo",
        )
        return SessionGate(ctx)

    def test_locked_initially(self):
        gate = self._make_gate(30)
        assert not gate.is_unlocked()

    def test_unlocked_with_zero_duration(self):
        gate = self._make_gate(0)
        assert gate.is_unlocked()

    def test_force_unlock(self):
        gate = self._make_gate(30)
        assert not gate.is_unlocked()
        gate.force_unlock()
        assert gate.is_unlocked()

    def test_elapsed_minutes(self):
        gate = self._make_gate(30)
        elapsed = gate.elapsed_minutes()
        assert 0 <= elapsed < 1

    def test_time_remaining_str_format(self):
        gate = self._make_gate(30)
        remaining = gate.time_remaining_str()
        assert "m" in remaining

    def test_time_remaining_zero_duration(self):
        gate = self._make_gate(0)
        assert gate.time_remaining_str() == "0m"

    def test_has_ended_initially_false(self):
        gate = self._make_gate(30)
        assert not gate.has_ended()
