"""End-to-end parallel agent flow tests.

Tests realistic multi-step user flows across the /parallel/* endpoints,
covering full lifecycle sequences, multi-run scenarios, and edge cases.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from httpx import ASGITransport

from run_manager import RunSlot, RunManager, MAX_CONCURRENT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_slot(**kwargs):
    defaults = {
        "run_id": "test-run-123",
        "container_name": "buddy-worker-abc12345",
        "status": "running",
        "container_id": "abc123",
    }
    defaults.update(kwargs)
    return RunSlot(**defaults)


def _slot_dict(slot: RunSlot) -> dict:
    """Return a full serialized dict for use in mock return values."""
    return RunManager.to_dict(slot)


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
    """Async test client for the agent FastAPI app."""
    with patch("utils.db.init_db", new_callable=AsyncMock), \
         patch("utils.db.close_db", new_callable=AsyncMock), \
         patch("utils.db.mark_crashed_runs", new_callable=AsyncMock, return_value=0), \
         patch("server._is_worker", return_value=True):
        from server import app
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


# ---------------------------------------------------------------------------
# Class: TestFullLifecycleFlows
# ---------------------------------------------------------------------------

class TestFullLifecycleFlows:
    """End-to-end lifecycle flows: start → signal → cleanup."""

    @pytest.mark.asyncio
    async def test_start_inject_stop_cleanup(self, client, mock_manager):
        """Start a run, inject a prompt, stop it, then clean up."""
        run_id = "flow-run-001"
        slot = _make_slot(run_id=run_id, status="running")

        # --- Step 1: Start ---
        mock_manager.start_run = AsyncMock(return_value=slot)
        resp = await client.post("/parallel/start", json={"prompt": "improve tests"})
        assert resp.status_code == 200
        assert resp.json()["run_id"] == run_id
        mock_manager.start_run.assert_awaited_once()

        # --- Step 2: Inject ---
        mock_manager.get_slot_by_run_id.return_value = slot
        mock_manager.inject_prompt = AsyncMock(return_value={"ok": True, "signal": "inject"})
        resp = await client.post(
            f"/parallel/runs/{run_id}/inject",
            json={"payload": "focus on performance"},
        )
        assert resp.status_code == 200
        mock_manager.inject_prompt.assert_awaited_once_with(
            slot.container_name, {"payload": "focus on performance"}
        )

        # --- Step 3: Stop ---
        mock_manager.stop_run = AsyncMock(return_value={"ok": True, "signal": "stop"})
        resp = await client.post(f"/parallel/runs/{run_id}/stop")
        assert resp.status_code == 200
        mock_manager.stop_run.assert_awaited_once_with(slot.container_name, "Stopped via dashboard")

        # --- Step 4: Cleanup ---
        slot.status = "stopped"
        mock_manager.cleanup_all_finished = MagicMock(return_value=1)
        resp = await client.post("/parallel/cleanup")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["cleaned"] == 1
        mock_manager.cleanup_all_finished.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_pause_resume_stop(self, client, mock_manager):
        """Start a run, pause it, resume it, then stop it."""
        run_id = "flow-run-002"
        slot = _make_slot(run_id=run_id, status="running")
        mock_manager.get_slot_by_run_id.return_value = slot

        # Start
        mock_manager.start_run = AsyncMock(return_value=slot)
        resp = await client.post("/parallel/start", json={})
        assert resp.status_code == 200

        # Pause
        mock_manager.pause_run = AsyncMock(return_value={"ok": True, "signal": "pause"})
        resp = await client.post(f"/parallel/runs/{run_id}/pause")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        mock_manager.pause_run.assert_awaited_once_with(slot.container_name)

        # Simulate state transition to paused
        slot.status = "paused"

        # Resume
        mock_manager.resume_run = AsyncMock(return_value={"ok": True, "signal": "resume"})
        resp = await client.post(f"/parallel/runs/{run_id}/resume")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        mock_manager.resume_run.assert_awaited_once_with(slot.container_name)

        # Simulate transition back to running
        slot.status = "running"

        # Stop
        mock_manager.stop_run = AsyncMock(return_value={"ok": True, "signal": "stop"})
        resp = await client.post(f"/parallel/runs/{run_id}/stop")
        assert resp.status_code == 200
        mock_manager.stop_run.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_start_unlock_complete(self, client, mock_manager):
        """Start a run, then unlock its session gate."""
        run_id = "flow-run-003"
        slot = _make_slot(run_id=run_id, status="running")

        mock_manager.start_run = AsyncMock(return_value=slot)
        resp = await client.post("/parallel/start", json={"prompt": "time-locked task"})
        assert resp.status_code == 200

        mock_manager.get_slot_by_run_id.return_value = slot
        mock_manager.unlock_run = AsyncMock(return_value={"ok": True, "signal": "unlock"})
        resp = await client.post(f"/parallel/runs/{run_id}/unlock")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        mock_manager.unlock_run.assert_awaited_once_with(slot.container_name)

    @pytest.mark.asyncio
    async def test_start_kill_cleanup(self, client, mock_manager):
        """Start a run, kill it immediately, then clean up."""
        run_id = "flow-run-004"
        slot = _make_slot(run_id=run_id, status="running")

        mock_manager.start_run = AsyncMock(return_value=slot)
        resp = await client.post("/parallel/start", json={})
        assert resp.status_code == 200

        # Kill
        mock_manager.get_slot_by_run_id.return_value = slot
        mock_manager.kill_run = AsyncMock(return_value={"ok": True, "signal": "kill"})
        resp = await client.post(f"/parallel/runs/{run_id}/kill")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        mock_manager.kill_run.assert_awaited_once_with(slot.container_name)

        # Simulate killed status
        slot.status = "killed"
        mock_manager.cleanup_all_finished = MagicMock(return_value=1)
        resp = await client.post("/parallel/cleanup")
        assert resp.status_code == 200
        assert resp.json()["cleaned"] == 1


# ---------------------------------------------------------------------------
# Class: TestMultiRunFlows
# ---------------------------------------------------------------------------

class TestMultiRunFlows:
    """Tests for multiple concurrent runs with independent operations."""

    @pytest.mark.asyncio
    async def test_three_concurrent_runs_independent_signals(self, client, mock_manager):
        """Start 3 runs, send different signals to each, verify each got the right one."""
        slots = [
            _make_slot(run_id=f"multi-run-{i}", container_name=f"buddy-worker-{i:08x}", status="running")
            for i in range(3)
        ]

        mock_manager.start_run = AsyncMock(side_effect=slots)
        for slot in slots:
            resp = await client.post("/parallel/start", json={"prompt": f"task {slot.run_id}"})
            assert resp.status_code == 200

        mock_manager.get_slot_by_run_id.side_effect = lambda rid: next(
            (s for s in slots if s.run_id == rid), None
        )

        # Stop run-0
        mock_manager.stop_run = AsyncMock(return_value={"ok": True, "signal": "stop"})
        resp = await client.post("/parallel/runs/multi-run-0/stop")
        assert resp.status_code == 200
        mock_manager.stop_run.assert_awaited_once_with(slots[0].container_name, "Stopped via dashboard")

        # Pause run-1
        mock_manager.pause_run = AsyncMock(return_value={"ok": True, "signal": "pause"})
        resp = await client.post("/parallel/runs/multi-run-1/pause")
        assert resp.status_code == 200
        mock_manager.pause_run.assert_awaited_once_with(slots[1].container_name)

        # Inject into run-2
        mock_manager.inject_prompt = AsyncMock(return_value={"ok": True, "signal": "inject"})
        resp = await client.post(
            "/parallel/runs/multi-run-2/inject",
            json={"payload": "focus on docs"},
        )
        assert resp.status_code == 200
        mock_manager.inject_prompt.assert_awaited_once_with(
            slots[2].container_name, {"payload": "focus on docs"}
        )

    @pytest.mark.asyncio
    async def test_start_runs_stop_one_others_continue(self, client, mock_manager):
        """Start 3 runs, stop one, verify others still reflected in status."""
        slots = [
            _make_slot(run_id=f"cont-run-{i}", container_name=f"buddy-worker-c{i:07x}", status="running")
            for i in range(3)
        ]
        mock_manager.start_run = AsyncMock(side_effect=slots)

        for slot in slots:
            resp = await client.post("/parallel/start", json={})
            assert resp.status_code == 200

        mock_manager.get_slot_by_run_id.side_effect = lambda rid: next(
            (s for s in slots if s.run_id == rid), None
        )
        mock_manager.stop_run = AsyncMock(return_value={"ok": True, "signal": "stop"})
        resp = await client.post("/parallel/runs/cont-run-1/stop")
        assert resp.status_code == 200

        # Simulate state update
        slots[1].status = "stopped"

        # Verify other slots still running
        assert slots[0].status == "running"
        assert slots[2].status == "running"
        assert slots[1].status == "stopped"

        mock_manager.get_all_slots.return_value = slots
        mock_manager.active_count.return_value = 2
        resp = await client.get("/parallel/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["active"] == 2

    @pytest.mark.asyncio
    async def test_fill_to_max_cleanup_start_more(self, client, mock_manager):
        """Fill all slots → 409 on next start → cleanup → new start succeeds."""
        mock_manager.start_run = AsyncMock(
            side_effect=RuntimeError(f"[run_manager] Max concurrent runs ({MAX_CONCURRENT}) reached")
        )
        resp = await client.post("/parallel/start", json={})
        assert resp.status_code == 409
        assert "Max concurrent" in resp.json()["detail"]

        # Simulate cleanup freeing slots
        mock_manager.cleanup_all_finished = MagicMock(return_value=3)
        resp = await client.post("/parallel/cleanup")
        assert resp.status_code == 200
        assert resp.json()["cleaned"] == 3

        # Now start succeeds
        new_slot = _make_slot(run_id="new-run-after-cleanup", status="running")
        mock_manager.start_run = AsyncMock(return_value=new_slot)
        resp = await client.post("/parallel/start", json={"prompt": "fresh start"})
        assert resp.status_code == 200
        assert resp.json()["run_id"] == "new-run-after-cleanup"


# ---------------------------------------------------------------------------
# Class: TestEdgeCases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge cases: nonexistent runs and double signals."""

    @pytest.mark.asyncio
    async def test_signal_to_nonexistent_run(self, client, mock_manager):
        """All signal endpoints return 404 for an unknown run ID."""
        mock_manager.get_slot_by_run_id.return_value = None

        for endpoint in ("stop", "pause", "resume", "kill", "unlock"):
            resp = await client.post(f"/parallel/runs/ghost-run-999/{endpoint}", json={})
            assert resp.status_code == 404, f"Expected 404 for /{endpoint}, got {resp.status_code}"
            assert "not found" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_inject_to_nonexistent_run(self, client, mock_manager):
        """Inject with payload returns 404 for unknown run ID."""
        mock_manager.get_slot_by_run_id.return_value = None
        resp = await client.post(
            "/parallel/runs/ghost-run-999/inject",
            json={"payload": "test"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_kill_completed_run(self, client, mock_manager):
        """Kill endpoint has no status guard — it always calls through."""
        slot = _make_slot(run_id="killed-run", status="killed")
        mock_manager.get_slot_by_run_id.return_value = slot
        mock_manager.kill_run = AsyncMock(return_value={"ok": True, "signal": "kill"})

        resp = await client.post("/parallel/runs/killed-run/kill")
        assert resp.status_code == 200
        mock_manager.kill_run.assert_awaited_once_with(slot.container_name)

    @pytest.mark.asyncio
    async def test_cleanup_returns_count_from_manager(self, client, mock_manager):
        """Cleanup returns whatever count cleanup_all_finished returns."""
        mock_manager.cleanup_all_finished = MagicMock(return_value=0)

        resp = await client.post("/parallel/cleanup")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["cleaned"] == 0

    @pytest.mark.asyncio
    async def test_status_reflects_active_count(self, client, mock_manager):
        """After stopping one of 3 runs, status active count drops to 2."""
        slots = [
            _make_slot(run_id=f"cnt-{i}", container_name=f"buddy-worker-n{i:07x}", status="running")
            for i in range(3)
        ]
        mock_manager.get_slot_by_run_id.side_effect = lambda rid: next(
            (s for s in slots if s.run_id == rid), None
        )
        mock_manager.stop_run = AsyncMock(return_value={"ok": True})

        resp = await client.post("/parallel/runs/cnt-0/stop")
        assert resp.status_code == 200
        slots[0].status = "stopped"

        mock_manager.get_all_slots.return_value = slots
        mock_manager.active_count.return_value = 2

        resp = await client.get("/parallel/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["active"] == 2
        assert data["total_slots"] == 3


# ---------------------------------------------------------------------------
# Class: TestSimplePromptVariations
# ---------------------------------------------------------------------------

class TestSimplePromptVariations:
    """Tests that start parameters are forwarded correctly to RunManager."""

    @pytest.mark.asyncio
    async def test_start_with_no_prompt(self, client, mock_manager):
        """Starting with no prompt succeeds and passes None prompt to manager."""
        slot = _make_slot(run_id="no-prompt-run", status="running", prompt=None)
        mock_manager.start_run = AsyncMock(return_value=slot)

        resp = await client.post("/parallel/start", json={})

        assert resp.status_code == 200
        mock_manager.start_run.assert_awaited_once()
        call_kwargs = mock_manager.start_run.call_args.kwargs
        assert call_kwargs.get("prompt") is None

    @pytest.mark.asyncio
    async def test_start_with_custom_prompt(self, client, mock_manager):
        """Starting with a specific prompt string passes it through to start_run."""
        custom = "Refactor the auth module for better readability"
        slot = _make_slot(run_id="prompt-run", status="running", prompt=custom)
        mock_manager.start_run = AsyncMock(return_value=slot)

        resp = await client.post("/parallel/start", json={"prompt": custom})

        assert resp.status_code == 200
        mock_manager.start_run.assert_awaited_once()
        call_kwargs = mock_manager.start_run.call_args.kwargs
        assert call_kwargs.get("prompt") == custom

    @pytest.mark.asyncio
    async def test_start_with_budget_and_duration(self, client, mock_manager):
        """Budget and duration params are forwarded to start_run."""
        slot = _make_slot(run_id="budget-run", status="running", max_budget_usd=10.0, duration_minutes=60)
        mock_manager.start_run = AsyncMock(return_value=slot)

        resp = await client.post("/parallel/start", json={
            "max_budget_usd": 10.0,
            "duration_minutes": 60,
        })

        assert resp.status_code == 200
        mock_manager.start_run.assert_awaited_once()
        call_kwargs = mock_manager.start_run.call_args.kwargs
        assert call_kwargs.get("max_budget_usd") == 10.0
        assert call_kwargs.get("duration_minutes") == 60

    @pytest.mark.asyncio
    async def test_start_with_different_base_branches(self, client, mock_manager):
        """Each run's base_branch is forwarded to start_run independently."""
        branches = ["main", "develop", "feature/my-feature"]

        for branch in branches:
            slot = _make_slot(run_id=f"branch-run-{branch}", status="running", base_branch=branch)
            mock_manager.start_run = AsyncMock(return_value=slot)

            resp = await client.post("/parallel/start", json={"base_branch": branch})

            assert resp.status_code == 200
            call_kwargs = mock_manager.start_run.call_args.kwargs
            assert call_kwargs.get("base_branch") == branch
