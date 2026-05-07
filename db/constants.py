"""Shared constants importable from both the agent and dashboard containers.

The `db` package is the only Python package imported by both `autofyn/` and
`dashboard/backend/`, so cross-container constants that must not drift live here.
"""

import re

import posixpath

from config.constants import SANDBOX_REPO_DIR as SANDBOX_REPO_DIR

# ── Secret Redaction ──
SECRET_REDACT_MASK: str = "***REDACTED***"

# ── Run Statuses ──
# Individual status values — used at assignment/comparison sites.
RUN_STATUS_STARTING: str = "starting"
RUN_STATUS_RUNNING: str = "running"
RUN_STATUS_PAUSED: str = "paused"
RUN_STATUS_RATE_LIMITED: str = "rate_limited"
RUN_STATUS_COMPLETED: str = "completed"
RUN_STATUS_COMPLETED_NO_CHANGES: str = "completed_no_changes"
RUN_STATUS_STOPPED: str = "stopped"
RUN_STATUS_ERROR: str = "error"
RUN_STATUS_CRASHED: str = "crashed"
RUN_STATUS_KILLED: str = "killed"
RUN_STATUS_CONNECTOR_LOST: str = "connector_lost"

# Canonical set of all run status values.
# Cross-language sync test (test_run_status_sync.py) verifies this matches
# the TypeScript RunStatus union in dashboard/frontend/lib/types.ts.
RUN_STATUSES: frozenset[str] = frozenset({
    RUN_STATUS_STARTING,
    RUN_STATUS_RUNNING,
    RUN_STATUS_PAUSED,
    RUN_STATUS_RATE_LIMITED,
    RUN_STATUS_COMPLETED,
    RUN_STATUS_COMPLETED_NO_CHANGES,
    RUN_STATUS_STOPPED,
    RUN_STATUS_ERROR,
    RUN_STATUS_CRASHED,
    RUN_STATUS_KILLED,
    RUN_STATUS_CONNECTOR_LOST,
})

# Statuses where the run is still alive (not terminal).
ACTIVE_RUN_STATUSES: frozenset[str] = frozenset({
    RUN_STATUS_STARTING,
    RUN_STATUS_RUNNING,
    RUN_STATUS_PAUSED,
    RUN_STATUS_RATE_LIMITED,
    RUN_STATUS_CONNECTOR_LOST,
})

# Truly terminal statuses — run's background task has stopped.
TERMINAL_RUN_STATUSES: frozenset[str] = frozenset({
    RUN_STATUS_COMPLETED,
    RUN_STATUS_COMPLETED_NO_CHANGES,
    RUN_STATUS_STOPPED,
    RUN_STATUS_ERROR,
    RUN_STATUS_CRASHED,
    RUN_STATUS_KILLED,
})

# Statuses that the /cleanup endpoint removes from the in-memory registry.
# Only terminal runs — active runs (including rate_limited) still have
# live sandboxes and background tasks.
CLEANABLE_RUN_STATUSES: frozenset[str] = frozenset(
    TERMINAL_RUN_STATUSES
)

# ── Models ──
# Pinned to exact SDK model IDs. No aliases, no translation layer.
SUPPORTED_OPUS: str = "claude-opus-4-6"
SUPPORTED_SONNET: str = "claude-sonnet-4-6"
LEGACY_OPUS: str = "claude-opus-4-5"

VALID_MODELS: tuple[str, ...] = (SUPPORTED_OPUS, SUPPORTED_SONNET, LEGACY_OPUS)
DEFAULT_MODEL: str = SUPPORTED_OPUS
VALID_MODELS_PATTERN: str = f"^({'|'.join(VALID_MODELS)})$"

# Structured metadata for /api/models endpoint.
SUPPORTED_MODELS: list[dict[str, str]] = [
    {"id": SUPPORTED_OPUS, "label": "Claude Opus 4.6", "badge": "Opus", "tier": "opus"},
    {"id": SUPPORTED_SONNET, "label": "Claude Sonnet 4.6", "badge": "Sonnet", "tier": "sonnet"},
    {"id": LEGACY_OPUS, "label": "Claude Opus 4.5", "badge": "Opus 4.5", "tier": "legacy"},
]

# ── Effort ──
VALID_EFFORTS: tuple[str, ...] = ("low", "medium", "high", "max")
DEFAULT_EFFORT: str = "high"
DEFAULT_BASE_BRANCH: str = "main"
VALID_EFFORTS_PATTERN: str = f"^({'|'.join(VALID_EFFORTS)})$"

