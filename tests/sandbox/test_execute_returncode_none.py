"""Regression test for falsy returncode check in handle_execute.

When asyncio.subprocess.Process.returncode is None after communicate()
(indeterminate state), the handler must return exit_code -1, not 0.
The old code used `proc.returncode or 0` which silently masked None as success.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import web

from handlers.execute import handle_execute


def _request(payload: dict) -> MagicMock:
    """Build a mock aiohttp Request whose .json() returns the given payload."""
    req = MagicMock()
    req.json = AsyncMock(return_value=payload)
    return req


def _parse(response: web.Response) -> dict:
    """Pull the JSON body out of an aiohttp Response."""
    body = response.body
    assert body is not None
    return json.loads(body.decode("utf-8"))


class TestExecuteReturncodeNone:
    """Regression: proc.returncode None must produce exit_code -1, not 0."""

    @pytest.mark.asyncio
    async def test_returncode_none_returns_minus_one(self) -> None:
        """When returncode is None after communicate(), exit_code must be -1."""
        mock_proc = MagicMock()
        mock_proc.returncode = None
        mock_proc.communicate = AsyncMock(return_value=(b"some output", b""))

        with patch(
            "handlers.execute.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=mock_proc),
        ):
            resp = await handle_execute(_request({"args": ["true"]}))

        body = _parse(resp)
        assert body["exit_code"] == -1

    @pytest.mark.asyncio
    async def test_returncode_zero_returns_zero(self) -> None:
        """When returncode is 0 (success), exit_code must be 0, not -1."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"ok", b""))

        with patch(
            "handlers.execute.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=mock_proc),
        ):
            resp = await handle_execute(_request({"args": ["true"]}))

        body = _parse(resp)
        assert body["exit_code"] == 0

    @pytest.mark.asyncio
    async def test_returncode_nonzero_returned_unchanged(self) -> None:
        """When returncode is nonzero, exit_code must reflect the actual code."""
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"", b"error"))

        with patch(
            "handlers.execute.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=mock_proc),
        ):
            resp = await handle_execute(_request({"args": ["false"]}))

        body = _parse(resp)
        assert body["exit_code"] == 1
