"""Config resolution: CLI flags > env vars > ~/.buddy/cli.toml > Docker volume."""

from __future__ import annotations

import os
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path

from cli.constants import API_KEY_CONTAINER_PATH, BUDDY_HOME, DASHBOARD_CONTAINER, DEFAULT_API_URL

CONFIG_PATH = Path(BUDDY_HOME) / "cli.toml"


@dataclass
class State:
    """Global CLI state populated by the root callback."""

    api_key: str | None = None
    api_url: str | None = None
    json_mode: bool = False


# Module-level singleton — written by main.py callback, read by commands.
state = State()


def _load_toml() -> dict:
    """Load ~/.buddy/cli.toml if it exists."""
    if CONFIG_PATH.is_file():
        return tomllib.loads(CONFIG_PATH.read_text())
    return {}


def _read_key_from_container() -> str | None:
    """Read the API key from the dashboard container's /data volume."""
    try:
        result = subprocess.run(
            ["docker", "exec", DASHBOARD_CONTAINER, "cat", API_KEY_CONTAINER_PATH],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def resolve_api_url() -> str:
    """Resolve the API base URL (no trailing slash)."""
    if state.api_url:
        return state.api_url.rstrip("/")
    env = os.environ.get("BUDDY_API_URL")
    if env:
        return env.rstrip("/")
    cfg = _load_toml().get("api_url")
    if cfg:
        return str(cfg).rstrip("/")
    return DEFAULT_API_URL


def resolve_api_key() -> str | None:
    """Resolve the API key.

    Priority: --api-key flag > BUDDY_API_KEY env > cli.toml > docker volume.
    """
    if state.api_key:
        return state.api_key
    env = os.environ.get("BUDDY_API_KEY")
    if env:
        return env
    toml_key = _load_toml().get("api_key")
    if toml_key:
        return str(toml_key)
    return _read_key_from_container()
