"""Sandbox constants loaded from config.yml."""

import logging
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
SANDBOX_PORT: int = 8080
SANDBOX_HOST: str = "0.0.0.0"

# ── Security ──
INTERNAL_SECRET_HEADER: str = "X-Internal-Secret"
INTERNAL_SECRET_ENV_VAR: str = "SANDBOX_INTERNAL_SECRET"

# ── Agent HTTP client ──
# Env var name for the agent URL. Set by docker-compose.yml for the static
# sandbox; injected directly by pool.py for pool-created sandboxes.
AGENT_URL_ENV_VAR: str = "AF_AGENT_URL"


CREDENTIAL_PATTERNS: list[str] = _security_cfg["credential_patterns"]
SECRET_ENV_VARS: str = _security_cfg["secret_env_vars"]

# ── Session ──
MAX_CONCURRENT_SESSIONS: int = _cfg["max_concurrent_sessions"]
SESSION_EVENT_QUEUE_SIZE: int = _cfg["session_event_queue_size"]

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

# ── Retry (transient network errors on git/gh commands) ──
RETRY_MAX_ATTEMPTS: int = _cfg["retry_max_attempts"]
RETRY_BASE_DELAY_SEC: float = _cfg["retry_base_delay_sec"]

# ── Agent HTTP client (event logging POSTs to agent container) ──
AGENT_HTTP_TIMEOUT_SEC: int = 10
AGENT_LOG_RETRY_ATTEMPTS: int = 3
AGENT_LOG_RETRY_BASE_SEC: float = 0.5
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
