"""Regression test for SSE stream sending ping before run_ended.

Bug: The event_generator while loop checked `if not result.events` (emit ping)
BEFORE checking `if result.ended_payload` (emit run_ended + return).
When a run ended with no new events in the final poll, the stream emitted:
  event: ping
  event: run_ended
instead of just:
  event: run_ended

Fix: Check ended_payload first so the generator returns immediately without
emitting a spurious ping.
"""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _import_streaming_module() -> object:
    """Import backend.endpoints.streaming with auth + db stubbed out."""
    auth_mock = MagicMock()
    auth_mock._api_key = "test"
    auth_mock.verify_api_key_or_query = MagicMock()
    sys.modules["backend.auth"] = auth_mock
    sys.modules["backend.db"] = MagicMock()
    sys.modules["db.connection"] = MagicMock()
    sys.modules["db.models"] = MagicMock()

    import backend.endpoints.streaming as streaming_mod
    return streaming_mod


_streaming = _import_streaming_module()


async def _collect_events(run_id: str) -> list[str]:
    """Run the SSE event_generator once (one poll) and collect all yielded strings."""
    streaming_mod = _streaming
    stream_events_fn = streaming_mod.stream_events  # type: ignore[attr-defined]

    # We test event_generator directly by extracting it from a StreamingResponse
    # Patch _init_cursors to return (0, 0) and asyncio.sleep to stop after 1 iteration
    response = await stream_events_fn(run_id=run_id, after_tool=0, after_audit=0)

    events: list[str] = []
    async for chunk in response.body_iterator:  # type: ignore[attr-defined]
        events.append(chunk)
        # Stop after we see run_ended or ping — we only want one iteration
        if "run_ended" in chunk or ("ping" in chunk and len(events) >= 2):
            break
    return events


class TestSseNoPingBeforeEnded:
    """When run ends with no new events, only run_ended should be emitted (no ping)."""

    @pytest.mark.asyncio
    async def test_run_ended_no_ping_when_no_events(self) -> None:
        """ended_payload set, events empty → emit run_ended only, no ping."""
        ended_payload = {
            "status": "completed",
            "total_cost_usd": 0.5,
            "total_input_tokens": 100,
            "total_output_tokens": 50,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
            "context_tokens": 0,
        }
        # Build a PollResult-like NamedTuple via the module
        _PollResult = _streaming._PollResult  # type: ignore[attr-defined]
        poll_result = _PollResult(events=[], last_tool_id=0, last_audit_id=0, ended_payload=ended_payload)

        with (
            patch("backend.endpoints.streaming._init_cursors", new=AsyncMock(return_value=(0, 0))),
            patch(
                "backend.endpoints.streaming._poll_and_yield",
                new=AsyncMock(return_value=poll_result),
            ),
        ):
            events = await _collect_events("run-test-123")

        # Filter out the initial connected event
        non_connected = [e for e in events if "connected" not in e]

        run_ended_events = [e for e in non_connected if "run_ended" in e]
        ping_events = [e for e in non_connected if "ping" in e]

        assert len(run_ended_events) == 1, "run_ended must be emitted exactly once"
        assert len(ping_events) == 0, (
            "ping must NOT be emitted when run ends with no events — "
            f"got ping events: {ping_events}"
        )

    @pytest.mark.asyncio
    async def test_ping_emitted_when_no_events_and_not_ended(self) -> None:
        """events empty, ended_payload None → emit ping (normal keepalive)."""
        _PollResult = _streaming._PollResult  # type: ignore[attr-defined]
        poll_result_empty = _PollResult(events=[], last_tool_id=0, last_audit_id=0, ended_payload=None)
        ended_payload = {"status": "completed", "total_cost_usd": 0.0,
                         "total_input_tokens": 0, "total_output_tokens": 0,
                         "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
                         "context_tokens": 0}
        poll_result_ended = _PollResult(events=[], last_tool_id=0, last_audit_id=0, ended_payload=ended_payload)

        call_count = 0

        async def side_effect(*args: object, **kwargs: object) -> object:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return poll_result_empty
            return poll_result_ended

        with (
            patch("backend.endpoints.streaming._init_cursors", new=AsyncMock(return_value=(0, 0))),
            patch("backend.endpoints.streaming._poll_and_yield", new=AsyncMock(side_effect=side_effect)),
            patch("backend.endpoints.streaming.asyncio.sleep", new=AsyncMock()),
        ):
            events = await _collect_events("run-test-456")

        non_connected = [e for e in events if "connected" not in e]
        ping_events = [e for e in non_connected if "ping" in e]

        assert len(ping_events) >= 1, "ping must be emitted when no events and run not ended"
