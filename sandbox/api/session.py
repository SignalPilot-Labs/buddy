"""Claude SDK session HTTP handlers for the sandbox.

Thin wrappers around SessionManager: start, stream events (with sequenced
reads), send follow-up messages, interrupt, stop, ack, delete. Each session
is owned by the manager instance stored on the aiohttp app under "sessions".
"""

import asyncio
import json
import logging

from aiohttp import web

from constants import EVENT_LOG_READ_TIMEOUT_SEC
from sdk.errors import ClientNotReadyError
from sdk.errors import SessionNotFoundError
from sdk.event_log import SessionEventGap
from sdk.manager import SessionManager

log = logging.getLogger("sandbox.endpoints.session")


def _parse_int_query(request: web.Request, param_name: str, default: int) -> int:
    """Parse an integer query parameter, raising HTTP 400 on invalid input."""
    raw = request.query.get(param_name, str(default))
    try:
        return int(raw)
    except ValueError:
        raise web.HTTPBadRequest(
            content_type="application/json",
            text=json.dumps(
                {"error": f"Invalid query parameter '{param_name}': expected integer, got {raw!r}"}
            ),
        )


def _require_session(handler):
    """Decorator that maps SessionNotFoundError to HTTP 404."""
    async def wrapper(request: web.Request):
        try:
            return await handler(request)
        except SessionNotFoundError as e:
            return web.json_response({"error": str(e)}, status=404)
    wrapper.__name__ = handler.__name__
    return wrapper


async def handle_start(request: web.Request) -> web.Response:
    """Start a new Claude SDK session."""
    sessions: SessionManager = request.app["sessions"]
    body = await request.json()
    session_id = await sessions.start(body)
    return web.json_response({"session_id": session_id})


@_require_session
async def handle_events(request: web.Request) -> web.StreamResponse:
    """Stream SSE events from a session, supporting sequenced reads."""
    session_id = request.match_info["session_id"]
    sessions: SessionManager = request.app["sessions"]
    event_log = sessions.get_event_log(session_id)

    after_seq = _parse_int_query(request, "after_seq", 0)

    response = web.StreamResponse()
    response.content_type = "text/event-stream"
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Connection"] = "keep-alive"
    await response.prepare(request)

    try:
        while True:
            try:
                events = await event_log.read_after(after_seq, EVENT_LOG_READ_TIMEOUT_SEC)
            except asyncio.TimeoutError:
                continue
            except SessionEventGap:
                error_payload = json.dumps({"error": "session_event_gap"})
                payload = f"event: session_error\ndata: {error_payload}\n\n"
                await response.write(payload.encode("utf-8"))
                break

            for event in events:
                data = json.dumps({**event.data, "seq": event.seq})
                payload = f"id: {event.seq}\nevent: {event.event}\ndata: {data}\n\n"
                await response.write(payload.encode("utf-8"))
                after_seq = event.seq

                if event.event in ("session_end", "session_error", "session_event_log_overflow"):
                    return response
    except (asyncio.CancelledError, ConnectionResetError):
        pass

    return response


@_require_session
async def handle_message(request: web.Request) -> web.Response:
    """Send a follow-up message to a session."""
    session_id = request.match_info["session_id"]
    sessions: SessionManager = request.app["sessions"]
    body = await request.json()
    try:
        await sessions.send_message(session_id, body["text"])
    except ClientNotReadyError as e:
        return web.json_response({"error": str(e)}, status=503)
    return web.json_response({"status": "sent"})


@_require_session
async def handle_interrupt(request: web.Request) -> web.Response:
    """Interrupt a session's current response."""
    session_id = request.match_info["session_id"]
    sessions: SessionManager = request.app["sessions"]
    try:
        await sessions.interrupt(session_id)
    except ClientNotReadyError as e:
        return web.json_response({"error": str(e)}, status=503)
    return web.json_response({"status": "interrupted"})


@_require_session
async def handle_stop(request: web.Request) -> web.Response:
    """Stop a session."""
    session_id = request.match_info["session_id"]
    sessions: SessionManager = request.app["sessions"]
    await sessions.stop(session_id)
    return web.json_response({"status": "stopped"})


@_require_session
async def handle_unlock(request: web.Request) -> web.Response:
    """Unlock a session's time gate so end_session is allowed."""
    session_id = request.match_info["session_id"]
    sessions: SessionManager = request.app["sessions"]
    sessions.unlock(session_id)
    return web.json_response({"status": "unlocked"})


@_require_session
async def handle_trim(request: web.Request) -> web.Response:
    """Discard processed events up through seq, freeing sandbox memory."""
    session_id = request.match_info["session_id"]
    sessions: SessionManager = request.app["sessions"]
    seq = _parse_int_query(request, "seq", 0)
    event_log = sessions.get_event_log(session_id)
    event_log.trim_through(seq)
    return web.json_response({"status": "trimmed", "through_seq": seq})


@_require_session
async def handle_delete(request: web.Request) -> web.Response:
    """Delete a session and release its event log. Called after draining."""
    session_id = request.match_info["session_id"]
    sessions: SessionManager = request.app["sessions"]
    sessions.delete(session_id)
    return web.json_response({"status": "deleted"})


def register(app: web.Application) -> None:
    """Attach all /session/* routes to the aiohttp app."""
    app.router.add_post("/session/start", handle_start)
    app.router.add_get("/session/{session_id}/events", handle_events)
    app.router.add_post("/session/{session_id}/message", handle_message)
    app.router.add_post("/session/{session_id}/interrupt", handle_interrupt)
    app.router.add_post("/session/{session_id}/stop", handle_stop)
    app.router.add_post("/session/{session_id}/unlock", handle_unlock)
    app.router.add_post("/session/{session_id}/trim", handle_trim)
    app.router.add_delete("/session/{session_id}", handle_delete)
