"""Tests for capacity counting and run selection using the extracted pure functions."""

import logging
from unittest.mock import MagicMock

import pytest

from utils.constants import MAX_CONCURRENT_RUNS
from utils.models import ActiveRun
from utils.run_helpers import (
    CapacityError,
    RunLookupError,
    active_count,
    check_capacity,
    get_run_or_first,
)


class TestParallelRunCapacity:
    """Tests for active_count(), check_capacity(), and get_run_or_first()."""

    def test_active_count_includes_starting_and_running(self) -> None:
        runs = {
            "r1": ActiveRun(run_id="r1", status="starting"),
            "r2": ActiveRun(run_id="r2", status="running"),
            "r3": ActiveRun(run_id="r3", status="completed"),
        }
        assert active_count(runs) == 2

    def test_active_count_includes_paused(self) -> None:
        runs = {
            "r1": ActiveRun(run_id="r1", status="running"),
            "r2": ActiveRun(run_id="r2", status="paused"),
        }
        assert active_count(runs) == 2

    def test_active_count_excludes_terminal(self) -> None:
        runs = {
            "r1": ActiveRun(run_id="r1", status="completed"),
            "r2": ActiveRun(run_id="r2", status="crashed"),
            "r3": ActiveRun(run_id="r3", status="stopped"),
        }
        assert active_count(runs) == 0

    def test_check_capacity_raises_at_max(self) -> None:
        runs = {
            str(i): ActiveRun(run_id=str(i), status="running")
            for i in range(MAX_CONCURRENT_RUNS)
        }
        with pytest.raises(CapacityError) as exc_info:
            check_capacity(runs, MAX_CONCURRENT_RUNS)
        assert exc_info.value.status_code == 409

    def test_check_capacity_allows_below_max(self) -> None:
        runs = {
            str(i): ActiveRun(run_id=str(i), status="running")
            for i in range(MAX_CONCURRENT_RUNS - 1)
        }
        # Should not raise
        check_capacity(runs, MAX_CONCURRENT_RUNS)

    def test_get_run_or_first_warns_without_run_id(self, caplog: pytest.LogCaptureFixture) -> None:
        active = ActiveRun(run_id="run-abc", status="running")
        active.events = MagicMock()
        runs = {"run-abc": active}

        with caplog.at_level(logging.WARNING, logger="server"):
            result = get_run_or_first(runs, None)

        assert result is active
        assert "get_run_or_first called without run_id" in caplog.text

    def test_get_run_or_first_by_id(self) -> None:
        target = ActiveRun(run_id="run-xyz", status="running")
        runs = {"run-xyz": target}
        result = get_run_or_first(runs, "run-xyz")
        assert result is target

    def test_get_run_or_first_raises_404_for_missing_id(self) -> None:
        runs: dict[str, ActiveRun] = {}
        with pytest.raises(RunLookupError) as exc_info:
            get_run_or_first(runs, "nonexistent")
        assert exc_info.value.status_code == 404

    def test_get_run_or_first_raises_409_when_no_active_run(self) -> None:
        runs: dict[str, ActiveRun] = {}
        with pytest.raises(RunLookupError) as exc_info:
            get_run_or_first(runs, None)
        assert exc_info.value.status_code == 409
