"""Integration tests for parallel run endpoints.

Exercises endpoint routing and run_id dispatch using a fake AgentServer.
"""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from endpoints import register_routes
from utils.models import ActiveRun


@pytest.fixture
def mock_server():
    """Minimal AgentServer stand-in exposing the methods endpoints.py calls."""
    server = MagicMock()
    server.runs.return_value = {}
    server.active_count.return_value = 0
    server.ensure_capacity = MagicMock()
    return server


@pytest.fixture
def app(mock_server):
    """FastAPI app with routes registered against the mock server."""
    instance = FastAPI()
    register_routes(instance, mock_server)
    return instance


@pytest.fixture
def client(app):
    """Test client for the fake app."""
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for GET /health."""

    def test_idle_when_no_runs(self, client, mock_server) -> None:
        mock_server.runs.return_value = {}
        mock_server.active_count.return_value = 0
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "idle"
        assert data["active_runs"] == 0

    def test_running_when_active(self, client, mock_server) -> None:
        run = ActiveRun(run_id="run-1", status="running")
        mock_server.runs.return_value = {"run-1": run}
        mock_server.active_count.return_value = 1
        resp = client.get("/health")
        data = resp.json()
        assert data["status"] == "running"
        assert data["active_runs"] == 1


class TestControlSignals:
    """Tests for control signal endpoints with run_id routing."""

    @staticmethod
    def _make_running(mock_server):
        inbox = MagicMock()
        inbox.push = MagicMock()
        run = ActiveRun(run_id="run-1", status="running")
        run.inbox = inbox
        mock_server.runs.return_value = {"run-1": run}
        mock_server.get_run_or_first = MagicMock(return_value=run)
        return run, inbox

    def test_stop_with_run_id(self, client, mock_server) -> None:
        _, inbox = self._make_running(mock_server)
        resp = client.post("/stop?run_id=run-1")
        assert resp.status_code == 200
        inbox.push.assert_called_once_with("stop", "User stop via API")

    def test_pause_with_run_id(self, client, mock_server) -> None:
        _, inbox = self._make_running(mock_server)
        resp = client.post("/pause?run_id=run-1")
        assert resp.status_code == 200
        inbox.push.assert_called_once_with("pause", "")

    def test_resume_with_run_id(self, client, mock_server) -> None:
        _, inbox = self._make_running(mock_server)
        resp = client.post("/resume?run_id=run-1")
        assert resp.status_code == 200
        inbox.push.assert_called_once_with("resume", "")

    def test_inject_with_run_id(self, client, mock_server) -> None:
        _, inbox = self._make_running(mock_server)
        resp = client.post("/inject?run_id=run-1", json={"payload": "do something"})
        assert resp.status_code == 200
        inbox.push.assert_called_once_with("inject", "do something")

    def test_unlock_with_run_id(self, client, mock_server) -> None:
        run, inbox = self._make_running(mock_server)
        run.time_lock = MagicMock()
        resp = client.post("/unlock?run_id=run-1")
        assert resp.status_code == 200
        assert run.time_lock is not None
        run.time_lock.unlock.assert_called_once()

    def test_kill_cancels_task(self, client, mock_server) -> None:
        run, _ = self._make_running(mock_server)
        task = MagicMock()
        task.done.return_value = False
        run.task = task
        resp = client.post("/kill?run_id=run-1")
        assert resp.status_code == 200
        task.cancel.assert_called_once()

    def test_stop_without_inbox_returns_409(self, client, mock_server) -> None:
        from fastapi import HTTPException

        mock_server.get_run_or_first = MagicMock(
            side_effect=HTTPException(status_code=409, detail="No run in progress"),
        )
        resp = client.post("/stop")
        assert resp.status_code == 409


class TestCleanup:
    """Tests for POST /cleanup."""

    def test_removes_terminal_runs(self, client, mock_server) -> None:
        runs_dict = {
            "run-1": ActiveRun(run_id="run-1", status="completed"),
            "run-2": ActiveRun(run_id="run-2", status="running"),
            "run-3": ActiveRun(run_id="run-3", status="crashed"),
        }
        mock_server.runs.return_value = runs_dict
        resp = client.post("/cleanup")
        data = resp.json()
        assert data["cleaned"] == 2
        assert "run-2" in runs_dict
        assert "run-1" not in runs_dict
        assert "run-3" not in runs_dict
