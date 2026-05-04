"""POST /env handler — runtime secret injection for remote sandboxes.

The agent calls this once after health check, before bootstrap, to inject
high-value credentials (Claude token, git token) that must not appear in
Slurm job metadata or process environment at startup time.
"""

import logging
import os

from aiohttp import web

log = logging.getLogger("sandbox.handlers.env")


async def handle_set_env(request: web.Request) -> web.Response:
    """Accept a JSON dict of env vars and merge them into os.environ."""
    body = await request.json()
    env_vars: dict[str, str] = body.get("env_vars", {})
    for key, value in env_vars.items():
        os.environ[key] = value
    log.info("Injected %d env vars", len(env_vars))
    return web.json_response({"ok": True, "count": len(env_vars)})


def register(app: web.Application) -> None:
    """Attach /env route to the aiohttp app."""
    app.router.add_post("/env", handle_set_env)
