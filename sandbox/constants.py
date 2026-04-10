"""Sandbox constants loaded from config.yml."""

from config.loader import sandbox_config, security_config

_cfg = sandbox_config()
_security_cfg = security_config()

# ── Execution ──
CMD_TIMEOUT: int = _cfg.get("exec_timeout_sec", 120)
SANDBOX_PORT: int = 8080
SANDBOX_HOST: str = "0.0.0.0"

# ── Security ──
INTERNAL_SECRET_HEADER: str = "X-Internal-Secret"
INTERNAL_SECRET_ENV_VAR: str = "AGENT_INTERNAL_SECRET"

CREDENTIAL_PATTERNS: list[str] = _security_cfg.get("credential_patterns", [])
SECRET_ENV_VARS: str = _security_cfg.get("secret_env_vars", "")

# ── Session ──
MAX_CONCURRENT_SESSIONS: int = _cfg.get("max_concurrent_sessions", 5)
SESSION_EVENT_QUEUE_SIZE: int = _cfg.get("session_event_queue_size", 1000)

# ── Time Lock ──
EARLY_EXIT_THRESHOLD_MIN: float = 5.0  # Allow end_session when < 5 min remain

# ── Subagent Limits ──
SUBAGENT_TIMEOUT_SEC: int = 45 * 60
INPUT_SUMMARY_MAX_LEN: int = 1000

# ── Subagent Attribution ──
# Tool name the SDK reports for Task subagent invocations. The hook's
# PreToolUse fires with this name immediately before SubagentStart, and
# its tool_use_id is the parent link the SubagentStart payload lacks.
TASK_TOOL_NAME: str = "Agent"
