"""Regression tests for connector proxy.py httpx network exception handling.

Bug: handle_proxy had no try/except around httpx.AsyncClient.stream(), so
ConnectError, TimeoutException, and ReadError propagated as unhandled
exceptions, causing aiohttp to return 500 with a raw Python traceback.

Fix: Wrap the httpx block in try/except — return 502 for connection/read
errors and 504 for timeouts.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from cli.connector.forward_state import ForwardState
from cli.connector.proxy import handle_proxy

HTTP_502 = 502
HTTP_504 = 504
HTTP_404 = 404

RUN_KEY = "test-run-abc"


def _make_state(local_port: int = 19000) -> ForwardState:
    """Build a minimal ForwardState for use in proxy tests."""
    return ForwardState(
        run_key=RUN_KEY,
        ssh_target="user@hpc",
        sandbox_type="slurm",
        local_port=local_port,
        tunnel_process=MagicMock(),
        start_process=None,
        sandbox_secret="s3cr3t",
        backend_id=None,
        work_dir="~/scratch",
    )


def _make_request(run_key: str = RUN_KEY) -> web.Request:
    """Create a mocked aiohttp request with match_info and can_read_body=False."""
    return make_mocked_request(
        "GET",
        f"/proxy/{run_key}/health",
        match_info={"run_key": run_key, "path": "health"},
    )


def _mock_client_raising(exc: Exception) -> MagicMock:
    """Create a mock httpx.AsyncClient whose stream() raises exc."""
    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__aenter__ = AsyncMock(side_effect=exc)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_client = MagicMock()
    mock_client.stream = MagicMock(return_value=mock_stream_ctx)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    mock_cls = MagicMock(return_value=mock_client)
    return mock_cls


class TestProxyConnectError:
    """handle_proxy must return 502 when httpx.ConnectError is raised."""

    @pytest.mark.asyncio
    async def test_connect_error_returns_502(self) -> None:
        """ConnectError during stream → 502 JSON response."""
        request = _make_request()
        states = {RUN_KEY: _make_state()}

        mock_cls = _mock_client_raising(httpx.ConnectError("Connection refused"))
        with patch("cli.connector.proxy.httpx.AsyncClient", mock_cls):
            response = await handle_proxy(request, states)

        assert response.status == HTTP_502

    @pytest.mark.asyncio
    async def test_connect_error_response_body_contains_error_key(self) -> None:
        """ConnectError response body must include an 'error' key."""
        request = _make_request()
        states = {RUN_KEY: _make_state()}

        mock_cls = _mock_client_raising(httpx.ConnectError("Connection refused"))
        with patch("cli.connector.proxy.httpx.AsyncClient", mock_cls):
            response = await handle_proxy(request, states)

        body = response.body  # type: ignore[attr-defined]
        data = json.loads(body)
        assert "error" in data


class TestProxyTimeoutError:
    """handle_proxy must return 504 when httpx.TimeoutException is raised."""

    @pytest.mark.asyncio
    async def test_timeout_returns_504(self) -> None:
        """TimeoutException during stream → 504 JSON response."""
        request = _make_request()
        states = {RUN_KEY: _make_state()}

        mock_cls = _mock_client_raising(httpx.TimeoutException("Request timed out"))
        with patch("cli.connector.proxy.httpx.AsyncClient", mock_cls):
            response = await handle_proxy(request, states)

        assert response.status == HTTP_504

    @pytest.mark.asyncio
    async def test_timeout_response_body_contains_error_key(self) -> None:
        """TimeoutException response body must include an 'error' key."""
        request = _make_request()
        states = {RUN_KEY: _make_state()}

        mock_cls = _mock_client_raising(httpx.TimeoutException("Request timed out"))
        with patch("cli.connector.proxy.httpx.AsyncClient", mock_cls):
            response = await handle_proxy(request, states)

        body = response.body  # type: ignore[attr-defined]
        data = json.loads(body)
        assert "error" in data


class TestProxyReadError:
    """handle_proxy must return 502 when httpx.ReadError is raised."""

    @pytest.mark.asyncio
    async def test_read_error_returns_502(self) -> None:
        """ReadError during stream → 502 JSON response."""
        request = _make_request()
        states = {RUN_KEY: _make_state()}

        mock_cls = _mock_client_raising(httpx.ReadError("Connection reset"))
        with patch("cli.connector.proxy.httpx.AsyncClient", mock_cls):
            response = await handle_proxy(request, states)

        assert response.status == HTTP_502


class TestProxyWriteError:
    """handle_proxy must return 502 when httpx.WriteError is raised."""

    @pytest.mark.asyncio
    async def test_write_error_returns_502(self) -> None:
        """WriteError during stream → 502 JSON response."""
        request = _make_request()
        states = {RUN_KEY: _make_state()}

        mock_cls = _mock_client_raising(httpx.WriteError("Broken pipe"))
        with patch("cli.connector.proxy.httpx.AsyncClient", mock_cls):
            response = await handle_proxy(request, states)

        assert response.status == HTTP_502


class TestProxyProtocolError:
    """handle_proxy must return 502 when httpx.RemoteProtocolError is raised."""

    @pytest.mark.asyncio
    async def test_remote_protocol_error_returns_502(self) -> None:
        """RemoteProtocolError during stream → 502 JSON response."""
        request = _make_request()
        states = {RUN_KEY: _make_state()}

        mock_cls = _mock_client_raising(httpx.RemoteProtocolError("Malformed response"))
        with patch("cli.connector.proxy.httpx.AsyncClient", mock_cls):
            response = await handle_proxy(request, states)

        assert response.status == HTTP_502


class TestProxyMissingTunnel:
    """handle_proxy returns 404 when no tunnel is active for the run_key."""

    @pytest.mark.asyncio
    async def test_missing_run_key_returns_404(self) -> None:
        """No state entry for run_key → 404."""
        request = _make_request(run_key="nonexistent")
        states: dict[str, ForwardState] = {}

        response = await handle_proxy(request, states)

        assert response.status == HTTP_404
