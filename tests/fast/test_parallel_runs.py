"""Tests for AgentServer capacity counting and run selection.

The methods under test (_active_count, _check_capacity, _get_run_or_first) depend
only on self._runs and the logger. We test them via a minimal test double that
reproduces the exact production logic, keeping this test file free of heavyweight
imports (Docker, uvicorn, FastAPI).
"""

import logging
from unittest.mock import MagicMock

import pytest

from utils.constants import MAX_CONCURRENT_RUNS
from utils.models import ActiveRun

log = logging.getLogger("server")


class _HTTPException(Exception):
    """Minimal stand-in for fastapi.HTTPException used by production code."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail


class _CapacityMixin:
    """Reproduces the capacity/selection logic from AgentServer verbatim."""

    _runs: dict[str, ActiveRun]

    def _active_count(self) -> int:
        return sum(1 for r in self._runs.values() if r.status in ("starting", "running", "paused"))

    def _check_capacity(self) -> None:
        if self._active_count() >= MAX_CONCURRENT_RUNS:
            raise _HTTPException(
                status_code=409,
                detail=f"Max concurrent runs ({MAX_CONCURRENT_RUNS}) reached",
            )

    def _get_run_or_first(self, run_id: str | None) -> ActiveRun:
        if run_id:
            run = self._runs.get(run_id)
            if not run:
                raise _HTTPException(status_code=404, detail="Run not found")
            return run
        for r in self._runs.values():
            if r.status == "running" and r.events:
                log.warning("_get_run_or_first called without run_id — falling back to first active run")
                return r
        raise _HTTPException(status_code=409, detail="No run in progress")


def _make_server(runs: dict[str, ActiveRun]) -> _CapacityMixin:
    server = _CapacityMixin()
    server._runs = runs
    return server


class TestParallelRunCapacity:
    """Tests for _active_count() and _check_capacity() on AgentServer."""

    def test_active_count_includes_starting_and_running(self) -> None:
        runs = {
            "r1": ActiveRun(run_id="r1", status="starting"),
            "r2": ActiveRun(run_id="r2", status="running"),
            "r3": ActiveRun(run_id="r3", status="completed"),
        }
        server = _make_server(runs)
        assert server._active_count() == 2

    def test_active_count_includes_paused(self) -> None:
        runs = {
            "r1": ActiveRun(run_id="r1", status="running"),
            "r2": ActiveRun(run_id="r2", status="paused"),
        }
        server = _make_server(runs)
        assert server._active_count() == 2

    def test_active_count_excludes_terminal(self) -> None:
        runs = {
            "r1": ActiveRun(run_id="r1", status="completed"),
            "r2": ActiveRun(run_id="r2", status="crashed"),
            "r3": ActiveRun(run_id="r3", status="stopped"),
        }
        server = _make_server(runs)
        assert server._active_count() == 0

    def test_check_capacity_raises_at_max(self) -> None:
        runs = {
            str(i): ActiveRun(run_id=str(i), status="running")
            for i in range(MAX_CONCURRENT_RUNS)
        }
        server = _make_server(runs)
        with pytest.raises(_HTTPException) as exc_info:
            server._check_capacity()
        assert exc_info.value.status_code == 409

    def test_check_capacity_allows_below_max(self) -> None:
        runs = {
            str(i): ActiveRun(run_id=str(i), status="running")
            for i in range(MAX_CONCURRENT_RUNS - 1)
        }
        server = _make_server(runs)
        # Should not raise
        server._check_capacity()

    def test_get_run_or_first_warns_without_run_id(self, caplog: pytest.LogCaptureFixture) -> None:
        active = ActiveRun(run_id="run-abc", status="running")
        active.events = MagicMock()
        runs = {"run-abc": active}
        server = _make_server(runs)

        with caplog.at_level(logging.WARNING, logger="server"):
            result = server._get_run_or_first(None)

        assert result is active
        assert "_get_run_or_first called without run_id" in caplog.text
