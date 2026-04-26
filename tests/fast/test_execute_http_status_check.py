"""Regression test — Execute.run must raise HTTPStatusError on 4xx/5xx responses.

Bug: raise_for_status() was called AFTER resp.json() and the exit_code check.
A 500 response with an exit_code in the body was silently returned as ExecResult
instead of raising an error. The fix moves raise_for_status() before body inspection.
"""

import pytest
import httpx
from unittest.mock import patch

from utils.models import ExecRequest, ExecResult


def _make_request() -> ExecRequest:
    return ExecRequest(args=["echo", "hi"], timeout=30, env={}, cwd="/tmp")


def _make_response(status_code: int, body: dict) -> httpx.Response:
    """Build an httpx.Response with the given status and JSON body."""
    request = httpx.Request("POST", "http://sandbox/execute")
    return httpx.Response(status_code=status_code, json=body, request=request)


class TestExecuteHttpStatusCheck:
    """Execute.run raises HTTPStatusError before inspecting the body on error responses."""

    @pytest.mark.asyncio
    async def test_http_500_with_exit_code_raises_status_error(self) -> None:
        """500 response with exit_code in body must raise HTTPStatusError, not return ExecResult.

        This is the exact regression: old code checked exit_code first, so a 500
        response with a valid-looking body was returned as a successful ExecResult.
        """
        from autofyn.sandbox_client.handlers.execute import Execute

        error_response = _make_response(
            500, {"exit_code": 1, "stdout": "", "stderr": "internal error"}
        )

        async def mock_post(*args, **kwargs):
            return error_response

        client = httpx.AsyncClient()
        execute = Execute(http=client)
        with patch.object(client, "post", side_effect=mock_post):
            with pytest.raises(httpx.HTTPStatusError):
                await execute.run(_make_request())

    @pytest.mark.asyncio
    async def test_http_200_with_exit_code_returns_exec_result(self) -> None:
        """200 response with exit_code in body returns ExecResult normally."""
        from autofyn.sandbox_client.handlers.execute import Execute

        ok_response = _make_response(
            200, {"exit_code": 0, "stdout": "hi", "stderr": ""}
        )

        async def mock_post(*args, **kwargs):
            return ok_response

        client = httpx.AsyncClient()
        execute = Execute(http=client)
        with patch.object(client, "post", side_effect=mock_post):
            result = await execute.run(_make_request())

        assert isinstance(result, ExecResult)
        assert result.exit_code == 0
        assert result.stdout == "hi"

    @pytest.mark.asyncio
    async def test_http_200_without_exit_code_raises_runtime_error(self) -> None:
        """200 response without exit_code raises RuntimeError (malformed response)."""
        from autofyn.sandbox_client.handlers.execute import Execute

        malformed_response = _make_response(200, {"error": "sandbox misconfigured"})

        async def mock_post(*args, **kwargs):
            return malformed_response

        client = httpx.AsyncClient()
        execute = Execute(http=client)
        with patch.object(client, "post", side_effect=mock_post):
            with pytest.raises(RuntimeError, match="Sandbox error"):
                await execute.run(_make_request())

    @pytest.mark.asyncio
    async def test_http_403_raises_status_error(self) -> None:
        """403 response raises HTTPStatusError regardless of body."""
        from autofyn.sandbox_client.handlers.execute import Execute

        forbidden_response = _make_response(403, {"detail": "forbidden"})

        async def mock_post(*args, **kwargs):
            return forbidden_response

        client = httpx.AsyncClient()
        execute = Execute(http=client)
        with patch.object(client, "post", side_effect=mock_post):
            with pytest.raises(httpx.HTTPStatusError):
                await execute.run(_make_request())
