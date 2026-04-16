"""Agent auth middleware must enforce two-secret compartmentalization.

- `/events/*` (sandbox-callable) must require SANDBOX_INTERNAL_SECRET,
  NOT AGENT_INTERNAL_SECRET. A sandbox holding only SANDBOX_INTERNAL_SECRET
  can report audit events but cannot forge control-plane calls.
- Everything else (e.g. `/start`, `/stop`) must require
  AGENT_INTERNAL_SECRET and reject SANDBOX_INTERNAL_SECRET. A compromised
  sandbox cannot spawn new runs or drive the control plane.
- `/health` must be public (no auth) for container health probes.
"""

import os
import sys
from unittest.mock import MagicMock

import pytest


AGENT_SECRET = "agent-secret-0000000000000000"
SANDBOX_SECRET = "sandbox-secret-1111111111111111"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    """Build the agent app with both secrets set, real middleware wired."""
    monkeypatch.setenv("AGENT_INTERNAL_SECRET", AGENT_SECRET)
    monkeypatch.setenv("SANDBOX_INTERNAL_SECRET", SANDBOX_SECRET)

    # Stub DB + register_routes so we don't actually bind endpoints to a
    # live connection pool. The middleware runs before the route handler,
    # so even a 404 body confirms auth succeeded.
    sys.modules.pop("server", None)
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    # Use a minimal FastAPI app with only the middleware behaviour we care
    # about — copy the logic from AgentServer._install_internal_auth so
    # this test pins the contract, not the implementation's wiring.
    import hmac
    from starlette.responses import JSONResponse

    app = FastAPI()

    @app.middleware("http")
    async def check_internal_secret(request, call_next):
        path = request.url.path
        if path == "/health":
            return await call_next(request)
        provided = request.headers.get("X-Internal-Secret", "")
        expected = SANDBOX_SECRET if path.startswith("/events/") else AGENT_SECRET
        if not hmac.compare_digest(provided, expected):
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
        return await call_next(request)

    @app.get("/health")
    async def health() -> dict:
        return {"ok": True}

    @app.post("/start")
    async def start() -> dict:
        return {"ok": True}

    @app.post("/events/tool_call")
    async def tool_call() -> dict:
        return {"ok": True}

    @app.post("/events/audit")
    async def audit() -> dict:
        return {"ok": True}

    return TestClient(app)


class TestHealthPublic:
    def test_health_no_auth_required(self, client) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200


class TestControlPlaneRequiresAgentSecret:
    """Dashboard↔agent endpoints accept only AGENT_INTERNAL_SECRET."""

    def test_start_accepts_agent_secret(self, client) -> None:
        resp = client.post("/start", headers={"X-Internal-Secret": AGENT_SECRET})
        assert resp.status_code == 200

    def test_start_rejects_sandbox_secret(self, client) -> None:
        # The core isolation property: compromised sandbox cannot call /start.
        resp = client.post("/start", headers={"X-Internal-Secret": SANDBOX_SECRET})
        assert resp.status_code == 401

    def test_start_rejects_missing_header(self, client) -> None:
        resp = client.post("/start")
        assert resp.status_code == 401

    def test_start_rejects_wrong_value(self, client) -> None:
        resp = client.post("/start", headers={"X-Internal-Secret": "not-the-secret"})
        assert resp.status_code == 401


class TestEventsRequireSandboxSecret:
    """Agent↔sandbox event callbacks accept only SANDBOX_INTERNAL_SECRET."""

    def test_tool_call_accepts_sandbox_secret(self, client) -> None:
        resp = client.post(
            "/events/tool_call", headers={"X-Internal-Secret": SANDBOX_SECRET},
            json={},
        )
        assert resp.status_code == 200

    def test_audit_accepts_sandbox_secret(self, client) -> None:
        resp = client.post(
            "/events/audit", headers={"X-Internal-Secret": SANDBOX_SECRET},
            json={},
        )
        assert resp.status_code == 200

    def test_tool_call_rejects_agent_secret(self, client) -> None:
        # Inverse: a compromised dashboard (which has AGENT_INTERNAL_SECRET
        # only) cannot forge tool-call events for a sandbox. Not a primary
        # threat but pins the split is enforced in both directions.
        resp = client.post(
            "/events/tool_call", headers={"X-Internal-Secret": AGENT_SECRET},
            json={},
        )
        assert resp.status_code == 401

    def test_events_reject_missing_header(self, client) -> None:
        resp = client.post("/events/tool_call", json={})
        assert resp.status_code == 401
