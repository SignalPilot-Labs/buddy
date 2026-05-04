"""POST /env handler — runtime secret injection for remote sandboxes.

The agent calls this once after health check, before bootstrap, to inject
high-value credentials (Claude token, git token) that must not appear in
Slurm job metadata or process environment at startup time.
"""

import logging
import os

from aiohttp import web

log = logging.getLogger("sandbox.handlers.env")

_DENIED_ENV_PREFIXES: tuple[str, ...] = (
    "LD_",
    "DYLD_",
)

_DENIED_ENV_KEYS: frozenset[str] = frozenset({
    "PATH",
    "HOME",
    "SHELL",
    "USER",
    "PYTHONPATH",
    "AF_SANDBOX_PORT",
    "AF_HEARTBEAT_TIMEOUT",
    "SANDBOX_INTERNAL_SECRET",
})


def _is_denied_key(key: str) -> bool:
    """Check if an env var key is on the denylist."""
    if key in _DENIED_ENV_KEYS:
        return True
    for prefix in _DENIED_ENV_PREFIXES:
        if key.startswith(prefix):
            return True
    return False


async def handle_set_env(request: web.Request) -> web.Response:
    """Accept a JSON dict of env vars and merge them into os.environ."""
    body = await request.json()
    if "env_vars" not in body:
        return web.json_response(
            {"error": "Missing required field: env_vars"}, status=400,
        )
    env_vars: dict[str, str] = body["env_vars"]
    denied: list[str] = [k for k in env_vars if _is_denied_key(k)]
    if denied:
        return web.json_response(
            {"error": f"Denied env var keys: {denied}"}, status=400,
        )
    for key, value in env_vars.items():
        os.environ[key] = value
    log.info("Injected %d env vars", len(env_vars))
    return web.json_response({"ok": True, "count": len(env_vars)})


def register(app: web.Application) -> None:
    """Attach /env route to the aiohttp app."""
    app.router.add_post("/env", handle_set_env)
