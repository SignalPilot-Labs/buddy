"""All magic values for the agent package."""

from pathlib import Path

# ── Subagent Timeouts ──
SUBAGENT_IDLE_KILL_SEC = 10 * 60     # 10 min idle — trigger interrupt+recovery
PULSE_CHECK_INTERVAL_SEC = 30

# ── Run Limits ──
RATE_LIMIT_MAX_WAIT_SEC = 600      # Max seconds to wait for rate limit reset before stopping
SESSION_IDLE_TIMEOUT_SEC = 120     # 2 min — nudge agent if no SSE events

# ── Logging ──
PROMPT_SUMMARY_LIMIT = 200         # Custom prompt preview in API responses and audit
LOG_PREVIEW_LIMIT = 200           # One-line log preview of assistant messages

# ── Paths ──
WORK_DIR = "/home/agentuser/repo"
PROMPTS_DIR = Path("/workspace/autofyn/prompts")
PROMPTS_FALLBACK_DIR = Path(__file__).parent.parent / "prompts"

# ── Git ──
BRANCH_NAME_PATTERN = r'^[a-zA-Z0-9][a-zA-Z0-9\-_./]*$'
BRANCH_NAME_MAX_LEN = 256
BRANCH_SLUG_MAX_LEN = 30
GIT_RETRY_ATTEMPTS = 3
GIT_RETRY_DELAY_SEC = 2.0
RATE_LIMIT_SLEEP_BUFFER_SEC = 5

# ── Input Limits ──
INJECT_PAYLOAD_MAX_LEN = 50000

# ── Usage Tracking ──
USAGE_EMIT_INTERVAL = 10  # Emit usage audit event every N assistant messages

# ── Cost Estimation (per-token, USD · Opus rates as upper bound) ──
COST_PER_INPUT = 15.0 / 1_000_000
COST_PER_OUTPUT = 75.0 / 1_000_000
COST_PER_CACHE_WRITE = 18.75 / 1_000_000
COST_PER_CACHE_READ = 1.50 / 1_000_000

# ── Server ──
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8500
MAX_CONCURRENT_RUNS = 5

# ── Sandbox ──
# Defaults — overridden by config.yml sandbox section at runtime.
SANDBOX_URL_DEFAULT = "http://sandbox:8080"
SANDBOX_EXEC_TIMEOUT_DEFAULT = 120
SANDBOX_CLONE_TIMEOUT_DEFAULT = 300
SANDBOX_HEALTH_TIMEOUT_DEFAULT = 5
SANDBOX_CLIENT_DEFAULT_TIMEOUT = 300

# ── Token env keys — passed per-run via extra_env, not os.environ ──
ENV_KEY_CLAUDE_TOKEN = "CLAUDE_CODE_OAUTH_TOKEN"
ENV_KEY_GIT_TOKEN = "GIT_TOKEN"

# ── Sandbox Pool (per-run containers) ──
SANDBOX_POOL_IMAGE = "autofyn-sandbox"  # built by docker compose
SANDBOX_POOL_NETWORK = "autofyn_default"         # compose default network
SANDBOX_POOL_PORT = 8080
SANDBOX_POOL_HEALTH_POLL_SEC = 2
SANDBOX_POOL_ENV_PASSTHROUGH = [
    "AGENT_INTERNAL_SECRET",
]
