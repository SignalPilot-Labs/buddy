"""All magic values for the agent package."""

from pathlib import Path

# ── Subagent Timeouts ──
SUBAGENT_IDLE_KILL_SEC = 10 * 60     # 10 min idle — trigger interrupt+recovery
PULSE_CHECK_INTERVAL_SEC = 30

# ── Run Limits ──
MAX_ROUNDS = 500
RATE_LIMIT_MAX_WAIT_SEC = 600      # Max seconds to wait for rate limit reset before stopping

# ── Truncation Limits (audit/logging) ──
PROMPT_SUMMARY_LIMIT = 200         # Custom prompt preview in API responses and audit
TEXT_CHUNK_LIMIT = 500             # Per-round text chunks collected for planner context
ROUND_SUMMARY_LIMIT = 1500        # Combined round text sent to planner prompt
LOG_PREVIEW_LIMIT = 200           # One-line log preview of assistant messages
FILES_CHANGED_LIMIT = 500         # Git files-changed list in planner audit meta
ROUND_SUMMARY_AUDIT_LIMIT = 500   # Round summary stored in planner audit meta

# ── Paths ──
WORK_DIR = "/home/agentuser/repo"
PROMPTS_DIR = Path("/workspace/autofyn/prompts")
PROMPTS_FALLBACK_DIR = Path(__file__).parent.parent / "prompts"

# ── Git ──
BRANCH_NAME_PATTERN = r'^[a-zA-Z0-9][a-zA-Z0-9\-_./]*$'
BRANCH_NAME_MAX_LEN = 256
GIT_RETRY_ATTEMPTS = 3
GIT_RETRY_DELAY_SEC = 2.0
RATE_LIMIT_SLEEP_BUFFER_SEC = 5

# ── Input Limits ──
INJECT_PAYLOAD_MAX_LEN = 50000
MAX_OPERATOR_MESSAGES = 25

# ── Server ──
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8500
MAX_CONCURRENT_RUNS = 10
START_RATE_LIMIT_MAX = 5
START_RATE_LIMIT_WINDOW_SEC = 60.0

# ── Sandbox ──
# Defaults — overridden by config.yml sandbox section at runtime.
SANDBOX_URL_DEFAULT = "http://sandbox:8080"
SANDBOX_EXEC_TIMEOUT_DEFAULT = 120
SANDBOX_CLONE_TIMEOUT_DEFAULT = 300
SANDBOX_HEALTH_TIMEOUT_DEFAULT = 5
SANDBOX_CLIENT_DEFAULT_TIMEOUT = 300

# ── Sandbox Pool (per-run containers) ──
SANDBOX_POOL_IMAGE = "autofyn-autofyn-sandbox"  # built by docker compose
SANDBOX_POOL_NETWORK = "autofyn_default"         # compose default network
SANDBOX_POOL_PORT = 8080
SANDBOX_POOL_HEALTH_POLL_SEC = 2
