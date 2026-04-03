"""Tests for /parallel/* endpoints in buddy/server.py."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from httpx import ASGITransport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_slot(**kwargs):
    from run_manager import RunSlot
    defaults = {
        "run_id": "test-run-123",
        "container_name": "buddy-worker-abc12345",
        "status": "running",
        "container_id": "abc123",
    }
    defaults.update(kwargs)
    return RunSlot(**defaults)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_manager():
    with patch("server._run_manager") as m:
        m.get_all_slots.return_value = []
        m.active_count.return_value = 0
        m.get_slot_by_run_id.return_value = None
        yield m


@pytest_asyncio.fixture
async def client(mock_manager):
    """Create an async test client for the FastAPI app."""
    with patch("utils.db.init_db", new_callable=AsyncMock), \
         patch("utils.db.close_db", new_callable=AsyncMock), \
         patch("utils.db.mark_crashed_runs", new_callable=AsyncMock, return_value=0), \
         patch("server._is_worker", return_value=True):
        from server import app
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_idle(client):
    """Returns idle status when no run is active."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "idle"
    assert data["current_run_id"] is None


# ---------------------------------------------------------------------------
# Parallel status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parallel_status(client, mock_manager):
    """Returns a status summary of all parallel slots."""
    slot = _make_slot()
    mock_manager.get_all_slots.return_value = [slot]
    mock_manager.active_count.return_value = 1

    resp = await client.get("/parallel/status")

    assert resp.status_code == 200
    data = resp.json()
    assert "total_slots" in data
    assert "active" in data
    assert data["max_concurrent"] == 10


@pytest.mark.asyncio
async def test_parallel_runs_empty(client, mock_manager):
    """Returns an empty list when no runs exist."""
    mock_manager.get_all_slots.return_value = []
    resp = await client.get("/parallel/runs")
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# Parallel start
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parallel_start_success(client, mock_manager):
    """Mocks RunManager.start_run and verifies a successful response."""
    slot = _make_slot(run_id="new-run-456", status="running")
    mock_manager.start_run = AsyncMock(return_value=slot)

    resp = await client.post("/parallel/start", json={
        "prompt": "Improve tests",
        "max_budget_usd": 5.0,
        "duration_minutes": 30,
    })

    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == "new-run-456"
    mock_manager.start_run.assert_awaited_once()


@pytest.mark.asyncio
async def test_parallel_start_max_concurrent(client, mock_manager):
    """Returns 409 when maximum concurrent runs are already active."""
    mock_manager.start_run = AsyncMock(
        side_effect=RuntimeError("[run_manager] Max concurrent runs (10) reached")
    )
    resp = await client.post("/parallel/start", json={})
    assert resp.status_code == 409
    assert "Max concurrent" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Parallel run — get
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parallel_run_get(client, mock_manager):
    """Returns slot data for a known run ID."""
    slot = _make_slot()
    mock_manager.get_slot_by_run_id.return_value = slot

    resp = await client.get("/parallel/runs/test-run-123")

    assert resp.status_code == 200
    assert resp.json()["run_id"] == "test-run-123"


@pytest.mark.asyncio
async def test_parallel_run_get_not_found(client, mock_manager):
    """Returns 404 when run ID does not exist."""
    mock_manager.get_slot_by_run_id.return_value = None
    resp = await client.get("/parallel/runs/nonexistent-run")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Parallel run — stop
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parallel_run_stop(client, mock_manager):
    """Sends a stop signal to a running run."""
    slot = _make_slot(status="running")
    mock_manager.get_slot_by_run_id.return_value = slot
    mock_manager.stop_run = AsyncMock(return_value={"ok": True, "signal": "stop"})

    resp = await client.post("/parallel/runs/test-run-123/stop")
    assert resp.status_code == 200
    mock_manager.stop_run.assert_awaited_once_with(slot.container_name, "Stopped via dashboard")


@pytest.mark.asyncio
async def test_parallel_run_stop_not_found(client, mock_manager):
    """Returns 404 when run is not found."""
    mock_manager.get_slot_by_run_id.return_value = None

    resp = await client.post("/parallel/runs/ghost-run/stop")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Parallel run — kill
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parallel_run_kill(client, mock_manager):
    """Kills a parallel run immediately."""
    slot = _make_slot(status="running")
    mock_manager.get_slot_by_run_id.return_value = slot
    mock_manager.kill_run = AsyncMock(return_value={"ok": True, "signal": "kill"})

    resp = await client.post("/parallel/runs/test-run-123/kill")
    assert resp.status_code == 200
    mock_manager.kill_run.assert_awaited_once_with(slot.container_name)


