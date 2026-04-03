"""Extended security tests — require FastAPI TestClient. Run after major changes."""

import hmac

import pytest
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.testclient import TestClient


SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


@pytest.fixture
def cors_app() -> TestClient:
    """FastAPI app with same CORS + security headers as production."""
    app = FastAPI()

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next) -> Response:
        response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3400"],
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-API-Key", "Authorization"],
    )

    @app.get("/test")
    async def test_endpoint():
        return {"ok": True}

    return TestClient(app)


@pytest.fixture
def auth_app() -> TestClient:
    """FastAPI app with internal secret auth middleware."""
    app = FastAPI()
    secret = "test-internal-secret-value"

    @app.middleware("http")
    async def check_internal_secret(request: Request, call_next) -> Response:
        if request.url.path == "/health":
            return await call_next(request)
        provided = request.headers.get("X-Internal-Secret", "")
        if not hmac.compare_digest(provided, secret):
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
        return await call_next(request)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/start")
    async def start():
        return {"ok": True}

    @app.get("/branches")
    async def branches():
        return ["main"]

    return TestClient(app)


class TestSecurityHeaders:
    """Every response must include security headers."""

    def test_all_headers_present(self, cors_app: TestClient):
        res = cors_app.get("/test")
        for header, value in SECURITY_HEADERS.items():
            assert res.headers[header] == value


class TestCors:
    """CORS must be locked to explicit origins."""

    def test_allowed_origin(self, cors_app: TestClient):
        res = cors_app.get("/test", headers={"Origin": "http://localhost:3400"})
        assert res.headers.get("access-control-allow-origin") == "http://localhost:3400"

    def test_disallowed_origin(self, cors_app: TestClient):
        res = cors_app.get("/test", headers={"Origin": "http://evil.com"})
        assert "access-control-allow-origin" not in res.headers

    def test_preflight_allowed(self, cors_app: TestClient):
        res = cors_app.options("/test", headers={
            "Origin": "http://localhost:3400",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-API-Key",
        })
        assert res.status_code == 200
        assert "X-API-Key" in res.headers.get("access-control-allow-headers", "")

    def test_preflight_disallowed(self, cors_app: TestClient):
        res = cors_app.options("/test", headers={
            "Origin": "http://evil.com",
            "Access-Control-Request-Method": "POST",
        })
        assert "access-control-allow-origin" not in res.headers

    def test_no_wildcard(self, cors_app: TestClient):
        res = cors_app.get("/test", headers={"Origin": "http://localhost:3400"})
        assert res.headers.get("access-control-allow-origin") != "*"


class TestInternalAuth:
    """Agent internal secret auth middleware."""

    def test_health_accessible_without_secret(self, auth_app: TestClient):
        assert auth_app.get("/health").status_code == 200

    def test_rejects_without_secret(self, auth_app: TestClient):
        assert auth_app.post("/start").status_code == 401

    def test_rejects_wrong_secret(self, auth_app: TestClient):
        assert auth_app.post("/start", headers={"X-Internal-Secret": "wrong"}).status_code == 401

    def test_accepts_correct_secret(self, auth_app: TestClient):
        assert auth_app.post("/start", headers={"X-Internal-Secret": "test-internal-secret-value"}).status_code == 200

    def test_get_also_protected(self, auth_app: TestClient):
        assert auth_app.get("/branches").status_code == 401
        assert auth_app.get("/branches", headers={"X-Internal-Secret": "test-internal-secret-value"}).status_code == 200
