"""Shared constants importable from both the agent and dashboard containers.

The `db` package is the only Python package imported by both `autofyn/` and
`dashboard/backend/`, so cross-container constants that must not drift live here.
"""

import posixpath

# Placeholder branch name for runs that haven't been bootstrapped yet.
# The DB column is non-nullable, so we use this sentinel instead of NULL.
# Bootstrap must treat this as "no branch" and generate a real name.
BRANCH_PENDING_PLACEHOLDER: str = "pending"

# Valid Claude model identifiers accepted at the run-start boundary.
# Source of truth for: agent validation, dashboard Pydantic regex, fallback map.
# "opus" and "sonnet" are Claude Code aliases resolved by the CLI to the latest
# snapshot. "opus-4-5" is our own key for the previous Opus generation and is
# translated to the full model ID "claude-opus-4-5" at the SDK boundary.
VALID_MODELS: tuple[str, ...] = ("opus", "sonnet", "opus-4-5")

# Default model used when the caller does not specify one.
DEFAULT_MODEL: str = "opus"

# Pydantic/regex-friendly alternation pattern built from VALID_MODELS.
VALID_MODELS_PATTERN: str = f"^({'|'.join(VALID_MODELS)})$"

# Translation from our internal model keys to the exact model IDs the Claude
# Agent SDK forwards to the Anthropic API. Keys not present here are passed
# through unchanged (the CLI resolves "opus"/"sonnet" aliases itself).
MODEL_ID_TRANSLATION: dict[str, str] = {
    "opus-4-5": "claude-opus-4-5",
}

# ── Effort ──
# Valid effort levels for the Claude Agent SDK.
# "max" is only supported on 4.6 models (opus, sonnet); for older models
# it is silently downgraded to "high" at the bootstrap boundary.
VALID_EFFORTS: tuple[str, ...] = ("low", "medium", "high", "max")
DEFAULT_EFFORT: str = "medium"
VALID_EFFORTS_PATTERN: str = f"^({'|'.join(VALID_EFFORTS)})$"

# Models that support effort="max". Others get downgraded to "high".
MODELS_SUPPORTING_MAX_EFFORT: frozenset[str] = frozenset({"opus", "sonnet"})


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
    # Lifecycle
    "run_started",
    "run_ended",
    "killed",
    "fatal_error",
    "sandbox_crash",
    "teardown_failed",
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


def resolve_sdk_model(model: str) -> str:
    """Translate an internal model key to the SDK model ID, or pass through."""
    return MODEL_ID_TRANSLATION.get(model, model)
