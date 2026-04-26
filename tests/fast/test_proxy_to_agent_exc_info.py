"""Regression test: agent_request log.error must include exc_info=True.

Bug: When the httpx call inside agent_request raises a non-HTTP exception,
log.error() was called without exc_info=True, discarding the stack trace.

Fix: Add exc_info=True to the log.error() call in agent_request.
"""

from __future__ import annotations

import logging
import sys
from unittest.mock import MagicMock, patch

import pytest

# Stub out db.connection before importing backend.utils
if "db.connection" not in sys.modules:
    sys.modules["db.connection"] = MagicMock()

import backend.utils as utils_mod  # noqa: E402


class TestProxyToAgentExcInfo:
    """agent_request must log with exc_info=True on connection failure."""

    @pytest.mark.asyncio
    async def test_log_error_has_exc_info_on_connection_failure(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Stack trace must be attached when httpx raises a connection error."""

        def raise_connection_error(*args: object, **kwargs: object) -> None:
            raise ConnectionError("failed to connect to agent")

        with (
            patch.object(utils_mod.httpx, "AsyncClient") as mock_client_cls,
            caplog.at_level(logging.ERROR, logger="backend.utils"),
        ):
            mock_client = MagicMock()
            mock_client.__aenter__ = MagicMock(side_effect=raise_connection_error)
            mock_client.__aexit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = mock_client

            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                await utils_mod.agent_request(
                    method="GET",
                    path="/health",
                    timeout=5,
                    json_body=None,
                    params=None,
                    fallback=None,
                    extra_headers=None,
                )

        assert exc_info.value.status_code == 502

        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert error_records, "Expected at least one ERROR log record"
        record = error_records[0]
        assert record.exc_info is not None, (
            "log.error must be called with exc_info=True so the stack trace is preserved"
        )
