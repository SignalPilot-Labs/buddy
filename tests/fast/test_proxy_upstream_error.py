"""Regression test for connector proxy error handling.

Verifies that when the upstream sandbox dies mid-response (httpx raises
an exception during streaming), write_eof() is still called to properly
close the aiohttp response and prevent the client from hanging.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from cli.connector.forward_state import ForwardState
from cli.connector.proxy import handle_proxy


def _make_forward_state(run_key: str) -> ForwardState:
    """Create a minimal ForwardState for testing."""
    return ForwardState(
        run_key=run_key,
        ssh_target="user@host",
        sandbox_type="slurm",
        local_port=9999,
        tunnel_process=None,  # type: ignore[arg-type]
        start_process=None,
        sandbox_secret="test-secret",
        backend_id=None,
    )


def _make_aiohttp_request(run_key: str) -> MagicMock:
    """Create a minimal mock aiohttp Request."""
    request = MagicMock()
    request.match_info = {"run_key": run_key, "path": "api/test"}
    request.method = "GET"
    request.can_read_body = False
    request.query_string = ""
    request.headers = {}
    return request


class TestProxyUpstreamError:
    """Proxy must call write_eof() even when upstream dies mid-stream."""

    @pytest.mark.asyncio
    async def test_write_eof_called_on_upstream_read_error(self) -> None:
        """write_eof() must be called when aiter_bytes() raises httpx.ReadError."""
        run_key = "test-run"
        request = _make_aiohttp_request(run_key)
        states = {run_key: _make_forward_state(run_key)}

        response_mock = MagicMock()
        response_mock.prepare = AsyncMock()
        response_mock.write = AsyncMock()
        response_mock.write_eof = AsyncMock()

        async def failing_aiter_bytes() -> object:
            yield b"first chunk"
            raise httpx.ReadError("upstream died", request=MagicMock())

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.aiter_bytes = failing_aiter_bytes
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_client = MagicMock()
        mock_client.stream = MagicMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("cli.connector.proxy.httpx.AsyncClient", return_value=mock_client),
            patch("cli.connector.proxy.web.StreamResponse", return_value=response_mock),
        ):
            result = await handle_proxy(request, states)

        # write_eof must be called to terminate the response cleanly
        response_mock.write_eof.assert_awaited_once()
        # The first chunk must have been written before the error
        response_mock.write.assert_awaited_once_with(b"first chunk")
        assert result is response_mock

    @pytest.mark.asyncio
    async def test_write_eof_called_on_successful_response(self) -> None:
        """write_eof() must also be called on a successful complete response."""
        run_key = "test-run"
        request = _make_aiohttp_request(run_key)
        states = {run_key: _make_forward_state(run_key)}

        response_mock = MagicMock()
        response_mock.prepare = AsyncMock()
        response_mock.write = AsyncMock()
        response_mock.write_eof = AsyncMock()

        async def success_aiter_bytes() -> object:
            yield b"chunk1"
            yield b"chunk2"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.aiter_bytes = success_aiter_bytes
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_client = MagicMock()
        mock_client.stream = MagicMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("cli.connector.proxy.httpx.AsyncClient", return_value=mock_client),
            patch("cli.connector.proxy.web.StreamResponse", return_value=response_mock),
        ):
            result = await handle_proxy(request, states)

        response_mock.write_eof.assert_awaited_once()
        assert response_mock.write.await_count == 2
        assert result is response_mock

    @pytest.mark.asyncio
    async def test_missing_run_key_returns_404(self) -> None:
        """Requests for unknown run_key must return a 404 JSON response immediately."""
        request = _make_aiohttp_request("unknown-run")
        states: dict[str, ForwardState] = {}

        with patch("cli.connector.proxy.web.json_response") as mock_json_response:
            mock_json_response.return_value = MagicMock()
            await handle_proxy(request, states)

        mock_json_response.assert_called_once_with(
            {"error": "No active tunnel for run unknown-run"}, status=404
        )
