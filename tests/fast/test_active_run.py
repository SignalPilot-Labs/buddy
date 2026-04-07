"""Tests for ActiveRun dataclass."""

from utils.models import ActiveRun


class TestActiveRun:
    """Tests for ActiveRun in-memory tracking."""

    def test_default_status_is_starting(self):
        run = ActiveRun()
        assert run.status == "starting"

    def test_run_id_initially_none(self):
        run = ActiveRun()
        assert run.run_id is None

    def test_run_id_can_be_set(self):
        run = ActiveRun(run_id="abc-123")
        assert run.run_id == "abc-123"

    def test_started_at_is_float(self):
        run = ActiveRun()
        assert isinstance(run.started_at, float)
        assert run.started_at > 0

    def test_task_events_session_initially_none(self):
        run = ActiveRun()
        assert run.task is None
        assert run.events is None
        assert run.session is None

    def test_error_message_initially_none(self):
        run = ActiveRun()
        assert run.error_message is None
