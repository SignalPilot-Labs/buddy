"""POST /env handler — runtime secret injection for all sandbox types.

Called once by the agent after health check, before bootstrap. Injects
secrets (GIT_TOKEN, CLAUDE_CODE_OAUTH_TOKEN, etc.) into os.environ so
they never appear in Docker inspect, SSH command lines, or Slurm metadata.

If GIT_TOKEN is present, also configures git's global credential helper
so every subsequent git/gh command authenticates transparently.
"""

import asyncio
import logging
import os
import subprocess

from aiohttp import web

from constants import GIT_CREDENTIAL_HELPER, CMD_TIMEOUT

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

_GIT_TOKEN_KEY: str = "GIT_TOKEN"
_GH_TOKEN_KEY: str = "GH_TOKEN"


def _is_denied_key(key: str) -> bool:
    """Check if an env var key is on the denylist."""
    if key in _DENIED_ENV_KEYS:
        return True
    for prefix in _DENIED_ENV_PREFIXES:
        if key.startswith(prefix):
            return True
    return False


async def _install_git_credential_helper() -> None:
    """Configure git's global credential helper to read $GIT_TOKEN at request time.

    Called automatically when GIT_TOKEN is injected via /env. The helper
    is a shell function that echoes the env var — nothing written to disk.
    """
    proc = await asyncio.create_subprocess_exec(
        "git", "config", "--global", "credential.helper", GIT_CREDENTIAL_HELPER,
        cwd="/",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    _, stderr = await asyncio.wait_for(proc.communicate(), timeout=CMD_TIMEOUT)
    if proc.returncode != 0:
        err = (stderr or b"").decode().strip()
        raise RuntimeError(f"git config credential.helper failed: {err}")


async def handle_set_env(request: web.Request) -> web.Response:
    """Accept a JSON dict of env vars and merge them into os.environ.

    If GIT_TOKEN is included, also sets GH_TOKEN to the same value and
    installs the git credential helper for transparent authentication.
    """
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

    if _GIT_TOKEN_KEY in env_vars:
        os.environ[_GH_TOKEN_KEY] = env_vars[_GIT_TOKEN_KEY]
        await _install_git_credential_helper()
        log.info("Git credentials installed via /env")

    log.info("Injected %d env vars", len(env_vars))
    return web.json_response({"ok": True, "count": len(env_vars)})


def register(app: web.Application) -> None:
    """Attach /env route to the aiohttp app."""
    app.router.add_post("/env", handle_set_env)
