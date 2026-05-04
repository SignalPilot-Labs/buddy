"""AutoFyn Sandbox Server — HTTP API app wiring.

Starts the aiohttp app, installs auth middleware, and registers the six
endpoint groups (execute, session, file_system, repo, health, env). All request
handling lives under sandbox/handlers/.
"""

import hmac
import logging
import os
import sys

from aiohttp import web

from config.loader import sandbox_config
from constants import (
    AccessNoiseFilter,
    INTERNAL_SECRET_ENV_VAR,
    INTERNAL_SECRET_HEADER,
    SANDBOX_HOST,
    SANDBOX_PORT,
    SANDBOX_SECRET_FILE_ENV_VAR,
)
from handlers.env import register as register_env
from handlers.execute import register as register_execute
from handlers.file_system import register as register_file_system
from handlers.health import register as register_health
from handlers.repo import register as register_repo
from handlers.session import register as register_session
from heartbeat import HeartbeatTracker
from session.manager import SessionManager

cfg = sandbox_config()

logging.basicConfig(level=getattr(logging, cfg["log_level"].upper()))
log = logging.getLogger("sandbox.server")


# Suppress health check noise from EVERY logger that could emit it.
# aiohttp.access is the main offender; apply to root as a safety net.
_health_filter = AccessNoiseFilter()
for _logger_name in ("aiohttp.access", "aiohttp.server", "aiohttp.web", ""):
    logging.getLogger(_logger_name).addFilter(_health_filter)


def _load_sandbox_secret() -> str:
    """Load the sandbox authentication secret.

    Local Docker: reads from SANDBOX_INTERNAL_SECRET env var.
    Remote: reads from file path in AF_SANDBOX_SECRET_FILE env var.
    Exactly one source must be set.
    """
    env_secret = os.environ.pop(INTERNAL_SECRET_ENV_VAR, "")
    file_path = os.environ.get(SANDBOX_SECRET_FILE_ENV_VAR, "")

    if env_secret and file_path:
        raise RuntimeError(
            f"Both {INTERNAL_SECRET_ENV_VAR} and {SANDBOX_SECRET_FILE_ENV_VAR} are set — exactly one required"
        )
    if env_secret:
        return env_secret
    if file_path:
        with open(file_path) as f:
            secret = f.read().strip()
        if not secret:
            raise RuntimeError(f"Secret file {file_path} is empty")
        return secret
    raise RuntimeError(
        f"Neither {INTERNAL_SECRET_ENV_VAR} nor {SANDBOX_SECRET_FILE_ENV_VAR} is set — sandbox cannot start"
    )


_INTERNAL_SECRET = _load_sandbox_secret()


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


@web.middleware
async def heartbeat_middleware(
    request: web.Request,
    handler,
) -> web.StreamResponse:
    """Touch the heartbeat tracker on every incoming request."""
    tracker: HeartbeatTracker = request.app["heartbeat"]
    tracker.touch()
    return await handler(request)


async def on_startup(app: web.Application) -> None:
    """Initialize session manager and start heartbeat tracker."""
    app["sessions"] = SessionManager()
    tracker = HeartbeatTracker()
    app["heartbeat"] = tracker
    tracker.start()


async def on_bind_ready(app: web.Application) -> None:
    """Print AF_BOUND marker for start command wrappers."""
    port = SANDBOX_PORT
    print(f'AF_BOUND {{"port":{port}}}', flush=True)
    sys.stdout.flush()


async def on_shutdown(app: web.Application) -> None:
    """Stop all sessions and heartbeat tracker."""
    sessions: SessionManager = app["sessions"]
    await sessions.stop_all()
    tracker: HeartbeatTracker = app["heartbeat"]
    tracker.stop()


def main() -> None:
    """Start the sandbox HTTP server."""
    app = web.Application(middlewares=[auth_middleware, heartbeat_middleware])
    app.on_startup.append(on_startup)
    app.on_startup.append(on_bind_ready)
    app.on_shutdown.append(on_shutdown)

    register_execute(app)
    register_session(app)
    register_file_system(app)
    register_repo(app)
    register_health(app)
    register_env(app)

    log.info("Sandbox server starting on :%d", SANDBOX_PORT)
    web.run_app(app, host=SANDBOX_HOST, port=SANDBOX_PORT)


if __name__ == "__main__":
    main()
