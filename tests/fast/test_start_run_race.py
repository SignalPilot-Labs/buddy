"""Regression test for TOCTOU capacity bypass in start_run.

Bug: ensure_capacity() (capacity check) was separated from register_run()
(slot reservation) by ~38 lines of async operations. Concurrent requests
could both pass the check before either registered, bypassing max_concurrent_runs.

Fix: check_and_reserve_run() atomically checks capacity and registers the
ActiveRun with no await points between check and registration.
"""

from __future__ import annotations

import asyncio
import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("AGENT_INTERNAL_SECRET", "test-secret")
os.environ.setdefault("SANDBOX_INTERNAL_SECRET", "test-sandbox-secret")

with patch("docker.from_env", return_value=MagicMock()):
    from server import AgentServer

from fastapi import HTTPException
from utils.models import ActiveRun


def _make_server_at_capacity_zero() -> AgentServer:
    """Build an AgentServer with max_concurrent_runs=1 and no runs registered."""
    srv = AgentServer.__new__(AgentServer)
    srv._pool = MagicMock()
    srv._runs = {}
    srv._internal_secret = "test-secret"
    return srv


class TestStartRunRace:
    """check_and_reserve_run must prevent concurrent capacity bypass."""

    def test_check_and_reserve_returns_active_run(self) -> None:
        """check_and_reserve_run must return an ActiveRun with the given run_id."""
        srv = _make_server_at_capacity_zero()
        with patch("server.max_concurrent_runs", return_value=2):
            active = srv.check_and_reserve_run("run-abc")

        assert active.run_id == "run-abc"
        assert "run-abc" in srv._runs

    def test_check_and_reserve_registers_before_returning(self) -> None:
        """check_and_reserve_run must register the run before returning."""
        srv = _make_server_at_capacity_zero()
        with patch("server.max_concurrent_runs", return_value=2):
            active = srv.check_and_reserve_run("run-abc")

        assert srv._runs["run-abc"] is active

    def test_check_and_reserve_raises_409_when_at_capacity(self) -> None:
        """check_and_reserve_run must raise HTTPException(409) when at capacity."""
        srv = _make_server_at_capacity_zero()
        existing = ActiveRun(run_id="run-existing")
        srv._runs["run-existing"] = existing

        with patch("server.max_concurrent_runs", return_value=1):
            with pytest.raises(HTTPException) as exc_info:
                srv.check_and_reserve_run("run-new")

        assert exc_info.value.status_code == 409
        assert "run-new" not in srv._runs

    @pytest.mark.asyncio
    async def test_concurrent_requests_only_one_passes_capacity_check(self) -> None:
        """Two concurrent check_and_reserve_run calls with max=1 must let exactly one through.

        Before the fix, ensure_capacity+register_run were separated by awaits, so
        both concurrent requests could pass the check before either registered.
        After the fix, check_and_reserve_run is synchronous (no awaits), so the
        second call sees the first run already registered.
        """
        srv = _make_server_at_capacity_zero()

        results: list[ActiveRun | HTTPException] = []

        async def try_reserve(run_id: str) -> None:
            with patch("server.max_concurrent_runs", return_value=1):
                try:
                    active = srv.check_and_reserve_run(run_id)
                    results.append(active)
                except HTTPException as e:
                    results.append(e)

        await asyncio.gather(
            try_reserve("run-1"),
            try_reserve("run-2"),
        )

        successes = [r for r in results if isinstance(r, ActiveRun)]
        failures = [r for r in results if isinstance(r, HTTPException)]

        assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}"
        assert len(failures) == 1, f"Expected exactly 1 failure (409), got {len(failures)}"
        assert failures[0].status_code == 409

    @pytest.mark.asyncio
    async def test_failed_run_is_removed_from_registry(self) -> None:
        """If async ops fail after reserving, remove_run must clean up the slot."""
        srv = _make_server_at_capacity_zero()

        with patch("server.max_concurrent_runs", return_value=2):
            srv.check_and_reserve_run("run-fail")

        assert "run-fail" in srv._runs

        srv.remove_run("run-fail")

        assert "run-fail" not in srv._runs

    @pytest.mark.asyncio
    async def test_second_run_allowed_after_first_removed(self) -> None:
        """After remove_run, capacity is freed and a new run can be reserved."""
        srv = _make_server_at_capacity_zero()

        with patch("server.max_concurrent_runs", return_value=1):
            srv.check_and_reserve_run("run-1")
            srv.remove_run("run-1")
            active2 = srv.check_and_reserve_run("run-2")

        assert active2.run_id == "run-2"
        assert "run-2" in srv._runs
