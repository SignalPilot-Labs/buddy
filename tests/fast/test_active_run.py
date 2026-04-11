"""Tests for ActiveRun dataclass."""

from utils.models import ActiveRun


class TestActiveRun:
    """Tests for ActiveRun in-memory tracking."""

    def test_default_status_is_starting(self) -> None:
        run = ActiveRun()
        assert run.status == "starting"

    def test_run_id_initially_none(self) -> None:
        run = ActiveRun()
        assert run.run_id is None

    def test_run_id_can_be_set(self) -> None:
        run = ActiveRun(run_id="abc-123")
        assert run.run_id == "abc-123"

    def test_started_at_is_float(self) -> None:
        run = ActiveRun()
        assert isinstance(run.started_at, float)
        assert run.started_at > 0

    def test_task_inbox_time_lock_initially_none(self) -> None:
        run = ActiveRun()
        assert run.task is None
        assert run.inbox is None
        assert run.time_lock is None

    def test_error_message_initially_none(self) -> None:
        run = ActiveRun()
        assert run.error_message is None