# Models that support effort="max". Others get downgraded to "high".
MODELS_SUPPORTING_MAX_EFFORT: frozenset[str] = frozenset({SUPPORTED_OPUS, SUPPORTED_SONNET})


# ── Host Mounts ──
# Paths that must never be mounted into a sandbox, regardless of user config.
# Prevents credential leaks, system damage, and container escapes.
BLOCKED_MOUNT_PREFIXES: tuple[str, ...] = (
    "/etc",
    "/proc",
    "/sys",
    "/dev",
    "/var/run",
    "/root",
    "/boot",
    "/sbin",
    "/usr/sbin",
)
BLOCKED_MOUNT_PATHS: frozenset[str] = frozenset({
    "/",
    "/home",
    "/tmp",
    "/var",
    "/usr",
})
VALID_MOUNT_MODES: frozenset[str] = frozenset({"ro", "rw"})

# Container paths that must not be overwritten by user mounts.
# The repo root itself is blocked (it's a Docker volume), but subdirs
# like /home/agentuser/repo/data are allowed — users mount data there.
BLOCKED_CONTAINER_PATHS: frozenset[str] = frozenset({
    "/home/agentuser/.claude",
    "/tmp/repo-clone",
})
BLOCKED_CONTAINER_EXACT_PATHS: frozenset[str] = frozenset({
    "/",
    SANDBOX_REPO_DIR,
})
MAX_HOST_MOUNTS: int = 10
MAX_MCP_SERVERS: int = 10


def validate_host_mount(
    host_path: str,
    container_path: str,
    mode: str,
) -> str | None:
    """Validate a single host mount entry. Returns error string or None if valid.

    Paths are normalized with posixpath.normpath to resolve `..`, `//`,
    and trailing slashes before checking against blocked lists.
    """
    if not host_path or not host_path.startswith("/"):
        return f"host_path must be an absolute path, got: {host_path!r}"
    if not container_path or not container_path.startswith("/"):
        return f"container_path must be an absolute path, got: {container_path!r}"
    if mode not in VALID_MOUNT_MODES:
        return f"mode must be one of {VALID_MOUNT_MODES}, got: {mode!r}"

    resolved_host = posixpath.normpath(host_path)
    resolved_container = posixpath.normpath(container_path)

    # Container path checks
    if resolved_container in BLOCKED_CONTAINER_EXACT_PATHS:
        return f"container_path would overwrite sandbox internals: {container_path!r}"
    for blocked in BLOCKED_CONTAINER_PATHS:
        if resolved_container == blocked or resolved_container.startswith(blocked + "/"):
            return f"container_path would overwrite sandbox internals: {container_path!r}"

    # Host path checks
    if resolved_host in BLOCKED_MOUNT_PATHS:
        return f"host_path is blocked: {host_path!r}"
    for prefix in BLOCKED_MOUNT_PREFIXES:
        if resolved_host == prefix or resolved_host.startswith(prefix + "/"):
            return f"host_path under blocked prefix {prefix}: {host_path!r}"
    return None


# ── Remote Sandbox Timeouts ──
SSH_CONNECT_TIMEOUT_SEC: int = 30
SANDBOX_QUEUE_TIMEOUT_SEC: int = 1800
SANDBOX_BOOT_TIMEOUT_SEC: int = 120
SANDBOX_STOP_TIMEOUT_SEC: int = 60
CONNECTOR_RECONNECT_TIMEOUT_SEC: int = 300
SANDBOX_HEARTBEAT_TIMEOUT_SEC: int = 1800

# ── Remote Sandbox Types ──
SANDBOX_TYPE_SLURM: str = "slurm"
SANDBOX_TYPE_DOCKER: str = "docker"
VALID_SANDBOX_TYPES: frozenset[str] = frozenset({SANDBOX_TYPE_SLURM, SANDBOX_TYPE_DOCKER})

# ── Sandbox Protocol ──
SANDBOX_PROTOCOL_VERSION: int = 1

# Regex for safe remote mount paths: absolute POSIX, no spaces or shell metacharacters.
REMOTE_MOUNT_PATH_RE: re.Pattern[str] = re.compile(r"^/[a-zA-Z0-9._/\-]+$")

# SSH target validation: user@host, host, host:port — no shell metacharacters.
SSH_TARGET_RE: re.Pattern[str] = re.compile(r"^[a-zA-Z0-9@._:/\-]+$")

