"""AutoFyn Sandbox Server — HTTP API for command execution and Claude SDK sessions.

Endpoints:
  /exec              — run commands (git, npm, etc.)
  /session/start     — start a Claude SDK session
  /session/{id}/*    — stream events, send messages, interrupt, stop
  /health            — health check
"""

import asyncio
import hmac
import json
import logging
import os
import re

from aiohttp import web

from config.loader import sandbox_config
from constants import (
    CMD_TIMEOUT,
    INTERNAL_SECRET_ENV_VAR,
    INTERNAL_SECRET_HEADER,
    SANDBOX_HOST,
    SANDBOX_PORT,
    SECRET_ENV_VARS,
)
from db.connection import connect as db_connect, close as db_close
from session.manager import SessionManager

cfg = sandbox_config()

logging.basicConfig(level=getattr(logging, cfg.get("log_level", "info").upper()))
log = logging.getLogger("sandbox.server")


def require_session(handler):
    """Decorator that returns 404 if the session ID is not found."""
    async def wrapper(request: web.Request):
        try:
            return await handler(request)
        except RuntimeError as e:
            if "not found" in str(e):
                return web.json_response({"error": str(e)}, status=404)
            raise
    wrapper.__name__ = handler.__name__
    return wrapper


# ─── Subprocess env ──────────────────────────────────────────────────────────

_STRIP_PATTERN = re.compile(SECRET_ENV_VARS) if SECRET_ENV_VARS else None


def _safe_env() -> dict[str, str]:
    """Copy os.environ, stripping AutoFyn-internal secrets.

    Project secrets (API keys etc.) are kept — the sandbox needs them
    to build and run the target project. Only our own credentials
    (GIT_TOKEN, CLAUDE_CODE_OAUTH_TOKEN, AGENT_INTERNAL_SECRET, etc.)
    are removed so the LLM cannot read them from the process env.
    """
    return {
        k: v for k, v in os.environ.items()
        if not (_STRIP_PATTERN and _STRIP_PATTERN.search(k))
    }


# ─── Auth Middleware ─────────────────────────────────────────────────────────

@web.middleware
async def auth_middleware(
    request: web.Request,
    handler,
) -> web.StreamResponse:
    """Check X-Internal-Secret header on all endpoints except /health."""
    if request.path == "/health":
        return await handler(request)

    secret = os.environ.get(INTERNAL_SECRET_ENV_VAR, "")
    if not secret:
        log.error("AGENT_INTERNAL_SECRET not set — rejecting all requests")
        return web.json_response({"error": "server misconfigured"}, status=500)

    provided = request.headers.get(INTERNAL_SECRET_HEADER, "")
    if not hmac.compare_digest(provided, secret):
        log.warning("Auth failed from %s on %s", request.remote, request.path)
        return web.json_response({"error": "unauthorized"}, status=401)

    return await handler(request)


# ─── Command Execution ──────────────────────────────────────────────────────

async def handle_exec(request: web.Request) -> web.Response:
    """Execute a command in the sandbox. Security is via gVisor isolation."""
    body = await request.json()
    args: list[str] = body.get("args", [])
    cwd: str = body.get("cwd", "/")
    timeout: int = body.get("timeout", CMD_TIMEOUT)
    extra_env: dict[str, str] = body.get("env", {})

    if not args:
        return web.json_response({"error": "args is required"}, status=400)

    env = _safe_env()
    env.update(extra_env)

    proc: asyncio.subprocess.Process | None = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *args, cwd=cwd, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, env=env,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return web.json_response({
            "stdout": (stdout or b"").decode().strip(),
            "stderr": (stderr or b"").decode().strip(),
            "exit_code": proc.returncode or 0,
        })
    except asyncio.TimeoutError:
        if proc:
            proc.kill()
        return web.json_response({
            "stdout": "", "stderr": "Command timed out", "exit_code": -1,
        }, status=408)
    except FileNotFoundError:
        return web.json_response({
            "stdout": "", "stderr": f"Command not found: {args[0]}", "exit_code": -1,
        }, status=404)


# ─── Session Endpoints ───────────────────────────────────────────────────────

async def handle_session_start(request: web.Request) -> web.Response:
    """Start a Claude SDK session."""
    sessions: SessionManager = request.app["sessions"]
    body = await request.json()
    session_id = await sessions.start(body)
    return web.json_response({"session_id": session_id})


@require_session
async def handle_session_events(request: web.Request) -> web.StreamResponse:
    """Stream SSE events from a session."""
    session_id = request.match_info["session_id"]
    sessions: SessionManager = request.app["sessions"]
    queue = sessions.get_event_queue(session_id)

    response = web.StreamResponse()
    response.content_type = "text/event-stream"
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Connection"] = "keep-alive"
    await response.prepare(request)

    try:
        while True:
            event = await queue.get()
            event_type = event.get("event", "message")
            data = json.dumps(event.get("data", {}))
            payload = f"event: {event_type}\ndata: {data}\n\n"
            await response.write(payload.encode("utf-8"))

            if event_type in ("session_end", "session_error"):
                break
    except (asyncio.CancelledError, ConnectionResetError):
        pass

    return response


@require_session
async def handle_session_message(request: web.Request) -> web.Response:
    """Send a follow-up message to a session."""
    session_id = request.match_info["session_id"]
    sessions: SessionManager = request.app["sessions"]
    body = await request.json()
    await sessions.send_message(session_id, body["text"])
    return web.json_response({"status": "sent"})


@require_session
async def handle_session_interrupt(request: web.Request) -> web.Response:
    """Interrupt a session's current response."""
    session_id = request.match_info["session_id"]
    sessions: SessionManager = request.app["sessions"]
    await sessions.interrupt(session_id)
    return web.json_response({"status": "interrupted"})


@require_session
async def handle_session_stop(request: web.Request) -> web.Response:
    """Stop a session."""
    session_id = request.match_info["session_id"]
    sessions: SessionManager = request.app["sessions"]
    await sessions.stop(session_id)
    return web.json_response({"status": "stopped"})


# ─── Health ──────────────────────────────────────────────────────────────────

async def handle_health(request: web.Request) -> web.Response:
    """Return health status."""
    sessions: SessionManager = request.app["sessions"]
    return web.json_response({
        "status": "healthy",
        "active_sessions": sessions.active_count(),
    })


# ─── App lifecycle ───────────────────────────────────────────────────────────

async def on_startup(app: web.Application) -> None:
    """Initialize DB and session manager."""
    await db_connect()
    log.info("Database connection pool initialized")
    app["sessions"] = SessionManager()


async def on_shutdown(app: web.Application) -> None:
    """Stop all sessions and close DB."""
    sessions: SessionManager = app["sessions"]
    await sessions.stop_all()
    await db_close()
    log.info("Database connection pool closed")


def main() -> None:
    """Start the sandbox HTTP server."""
    app = web.Application(middlewares=[auth_middleware])
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    app.router.add_post("/exec", handle_exec)
    app.router.add_post("/session/start", handle_session_start)
    app.router.add_get("/session/{session_id}/events", handle_session_events)
    app.router.add_post("/session/{session_id}/message", handle_session_message)
    app.router.add_post("/session/{session_id}/interrupt", handle_session_interrupt)
    app.router.add_post("/session/{session_id}/stop", handle_session_stop)
    app.router.add_get("/health", handle_health)

    log.info("Sandbox server starting on :%d", SANDBOX_PORT)
    web.run_app(app, host=SANDBOX_HOST, port=SANDBOX_PORT)


if __name__ == "__main__":
    main()
