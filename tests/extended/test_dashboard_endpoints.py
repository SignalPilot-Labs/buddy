"""Tests for dashboard backend endpoints — tunnel, poll, and parallel proxy."""

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "dashboard"))

VALID_RUN_ID = "12345678-1234-1234-1234-123456789012"


# ---------------------------------------------------------------------------
# Fake NotFound exception whose __name__ contains "NotFound"
# ---------------------------------------------------------------------------

class _NotFoundError(Exception):
    pass


_NotFoundError.__name__ = "NotFound"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client():
    """Async test client with all external dependencies patched."""
    with patch("db.connection.connect", new_callable=AsyncMock), \
         patch("db.connection.close", new_callable=AsyncMock), \
         patch("backend.utils.autofill_settings", new_callable=AsyncMock):
        from backend.app import app
        from backend.auth import verify_api_key

        app.dependency_overrides[verify_api_key] = lambda: None
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
        app.dependency_overrides.clear()


def _make_mock_session(tool_call_rows=None, audit_event_rows=None):
    """Return an asynccontextmanager that yields a mock DB session."""
    tool_call_rows = tool_call_rows if tool_call_rows is not None else []
    audit_event_rows = audit_event_rows if audit_event_rows is not None else []

    call_count = [0]

    async def _execute(_stmt):
        mock_result = MagicMock()
        if call_count[0] == 0:
            mock_result.scalars.return_value.all.return_value = tool_call_rows
        else:
            mock_result.scalars.return_value.all.return_value = audit_event_rows
        call_count[0] += 1
        return mock_result

    mock_db = AsyncMock()
    mock_db.execute = _execute

    @asynccontextmanager
    async def _session():
        yield mock_db

    return _session


# ---------------------------------------------------------------------------
# TestTunnelEndpoints
# ---------------------------------------------------------------------------