# Work directory validation: ~/path or /absolute/path — no shell metacharacters.
WORK_DIR_RE: re.Pattern[str] = re.compile(r"^(~/?|/)[a-zA-Z0-9._/\-]*$")

# ── Remote Sandbox Config CRUD Limits ──
REMOTE_SANDBOX_KEY_PREFIX: str = "remote_sandbox:"
REMOTE_MOUNTS_KEY_PREFIX: str = "remote_mounts:"
SANDBOX_NAME_MIN_LEN: int = 1
SANDBOX_NAME_MAX_LEN: int = 256
SSH_TARGET_MIN_LEN: int = 1
SSH_TARGET_MAX_LEN: int = 512
START_CMD_MIN_LEN: int = 1
START_CMD_MAX_LEN: int = 65536
QUEUE_TIMEOUT_MIN: int = 60
QUEUE_TIMEOUT_MAX: int = 86400
HEARTBEAT_TIMEOUT_MIN: int = 60
HEARTBEAT_TIMEOUT_MAX: int = 86400
MAX_REMOTE_MOUNTS: int = 50

_BLOCKED_REMOTE_MOUNT_PREFIXES: tuple[str, ...] = ("/proc", "/sys", "/dev")


def validate_remote_mount_path(path: str) -> str | None:
    """Validate a remote mount path. Returns error string or None if valid."""
    if not path or not path.startswith("/"):
        return f"Path must be absolute, got: {path!r}"
    if not REMOTE_MOUNT_PATH_RE.fullmatch(path):
        return f"Path contains invalid characters (spaces, shell metacharacters not allowed): {path!r}"
    normalized = posixpath.normpath(path)
    for prefix in _BLOCKED_REMOTE_MOUNT_PREFIXES:
        if normalized == prefix or normalized.startswith(prefix + "/"):
            return f"Path under blocked prefix {prefix}: {path!r}"
    return None


# ── Starter Presets ──
# Preset keys for the "Quick Start" cards in the new-run modal.
# The agent resolves each key to a markdown prompt in prompts/starter/.
STARTER_PRESET_KEYS: tuple[str, ...] = (
    "security_hardening",
    "bug_bash",
    "code_quality",
    "test_coverage",
)
VALID_PRESET_PATTERN: str = f"^({'|'.join(STARTER_PRESET_KEYS)})$"


# ── Tool Call Phases ──
# Canonical set of valid phase values for tool call events.
# Mirrors the DB CheckConstraint in db/models.py.
TOOL_CALL_PHASES: frozenset[str] = frozenset({"pre", "post"})

# ── UUID Pattern ──
# Strict UUID pattern (hex with hyphens, grouped, case-insensitive).
UUID_PATTERN: str = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"

# ── Input Limits ──
# Maximum characters for a user-submitted prompt.  ~25 K tokens — generous
# for any legitimate use-case but prevents multi-MB DoS payloads.
PROMPT_MAX_LEN: int = 100_000

# ── Env Var Validation ──
# Regex for a valid POSIX environment variable key: must start with a letter or
# underscore, followed by letters, digits, or underscores only.  No spaces,
# no shell metacharacters, no digits in the first position.
ENV_VAR_KEY_RE: re.Pattern[str] = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Maximum byte lengths for env var keys and values.
ENV_VAR_MAX_KEY_LEN: int = 256
ENV_VAR_MAX_VALUE_LEN: int = 65536

# Maximum number of env vars that can be stored per repo.
MAX_ENV_VARS: int = 100

# ── GitHub Repo ──
# Maximum length and pattern for owner/repo slugs (ASCII-only).
GITHUB_REPO_MAX_LEN: int = 256
GITHUB_REPO_PATTERN: str = r"^[a-zA-Z0-9_\-\.]+/[a-zA-Z0-9_\-\.]+$"
GITHUB_REPO_RE: re.Pattern[str] = re.compile(GITHUB_REPO_PATTERN)


def validate_prompt_length(v: str | None) -> str | None:
    """Shared prompt length validator for Pydantic models."""
    if v is not None and len(v) > PROMPT_MAX_LEN:
        raise ValueError(f"prompt must be under {PROMPT_MAX_LEN} characters")
    return v


def validate_github_repo(v: str | None) -> str | None:
    """Shared github_repo format and length validator for Pydantic models."""
    if v is None:
        return v
    if len(v) > GITHUB_REPO_MAX_LEN:
        raise ValueError(f"github_repo must be under {GITHUB_REPO_MAX_LEN} characters")
    if not GITHUB_REPO_RE.fullmatch(v):
        raise ValueError("github_repo must match owner/repo format")
    return v

