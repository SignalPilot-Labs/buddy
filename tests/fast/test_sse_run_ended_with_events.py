"""Regression test for SSE stream delaying run_ended detection.

Bug: _poll_and_yield checked `if found_any else await _check_run_ended(run_id)`,
meaning run_ended was only detected on polls that returned no events. If the
final audit events and the run ending arrived in the same poll window, the SSE
stream would spin on empty polls before eventually detecting run_ended.

Fix: always call _check_run_ended regardless of whether events were found.
"""

import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _import_streaming_module() -> object:
    """Import backend.endpoints.streaming with auth + db stubbed out."""
    auth_mock = MagicMock()
    auth_mock._api_key = "test"
    auth_mock.verify_sse_token = MagicMock()
    sys.modules["backend.auth"] = auth_mock
    sys.modules["backend.db"] = MagicMock()
    sys.modules["db.connection"] = MagicMock()
    sys.modules["db.models"] = MagicMock()

    import backend.endpoints.streaming as streaming_mod
    return streaming_mod


_streaming = _import_streaming_module()
_poll_and_yield = _streaming._poll_and_yield  # type: ignore[attr-defined]


def _make_ts() -> datetime:
    """Return a fixed datetime for sortable event tuples."""
    return datetime(2024, 1, 1, 12, 0, 0)


class TestSseRunEndedWithEvents:
    """_poll_and_yield must return ended_payload even when events are found."""

    @pytest.mark.asyncio
    async def test_ended_payload_returned_when_events_exist(self) -> None:
        """ended_payload is non-None even when tool_calls and audit events are found."""
        ts = _make_ts()
        tool_events = [(ts, 1, "event: tool_call\ndata: {}\n\n")]
        audit_events = [(ts, 2, "event: audit\ndata: {}\n\n")]
        cost_payload = {
            "status": "completed",
            "total_cost_usd": 1.23,
            "total_input_tokens": 1000,
            "total_output_tokens": 500,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
            "context_tokens": 0,
        }

        with (
            patch(
                "backend.endpoints.streaming._fetch_new_tool_calls",
                new_callable=AsyncMock,
                return_value=(tool_events, 42),
            ),
            patch(
                "backend.endpoints.streaming._fetch_new_audit_events",
                new_callable=AsyncMock,
                return_value=(audit_events, 99),
            ),
            patch(
                "backend.endpoints.streaming._check_run_ended",
                new_callable=AsyncMock,
                return_value=cost_payload,
            ),
            patch(
                "backend.endpoints.streaming.session",
                return_value=MagicMock(
                    __aenter__=AsyncMock(return_value=MagicMock()),
                    __aexit__=AsyncMock(return_value=None),
                ),
            ),
        ):
            result = await _poll_and_yield("run-123", 0, 0)

        assert result.ended_payload is not None, (
            "ended_payload must be set even when events were found in the same poll"
        )
        assert result.ended_payload == cost_payload
        assert len(result.events) == 2

    @pytest.mark.asyncio
    async def test_ended_payload_none_when_run_still_active(self) -> None:
        """ended_payload is None when the run has not yet ended."""
        ts = _make_ts()
        tool_events = [(ts, 1, "event: tool_call\ndata: {}\n\n")]

        with (
            patch(
                "backend.endpoints.streaming._fetch_new_tool_calls",
                new_callable=AsyncMock,
                return_value=(tool_events, 10),
            ),
            patch(
                "backend.endpoints.streaming._fetch_new_audit_events",
                new_callable=AsyncMock,
                return_value=([], 0),
            ),
            patch(
                "backend.endpoints.streaming._check_run_ended",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "backend.endpoints.streaming.session",
                return_value=MagicMock(
                    __aenter__=AsyncMock(return_value=MagicMock()),
                    __aexit__=AsyncMock(return_value=None),
                ),
            ),
        ):
            result = await _poll_and_yield("run-123", 0, 0)

        assert result.ended_payload is None
        assert len(result.events) == 1

    @pytest.mark.asyncio
    async def test_ended_payload_set_with_no_events(self) -> None:
        """ended_payload is also set on polls where no events were found."""
        cost_payload = {
            "status": "error",
            "total_cost_usd": 0.0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
            "context_tokens": 0,
        }

        with (
            patch(
                "backend.endpoints.streaming._fetch_new_tool_calls",
                new_callable=AsyncMock,
                return_value=([], 0),
            ),
            patch(
                "backend.endpoints.streaming._fetch_new_audit_events",
                new_callable=AsyncMock,
                return_value=([], 0),
            ),
            patch(
                "backend.endpoints.streaming._check_run_ended",
                new_callable=AsyncMock,
                return_value=cost_payload,
            ),
            patch(
                "backend.endpoints.streaming.session",
                return_value=MagicMock(
                    __aenter__=AsyncMock(return_value=MagicMock()),
                    __aexit__=AsyncMock(return_value=None),
                ),
            ),
        ):
            result = await _poll_and_yield("run-123", 0, 0)

        assert result.ended_payload is not None
        assert result.events == []
