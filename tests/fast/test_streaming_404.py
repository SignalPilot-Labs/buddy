"""Regression tests: stream_events and poll_events return 404 for non-existent run_id.

Bug: Both SSE and polling endpoints did not validate run_id existence.
- stream_events would open an infinite SSE loop sending keepalive pings forever.
- poll_events would return HTTP 200 with empty events list.

Fix: _validate_run_exists helper raises HTTPException(404) before any streaming
or polling logic runs. The check in stream_events happens before the
StreamingResponse is constructed so the 404 is a proper HTTP status code,
not an SSE event.
"""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


def _stub_streaming_modules() -> object:
    """Import backend.endpoints.streaming with auth + db stubbed out."""
    auth_mock = MagicMock()
    auth_mock.verify_sse_token = MagicMock()
    auth_mock.verify_api_key = MagicMock()
    sys.modules["backend.auth"] = auth_mock
    sys.modules["backend.db"] = MagicMock()
    sys.modules["db.connection"] = MagicMock()
    sys.modules["db.models"] = MagicMock()

    import backend.endpoints.streaming as streaming_mod
    return streaming_mod


_streaming = _stub_streaming_modules()


def _make_null_session() -> MagicMock:
    """Build a mock async session context manager whose execute() returns None scalar."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=None)
    mock_session_obj = AsyncMock()
    mock_session_obj.execute = AsyncMock(return_value=mock_result)
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session_obj)
    ctx.__aexit__ = AsyncMock(return_value=None)
    return ctx


class TestStreaming404:
    """stream_events and poll_events must return 404 for non-existent run_id."""

    @pytest.mark.asyncio
    async def test_validate_run_exists_raises_for_none_result(self) -> None:
        """_validate_run_exists raises HTTPException(404) when query returns None.

        We patch select() so that the function body can run without SQLAlchemy
        rejecting the mocked Run model class that other test modules put in sys.modules.
        """
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        validate_fn = _streaming._validate_run_exists  # type: ignore[attr-defined]

        with patch("backend.endpoints.streaming.select", return_value=MagicMock()):
            with pytest.raises(HTTPException) as exc_info:
                await validate_fn(mock_session, "nonexistent-id")

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Run not found"

    @pytest.mark.asyncio
    async def test_validate_run_exists_does_not_raise_for_existing_run(self) -> None:
        """_validate_run_exists passes without raising when run is found."""
        mock_run = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_run)
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        validate_fn = _streaming._validate_run_exists  # type: ignore[attr-defined]

        with patch("backend.endpoints.streaming.select", return_value=MagicMock()):
            # Must not raise
            await validate_fn(mock_session, "existing-id")

    @pytest.mark.asyncio
    async def test_stream_events_returns_404_for_missing_run(self) -> None:
        """stream_events raises HTTPException(404) before yielding any SSE events."""
        with (
            patch(
                "backend.endpoints.streaming._validate_run_exists",
                new_callable=AsyncMock,
                side_effect=HTTPException(status_code=404, detail="Run not found"),
            ),
            patch("backend.endpoints.streaming.session", return_value=_make_null_session()),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await _streaming.stream_events(  # type: ignore[attr-defined]
                    run_id="00000000-0000-0000-0000-000000000000",
                    after_tool=-1,
                    after_audit=-1,
                )
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Run not found"

    @pytest.mark.asyncio
    async def test_poll_events_returns_404_for_missing_run(self) -> None:
        """poll_events raises HTTPException(404) before querying tool calls or audit events."""
        with (
            patch(
                "backend.endpoints.streaming._validate_run_exists",
                new_callable=AsyncMock,
                side_effect=HTTPException(status_code=404, detail="Run not found"),
            ),
            patch("backend.endpoints.streaming.session", return_value=_make_null_session()),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await _streaming.poll_events(  # type: ignore[attr-defined]
                    run_id="00000000-0000-0000-0000-000000000000",
                    after_tool=0,
                    after_audit=0,
                    limit=50,
                )
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Run not found"

    @pytest.mark.asyncio
    async def test_stream_events_proceeds_for_existing_run(self) -> None:
        """stream_events returns a StreamingResponse (not 404) for an existing run."""
        from fastapi.responses import StreamingResponse

        with (
            patch(
                "backend.endpoints.streaming._validate_run_exists",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch("backend.endpoints.streaming.session", return_value=_make_null_session()),
            patch(
                "backend.endpoints.streaming._init_cursors",
                new_callable=AsyncMock,
                return_value=(0, 0),
            ),
        ):
            response = await _streaming.stream_events(  # type: ignore[attr-defined]
                run_id="12345678-0000-0000-0000-000000000000",
                after_tool=-1,
                after_audit=-1,
            )

        assert isinstance(response, StreamingResponse)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_poll_events_proceeds_for_existing_run(self) -> None:
        """poll_events returns events dict (not 404) for an existing run."""
        mock_session_obj = AsyncMock()
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_session_obj)
        ctx.__aexit__ = AsyncMock(return_value=None)

        with (
            patch(
                "backend.endpoints.streaming._validate_run_exists",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch("backend.endpoints.streaming.session", return_value=ctx),
            patch(
                "backend.endpoints.streaming._query_recent_tool_calls",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "backend.endpoints.streaming._query_recent_audit_events",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            result = await _streaming.poll_events(  # type: ignore[attr-defined]
                run_id="12345678-0000-0000-0000-000000000000",
                after_tool=0,
                after_audit=0,
                limit=50,
            )

        assert "events" in result
        assert result["events"] == []