# ── SQL DDL Safety ──
# Allowlisted values for control_signals.signal CHECK constraint and migration DDL.
# Used by validate_sql_identifier() to prevent SQL injection via f-string DDL.
VALID_CONTROL_SIGNALS: tuple[str, ...] = ("pause", "resume", "inject", "stop", "unlock", "kill")

# Allowlisted column names for cache token migration DDL.
MIGRATION_CACHE_TOKEN_COLUMNS: tuple[str, ...] = (
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)

# Allowlisted table names for idempotency_key migration DDL.
MIGRATION_IDEMPOTENCY_TABLES: tuple[str, ...] = ("tool_calls", "audit_log")

# Sandbox snapshot columns for migration DDL: (column_name, sql_type) pairs.
# All column names are safe SQL identifiers (lowercase letters and underscores only).
MIGRATION_SANDBOX_SNAPSHOT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("sandbox_id", "VARCHAR"),
    ("sandbox_backend_id", "VARCHAR"),
)

# Columns removed after /env refactor — no longer snapshotted per-run.
# The sandbox config lives in the settings table keyed by sandbox_id.
MIGRATION_SANDBOX_DROP_COLUMNS: tuple[str, ...] = (
    "sandbox_type",
    "sandbox_ssh_target",
    "sandbox_start_cmd",
    "sandbox_remote_host",
    "sandbox_remote_port",
)

# Allowlist of column names from MIGRATION_SANDBOX_SNAPSHOT_COLUMNS for DDL safety.
MIGRATION_SANDBOX_SNAPSHOT_COL_NAMES: tuple[str, ...] = tuple(
    col for col, _ in MIGRATION_SANDBOX_SNAPSHOT_COLUMNS
)

# Regex for a safe SQL identifier: lowercase letters, digits, and underscores only.
# No SQL metacharacters, no quotes, no spaces.
SAFE_SQL_IDENTIFIER_RE: re.Pattern[str] = re.compile(r"^[a-z_][a-z0-9_]*$")


def validate_sql_identifier(value: str, allowlist: tuple[str, ...]) -> str:
    """Validate a SQL identifier against an allowlist and a safe-character regex.

    Both checks are defense-in-depth: the allowlist is the primary gate,
    the regex is a secondary sanity check. Raises ValueError if either fails.
    Returns the value unchanged if both checks pass.
    """
    if value not in allowlist:
        raise ValueError(
            f"SQL identifier {value!r} is not in the allowlist {allowlist!r}"
        )
    if not SAFE_SQL_IDENTIFIER_RE.fullmatch(value):
        raise ValueError(
            f"SQL identifier {value!r} contains unsafe characters"
        )
    return value


# ── Audit Event Types ──
# Canonical set of all event_type values written by log_audit() across
# the agent, sandbox, and dashboard containers.  Both the Python backend
# and the TypeScript frontend must stay in sync with this set — there are
# cross-language tests that verify it.
AUDIT_EVENT_TYPES: frozenset[str] = frozenset({
    # Bootstrap progress
    "run_starting",
    "sandbox_created",
    "repo_cloned",
    # Lifecycle
    "run_started",
    "run_ended",
    "killed",
    "fatal_error",
    "sandbox_crash",
    "teardown_failed",
    "agent_restarted",
    # Round management
    "round_ended",
    "session_error",
    "max_rounds_reached",
    # User actions
    "pause_requested",
    "stop_requested",
    "prompt_submitted",
    "prompt_injected",
    # Git / PR
    "push_failed",
    "pr_failed",
    "pr_created",
    "auto_commit",
    "no_changes",
    # Session control
    "end_session_denied",
    "run_unlocked",
    "run_resumed",
    # Permission / security
    "permission_denied",
    # Rate limiting
    "rate_limit",
    # Idle / stuck detection
    "idle_timeout",
    "idle_nudge",
    "tool_timeout",
    "stuck_recovery",
    # Subagent tracking
    "subagent_start",
    "subagent_complete",
    "agent_stop",
    # MCP
    "mcp_warning",
    # Remote sandbox
    "sandbox_queued",
    "sandbox_allocated",
    "startup_log",
    "sandbox_start_failed",
    # LLM output
    "llm_text",
    "llm_thinking",
    "usage",
})
