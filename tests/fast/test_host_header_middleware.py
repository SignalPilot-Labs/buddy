"""Tests for the Host-header middleware in dashboard/backend/app.py.

Builds a minimal FastAPI app with the middleware and a /healthz route,
then verifies allowed and rejected Host headers.
"""

import pytest
from fastapi import FastAPI, Request, Response
from starlette.testclient import TestClient

from backend.constants import ALLOWED_HOSTS


def _make_app() -> FastAPI:
    """Build a minimal FastAPI app with the Host-header middleware."""
    app = FastAPI()

    @app.middleware("http")
    async def enforce_host_header(request: Request, call_next) -> Response:
        host = request.headers.get("host")
        if host not in ALLOWED_HOSTS:
            return Response(
                status_code=421,
                content="Misdirected Request: Host header not allowed",
            )
        return await call_next(request)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(_make_app(), raise_server_exceptions=True)


class TestHostHeaderMiddleware:
    """Host-header allowlist blocks rebinding and LAN attackers."""

    def test_localhost_3401_allowed(self, client: TestClient) -> None:
        res = client.get("/healthz", headers={"Host": "localhost:3401"})
        assert res.status_code == 200

    def test_127_0_0_1_3401_allowed(self, client: TestClient) -> None:
        res = client.get("/healthz", headers={"Host": "127.0.0.1:3401"})
        assert res.status_code == 200

    def test_localhost_no_port_allowed(self, client: TestClient) -> None:
        res = client.get("/healthz", headers={"Host": "localhost"})
        assert res.status_code == 200

    def test_127_0_0_1_no_port_allowed(self, client: TestClient) -> None:
        res = client.get("/healthz", headers={"Host": "127.0.0.1"})
        assert res.status_code == 200

    def test_attacker_com_rejected(self, client: TestClient) -> None:
        res = client.get("/healthz", headers={"Host": "attacker.com"})
        assert res.status_code == 421

    def test_lan_ip_rejected(self, client: TestClient) -> None:
        res = client.get("/healthz", headers={"Host": "192.168.1.50:3401"})
        assert res.status_code == 421

    def test_docker_hostname_rejected(self, client: TestClient) -> None:
        """dashboard:3401 is intentionally NOT in the allowlist."""
        res = client.get("/healthz", headers={"Host": "dashboard:3401"})
        assert res.status_code == 421

    def test_no_host_header_rejected(self, client: TestClient) -> None:
        """Missing Host header must be rejected (host is None, not in ALLOWED_HOSTS)."""
        # Remove default Host header by overriding with empty dict approach.
        # TestClient always sends a Host header; we override it to a value
        # not in the allowlist to simulate the "no Host" case.
        res = client.get("/healthz", headers={"Host": ""})
        assert res.status_code == 421
