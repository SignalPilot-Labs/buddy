"""Config loader for AutoFyn.

Resolution order (later overrides earlier):
  1. Built-in defaults (config/config.yml in repo)
  2. ~/.autofyn/config.yml (global user config)
  3. .autofyn/config.yml (per-project config)
  4. Environment variables (AF_* prefix, highest priority)

On first run, copies the default config to .autofyn/config.yml so the
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
_GLOBAL_CONFIG = Path.home() / ".autofyn" / "config.yml"
_PROJECT_CONFIG = _REPO_ROOT / ".autofyn" / "config.yml"


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
    """Append .autofyn/ to .gitignore if not already listed."""
    gitignore = _REPO_ROOT / ".gitignore"
    entry = ".autofyn/"
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
    """Copy default config to .autofyn/config.yml on first run."""
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
    # Sandbox overrides (AF_* prefix)
    sandbox = config["sandbox"]
    sandbox_env_map = {
        "AF_SANDBOX_URL": ("url", str),
        "AF_MAX_VMS": ("max_vms", int),
        "AF_VM_MEMORY_MB": ("vm_memory_mb", int),
        "AF_VM_VCPUS": ("vm_vcpus", int),
        "AF_VM_TIMEOUT_SEC": ("vm_timeout_sec", int),
        "AF_EXEC_TIMEOUT_SEC": ("exec_timeout_sec", int),
        "AF_CLONE_TIMEOUT_SEC": ("clone_timeout_sec", int),
        "AF_NPM_TIMEOUT_SEC": ("npm_timeout_sec", int),
        "AF_LOG_LEVEL": ("log_level", str),
        "AF_ALLOW_DOCKER": ("allow_docker", lambda v: v.lower() in ("1", "true", "yes")),
    }
    for env_var, (key, cast) in sandbox_env_map.items():
        val = os.getenv(env_var)
        if val is not None:
            sandbox[key] = cast(val)
    config["sandbox"] = sandbox

    # Database password override
    db = config["database"]
    db_password = os.getenv("DB_PASSWORD")
    if db_password is not None:
        db["password"] = db_password
    config["database"] = db

    # Agent overrides
    agent = config["agent"]
    agent_env_map: dict[str, tuple[str, type[int]]] = {
        "AF_MAX_ROUNDS": ("max_rounds", int),
        "AF_TOOL_CALL_TIMEOUT_SEC": ("tool_call_timeout_sec", int),
        "AF_SESSION_IDLE_TIMEOUT_SEC": ("session_idle_timeout_sec", int),
        "AF_SUBAGENT_IDLE_KILL_SEC": ("subagent_idle_kill_sec", int),
        "AF_MAX_CONCURRENT_RUNS": ("max_concurrent_runs", int),
    }
    for env_var, (key, cast) in agent_env_map.items():
        val = os.getenv(env_var)
        if val is not None:
            agent[key] = cast(val)
    config["agent"] = agent

    return config


def load(repo_path: Path | None) -> dict:
    """Load merged config from all sources.

    Resolution order (later overrides earlier):
      1. Built-in defaults (config/config.yml)
      2. ~/.autofyn/config.yml (global user config)
      3. .autofyn/config.yml (per-project AutoFyn config)
      4. <repo_path>/.autofyn/config.yml (target repo config, if repo_path given)
      5. AF_* environment variables (highest priority)
    """
    _ensure_project_config()
    config = _load_yaml(_DEFAULT_CONFIG)
    config = _deep_merge(config, _load_yaml(_GLOBAL_CONFIG))
    config = _deep_merge(config, _load_yaml(_PROJECT_CONFIG))
    if repo_path is not None:
        config = _deep_merge(config, _load_yaml(repo_path / ".autofyn" / "config.yml"))
    config = _apply_env_overrides(config)
    return config


def agent_config(repo_path: Path | None) -> dict:
    """Load just the agent section."""
    return load(repo_path)["agent"]


def sandbox_config() -> dict:
    """Load just the sandbox section."""
    return load(None)["sandbox"]


_REQUIRED_DB_KEYS = {
    "host",
    "port",
    "name",
    "user",
    "password",
    "pool_size",
    "max_overflow",
    "pool_timeout",
    "pool_recycle",
    "echo",
}


def database_config() -> dict:
    """Load just the database section. Raises if missing or incomplete."""
    cfg = load(None)["database"]
    missing = _REQUIRED_DB_KEYS - set(cfg.keys())
    if missing:
        raise RuntimeError(
            f"Missing database config keys: {', '.join(sorted(missing))}"
        )
    return cfg


def security_config() -> dict:
    """Load just the security section."""
    return load(None)["security"]
