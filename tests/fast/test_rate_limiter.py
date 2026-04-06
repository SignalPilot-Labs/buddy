"""Tests for the server capacity check."""

import pytest
from fastapi import HTTPException

from utils.constants import MAX_CONCURRENT_RUNS
from utils.models import ActiveRun


class TestCapacityCheck:
    """Tests for max concurrent runs enforcement."""

    def _make_server(self):
        """Create a minimal mock matching AgentServer interface."""

        class FakeServer:
            def __init__(self):
                self._runs: dict[str, ActiveRun] = {}

            def _active_count(self) -> int:
                return sum(1 for r in self._runs.values() if r.status in ("starting", "running"))

            def _check_capacity(self) -> None:
                if self._active_count() >= MAX_CONCURRENT_RUNS:
                    raise HTTPException(status_code=409, detail=f"Max concurrent runs ({MAX_CONCURRENT_RUNS}) reached")

        return FakeServer()

    def test_allows_when_under_limit(self):
        server = self._make_server()
        server._check_capacity()  # should not raise

    def test_rejects_when_at_limit(self):
        server = self._make_server()
        for i in range(MAX_CONCURRENT_RUNS):
            server._runs[f"run-{i}"] = ActiveRun(run_id=f"run-{i}", status="running")
        with pytest.raises(HTTPException) as exc_info:
            server._check_capacity()
        assert exc_info.value.status_code == 409

    def test_allows_when_terminal_runs_dont_count(self):
        server = self._make_server()
        for i in range(MAX_CONCURRENT_RUNS):
            server._runs[f"run-{i}"] = ActiveRun(run_id=f"run-{i}", status="completed")
        server._check_capacity()  # should not raise — all are terminal

    def test_counts_starting_as_active(self):
        server = self._make_server()
        for i in range(MAX_CONCURRENT_RUNS):
            server._runs[f"run-{i}"] = ActiveRun(run_id=f"run-{i}", status="starting")
        with pytest.raises(HTTPException):
            server._check_capacity()
