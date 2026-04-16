"""Sandbox constants loaded from config.yml."""

import logging
import re

from config.loader import sandbox_config, security_config


# ── Logging ──
class HealthLogFilter(logging.Filter):
    """Drop access log lines for /health — they flood logs every 10s."""

    def filter(self, record: logging.LogRecord) -> bool:
        return "GET /health" not in record.getMessage()

_cfg = sandbox_config()
_security_cfg = security_config()

# ── Execution ──
CMD_TIMEOUT: int = _cfg.get("exec_timeout_sec", 120)
SANDBOX_PORT: int = 8080
SANDBOX_HOST: str = "0.0.0.0"

# ── Security ──
INTERNAL_SECRET_HEADER: str = "X-Internal-Secret"
# Sandbox-scoped secret. Distinct from AGENT_INTERNAL_SECRET (dashboard↔agent)
# so a compromised sandbox cannot forge calls to the agent's control plane.
INTERNAL_SECRET_ENV_VAR: str = "SANDBOX_INTERNAL_SECRET"
# URL the sandbox uses to POST tool-call / audit events back to the agent.
# Set by the agent when the sandbox container is spawned.
AGENT_CALLBACK_URL_ENV_VAR: str = "AGENT_CALLBACK_URL"

CREDENTIAL_PATTERNS: list[str] = _security_cfg.get("credential_patterns", [])
SECRET_ENV_VARS: str = _security_cfg.get("secret_env_vars", "")
SECRET_ENV_KEYS: frozenset[str] = frozenset(SECRET_ENV_VARS.split("|")) if SECRET_ENV_VARS else frozenset()

# ── Session ──
MAX_CONCURRENT_SESSIONS: int = _cfg.get("max_concurrent_sessions", 5)
SESSION_EVENT_QUEUE_SIZE: int = _cfg.get("session_event_queue_size", 1000)

# ── Time Lock ──
EARLY_EXIT_THRESHOLD_MIN: float = 5.0  # Allow end_session when < 5 min remain
SECONDS_PER_MINUTE: int = 60

INPUT_SUMMARY_MAX_LEN: int = 1000
INPUT_CONTENT_MAX_LEN: int = 3000

# ── Subagent Attribution ──
# Tool name the SDK reports for Task subagent invocations. The hook's
# PreToolUse fires with this name immediately before SubagentStart, and
# its tool_use_id is the parent link the SubagentStart payload lacks.
TASK_TOOL_NAME: str = "Agent"

# ── Filesystem API ──
# Max file size the /file_system/read endpoint will return. Larger files
# must be streamed via /exec + tail/head or split before reading.
FS_READ_MAX_BYTES: int = 2 * 1024 * 1024

# ── Retry (transient network errors on git/gh commands) ──
RETRY_MAX_ATTEMPTS: int = 3
RETRY_BASE_DELAY_SEC: float = 2.0
RETRY_TRANSIENT_PATTERNS: tuple[str, ...] = (
    "error connecting",
    "connection refused",
    "connection reset",
    "timed out",
    "could not resolve",
)

# ── Repo handlers ──
REPO_WORK_DIR: str = "/home/agentuser/repo"
REPO_BRANCH_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9\-_./]*$")
REPO_BRANCH_NAME_MAX_LEN: int = 256

# Inline shell credential helper: reads $GIT_TOKEN at the moment git
# invokes it. Secret lives in process memory only — never on disk.
GIT_CREDENTIAL_HELPER: str = (
    '!f() { echo "username=x-access-token"; echo "password=${GIT_TOKEN}"; }; f'
)

# ── /proc leak path filter ──
# Matches sensitive /proc paths that expose process memory and environment.
# Load-bearing gate: /proc/1/environ still contains the execve() snapshot
# of ANTHROPIC_API_KEY / CLAUDE_CODE_OAUTH_TOKEN until a re-exec is shipped
# (deferred to round 4). This filter is the primary closure for F1.
#
# The pattern is NOT anchored so that it matches /proc/ appearing anywhere
# in a Bash token (e.g. "if=/proc/kcore", "< /proc/1/environ").
# This matches the original security.py behavior for Bash-only checking.
PROC_LEAK_PATH_RE: re.Pattern[str] = re.compile(
    r"/proc/(?:[^/\s]+/(?:environ|cmdline|mem|maps)|kcore)\b"
)

# ── Git environment isolation ──
# Env-var key names (as string constants — used in build_git_env).
GIT_CONFIG_NOSYSTEM_KEY: str = "GIT_CONFIG_NOSYSTEM"
GIT_CONFIG_GLOBAL_KEY: str = "GIT_CONFIG_GLOBAL"
GIT_CONFIG_COUNT_KEY: str = "GIT_CONFIG_COUNT"
XDG_CONFIG_HOME_KEY: str = "XDG_CONFIG_HOME"
HOME_ENV_KEY: str = "HOME"

# Values for the git-isolation environment variables.
GIT_CONFIG_NOSYSTEM_VALUE: str = "1"
GIT_CONFIG_GLOBAL_VALUE: str = "/dev/null"
GIT_CONFIG_COUNT_VALUE: str = "0"
XDG_CONFIG_HOME_VALUE: str = "/nonexistent"
GIT_ISOLATED_HOME: str = "/tmp/git-isolated"

# Keys to strip from the inherited env — GIT_CONFIG_* prefix families.
GIT_CONFIG_ENV_PREFIXES: tuple[str, ...] = ("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")

# Exact keys to strip from the inherited env.
GIT_CONFIG_EXACT_ENV_KEYS: frozenset[str] = frozenset({
    "GIT_CONFIG",
    "GIT_SSH_COMMAND",
    "GIT_EXEC_PATH",
    "GIT_TEMPLATE_DIR",
    "GIT_CONFIG_COUNT",
})

# Per-invocation git -c flags injected between `git` and the subcommand.
# These override any config that may be present in the env-isolated home.
PER_CALL_GIT_CONFIG_FLAGS: tuple[str, ...] = (
    "-c", f"credential.helper={GIT_CREDENTIAL_HELPER}",
    "-c", "include.path=/dev/null",
    "-c", "core.sshCommand=/bin/false",
    "-c", "protocol.ext.allow=never",
)

# ── Config write patterns (loaded from config.yml) ──
CONFIG_WRITE_PATTERNS: list[str] = _security_cfg.get("config_write_patterns", [])
