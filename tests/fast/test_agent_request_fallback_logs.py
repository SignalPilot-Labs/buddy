"""Regression test: agent_request logs errors even when fallback is provided.

Previously, when fallback was not None and the agent was unreachable,
the error was swallowed completely with no log line. Now it always logs.
"""

import logging
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

if "db.connection" not in sys.modules:
    sys.modules["db.connection"] = MagicMock()

from backend.utils import agent_request


class TestAgentRequestFallbackLogs:
    """agent_request must log errors even when returning a fallback."""

    @pytest.mark.asyncio
    async def test_fallback_still_logs_error(self, caplog: pytest.LogCaptureFixture) -> None:
        """Connection failure with fallback must log before returning fallback."""
        fallback_value = {"lines": [], "total": 0}

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.request = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        with (
            patch("backend.utils.httpx.AsyncClient", return_value=mock_client),
            caplog.at_level(logging.ERROR),
        ):
            result = await agent_request(
                "GET",
                "/nonexistent",
                1,
                None,
                None,
                fallback_value,
                extra_headers=None,
            )

        assert result == fallback_value
        error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert len(error_records) >= 1, "Expected an error log even with fallback"
        assert "Agent request failed" in error_records[0].message
