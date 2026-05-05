"""Regression test: _poll_and_yield must open exactly one DB session per poll cycle.

Bug: _check_run_ended opened its own session instead of accepting the caller's session,
causing 2 DB sessions per SSE poll cycle instead of 1. Under load with many concurrent
SSE streams this doubles DB connection usage unnecessarily.

Fix: _check_run_ended now accepts a required AsyncSession parameter and _poll_and_yield
calls it inside the existing session context, passing the already-open session.
"""

import sys
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


class TestStreamingSessionCount:
    """_poll_and_yield must open exactly one DB session per poll cycle."""

    @pytest.mark.asyncio
    async def test_single_session_per_poll_cycle(self) -> None:
        """Exactly one session context manager is entered during a single _poll_and_yield call."""
        enter_count = 0
        mock_session_obj = MagicMock()

        async def fake_aenter(_self: object) -> MagicMock:
            nonlocal enter_count
            enter_count += 1
            return mock_session_obj

        async def fake_aexit(_self: object, *args: object) -> None:
            pass

        session_ctx = MagicMock()
        session_ctx.__aenter__ = fake_aenter
        session_ctx.__aexit__ = fake_aexit

        check_run_ended_mock = AsyncMock(return_value=None)

        with (
            patch(
                "backend.endpoints.streaming.session",
                return_value=session_ctx,
            ),
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
                check_run_ended_mock,
            ),
        ):
            await _poll_and_yield("run-abc", 0, 0)

        # Verify exactly 1 session was opened
        assert enter_count == 1, (
            f"Expected exactly 1 DB session per poll cycle, got {enter_count}. "
            "_check_run_ended must share the session from _poll_and_yield."
        )

        # Verify _check_run_ended was called with the SAME session object
        check_run_ended_mock.assert_called_once()
        call_args = check_run_ended_mock.call_args
        assert call_args[0][0] is mock_session_obj, (
            "_check_run_ended must receive the session from _poll_and_yield, "
            f"not open its own. Got {call_args[0][0]!r}, expected {mock_session_obj!r}"
        )
