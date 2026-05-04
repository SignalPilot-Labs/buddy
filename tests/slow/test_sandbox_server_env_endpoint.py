"""Integration tests for the sandbox POST /env endpoint.

Tests runtime secret injection into the sandbox server. Uses aiohttp
test client against the real handler.
"""

import os
from unittest.mock import patch

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient

from sandbox.handlers.env import register as register_env


@pytest.fixture
def env_app() -> web.Application:
    """Build a minimal aiohttp app with just the /env endpoint."""
    app = web.Application()
    register_env(app)
    return app


@pytest.fixture
async def client(env_app: web.Application, aiohttp_client) -> TestClient:
    """Create a test client for the env endpoint."""
    return await aiohttp_client(env_app)


class TestEnvEndpoint:
    """POST /env merges env vars into os.environ."""

    @pytest.mark.asyncio
    async def test_injects_env_vars(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        """Env vars from request body appear in os.environ."""
        test_key = "_AUTOFYN_TEST_ENV_INJECT_12345"
        resp = await client.post("/env", json={"env_vars": {test_key: "secret_value"}})
        assert resp.status == 200
        data = await resp.json()
        assert data["ok"] is True
        assert data["count"] == 1
        assert os.environ.get(test_key) == "secret_value"
        monkeypatch.delenv(test_key, raising=False)

    @pytest.mark.asyncio
    async def test_empty_env_vars(self, client: TestClient) -> None:
        """Empty dict is valid — no env vars injected."""
        resp = await client.post("/env", json={"env_vars": {}})
        assert resp.status == 200
        data = await resp.json()
        assert data["count"] == 0

    @pytest.mark.asyncio
    async def test_missing_env_vars_field(self, client: TestClient) -> None:
        """Missing env_vars field returns 400."""
        resp = await client.post("/env", json={})
        assert resp.status == 400

    @pytest.mark.asyncio
    async def test_denied_env_key_rejected(self, client: TestClient) -> None:
        """Dangerous env vars like PATH are rejected."""
        resp = await client.post("/env", json={"env_vars": {"PATH": "/evil"}})
        assert resp.status == 400
        data = await resp.json()
        assert "Denied" in data["error"]
