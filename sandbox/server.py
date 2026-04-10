"""AutoFyn Sandbox Server — HTTP API app wiring.

Starts the aiohttp app, installs auth middleware, and registers the five
endpoint groups (execute, session, file_system, repo, health). All request
handling lives under sandbox/endpoints/.
"""

import hmac
import logging
import os

from aiohttp import web

from config.loader import sandbox_config
from constants import (
    INTERNAL_SECRET_ENV_VAR,
    INTERNAL_SECRET_HEADER,
    SANDBOX_HOST,
    SANDBOX_PORT,
)
from db.connection import connect as db_connect, close as db_close
from handlers.execute import register as register_execute
from handlers.file_system import register as register_file_system
from handlers.health import register as register_health
from handlers.repo import register as register_repo
from handlers.session import register as register_session
from session.manager import SessionManager

cfg = sandbox_config()

logging.basicConfig(level=getattr(logging, cfg.get("log_level", "info").upper()))
log = logging.getLogger("sandbox.server")


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

    register_execute(app)
    register_session(app)
    register_file_system(app)
    register_repo(app)
    register_health(app)

    log.info("Sandbox server starting on :%d", SANDBOX_PORT)
    web.run_app(app, host=SANDBOX_HOST, port=SANDBOX_PORT)


if __name__ == "__main__":
    main()
