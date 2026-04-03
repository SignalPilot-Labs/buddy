"""Tests for the dashboard's parallel run proxy endpoints (/api/parallel/*)."""

import pytest
import pytest_asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from httpx import ASGITransport

# Make dashboard package importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "dashboard"))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client():
    """Create an async test client for the dashboard FastAPI app."""
    with patch("db.connection.connect", new_callable=AsyncMock), \
         patch("db.connection.close", new_callable=AsyncMock), \
         patch("backend.utils.autofill_settings", new_callable=AsyncMock), \
         patch("backend.auth._load_api_key", new_callable=AsyncMock, return_value=None):
        from backend.app import app
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.fixture
def mock_agent_request():
    """Mock dashboard.backend.utils.agent_request at the function level."""
    with patch("backend.endpoints.agent_request") as mock:
        yield mock


@pytest.fixture
def mock_read_credentials():
    """Mock dashboard.backend.utils.read_credentials."""
    with patch("backend.endpoints.read_credentials", new_callable=AsyncMock, return_value={}) as mock:
        yield mock


# ---------------------------------------------------------------------------
# List parallel runs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_parallel_runs_success(client, mock_agent_request, mock_read_credentials):
    """Proxies GET /parallel/runs to agent and returns the response."""
    expected = [{"run_id": "run-1", "status": "running"}]
    mock_agent_request.return_value = expected

    resp = await client.get("/api/parallel/runs")

    assert resp.status_code == 200
    data = resp.json()
    assert data == expected
    mock_agent_request.assert_called_once()
    call_args = mock_agent_request.call_args
    assert call_args[0][0] == "GET"
    assert "/parallel/runs" in call_args[0][1]


