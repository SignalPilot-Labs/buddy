"""Sandbox constants loaded from config.yml."""

import logging
import os
import re

from config.loader import sandbox_config, security_config


# ── Logging ──
class AccessNoiseFilter(logging.Filter):
    """Drop health checks and high-frequency polling from access logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return "GET /health" not in msg and "/diff" not in msg


_cfg = sandbox_config()
_security_cfg = security_config()

# ── Execution ──
CMD_TIMEOUT: int = _cfg["exec_timeout_sec"]
SANDBOX_PORT: int = int(os.environ.get("AF_SANDBOX_PORT", "8080"))
SANDBOX_HOST: str = "0.0.0.0"

# ── Security ──
INTERNAL_SECRET_HEADER: str = "X-Internal-Secret"
INTERNAL_SECRET_ENV_VAR: str = "SANDBOX_INTERNAL_SECRET"

# ── Remote Sandbox ──
SANDBOX_SECRET_FILE_ENV_VAR: str = "AF_SANDBOX_SECRET_FILE"
SANDBOX_HEARTBEAT_TIMEOUT_ENV_VAR: str = "AF_HEARTBEAT_TIMEOUT"
SANDBOX_HEARTBEAT_CHECK_INTERVAL_SEC: int = 10
SANDBOX_PROTOCOL_VERSION: int = 1
SANDBOX_IMAGE_TAG: str = os.environ.get("AF_IMAGE_TAG", "unknown")

CREDENTIAL_PATTERNS: list[str] = _security_cfg["credential_patterns"]
SECRET_ENV_VARS: str = _security_cfg["secret_env_vars"]

# ── Session ──
MAX_CONCURRENT_SESSIONS: int = _cfg["max_concurrent_sessions"]

# ── Time Lock ──
EARLY_EXIT_THRESHOLD_MIN: float = _cfg["early_exit_threshold_min"]
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

# Directories the filesystem API is permitted to access.
FS_ALLOWED_PREFIXES: tuple[str, ...] = (
    "/home/agentuser/repo",
    "/tmp",
    "/home/agentuser/.claude",
    "/opt/autofyn",
)
FS_PATH_DENIED_MSG: str = "Path is outside allowed directories"
FS_PATH_EMPTY_MSG: str = "Path must not be empty"

# ── Retry (transient network errors on git/gh commands) ──
RETRY_MAX_ATTEMPTS: int = _cfg["retry_max_attempts"]
RETRY_BASE_DELAY_SEC: float = _cfg["retry_base_delay_sec"]

RETRY_TRANSIENT_PATTERNS: tuple[str, ...] = (
    "error connecting",
    "connection refused",
    "connection reset",
    "timed out",
    "could not resolve",
)

# ── Secret Redaction ──
SECRET_REDACT_MASK: str = "***REDACTED***"

# ── Repo handlers ──
REPO_WORK_DIR: str = "/home/agentuser/repo"
REPO_BRANCH_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9\-_./]*$")
REPO_BRANCH_NAME_MAX_LEN: int = 256

# Inline shell credential helper: reads $GIT_TOKEN at the moment git
# invokes it. Secret lives in process memory only — never on disk.
GIT_CREDENTIAL_HELPER: str = (
    '!f() { echo "username=x-access-token"; echo "password=${GIT_TOKEN}"; }; f'
)

# ── Repo git clone ──
GIT_CLONE_DEPTH: int = 50
CLONE_TMP_DIR: str = "/tmp/repo-clone"

# ── Stderr truncation limits ──
STDERR_DISPLAY_LIMIT: int = 2000
STDERR_SHORT_LIMIT: int = 500
STDERR_BRIEF_LIMIT: int = 200

# ── Auto-commit message ──
AUTO_COMMIT_MESSAGE: str = "Auto-commit: save uncommitted work at session end"


# ── Security: git remote write subcommands ──
# Matches only remote-mutating subcommands. Read-only commands like
# `git remote -v`, `git remote show`, `git remote get-url` are NOT matched.
GIT_REMOTE_WRITE_RE: re.Pattern[str] = re.compile(
    r"git\s+remote\s+(add|remove|rm|rename|set-url|set-head|set-branches|prune)\b"
)