@pytest.mark.asyncio
async def test_parallel_run_kill_not_found(client, mock_manager):
    """Returns 404 when run ID does not exist for kill."""
    mock_manager.get_slot_by_run_id.return_value = None
    resp = await client.post("/parallel/runs/ghost-run/kill")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Parallel run — pause
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parallel_run_pause(client, mock_manager):
    """Pauses a running parallel run."""
    slot = _make_slot(status="running")
    mock_manager.get_slot_by_run_id.return_value = slot
    mock_manager.pause_run = AsyncMock(return_value={"ok": True, "signal": "pause"})

    resp = await client.post("/parallel/runs/test-run-123/pause")
    assert resp.status_code == 200
    mock_manager.pause_run.assert_awaited_once_with(slot.container_name)


@pytest.mark.asyncio
async def test_parallel_run_pause_not_found(client, mock_manager):
    """Returns 404 when run is not found for pause."""
    mock_manager.get_slot_by_run_id.return_value = None
    resp = await client.post("/parallel/runs/ghost-run/pause")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Parallel run — resume
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parallel_run_resume(client, mock_manager):
    """Resumes a paused parallel run."""
    slot = _make_slot(status="paused")
    mock_manager.get_slot_by_run_id.return_value = slot
    mock_manager.resume_run = AsyncMock(return_value={"ok": True, "signal": "resume"})

    resp = await client.post("/parallel/runs/test-run-123/resume")
    assert resp.status_code == 200
    mock_manager.resume_run.assert_awaited_once_with(slot.container_name)


# ---------------------------------------------------------------------------
# Parallel run — inject
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parallel_run_inject(client, mock_manager):
    """Injects a prompt into a parallel run."""
    slot = _make_slot(status="running")
    mock_manager.get_slot_by_run_id.return_value = slot
    mock_manager.inject_prompt = AsyncMock(return_value={"ok": True, "signal": "inject"})

    resp = await client.post(
        "/parallel/runs/test-run-123/inject",
        json={"payload": "focus on tests"},
    )
    assert resp.status_code == 200
    mock_manager.inject_prompt.assert_awaited_once_with(
        slot.container_name, {"payload": "focus on tests"}
    )


@pytest.mark.asyncio
async def test_parallel_run_inject_not_found(client, mock_manager):
    """Returns 404 when run is not found for inject."""
    mock_manager.get_slot_by_run_id.return_value = None
    resp = await client.post("/parallel/runs/ghost-run/inject", json={"payload": "test"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Parallel run — unlock
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parallel_run_unlock(client, mock_manager):
    """Unlocks the session gate for a parallel run."""
    slot = _make_slot(status="running")
    mock_manager.get_slot_by_run_id.return_value = slot
    mock_manager.unlock_run = AsyncMock(return_value={"ok": True, "signal": "unlock"})

    resp = await client.post("/parallel/runs/test-run-123/unlock")
    assert resp.status_code == 200
    mock_manager.unlock_run.assert_awaited_once_with(slot.container_name)


# ---------------------------------------------------------------------------
# Parallel cleanup
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parallel_cleanup(client, mock_manager):
    """Calls cleanup_all_finished and reports how many were cleaned."""
    mock_manager.cleanup_all_finished = MagicMock(return_value=2)

    resp = await client.post("/parallel/cleanup")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["cleaned"] == 2
    mock_manager.cleanup_all_finished.assert_called_once()


# ---------------------------------------------------------------------------
# Parallel run health
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parallel_run_health(client, mock_manager):
    """Gets health data from a worker container."""
    slot = _make_slot(status="running")
    mock_manager.get_slot_by_run_id.return_value = slot
    mock_manager.get_worker_health = AsyncMock(return_value={
        "status": "running",
        "current_run_id": "test-run-123",
    })

    resp = await client.get("/parallel/runs/test-run-123/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "running"
    mock_manager.get_worker_health.assert_awaited_once_with(slot.container_name)


@pytest.mark.asyncio
async def test_parallel_run_health_not_found(client, mock_manager):
    """Returns 404 when run does not exist for health check."""
    mock_manager.get_slot_by_run_id.return_value = None
    resp = await client.get("/parallel/runs/ghost-run/health")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_parallel_run_health_unreachable(client, mock_manager):
    """Returns 502 when worker cannot be contacted."""
    slot = _make_slot(status="running")
    mock_manager.get_slot_by_run_id.return_value = slot
    mock_manager.get_worker_health = AsyncMock(
        side_effect=Exception("connection refused")
    )

    resp = await client.get("/parallel/runs/test-run-123/health")
    assert resp.status_code == 502
