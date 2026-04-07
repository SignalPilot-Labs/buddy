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

    def test_unreachable_fallback_shape(self):
        """The dashboard health fallback must match HealthResponse shape."""
        fallback = {"status": "unreachable", "active_runs": 0, "max_concurrent": 0, "runs": []}
        resp = HealthResponse.model_validate(fallback)
        assert resp.status == "unreachable"
        assert resp.runs == []
        assert resp.active_runs == 0

    def test_mixed_run_statuses(self):
        """Health response with runs in different statuses."""
        runs = [
            HealthRunEntry(run_id="r1", status="running", started_at=1.0, elapsed_minutes=10.0),
            HealthRunEntry(run_id="r2", status="paused", started_at=2.0),
            HealthRunEntry(run_id="r3", status="completed", started_at=3.0),
        ]
        resp = HealthResponse(status="running", active_runs=1, max_concurrent=10, runs=runs)
        assert len(resp.runs) == 3
        assert resp.runs[1].elapsed_minutes is None
        assert resp.runs[0].elapsed_minutes == 10.0

    def test_optional_fields_excluded_from_serialization(self):
        """None optional fields should serialize as None, not be omitted."""
        entry = HealthRunEntry(run_id="x", status="running", started_at=1.0)
        data = entry.model_dump()
        assert "elapsed_minutes" in data
        assert data["elapsed_minutes"] is None
        assert data["session_unlocked"] is None
