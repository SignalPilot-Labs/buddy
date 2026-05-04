"""AutoFyn Sandbox Server — HTTP API app wiring.

Starts the aiohttp app, installs auth middleware, and registers the six
endpoint groups (execute, session, file_system, repo, health, env). All request
handling lives under sandbox/handlers/.
"""

import asyncio
import hmac
import logging
import os

from aiohttp import web

from config.loader import sandbox_config
from constants import (
    AccessNoiseFilter,
    INTERNAL_SECRET_ENV_VAR,
    INTERNAL_SECRET_HEADER,
    SANDBOX_HOST,
    SANDBOX_PORT,
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
    """Load the sandbox authentication secret from SANDBOX_INTERNAL_SECRET env var.

    Works for both local Docker (set by docker-compose) and remote
    (passed as env var over SSH by the connector).
    """
    secret = os.environ.pop(INTERNAL_SECRET_ENV_VAR, "")
    if not secret:
        raise RuntimeError(
            f"{INTERNAL_SECRET_ENV_VAR} is not set — sandbox cannot start"
        )
    return secret


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
    """Touch the heartbeat tracker on authenticated requests only."""
    if request.path != "/health":
        tracker: HeartbeatTracker = request.app["heartbeat"]
        tracker.touch()
    return await handler(request)


async def on_startup(app: web.Application) -> None:
    """Initialize session manager and start heartbeat tracker."""
    app["sessions"] = SessionManager()
    tracker = HeartbeatTracker()
    app["heartbeat"] = tracker
    tracker.start()


async def on_shutdown(app: web.Application) -> None:
    """Stop all sessions and heartbeat tracker."""
    sessions: SessionManager = app["sessions"]
    await sessions.stop_all()
    tracker: HeartbeatTracker = app["heartbeat"]
    tracker.stop()


def _print_bound_port(site: web.TCPSite) -> None:
    """Print the actual bound port for AF_SANDBOX_PORT=0 (OS-assigned)."""
    name = site.name
    # site.name is "http://host:port" — extract the port
    port_str = name.rsplit(":", maxsplit=1)[-1]
    print(f'AF_BOUND {{"port":{port_str}}}', flush=True)


def main() -> None:
    """Start the sandbox HTTP server."""
    app = web.Application(middlewares=[auth_middleware, heartbeat_middleware])
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    register_execute(app)
    register_session(app)
    register_file_system(app)
    register_repo(app)
    register_health(app)
    register_env(app)

    log.info("Sandbox server starting on :%d", SANDBOX_PORT)
    if SANDBOX_PORT == 0:
        _run_with_dynamic_port(app)
    else:
        _print_static_bound(SANDBOX_PORT)
        web.run_app(app, host=SANDBOX_HOST, port=SANDBOX_PORT)


def _print_static_bound(port: int) -> None:
    """Print AF_BOUND marker for a known port before run_app blocks."""
    print(f'AF_BOUND {{"port":{port}}}', flush=True)


def _run_with_dynamic_port(app: web.Application) -> None:
    """Run with OS-assigned port and print AF_BOUND after binding."""

    async def _start() -> None:
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, SANDBOX_HOST, 0)
        await site.start()
        _print_bound_port(site)
        try:
            await asyncio.Event().wait()
        finally:
            await runner.cleanup()

    asyncio.run(_start())


if __name__ == "__main__":
    main()
