"""Module-level Git token holder for the sandbox.

Keeps GIT_TOKEN / GH_TOKEN out of os.environ so they are not inherited
by every subprocess spawned in this process (including Claude SDK Bash
subprocesses). Instead, each authenticated git/gh subprocess receives
the token via its own explicit env= dict built by build_git_env().

Deliberately NOT setting GITHUB_TOKEN in build_git_env: `gh` reads
GITHUB_TOKEN first and falls back to GH_TOKEN. Setting GITHUB_TOKEN
could collide with user-provided workflow tokens that the repo under
review legitimately relies on. We use GH_TOKEN only.

The token is process-lifetime: set once at bootstrap via set_git_token(),
read by every subsequent /repo/* handler. The sandbox serves a single
run; no mid-run token rotation is expected. No lock is needed because
aiohttp runs on a single-threaded event loop.
"""

import os

from constants import SECRET_ENV_KEYS

_GIT_TOKEN: str | None = None


def set_git_token(token: str) -> None:
    """Store the git token in the module-level holder. Does NOT touch os.environ."""
    if not token:
        raise ValueError("token must be a non-empty string")
    global _GIT_TOKEN
    _GIT_TOKEN = token


def get_git_token() -> str | None:
    """Return the stored token, or None if not yet set."""
    return _GIT_TOKEN


def clear_git_token() -> None:
    """Reset the stored token to None. Used by tests for isolation."""
    global _GIT_TOKEN
    _GIT_TOKEN = None


def build_git_env(with_token: bool) -> dict[str, str]:
    """Build a subprocess environment dict.

    Starts from os.environ, strips every key in SECRET_ENV_KEYS, then
    optionally injects GIT_TOKEN and GH_TOKEN from the module-level holder.

    Raises RuntimeError if with_token=True but no token has been set —
    fail-fast per CLAUDE.md; do NOT silently fall back to a no-token env.
    """
    env: dict[str, str] = {
        k: v for k, v in os.environ.items() if k not in SECRET_ENV_KEYS
    }
    if with_token:
        token = _GIT_TOKEN
        if token is None:
            raise RuntimeError(
                "build_git_env(with_token=True) called but no token is set — "
                "call set_git_token() first"
            )
        env["GIT_TOKEN"] = token
        env["GH_TOKEN"] = token
    return env
