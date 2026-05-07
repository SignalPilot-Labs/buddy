"""Tests for stopping a run during starting status (before inbox exists).

Verifies that /stop cancels the execute_run task when inbox is None,
which triggers the cleanup chain (pool.destroy → scancel for Slurm).
"""

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from endpoints.control import register_control_routes
from tests.fast.helpers import make_server
from utils.models import ActiveRun


def _make_client(server: MagicMock) -> TestClient:
    """Build a TestClient with control routes registered."""
    app = FastAPI()
    register_control_routes(app, server)
    return TestClient(app)


class TestStopDuringStarting:
    """Stop must cancel the task when inbox is None (run still starting)."""

    @pytest.mark.asyncio
    async def test_stop_cancels_task_when_no_inbox(self) -> None:
        """Stop with no inbox but a live task must cancel the task."""
        server = make_server()
        active = ActiveRun(run_id="run-1")
        active.task = MagicMock(spec=asyncio.Task)
        active.inbox = None

        client = _make_client(server)
        with patch.object(server, "get_run_or_first", return_value=active):
            resp = client.post("/stop", json={"skip_pr": False})

        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        active.task.cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_uses_inbox_when_available(self) -> None:
        """Stop with inbox available must push to inbox, not cancel task."""
        server = make_server()
        active = ActiveRun(run_id="run-1")
        active.task = MagicMock(spec=asyncio.Task)
        active.inbox = MagicMock()

        client = _make_client(server)
        with patch.object(server, "get_run_or_first", return_value=active):
            resp = client.post("/stop", json={"skip_pr": True})

        assert resp.status_code == 200
        active.inbox.push.assert_called_once_with("stop", "User stop via API")
        active.task.cancel.assert_not_called()
        assert active.skip_pr is True

    @pytest.mark.asyncio
    async def test_stop_409_when_no_inbox_and_no_task(self) -> None:
        """Stop with neither inbox nor task must return 409."""
        server = make_server()
        active = ActiveRun(run_id="run-1")
        active.task = None
        active.inbox = None

        client = _make_client(server)
        with patch.object(server, "get_run_or_first", return_value=active):
            resp = client.post("/stop", json={"skip_pr": False})

        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_stop_sets_skip_pr_before_cancel(self) -> None:
        """skip_pr must be set on ActiveRun before task is cancelled."""
        server = make_server()
        active = ActiveRun(run_id="run-1")
        active.task = MagicMock(spec=asyncio.Task)
        active.inbox = None

        client = _make_client(server)
        with patch.object(server, "get_run_or_first", return_value=active):
            resp = client.post("/stop", json={"skip_pr": True})

        assert resp.status_code == 200
        assert active.skip_pr is True
        active.task.cancel.assert_called_once()