@pytest.mark.asyncio
async def test_list_parallel_runs_agent_down(client, mock_agent_request, mock_read_credentials):
    """Returns fallback empty list when the agent is unreachable."""
    mock_agent_request.return_value = []

    resp = await client.get("/api/parallel/runs")

    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# Start parallel run
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_parallel_run_success(client, mock_agent_request, mock_read_credentials):
    """Forwards start request to agent and returns its response."""
    mock_agent_request.return_value = {"run_id": "par-abc", "status": "running"}
    mock_read_credentials.return_value = {"claude_token": "test-token"}

    resp = await client.post(
        "/api/parallel/start",
        json={"prompt": "improve tests", "max_budget_usd": 1.0, "base_branch": "main"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == "par-abc"
    mock_agent_request.assert_called_once()
    call_args = mock_agent_request.call_args
    assert call_args[0][0] == "POST"
    assert "/parallel/start" in call_args[0][1]


@pytest.mark.asyncio
async def test_start_parallel_run_agent_error(client, mock_agent_request, mock_read_credentials):
    """Returns 502 when the agent request raises a connection error."""
    from fastapi import HTTPException
    mock_agent_request.side_effect = HTTPException(status_code=502, detail="Agent unreachable")

    resp = await client.post("/api/parallel/start", json={})

    assert resp.status_code == 502
    assert "unreachable" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_start_parallel_run_conflict(client, mock_agent_request, mock_read_credentials):
    """Returns 409 when the agent reports a conflict."""
    from fastapi import HTTPException
    mock_agent_request.side_effect = HTTPException(status_code=409, detail="Max concurrent runs reached")

    resp = await client.post("/api/parallel/start", json={})

    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Parallel status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parallel_status_success(client, mock_agent_request, mock_read_credentials):
    """Returns the status payload from the agent."""
    mock_agent_request.return_value = {"total_slots": 4, "active": 1, "max_concurrent": 10, "slots": []}

    resp = await client.get("/api/parallel/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_slots"] == 4
    assert data["active"] == 1
    mock_agent_request.assert_called_once()
    assert "/parallel/status" in mock_agent_request.call_args[0][1]


@pytest.mark.asyncio
async def test_parallel_status_agent_down(client, mock_agent_request, mock_read_credentials):
    """Returns the fallback status dict when the agent cannot be reached."""
    mock_agent_request.return_value = {
        "total_slots": 0, "active": 0, "max_concurrent": 10, "slots": []
    }

    resp = await client.get("/api/parallel/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["max_concurrent"] == 10


# ---------------------------------------------------------------------------
# Run operations
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stop_parallel_run(client, mock_agent_request, mock_read_credentials):
    """Proxies stop signal to agent for the given run ID."""
    mock_agent_request.return_value = {"ok": True}

    resp = await client.post("/api/parallel/runs/run-1/stop")

    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    mock_agent_request.assert_called_once()
    assert "run-1/stop" in mock_agent_request.call_args[0][1]


@pytest.mark.asyncio
async def test_kill_parallel_run(client, mock_agent_request, mock_read_credentials):
    """Proxies kill signal to agent for the given run ID."""
    mock_agent_request.return_value = {"ok": True}

    resp = await client.post("/api/parallel/runs/run-2/kill")

    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert "run-2/kill" in mock_agent_request.call_args[0][1]


@pytest.mark.asyncio
async def test_pause_parallel_run(client, mock_agent_request, mock_read_credentials):
    """Proxies pause signal to agent for the given run ID."""
    mock_agent_request.return_value = {"ok": True, "signal": "pause"}

    resp = await client.post("/api/parallel/runs/run-3/pause")

    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert "run-3/pause" in mock_agent_request.call_args[0][1]


@pytest.mark.asyncio
async def test_resume_parallel_run(client, mock_agent_request, mock_read_credentials):
    """Proxies resume signal to agent for the given run ID."""
    mock_agent_request.return_value = {"ok": True, "signal": "resume"}

    resp = await client.post("/api/parallel/runs/run-4/resume")

    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert "run-4/resume" in mock_agent_request.call_args[0][1]


@pytest.mark.asyncio
async def test_inject_parallel_run(client, mock_agent_request, mock_read_credentials):
    """Proxies inject with payload to agent for the given run ID."""
    mock_agent_request.return_value = {"ok": True, "signal": "inject"}

    resp = await client.post(
        "/api/parallel/runs/run-5/inject",
        json={"payload": "please focus on performance"},
    )

    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    mock_agent_request.assert_called_once()
    assert "run-5/inject" in mock_agent_request.call_args[0][1]
    body_arg = mock_agent_request.call_args[0][3]  # json_body is 4th positional arg
    assert body_arg == {"payload": "please focus on performance"}


@pytest.mark.asyncio
async def test_unlock_parallel_run(client, mock_agent_request, mock_read_credentials):
    """Proxies unlock signal to agent for the given run ID."""
    mock_agent_request.return_value = {"ok": True, "signal": "unlock"}

    resp = await client.post("/api/parallel/runs/run-6/unlock")

    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert "run-6/unlock" in mock_agent_request.call_args[0][1]


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cleanup_parallel(client, mock_agent_request, mock_read_credentials):
    """Proxies cleanup request to agent and returns its response."""
    mock_agent_request.return_value = {"ok": True, "cleaned": 3}

    resp = await client.post("/api/parallel/cleanup")

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["cleaned"] == 3
    mock_agent_request.assert_called_once()
    assert "/parallel/cleanup" in mock_agent_request.call_args[0][1]


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parallel_stop_agent_unreachable(client, mock_agent_request, mock_read_credentials):
    """Returns 502 when the agent is unreachable for stop signal."""
    from fastapi import HTTPException
    mock_agent_request.side_effect = HTTPException(status_code=502, detail="Agent unreachable")

    resp = await client.post("/api/parallel/runs/some-run-id/stop")

    assert resp.status_code == 502
    assert "unreachable" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_parallel_inject_agent_unreachable(client, mock_agent_request, mock_read_credentials):
    """Returns 502 when the agent is unreachable for inject."""
    from fastapi import HTTPException
    mock_agent_request.side_effect = HTTPException(status_code=502, detail="Agent unreachable")

    resp = await client.post(
        "/api/parallel/runs/some-run-id/inject",
        json={"payload": "focus on docs"},
    )

    assert resp.status_code == 502
    assert "unreachable" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_parallel_cleanup_agent_unreachable(client, mock_agent_request, mock_read_credentials):
    """Returns fallback value when agent is down for cleanup."""
    mock_agent_request.return_value = {"ok": True, "cleaned": 0}

    resp = await client.post("/api/parallel/cleanup")

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Per-run endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parallel_get_run(client, mock_agent_request, mock_read_credentials):
    """GET /api/parallel/runs/{run_id} returns a single run's data."""
    mock_agent_request.return_value = {"run_id": "run-abc", "status": "running"}

    resp = await client.get("/api/parallel/runs/run-abc")

    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == "run-abc"
    mock_agent_request.assert_called_once()
    assert "run-abc" in mock_agent_request.call_args[0][1]


@pytest.mark.asyncio
async def test_parallel_run_health(client, mock_agent_request, mock_read_credentials):
    """GET /api/parallel/runs/{run_id}/health returns health data."""
    mock_agent_request.return_value = {"status": "running", "current_run_id": "run-abc"}

    resp = await client.get("/api/parallel/runs/run-abc/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "running"
    mock_agent_request.assert_called_once()
    assert "run-abc/health" in mock_agent_request.call_args[0][1]
