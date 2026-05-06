"""AutoFyn Sandbox Server — HTTP API app wiring.

Starts the aiohttp app, installs auth middleware, and registers the five
endpoint groups (session, file_system, repo, health, env). All HTTP
handling lives under sandbox/api/; business logic under sandbox/repo/
and sandbox/session/.
"""

import asyncio
import hmac
import logging
import os
import secrets
import socket
import traceback

from aiohttp import web

from config.constants import AF_BOUND_MARKER, AF_READY_MARKER
from config.loader import sandbox_config
from constants import (
    AccessNoiseFilter,
    INTERNAL_SECRET_ENV_VAR,
    INTERNAL_SECRET_HEADER,
    SANDBOX_HOST,
    SANDBOX_PORT,
)
from api.env import register as register_env
from api.file_system import register as register_file_system
from api.health import register as register_health
from api.repo import register as register_repo
from api.session import register as register_session
from shared.heartbeat import HeartbeatTracker
from repo.service import RepoService
from sdk.manager import SessionManager

cfg = sandbox_config()

logging.basicConfig(level=getattr(logging, cfg["log_level"].upper()))
log = logging.getLogger("sandbox.server")


# Suppress health check noise from EVERY logger that could emit it.
# aiohttp.access is the main offender; apply to root as a safety net.
_health_filter = AccessNoiseFilter()
for _logger_name in ("aiohttp.access", "aiohttp.server", "aiohttp.web", ""):
    logging.getLogger(_logger_name).addFilter(_health_filter)


def _load_sandbox_secret() -> str:
    """Load or generate the sandbox authentication secret.

    For local Docker: reads SANDBOX_INTERNAL_SECRET set by docker-compose.
    For remote sandboxes: generates a fresh cryptographic secret at startup
    and transmits it back to the connector via the AF_READY marker over the
    encrypted SSH stdout pipe — never in SSH command-line arguments.
    """
    from_env = os.environ.pop(INTERNAL_SECRET_ENV_VAR, None)
    if from_env is not None:
        return from_env
    return secrets.token_hex(32)


_INTERNAL_SECRET = _load_sandbox_secret()


@web.middleware
async def error_middleware(
    request: web.Request,
    handler,
) -> web.StreamResponse:
    """Catch unhandled exceptions, log the traceback, and return it in the 500 body."""
    try:
        return await handler(request)
    except web.HTTPException as exc:
        if exc.status >= 500:
            log.error("%s %s -> %d: %s", request.method, request.path, exc.status, exc.text)
        raise
    except Exception as exc:
        tb = traceback.format_exc()
        log.error("Unhandled error on %s %s:\n%s", request.method, request.path, tb)
        return web.json_response(
            {"error": str(exc), "traceback": tb},
            status=500,
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
    """Initialize services and start heartbeat tracker."""
    app["sessions"] = SessionManager()
    app["repo_service"] = RepoService()
    tracker = HeartbeatTracker()
    app["heartbeat"] = tracker
    tracker.start()


async def on_shutdown(app: web.Application) -> None:
    """Stop all sessions and heartbeat tracker."""
    sessions: SessionManager = app["sessions"]
    await sessions.stop_all()
    tracker: HeartbeatTracker = app["heartbeat"]
    tracker.stop()


def _emit_markers(port: int, secret: str) -> None:
    """Print AF_BOUND and AF_READY markers after the server has bound the port.

    The secret is embedded in the AF_READY JSON payload and transmitted
    securely over the encrypted SSH stdout pipe.
    """
    host = socket.gethostname()
    print(f'{AF_BOUND_MARKER} {{"port":{port}}}', flush=True)
    print(f'{AF_READY_MARKER} {{"host":"{host}","port":{port},"secret":"{secret}"}}', flush=True)


def main() -> None:
    """Start the sandbox HTTP server."""
    app = web.Application(middlewares=[error_middleware, auth_middleware, heartbeat_middleware])
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    register_session(app)
    register_file_system(app)
    register_repo(app)
    register_health(app)
    register_env(app)

    log.info("Sandbox server starting on :%d", SANDBOX_PORT)

    async def _run() -> None:
        """Bind, emit markers, then block until shutdown."""
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, SANDBOX_HOST, SANDBOX_PORT)
        await site.start()
        _emit_markers(SANDBOX_PORT, _INTERNAL_SECRET)
        try:
            await asyncio.Event().wait()
        finally:
            await runner.cleanup()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
