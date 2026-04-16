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

from constants import (
    GIT_CONFIG_COUNT_KEY,
    GIT_CONFIG_COUNT_VALUE,
    GIT_CONFIG_ENV_PREFIXES,
    GIT_CONFIG_EXACT_ENV_KEYS,
    GIT_CONFIG_GLOBAL_KEY,
    GIT_CONFIG_GLOBAL_VALUE,
    GIT_CONFIG_NOSYSTEM_KEY,
    GIT_CONFIG_NOSYSTEM_VALUE,
    GIT_ISOLATED_HOME,
    HOME_ENV_KEY,
    SECRET_ENV_KEYS,
    XDG_CONFIG_HOME_KEY,
    XDG_CONFIG_HOME_VALUE,
)

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


def strip_git_config_env(env: dict[str, str]) -> dict[str, str]:
    """Strip GIT_CONFIG_* and related keys from an env dict.

    Removes any key matching GIT_CONFIG_KEY_* or GIT_CONFIG_VALUE_* prefixes,
    plus exact keys in GIT_CONFIG_EXACT_ENV_KEYS (which includes GIT_CONFIG_COUNT,
    GIT_SSH_COMMAND, GIT_EXEC_PATH, GIT_TEMPLATE_DIR, GIT_CONFIG).

    Returns a new dict — does not mutate the input.
    """
    return {
        k: v
        for k, v in env.items()
        if not any(k.startswith(prefix) for prefix in GIT_CONFIG_ENV_PREFIXES)
        and k not in GIT_CONFIG_EXACT_ENV_KEYS
    }


def build_git_env(*, with_token: bool) -> dict[str, str]:
    """Build a subprocess environment dict for git/gh operations.

    Starts from os.environ, strips every key in SECRET_ENV_KEYS and
    GIT_CONFIG_* injection keys, adds git-isolation vars, then optionally
    injects GIT_TOKEN and GH_TOKEN from the module-level holder.

    The git-isolation vars prevent any attacker-written ~/.gitconfig or
    GIT_CONFIG_KEY_* env injection from affecting handler-owned git calls:
      - GIT_CONFIG_NOSYSTEM=1   skip /etc/gitconfig
      - GIT_CONFIG_GLOBAL=/dev/null  skip ~/.gitconfig
      - GIT_CONFIG_COUNT=0   disable env-var config injection
      - XDG_CONFIG_HOME=/nonexistent  no XDG config dir
      - HOME=/tmp/git-isolated  isolated home for credential-helper fallback

    These vars are set ONLY in the dict returned here. They are NEVER set
    in the sandbox process's os.environ — the subagent's own git calls must
    still be able to read legitimate repo config.

    Raises RuntimeError if with_token=True but no token has been set —
    fail-fast per CLAUDE.md; do NOT silently fall back to a no-token env.
    """
    # Start from os.environ, stripping secret keys.
    env: dict[str, str] = {
        k: v for k, v in os.environ.items() if k not in SECRET_ENV_KEYS
    }
    # Strip GIT_CONFIG_* injection keys.
    env = strip_git_config_env(env)

    # Apply git-isolation overrides.
    env[GIT_CONFIG_NOSYSTEM_KEY] = GIT_CONFIG_NOSYSTEM_VALUE
    env[GIT_CONFIG_GLOBAL_KEY] = GIT_CONFIG_GLOBAL_VALUE
    env[GIT_CONFIG_COUNT_KEY] = GIT_CONFIG_COUNT_VALUE
    env[XDG_CONFIG_HOME_KEY] = XDG_CONFIG_HOME_VALUE
    env[HOME_ENV_KEY] = GIT_ISOLATED_HOME

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