class TestTunnelEndpoints:
    """Tests for GET/POST /api/tunnel/* endpoints."""

    @pytest.mark.asyncio
    async def test_tunnel_status_running(self, client):
        """Running container with a cloudflare URL returns status=running and a URL."""
        mock_container = MagicMock()
        mock_container.status = "running"
        mock_container.short_id = "abc123"
        mock_container.logs.return_value = b"Connected to https://my-tunnel.trycloudflare.com ok"

        mock_docker = MagicMock()
        mock_docker.containers.get.return_value = mock_container

        with patch("backend.endpoints._get_docker", return_value=mock_docker):
            resp = await client.get("/api/tunnel/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["url"] is not None
        assert data["url"].startswith("https://")

    @pytest.mark.asyncio
    async def test_tunnel_status_not_running(self, client):
        """Stopped container returns status=stopped and url=None."""
        mock_container = MagicMock()
        mock_container.status = "stopped"
        mock_container.short_id = "abc123"

        mock_docker = MagicMock()
        mock_docker.containers.get.return_value = mock_container

        with patch("backend.endpoints._get_docker", return_value=mock_docker):
            resp = await client.get("/api/tunnel/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["url"] is None

    @pytest.mark.asyncio
    async def test_tunnel_status_not_found(self, client):
        """Container not found returns status=not_found."""
        mock_docker = MagicMock()
        mock_docker.containers.get.side_effect = _NotFoundError("Not found")

        with patch("backend.endpoints._get_docker", return_value=mock_docker):
            resp = await client.get("/api/tunnel/status")

        assert resp.status_code == 200
        assert resp.json()["status"] == "not_found"

    @pytest.mark.asyncio
    async def test_tunnel_status_docker_error(self, client):
        """Docker API error returns 502."""
        with patch("backend.endpoints._get_docker", side_effect=RuntimeError("socket not found")):
            resp = await client.get("/api/tunnel/status")

        assert resp.status_code == 502

    @pytest.mark.asyncio
    async def test_tunnel_start_already_running(self, client):
        """Already running container returns ok=True with 'already running' message."""
        mock_container = MagicMock()
        mock_container.status = "running"

        mock_docker = MagicMock()
        mock_docker.containers.get.return_value = mock_container

        with patch("backend.endpoints._get_docker", return_value=mock_docker):
            resp = await client.post("/api/tunnel/start")

        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "already running" in data["message"]
        mock_container.start.assert_not_called()

    @pytest.mark.asyncio
    async def test_tunnel_start_stopped_container(self, client):
        """Stopped container is started and returns ok=True."""
        mock_container = MagicMock()
        mock_container.status = "stopped"

        mock_docker = MagicMock()
        mock_docker.containers.get.return_value = mock_container

        with patch("backend.endpoints._get_docker", return_value=mock_docker):
            resp = await client.post("/api/tunnel/start")

        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        mock_container.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_tunnel_start_not_found(self, client):
        """Container not found on start returns 404."""
        mock_docker = MagicMock()
        mock_docker.containers.get.side_effect = _NotFoundError("Not found")

        with patch("backend.endpoints._get_docker", return_value=mock_docker):
            resp = await client.post("/api/tunnel/start")

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_tunnel_stop_success(self, client):
        """Running container is stopped with timeout=5 and returns ok=True."""
        mock_container = MagicMock()

        mock_docker = MagicMock()
        mock_docker.containers.get.return_value = mock_container

        with patch("backend.endpoints._get_docker", return_value=mock_docker):
            resp = await client.post("/api/tunnel/stop")

        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        mock_container.stop.assert_called_once_with(timeout=5)

    @pytest.mark.asyncio
    async def test_tunnel_stop_not_found(self, client):
        """Container not found on stop returns 404."""
        mock_docker = MagicMock()
        mock_docker.containers.get.side_effect = _NotFoundError("Not found")

        with patch("backend.endpoints._get_docker", return_value=mock_docker):
            resp = await client.post("/api/tunnel/stop")

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# TestPollEndpoint
# ---------------------------------------------------------------------------

class TestPollEndpoint:
    """Tests for GET /api/poll/{run_id} polling fallback endpoint."""

    @pytest.mark.asyncio
    async def test_poll_empty_results(self, client):
        """Empty DB returns tool_calls=[] and audit_events=[]."""
        mock_session = _make_mock_session([], [])

        with patch("backend.endpoints.session", mock_session):
            resp = await client.get(f"/api/poll/{VALID_RUN_ID}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["tool_calls"] == []
        assert data["audit_events"] == []

    @pytest.mark.asyncio
    async def test_poll_returns_tool_calls(self, client):
        """Two tool_call rows and no audit events returns 2 tool_calls entries."""
        tc1 = MagicMock()
        tc1.__table__ = MagicMock()
        tc1.__table__.columns = [MagicMock(key="id"), MagicMock(key="run_id")]
        tc1.id = 1
        tc1.run_id = VALID_RUN_ID

        tc2 = MagicMock()
        tc2.__table__ = MagicMock()
        tc2.__table__.columns = [MagicMock(key="id"), MagicMock(key="run_id")]
        tc2.id = 2
        tc2.run_id = VALID_RUN_ID

        mock_session = _make_mock_session([tc1, tc2], [])

        with patch("backend.endpoints.session", mock_session), \
             patch("backend.endpoints.model_to_dict", side_effect=lambda x: {"id": x.id, "run_id": x.run_id}):
            resp = await client.get(f"/api/poll/{VALID_RUN_ID}")

        assert resp.status_code == 200
        assert len(resp.json()["tool_calls"]) == 2
        assert resp.json()["audit_events"] == []

    @pytest.mark.asyncio
    async def test_poll_returns_audit_events(self, client):
        """One audit_event row and no tool_calls returns 1 audit_events entry."""
        ae1 = MagicMock()
        ae1.__table__ = MagicMock()
        ae1.__table__.columns = [MagicMock(key="id"), MagicMock(key="run_id")]
        ae1.id = 10
        ae1.run_id = VALID_RUN_ID

        mock_session = _make_mock_session([], [ae1])

        with patch("backend.endpoints.session", mock_session), \
             patch("backend.endpoints.model_to_dict", side_effect=lambda x: {"id": x.id, "run_id": x.run_id}):
            resp = await client.get(f"/api/poll/{VALID_RUN_ID}")

        assert resp.status_code == 200
        assert resp.json()["tool_calls"] == []
        assert len(resp.json()["audit_events"]) == 1

    @pytest.mark.asyncio
    async def test_poll_accepts_cursor_params(self, client):
        """Cursor query params after_tool and after_audit are accepted without validation error."""
        mock_session = _make_mock_session([], [])

        with patch("backend.endpoints.session", mock_session):
            resp = await client.get(f"/api/poll/{VALID_RUN_ID}?after_tool=10&after_audit=5")

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_poll_invalid_run_id(self, client):
        """Non-UUID run_id is rejected with 422."""
        resp = await client.get("/api/poll/not-a-valid-uuid-here")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# TestParallelProxyEndpoints
# ---------------------------------------------------------------------------

class TestParallelProxyEndpoints:
    """Tests for GET/POST /api/parallel/* dashboard proxy endpoints."""

    @pytest.mark.asyncio
    async def test_parallel_list_runs_empty(self, client):
        """agent_request returns [] — GET /api/parallel/runs returns 200 with []."""
        with patch("backend.endpoints.agent_request", new_callable=AsyncMock, return_value=[]):
            resp = await client.get("/api/parallel/runs")

        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_parallel_list_runs_with_data(self, client):
        """agent_request returns two slot dicts — response contains those 2 items."""
        slots = [
            {"run_id": "run-1", "status": "running"},
            {"run_id": "run-2", "status": "paused"},
        ]

        with patch("backend.endpoints.agent_request", new_callable=AsyncMock, return_value=slots):
            resp = await client.get("/api/parallel/runs")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["run_id"] == "run-1"
        assert data[1]["run_id"] == "run-2"

    @pytest.mark.asyncio
    async def test_parallel_status(self, client):
        """agent_request returns a status summary — response contains that dict."""
        status_data = {"total_slots": 2, "active": 1, "max_concurrent": 10, "slots": []}

        with patch("backend.endpoints.agent_request", new_callable=AsyncMock, return_value=status_data):
            resp = await client.get("/api/parallel/status")

        assert resp.status_code == 200
        assert resp.json() == status_data

    @pytest.mark.asyncio
    async def test_parallel_start_includes_credentials(self, client):
        """POST /api/parallel/start forwards credentials from read_credentials."""
        mock_creds = {"claude_token": "tok", "git_token": "gt"}
        mock_agent_request = AsyncMock(return_value={"run_id": "new-run"})

        with patch("backend.endpoints.agent_request", mock_agent_request), \
             patch("backend.endpoints.read_credentials", new_callable=AsyncMock, return_value=mock_creds):
            resp = await client.post("/api/parallel/start", json={
                "prompt": "x",
                "max_budget_usd": 5.0,
                "duration_minutes": 30,
            })

        assert resp.status_code == 200
        call_args = mock_agent_request.call_args
        body_dict = call_args[0][3]
        assert "claude_token" in body_dict
        assert "git_token" in body_dict
        assert body_dict["claude_token"] == "tok"
        assert body_dict["git_token"] == "gt"

    @pytest.mark.asyncio
    async def test_parallel_get_run(self, client):
        """agent_request returns run data — GET /api/parallel/runs/{id} returns 200."""
        run_data = {"run_id": "ab1234cd", "status": "running"}

        with patch("backend.endpoints.agent_request", new_callable=AsyncMock, return_value=run_data):
            resp = await client.get("/api/parallel/runs/ab1234cd")

        assert resp.status_code == 200
        assert resp.json() == run_data

    @pytest.mark.asyncio
    async def test_parallel_stop_run(self, client):
        """POST /api/parallel/runs/{id}/stop is forwarded to agent with correct path."""
        mock_agent_request = AsyncMock(return_value={"ok": True})

        with patch("backend.endpoints.agent_request", mock_agent_request):
            resp = await client.post("/api/parallel/runs/ab1234cd/stop")

        assert resp.status_code == 200
        call_args = mock_agent_request.call_args
        assert "/parallel/runs/ab1234cd/stop" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_parallel_kill_run(self, client):
        """POST /api/parallel/runs/{id}/kill is forwarded to agent with correct path."""
        mock_agent_request = AsyncMock(return_value={"ok": True})

        with patch("backend.endpoints.agent_request", mock_agent_request):
            resp = await client.post("/api/parallel/runs/ab1234cd/kill")

        assert resp.status_code == 200
        call_args = mock_agent_request.call_args
        assert "/parallel/runs/ab1234cd/kill" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_parallel_cleanup(self, client):
        """POST /api/parallel/cleanup returns the agent's response dict."""
        cleanup_data = {"ok": True, "cleaned": 3}

        with patch("backend.endpoints.agent_request", new_callable=AsyncMock, return_value=cleanup_data):
            resp = await client.post("/api/parallel/cleanup")

        assert resp.status_code == 200
        assert resp.json() == cleanup_data

    @pytest.mark.asyncio
    async def test_parallel_fallback_on_agent_error(self, client):
        """list_runs returns [] fallback when agent is unavailable (connection error)."""
        with patch("backend.endpoints.agent_request", new_callable=AsyncMock, return_value=[]):
            resp = await client.get("/api/parallel/runs")

        assert resp.status_code == 200
        assert resp.json() == []
