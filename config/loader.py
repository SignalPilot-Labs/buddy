"""Config loader for Buddy.

Resolution order (later overrides earlier):
  1. Built-in defaults (config/config.yml in repo)
  2. ~/.buddy/config.yml (global user config)
  3. .buddy/config.yml (per-project config)
  4. Environment variables (SP_* prefix, highest priority)

On first run, copies the default config to .buddy/config.yml so the
user has a visible, editable file.
"""

import logging
import os
import shutil
from pathlib import Path

import yaml

log = logging.getLogger("config")

_REPO_ROOT = Path(__file__).parent.parent
_DEFAULT_CONFIG = _REPO_ROOT / "config" / "config.yml"
_GLOBAL_CONFIG = Path.home() / ".buddy" / "config.yml"
_PROJECT_CONFIG = _REPO_ROOT / ".buddy" / "config.yml"


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge override into base, recursing into nested dicts."""
    merged = base.copy()
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_yaml(path: Path) -> dict:
    """Load a YAML file, return empty dict if missing or invalid."""
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _ensure_gitignore_entry() -> None:
    """Append .buddy/ to .gitignore if not already listed."""
    gitignore = _REPO_ROOT / ".gitignore"
    entry = ".buddy/"
    if gitignore.exists():
        content = gitignore.read_text()
        if entry in content.splitlines():
            return
        if not content.endswith("\n"):
            content += "\n"
        gitignore.write_text(content + entry + "\n")
    else:
        gitignore.write_text(entry + "\n")
    log.info("Added %s to %s", entry, gitignore)


def _ensure_project_config() -> None:
    """Copy default config to .buddy/config.yml on first run."""
    if _PROJECT_CONFIG.exists():
        return
    if not _DEFAULT_CONFIG.exists():
        return
    _PROJECT_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(_DEFAULT_CONFIG, _PROJECT_CONFIG)
    _ensure_gitignore_entry()
    log.info("Created %s from defaults", _PROJECT_CONFIG)


def _apply_env_overrides(config: dict) -> dict:
    """Override config sections from environment variables."""
    # Sandbox overrides (SP_* prefix)
    sandbox = config.get("sandbox", {})
    sandbox_env_map = {
        "SP_MAX_VMS": ("max_vms", int),
        "SP_VM_MEMORY_MB": ("vm_memory_mb", int),
        "SP_VM_VCPUS": ("vm_vcpus", int),
        "SP_VM_TIMEOUT_SEC": ("vm_timeout_sec", int),
        "SP_LOG_LEVEL": ("log_level", str),
    }
    for env_var, (key, cast) in sandbox_env_map.items():
        val = os.getenv(env_var)
        if val is not None:
            sandbox[key] = cast(val)
    config["sandbox"] = sandbox

    # Database password override
    db = config.get("database", {})
    db_password = os.getenv("DB_PASSWORD")
    if db_password is not None:
        db["password"] = db_password
    config["database"] = db

    return config


def load() -> dict:
    """Load merged config from all sources."""
    _ensure_project_config()
    config = _load_yaml(_DEFAULT_CONFIG)
    config = _deep_merge(config, _load_yaml(_GLOBAL_CONFIG))
    config = _deep_merge(config, _load_yaml(_PROJECT_CONFIG))
    config = _apply_env_overrides(config)
    return config


def sandbox_config() -> dict:
    """Load just the sandbox section."""
    return load().get("sandbox", {})


_REQUIRED_DB_KEYS = {"host", "port", "name", "user", "password", "pool_size", "max_overflow", "pool_timeout", "pool_recycle", "echo"}


def database_config() -> dict:
    """Load just the database section. Raises if missing or incomplete."""
    cfg = load().get("database")
    if not cfg:
        raise RuntimeError("Missing 'database' section in config.yml")
    missing = _REQUIRED_DB_KEYS - set(cfg.keys())
    if missing:
        raise RuntimeError(f"Missing database config keys: {', '.join(sorted(missing))}")
    return cfg
