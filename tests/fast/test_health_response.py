"""Tests for HealthResponse and HealthRunEntry models."""

from utils.models import HealthResponse, HealthRunEntry


class TestHealthRunEntry:
    """Tests for HealthRunEntry model fields."""

    def test_minimal_entry(self):
        entry = HealthRunEntry(run_id="abc-123", status="running", started_at=1000.0)
        assert entry.run_id == "abc-123"
        assert entry.status == "running"
        assert entry.elapsed_minutes is None
        assert entry.time_remaining is None
        assert entry.session_unlocked is None

    def test_full_entry(self):
        entry = HealthRunEntry(
            run_id="abc-123",
            status="running",
            started_at=1000.0,
            elapsed_minutes=5.2,
            time_remaining="24m 48s",
            session_unlocked=True,
        )
        assert entry.elapsed_minutes == 5.2
        assert entry.time_remaining == "24m 48s"
        assert entry.session_unlocked is True


class TestHealthResponse:
    """Tests for HealthResponse model."""

    def test_idle_no_runs(self):
        resp = HealthResponse(status="idle", active_runs=0, max_concurrent=10, runs=[])
        assert resp.status == "idle"
        assert resp.active_runs == 0
        assert resp.runs == []

    def test_multiple_runs(self):
        runs = [
            HealthRunEntry(run_id="run-1", status="running", started_at=1000.0, elapsed_minutes=3.0),
            HealthRunEntry(run_id="run-2", status="running", started_at=2000.0, elapsed_minutes=1.0),
        ]
        resp = HealthResponse(status="running", active_runs=2, max_concurrent=10, runs=runs)
        assert resp.active_runs == 2
        assert len(resp.runs) == 2
        assert resp.runs[0].run_id == "run-1"
        assert resp.runs[1].run_id == "run-2"

    def test_serialization_round_trip(self):
        entry = HealthRunEntry(run_id="abc", status="running", started_at=1.0, elapsed_minutes=5.0)
        resp = HealthResponse(status="running", active_runs=1, max_concurrent=10, runs=[entry])
        data = resp.model_dump()
        assert data["runs"][0]["elapsed_minutes"] == 5.0
        restored = HealthResponse.model_validate(data)
        assert restored.runs[0].run_id == "abc"
