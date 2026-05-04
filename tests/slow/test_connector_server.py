"""Integration tests for ConnectorServer HTTP endpoints.

Tests the connector's HTTP API with a real aiohttp test server. SSH
operations are mocked — these tests verify HTTP routing, auth, NDJSON
streaming, and state management.
"""

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient

from connector.server import ConnectorServer


TEST_SECRET = "test-connector-secret-12345"


@pytest.fixture
def connector_app() -> web.Application:
    """Build a ConnectorServer app for testing."""
    server = ConnectorServer(TEST_SECRET, 0)
    return server._app


@pytest.fixture
async def client(connector_app: web.Application, aiohttp_client) -> TestClient:
    """Create a test client for the connector."""
    return await aiohttp_client(connector_app)


class TestConnectorHealth:
    """Health endpoint is unauthenticated and returns status."""

    @pytest.mark.asyncio
    async def test_health_returns_ok(self, client: TestClient) -> None:
        resp = await client.get("/health")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "ok"
        assert data["tunnels"] == []


class TestConnectorAuth:
    """All endpoints except /health require X-Connector-Secret."""

    @pytest.mark.asyncio
    async def test_stop_rejects_missing_secret(self, client: TestClient) -> None:
        resp = await client.post("/sandboxes/stop", json={"run_key": "test"})
        assert resp.status == 401

    @pytest.mark.asyncio
    async def test_stop_rejects_wrong_secret(self, client: TestClient) -> None:
        resp = await client.post(
            "/sandboxes/stop",
            json={"run_key": "test"},
            headers={"X-Connector-Secret": "wrong"},
        )
        assert resp.status == 401

    @pytest.mark.asyncio
    async def test_stop_accepts_correct_secret(self, client: TestClient) -> None:
        resp = await client.post(
            "/sandboxes/stop",
            json={"run_key": "nonexistent"},
            headers={"X-Connector-Secret": TEST_SECRET},
        )
        assert resp.status == 200


class TestConnectorLogs:
    """Logs endpoint returns ring buffer contents."""

    @pytest.mark.asyncio
    async def test_logs_empty_for_unknown_run(self, client: TestClient) -> None:
        resp = await client.get(
            "/sandboxes/unknown-run/logs",
            headers={"X-Connector-Secret": TEST_SECRET},
        )
        assert resp.status == 200
        data = await resp.json()
        assert data["lines"] == []
        assert data["total"] == 0


class TestConnectorShutdown:
    """Shutdown endpoint stops all active sandboxes."""

    @pytest.mark.asyncio
    async def test_shutdown_with_no_active_runs(self, client: TestClient) -> None:
        resp = await client.post(
            "/shutdown",
            headers={"X-Connector-Secret": TEST_SECRET},
        )
        assert resp.status == 200
        data = await resp.json()
        assert data["ok"] is True
        assert data["remaining"] == 0
