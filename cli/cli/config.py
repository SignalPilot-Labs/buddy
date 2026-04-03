"""Config resolution: CLI flags > env vars > ~/.buddy/cli.toml > defaults."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_PATH = Path.home() / ".buddy" / "cli.toml"

DEFAULT_API_URL = "http://localhost:3401"


@dataclass
class State:
    """Global CLI state populated by the root callback."""

    api_url: str | None = None
    api_key: str | None = None
    json_mode: bool = False
    project_dir: str | None = None


# Module-level singleton — written by main.py callback, read by commands.
state = State()


def _load_toml() -> dict:
    """Load ~/.buddy/cli.toml if it exists."""
    if CONFIG_PATH.is_file():
        return tomllib.loads(CONFIG_PATH.read_text())
    return {}


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
    """Resolve the API key (None = auth not configured)."""
    if state.api_key:
        return state.api_key
    env = os.environ.get("BUDDY_API_KEY")
    if env:
        return env
    return _load_toml().get("api_key")


def resolve_project_dir() -> str:
    """Resolve the Buddy project directory (where docker-compose.yml lives)."""
    if state.project_dir:
        return state.project_dir
    env = os.environ.get("BUDDY_PROJECT_DIR")
    if env:
        return env
    cfg = _load_toml().get("project_dir")
    if cfg:
        return str(cfg)
    return os.getcwd()
