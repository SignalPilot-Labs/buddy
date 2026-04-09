"""Integration tests for parallel run endpoints.

Tests the endpoint routing and run_id dispatch logic using a mocked AgentServer.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from utils.models import ActiveRun
from endpoints import register_routes


@pytest.fixture
def mock_server():
    """Create a mock AgentServer with the minimum interface."""
    server = MagicMock()
    server._runs = {}
    server._start_timestamps = []
    server._active_count = MagicMock(return_value=0)
    server._check_rate_limit = MagicMock()
    return server


@pytest.fixture
def app(mock_server):
    """Create a FastAPI app with routes registered."""
    app = FastAPI()
    register_routes(app, mock_server)
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for GET /health."""

    def test_idle_when_no_runs(self, client, mock_server):
        mock_server._active_count.return_value = 0
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "idle"
        assert data["active_runs"] == 0

    def test_running_when_active(self, client, mock_server):
        mock_server._active_count.return_value = 2
        resp = client.get("/health")
        data = resp.json()
        assert data["status"] == "running"
        assert data["active_runs"] == 2


class TestStatusEndpoint:
    """Tests for GET /status."""

    def test_returns_all_runs(self, client, mock_server):
        run = ActiveRun(run_id="run-1", status="running")
        mock_server._runs = {"run-1": run}
        mock_server._active_count.return_value = 1
        resp = client.get("/status")
        data = resp.json()
        assert data["active"] == 1
        assert len(data["runs"]) == 1
        assert data["runs"][0]["run_id"] == "run-1"

    def test_returns_specific_run(self, client, mock_server):
        run = ActiveRun(run_id="run-1", status="running")
        mock_server._runs = {"run-1": run}
        mock_server._get_run = MagicMock(return_value=run)
        resp = client.get("/status?run_id=run-1")
        data = resp.json()
        assert data["run_id"] == "run-1"
        assert data["status"] == "running"

    def test_404_for_unknown_run(self, client, mock_server):
        from fastapi import HTTPException
        mock_server._get_run = MagicMock(side_effect=HTTPException(status_code=404, detail="Run not found"))
        resp = client.get("/status?run_id=unknown")
        assert resp.status_code == 404


class TestControlSignals:
    """Tests for control signal endpoints with run_id routing."""

    def _make_running(self, mock_server):
        events = MagicMock()
        events.push = MagicMock()
        run = ActiveRun(run_id="run-1", status="running")
        run.events = events
        mock_server._runs = {"run-1": run}
        mock_server._get_run_or_first = MagicMock(return_value=run)
        return run, events

    def test_stop_with_run_id(self, client, mock_server):
        run, events = self._make_running(mock_server)
        resp = client.post("/stop?run_id=run-1")
        assert resp.status_code == 200
        events.push.assert_called_once_with("stop", "Operator stop via API")

    def test_pause_with_run_id(self, client, mock_server):
        run, events = self._make_running(mock_server)
        resp = client.post("/pause?run_id=run-1")
        assert resp.status_code == 200
        events.push.assert_called_once_with("pause", None)

    def test_resume_with_run_id(self, client, mock_server):
        run, events = self._make_running(mock_server)
        resp = client.post("/resume_signal?run_id=run-1")
        assert resp.status_code == 200
        events.push.assert_called_once_with("resume", None)

    def test_inject_with_run_id(self, client, mock_server):
        run, events = self._make_running(mock_server)
        resp = client.post("/inject?run_id=run-1", json={"payload": "do something"})
        assert resp.status_code == 200
        events.push.assert_called_once_with("inject", "do something")

    def test_unlock_with_run_id(self, client, mock_server):
        run, events = self._make_running(mock_server)
        resp = client.post("/unlock?run_id=run-1")
        assert resp.status_code == 200
        events.push.assert_called_once_with("unlock", None)

    def test_kill_cancels_task(self, client, mock_server):
        run, events = self._make_running(mock_server)
        task = MagicMock()
        task.done.return_value = False
        run.task = task
        resp = client.post("/kill?run_id=run-1")
        assert resp.status_code == 200
        task.cancel.assert_called_once()

    def test_stop_without_events_returns_409(self, client, mock_server):
        from fastapi import HTTPException
        mock_server._get_run_or_first = MagicMock(
            side_effect=HTTPException(status_code=409, detail="No run in progress")
        )
        resp = client.post("/stop")
        assert resp.status_code == 409


class TestCleanup:
    """Tests for POST /cleanup."""

    def test_removes_terminal_runs(self, client, mock_server):
        mock_server._runs = {
            "run-1": ActiveRun(run_id="run-1", status="completed"),
            "run-2": ActiveRun(run_id="run-2", status="running"),
            "run-3": ActiveRun(run_id="run-3", status="crashed"),
        }
        resp = client.post("/cleanup")
        data = resp.json()
        assert data["cleaned"] == 2
        assert "run-2" in mock_server._runs
        assert "run-1" not in mock_server._runs
        assert "run-3" not in mock_server._runs
