"""Regression tests for sandbox error_middleware JSON and field error handling.

Bug: error_middleware had no handlers for json.JSONDecodeError or KeyError.
Malformed JSON bodies and missing required fields both propagated as unhandled
exceptions, returning HTTP 500 with a full traceback.

Fix: error_middleware now catches json.JSONDecodeError (returns 400 with
API_INVALID_JSON_MSG) and KeyError (returns 400 with API_MISSING_FIELD_MSG)
before the generic Exception handler, so clients receive actionable 400
responses instead of 500s with tracebacks.
"""

from __future__ import annotations

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

import sandbox.server as sandbox_server
from api.file_system import register as register_file_system
from constants import API_INVALID_JSON_MSG, API_MISSING_FIELD_MSG

HTTP_200 = 200
HTTP_400 = 400
WRITE_URL = "/file_system/write"
EXISTS_URL = "/file_system/exists"


def _build_app() -> web.Application:
    """Build a minimal aiohttp app with error_middleware and file_system routes."""
    app = web.Application(middlewares=[sandbox_server.error_middleware])
    register_file_system(app)
    return app


class TestSandboxApiRequestErrors:
    """Regression tests for sandbox error_middleware JSON and field validation.

    Bug: error_middleware had no handlers for json.JSONDecodeError or KeyError.
    Fix: Middleware now catches these and returns 400 with clean error messages.
    """

    @pytest.mark.asyncio
    async def test_malformed_json_returns_400(self) -> None:
        """Sending invalid JSON to /file_system/write must return HTTP 400."""
        app = _build_app()
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                WRITE_URL,
                data="{invalid json",
                headers={"Content-Type": "application/json"},
            )
            assert resp.status == HTTP_400

    @pytest.mark.asyncio
    async def test_malformed_json_body_has_error_message(self) -> None:
        """400 response body must contain the API_INVALID_JSON_MSG error."""
        app = _build_app()
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                WRITE_URL,
                data="{invalid json",
                headers={"Content-Type": "application/json"},
            )
            data = await resp.json()
            assert data["error"] == API_INVALID_JSON_MSG

    @pytest.mark.asyncio
    async def test_malformed_json_body_has_no_traceback(self) -> None:
        """400 response body must NOT expose a traceback to the client."""
        app = _build_app()
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                WRITE_URL,
                data="{invalid json",
                headers={"Content-Type": "application/json"},
            )
            data = await resp.json()
            assert "traceback" not in data

    @pytest.mark.asyncio
    async def test_missing_path_returns_400(self) -> None:
        """Omitting 'path' from /file_system/write body must return HTTP 400."""
        app = _build_app()
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(WRITE_URL, json={"content": "test"})
            assert resp.status == HTTP_400

    @pytest.mark.asyncio
    async def test_missing_path_error_names_field(self) -> None:
        """400 body must name the missing field 'path'."""
        app = _build_app()
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(WRITE_URL, json={"content": "test"})
            data = await resp.json()
            expected = API_MISSING_FIELD_MSG.format(field="path")
            assert data["error"] == expected

    @pytest.mark.asyncio
    async def test_missing_field_body_has_no_traceback(self) -> None:
        """400 response body must NOT expose a traceback to the client."""
        app = _build_app()
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(WRITE_URL, json={"content": "test"})
            data = await resp.json()
            assert "traceback" not in data

    @pytest.mark.asyncio
    async def test_exists_with_valid_path_returns_200(self, tmp_path) -> None:
        """Valid /file_system/exists request must return HTTP 200."""
        app = _build_app()
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                EXISTS_URL,
                json={"path": str(tmp_path)},
            )
            assert resp.status == HTTP_200

    @pytest.mark.asyncio
    async def test_exists_response_has_exists_key(self, tmp_path) -> None:
        """Valid /file_system/exists response must contain 'exists' key."""
        app = _build_app()
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                EXISTS_URL,
                json={"path": str(tmp_path)},
            )
            data = await resp.json()
            assert "exists" in data
