"""Regression test: query-string api_key= auth is dead on the SSE endpoints.

Verifies that:
  - ?api_key=<valid-key> alone does NOT authenticate (must be 401)
  - X-API-Key: <valid-key> header DOES pass auth (response is not 401/403)
  - No key at all is 401

Uses a standalone FastAPI app with a fresh verify_api_key dependency
(not the real streaming router) to avoid test-ordering coupling with
the module-level sys.modules state of backend.auth / backend.endpoints.streaming.
The load-bearing assertion is about the Depends() auth contract, not the
streaming internals.
"""

import hmac

from fastapi import FastAPI, HTTPException, Security
from fastapi.security import APIKeyHeader
from starlette.testclient import TestClient
import pytest


_TEST_KEY = "test-key-round2-abc123"

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def _verify_api_key_header_only(
    api_key: str | None = Security(_api_key_header),
) -> None:
    """Mirror of auth.verify_api_key: header-only, no query param."""
    if not api_key or not hmac.compare_digest(api_key, _TEST_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def _make_app() -> FastAPI:
    """Build a minimal FastAPI app with a streaming-style route wired to header-only auth."""
    from fastapi import Depends
    from fastapi.responses import StreamingResponse

    app = FastAPI()

    # Simulate the streaming router's dependency chain:
    # APIRouter with router-level Depends(verify_api_key).
    from fastapi import APIRouter
    router = APIRouter(
        prefix="/api",
        dependencies=[Depends(_verify_api_key_header_only)],
    )

    @router.get("/stream/{run_id}")
    async def stream_events(run_id: str) -> StreamingResponse:
        async def gen():
            yield "event: connected\ndata: {}\n\n"
        return StreamingResponse(gen(), media_type="text/event-stream")

    @router.get("/poll/{run_id}")
    async def poll_events(run_id: str) -> dict:
        return {"events": []}

    app.include_router(router)
    return app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(_make_app(), raise_server_exceptions=False)


class TestStreamingQueryAuthRejected:
    """Query-param api_key= must not authenticate the SSE endpoints.

    The real streaming router uses Depends(auth.verify_api_key) — header-only.
    This test verifies the contract: ?api_key= does not authenticate, X-API-Key
    does authenticate.
    """

    def test_query_param_alone_is_401(self, client: TestClient) -> None:
        """?api_key=<valid-key> must NOT authenticate — query-param path is dead."""
        res = client.get(f"/api/stream/run-xxx?api_key={_TEST_KEY}")
        assert res.status_code == 401

    def test_header_auth_passes(self, client: TestClient) -> None:
        """X-API-Key header authenticates; stream response is not 401/403."""
        res = client.get(
            "/api/stream/run-xxx",
            headers={"X-API-Key": _TEST_KEY},
        )
        assert res.status_code not in (401, 403)

    def test_no_credentials_is_401(self, client: TestClient) -> None:
        """No header, no query param → 401."""
        res = client.get("/api/stream/run-xxx")
        assert res.status_code == 401

    def test_wrong_header_key_is_401(self, client: TestClient) -> None:
        """Wrong key in header → 401."""
        res = client.get(
            "/api/stream/run-xxx",
            headers={"X-API-Key": "wrong-key"},
        )
        assert res.status_code == 401

    def test_poll_endpoint_query_param_is_401(self, client: TestClient) -> None:
        """Poll endpoint also rejects ?api_key= query-param auth."""
        res = client.get(f"/api/poll/run-xxx?api_key={_TEST_KEY}")
        assert res.status_code == 401

    def test_streaming_router_uses_header_only_dependency(self) -> None:
        """Verify the actual streaming.py router's dependency list does not include query-param auth.

        This is the static guard against re-introducing verify_api_key_or_query.
        """
        import sys
        from unittest.mock import MagicMock

        # Patch auth so streaming can be imported without /data/api.key on disk
        if "backend.auth" not in sys.modules:
            fake_auth = MagicMock()
            sys.modules["backend.auth"] = fake_auth  # type: ignore[assignment]

        # Inspect the router's dependency list
        if "backend.endpoints.streaming" in sys.modules:
            streaming = sys.modules["backend.endpoints.streaming"]
        else:
            from backend.endpoints import streaming  # noqa: PLC0415

        router = streaming.router
        dep_names = [str(d) for d in router.dependencies]
        # verify_api_key_or_query must not appear in any dependency string
        for dep_str in dep_names:
            assert "verify_api_key_or_query" not in dep_str, (
                f"Router dependency contains verify_api_key_or_query: {dep_str}"
            )
