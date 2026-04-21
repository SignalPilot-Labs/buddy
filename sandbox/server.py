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
    AGENT_URL_ENV_VAR,
    AccessNoiseFilter,
    INTERNAL_SECRET_ENV_VAR,
    INTERNAL_SECRET_HEADER,
    SANDBOX_HOST,
    SANDBOX_PORT,
)
from handlers.execute import register as register_execute
from handlers.file_system import register as register_file_system
from handlers.health import register as register_health
from handlers.repo import register as register_repo
from handlers.session import register as register_session
from session.manager import SessionManager
from session.utils import close_agent_client

cfg = sandbox_config()

logging.basicConfig(level=getattr(logging, cfg["log_level"].upper()))
log = logging.getLogger("sandbox.server")


# Suppress health check noise from EVERY logger that could emit it.
# aiohttp.access is the main offender; apply to root as a safety net.
_health_filter = AccessNoiseFilter()
for _logger_name in ("aiohttp.access", "aiohttp.server", "aiohttp.web", ""):
    logging.getLogger(_logger_name).addFilter(_health_filter)


# Cache the internal secret in Python memory at import time, then scrub
# it from os.environ so subprocesses spawned by the SDK Bash tool (and
# anything else running in this process) cannot inherit it. The sandbox
# process keeps it in memory for auth_middleware — nothing on the OS env.
_INTERNAL_SECRET = os.environ.pop(INTERNAL_SECRET_ENV_VAR, "")
if not _INTERNAL_SECRET:
    raise RuntimeError(
        f"{INTERNAL_SECRET_ENV_VAR} is empty — sandbox cannot start",
    )


@web.middleware
async def auth_middleware(
    request: web.Request,
    handler,
) -> web.StreamResponse:
    """Check X-Internal-Secret header on all endpoints except /health."""
    if request.path == "/health":
        return await handler(request)

    provided = request.headers.get(INTERNAL_SECRET_HEADER, "")
    if not hmac.compare_digest(provided, _INTERNAL_SECRET):
        log.warning("Auth failed from %s on %s", request.remote, request.path)
        return web.json_response({"error": "unauthorized"}, status=401)

    return await handler(request)


async def on_startup(app: web.Application) -> None:
    """Initialize session manager and validate agent URL config."""
    agent_url = os.environ.get(AGENT_URL_ENV_VAR, "")
    if agent_url:
        app["agent_url"] = agent_url
        log.info("Agent URL: %s", agent_url)
    else:
        log.warning("%s is not set — audit logging to agent will fail", AGENT_URL_ENV_VAR)
    app["sessions"] = SessionManager()


async def on_shutdown(app: web.Application) -> None:
    """Stop all sessions and close aiohttp client."""
    sessions: SessionManager = app["sessions"]
    await sessions.stop_all()
    await close_agent_client()
    log.info("Agent HTTP client closed")


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
