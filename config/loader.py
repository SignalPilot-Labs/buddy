"""Config loader for AutoFyn.

Resolution order (later overrides earlier):
  1. Built-in defaults (config/config.yml in repo)
  2. ~/.autofyn/config.yml (global user config)
  3. .autofyn/config.yml (per-project config)
  4. overlay dict (target repo config, passed by caller)
  5. AF_* environment variables (highest priority)

On first run, copies the default config to .autofyn/config.yml so the
user has a visible, editable file.

Config split:
  Server-level (read once at startup, shared across all runs):
    port, max_concurrent_runs, cost_per_*, session_error_*, idle_nudge_*,
    pulse_check_interval_sec, all sandbox.*, database.*, security.*, dashboard.*

  Per-run (overridable by target repo .autofyn/config.yml):
    max_rounds, tool_call_timeout_sec, session_idle_timeout_sec,
    subagent_idle_kill_sec — see utils/run_config.py RunAgentConfig.
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

# ── Cache ────────────────────────────────────────────────────────────
# Keyed by (str(repo_path) or None, str(overlay) or None).
# Overlay configs are cached too — same overlay dict always produces
# the same result. clear_cache() resets everything (for tests).
_cache: dict[tuple[str | None, str | None], dict] = {}


def clear_cache() -> None:
    """Reset the config cache. For tests only."""
    _cache.clear()


# ── Safety bounds ────────────────────────────────────────────────────
# Per-run values that the target repo's .autofyn/config.yml can override.
# These bounds prevent a repo (or an AI agent editing the file) from
# setting values that burn infinite compute or break the watchdog loop.
_AGENT_BOUNDS: dict[str, tuple[int | float, int | float]] = {
    "max_rounds": (1, 512),
    "tool_call_timeout_sec": (60, 7200),          # 1 min – 2 hours
    "session_idle_timeout_sec": (30, 600),         # 30s – 10 min
    "subagent_idle_kill_sec": (60, 3600),          # 1 min – 1 hour
    "max_concurrent_runs": (1, 20),
    "session_error_max_retries": (0, 10),
    "session_error_base_backoff_sec": (1, 30),
    "idle_nudge_max_attempts": (1, 10),
    "pulse_check_interval_sec": (5, 120),
}

_SANDBOX_BOUNDS: dict[str, tuple[int | float, int | float]] = {
    "max_vms": (1, 50),
    "vm_memory_mb": (256, 8192),
    "vm_vcpus": (1, 16),
    "vm_timeout_sec": (30, 3600),
    "exec_timeout_sec": (10, 600),
    "clone_timeout_sec": (30, 1800),
    "npm_timeout_sec": (30, 1800),
    "session_start_timeout_sec": (5, 120),
    "health_timeout_sec": (1, 60),
    "max_concurrent_sessions": (1, 20),
    "session_event_queue_size": (100, 10000),
    "retry_max_attempts": (1, 10),
    "retry_base_delay_sec": (0.5, 30.0),
    "early_exit_threshold_min": (1.0, 30.0),
}

# Required keys per top-level section. load() raises RuntimeError if any
# are missing after merge — catches typos at startup, not mid-run.
_REQUIRED_AGENT_KEYS = {
    "port",
    "max_rounds",
    "tool_call_timeout_sec",
    "session_idle_timeout_sec",
    "subagent_idle_kill_sec",
    "max_concurrent_runs",
    "cost_per_input_token",
    "cost_per_output_token",
    "cost_per_cache_read_token",
    "cost_per_cache_write_token",
    "session_error_max_retries",
    "session_error_base_backoff_sec",
    "idle_nudge_max_attempts",
    "pulse_check_interval_sec",
}

_REQUIRED_SANDBOX_KEYS = {
    "url",
    "exec_timeout_sec",
    "clone_timeout_sec",
    "health_timeout_sec",
    "vm_timeout_sec",
    "max_concurrent_sessions",
    "session_event_queue_size",
    "log_level",
    "retry_max_attempts",
    "retry_base_delay_sec",
    "early_exit_threshold_min",
}

_REQUIRED_SECURITY_KEYS = {
    "credential_patterns",
    "secret_env_vars",
}

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


# ── Merge helper ─────────────────────────────────────────────────────

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
    sandbox = config.get("sandbox", {})
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
    db = config.get("database", {})
    db_password = os.getenv("DB_PASSWORD")
    if db_password is not None:
        db["password"] = db_password
    config["database"] = db

    # Agent overrides
    agent = config.get("agent", {})
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


def _clamp_section(
    section: dict,
    bounds: dict[str, tuple[int | float, int | float]],
    section_name: str,
) -> dict:
    """Clamp numeric values to their defined bounds. Logs warnings on clamp."""
    for key, (lo, hi) in bounds.items():
        if key not in section:
            continue
        raw = section[key]
        if not isinstance(raw, (int, float)):
            continue
        clamped_value = max(lo, min(hi, raw))
        # Preserve original type only when bounds are integers.
        # Float bounds (e.g. 0.5) must not be truncated by int().
        if isinstance(lo, int) and isinstance(hi, int) and isinstance(raw, int):
            clamped = int(clamped_value)
        else:
            clamped = float(clamped_value)
        if clamped != raw:
            log.warning(
                "Config %s.%s=%s clamped to [%s, %s] → %s",
                section_name, key, raw, lo, hi, clamped,
            )
            section[key] = clamped
    return section


def _validate_required_keys(config: dict) -> None:
    """Raise RuntimeError if any required config keys are missing."""
    checks: list[tuple[str, set[str]]] = [
        ("agent", _REQUIRED_AGENT_KEYS),
        ("sandbox", _REQUIRED_SANDBOX_KEYS),
        ("security", _REQUIRED_SECURITY_KEYS),
        ("database", _REQUIRED_DB_KEYS),
    ]
    for section_name, required in checks:
        section = config.get(section_name)
        if section is None:
            raise RuntimeError(f"Missing '{section_name}' section in config.yml")
        missing = required - set(section.keys())
        if missing:
            raise RuntimeError(
                f"Missing {section_name} config keys: {', '.join(sorted(missing))}"
            )


def load(overlay: dict | None) -> dict:
    """Load merged config from all sources.

    Resolution order (later overrides earlier):
      1. Built-in defaults (config/config.yml)
      2. ~/.autofyn/config.yml (global user config)
      3. .autofyn/config.yml (per-project AutoFyn config)
      4. overlay dict (target repo config, if provided)
      5. AF_* environment variables (highest priority)

    Results are cached by overlay identity. Pass None for server-level config.
    """
    cache_key: tuple[str | None, str | None] = (
        None,
        str(sorted(overlay.items())) if overlay else None,
    )
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    _ensure_project_config()
    config = _load_yaml(_DEFAULT_CONFIG)
    config = _deep_merge(config, _load_yaml(_GLOBAL_CONFIG))
    config = _deep_merge(config, _load_yaml(_PROJECT_CONFIG))
    if overlay is not None:
        config = _deep_merge(config, overlay)
    config = _apply_env_overrides(config)

    # Validate and clamp
    _validate_required_keys(config)
    config["agent"] = _clamp_section(config["agent"], _AGENT_BOUNDS, "agent")
    config["sandbox"] = _clamp_section(config["sandbox"], _SANDBOX_BOUNDS, "sandbox")

    _cache[cache_key] = config
    return config


def agent_config() -> dict:
    """Load just the agent section (server-level, no overlay)."""
    return load(None)["agent"]


def sandbox_config() -> dict:
    """Load just the sandbox section."""
    return load(None)["sandbox"]


def database_config() -> dict:
    """Load just the database section."""
    return load(None)["database"]


def security_config() -> dict:
    """Load just the security section."""
    return load(None)["security"]
