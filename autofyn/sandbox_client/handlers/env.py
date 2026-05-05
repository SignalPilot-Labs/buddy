"""Env handler — typed wrapper around sandbox POST /env.

Injects runtime secrets (GIT_TOKEN, CLAUDE_CODE_OAUTH_TOKEN, etc.) into
the sandbox process environment after creation, before bootstrap. This
is the universal path for all sandbox types (local Docker, remote Docker,
remote Slurm) — secrets never appear in container env, SSH args, or Slurm
metadata.
"""

import logging

import httpx

log = logging.getLogger("sandbox_client.env")


class Env:
    """Typed HTTP wrapper around sandbox POST /env."""

    def __init__(self, http: httpx.AsyncClient) -> None:
        """Initialize with shared HTTP client."""
        self._http = http

    async def set(self, env_vars: dict[str, str]) -> None:
        """Inject env vars into the sandbox process environment.

        If GIT_TOKEN is included, the sandbox also sets GH_TOKEN and
        installs the git credential helper automatically.
        """
        resp = await self._http.post("/env", json={"env_vars": env_vars})
        resp.raise_for_status()
        log.info("Injected %d env vars into sandbox", len(env_vars))
