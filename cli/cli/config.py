"""Config resolution: CLI flags > env vars > config.json > Docker volume."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from cli.constants import API_KEY_CONTAINER_PATH, BUDDY_HOME, DASHBOARD_CONTAINER, DEFAULT_API_URL, DOCKER_EXEC_TIMEOUT_SECONDS

CONFIG_PATH = Path(BUDDY_HOME) / "config.json"


@dataclass
class State:
    """Global CLI state populated by the root callback."""

    api_key: str | None = None
    api_url: str | None = None
    json_mode: bool = False


# Module-level singleton — written by main.py callback, read by commands.
state = State()


def _load_config() -> dict:
    """Load ~/.buddy/config.json if it exists."""
    if CONFIG_PATH.is_file():
        return json.loads(CONFIG_PATH.read_text())
    return {}


def _save_config(cfg: dict) -> None:
    """Write config dict to ~/.buddy/config.json."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2) + "\n")
    CONFIG_PATH.chmod(0o600)


def _read_key_from_container() -> str | None:
    """Read the API key from the dashboard container's /data volume."""
    result = subprocess.run(
        ["docker", "exec", DASHBOARD_CONTAINER, "cat", API_KEY_CONTAINER_PATH],
        capture_output=True,
        text=True,
        timeout=DOCKER_EXEC_TIMEOUT_SECONDS,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return None


def resolve_api_url() -> str:
    """Resolve the API base URL (no trailing slash)."""
    if state.api_url:
        return state.api_url.rstrip("/")
    env = os.environ.get("BUDDY_API_URL")
    if env:
        return env.rstrip("/")
    cfg = _load_config().get("api_url")
    if cfg:
        return str(cfg).rstrip("/")
    return DEFAULT_API_URL


def resolve_api_key() -> str | None:
    """Resolve the API key.

    Priority: --api-key flag > BUDDY_API_KEY env > config.json > docker volume.
    """
    if state.api_key:
        return state.api_key
    env = os.environ.get("BUDDY_API_KEY")
    if env:
        return env
    cfg_key = _load_config().get("api_key")
    if cfg_key:
        return str(cfg_key)
    return _read_key_from_container()
