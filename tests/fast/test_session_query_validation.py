"""Regression tests for sandbox session.py query parameter validation.

Bug: handle_events (line 48) and handle_trim (line 128) called
int(request.query.get(...)) without error handling. Non-numeric query values
like after_seq=abc or seq=notanumber raised ValueError, which propagated
as an unhandled exception and returned HTTP 500 with a raw traceback.

Fix: Introduced _parse_int_query() helper that raises web.HTTPBadRequest
(400) with a JSON body describing the invalid parameter.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from sandbox.api.session import _parse_int_query, handle_events, handle_trim

HTTP_400 = 400
HTTP_200 = 200


def _make_events_request(after_seq: str) -> web.Request:
    """Build a mocked GET /session/{id}/events?after_seq=<value> request."""
    request = make_mocked_request(
        "GET",
        f"/session/sess-1/events?after_seq={after_seq}",
        match_info={"session_id": "sess-1"},
    )
    event_log = MagicMock()
    sessions = MagicMock()
    sessions.get_event_log = MagicMock(return_value=event_log)
    request.app["sessions"] = sessions
    return request


def _make_trim_request(seq: str) -> web.Request:
    """Build a mocked POST /session/{id}/trim?seq=<value> request."""
    request = make_mocked_request(
        "POST",
        f"/session/sess-1/trim?seq={seq}",
        match_info={"session_id": "sess-1"},
    )
    event_log = MagicMock()
    event_log.trim_through = MagicMock()
    sessions = MagicMock()
    sessions.get_event_log = MagicMock(return_value=event_log)
    request.app["sessions"] = sessions
    return request


class TestParseIntQuery:
    """Unit tests for the _parse_int_query helper."""

    def test_valid_integer_returns_int(self) -> None:
        """Valid numeric string should be parsed to int."""
        request = make_mocked_request("GET", "/path?n=42", match_info={})
        result = _parse_int_query(request, "n", 0)
        assert result == 42

    def test_default_used_when_param_absent(self) -> None:
        """Missing param should return the default value."""
        request = make_mocked_request("GET", "/path", match_info={})
        result = _parse_int_query(request, "n", 7)
        assert result == 7

    def test_zero_is_valid(self) -> None:
        """Zero is a valid integer and must not use the default."""
        request = make_mocked_request("GET", "/path?n=0", match_info={})
        result = _parse_int_query(request, "n", 99)
        assert result == 0

    def test_invalid_string_raises_http_bad_request(self) -> None:
        """Non-numeric string must raise web.HTTPBadRequest."""
        request = make_mocked_request("GET", "/path?n=abc", match_info={})
        with pytest.raises(web.HTTPBadRequest):
            _parse_int_query(request, "n", 0)

    def test_bad_request_body_contains_param_name(self) -> None:
        """HTTPBadRequest body must mention the invalid parameter name."""
        request = make_mocked_request("GET", "/path?mykey=notanint", match_info={})
        exc: web.HTTPBadRequest | None = None
        try:
            _parse_int_query(request, "mykey", 0)
        except web.HTTPBadRequest as e:
            exc = e
        assert exc is not None
        body_text = exc.body.decode() if isinstance(exc.body, bytes) else str(exc.body)
        data = json.loads(body_text)
        assert "mykey" in data["error"]


class TestHandleEventsQueryValidation:
    """handle_events must return 400 when after_seq is non-numeric."""

    @pytest.mark.asyncio
    async def test_non_numeric_after_seq_raises_400(self) -> None:
        """after_seq=abc must trigger HTTPBadRequest (400)."""
        request = _make_events_request("abc")

        with pytest.raises(web.HTTPBadRequest) as exc_info:
            await handle_events(request)

        assert exc_info.value.status_code == HTTP_400

    @pytest.mark.asyncio
    async def test_non_numeric_after_seq_body_has_error(self) -> None:
        """400 response body must contain an 'error' key."""
        request = _make_events_request("notanumber")

        with pytest.raises(web.HTTPBadRequest) as exc_info:
            await handle_events(request)

        body = exc_info.value.body
        body_text = body.decode() if isinstance(body, bytes) else str(body)
        data = json.loads(body_text)
        assert "error" in data


class TestHandleTrimQueryValidation:
    """handle_trim must return 400 when seq is non-numeric."""

    @pytest.mark.asyncio
    async def test_non_numeric_seq_raises_400(self) -> None:
        """seq=notanumber must trigger HTTPBadRequest (400)."""
        request = _make_trim_request("notanumber")

        with pytest.raises(web.HTTPBadRequest) as exc_info:
            await handle_trim(request)

        assert exc_info.value.status_code == HTTP_400

    @pytest.mark.asyncio
    async def test_valid_seq_does_not_raise(self) -> None:
        """seq=5 must not raise and must return a 200 response."""
        request = _make_trim_request("5")

        response = await handle_trim(request)

        assert response.status == HTTP_200
