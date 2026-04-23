"""Shared constants importable from both the agent and dashboard containers.

The `db` package is the only Python package imported by both `autofyn/` and
`dashboard/backend/`, so cross-container constants that must not drift live here.
"""

import posixpath

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
    "/home/agentuser/repo",
})
MAX_HOST_MOUNTS: int = 10


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


# ── Audit Event Types ──
# Canonical set of all event_type values written by log_audit() across
# the agent, sandbox, and dashboard containers.  Both the Python backend
# and the TypeScript frontend must stay in sync with this set — there are
# cross-language tests that verify it.
AUDIT_EVENT_TYPES: frozenset[str] = frozenset({
    # Bootstrap progress
    "run_starting",
    "sandbox_ready",
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
    # LLM output
    "llm_text",
    "llm_thinking",
    "usage",
})
