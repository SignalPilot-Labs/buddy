"""All magic values for the agent package."""

import logging
from pathlib import Path


# ── Logging ──
class AccessNoiseFilter(logging.Filter):
    """Drop health checks and high-frequency polling from access logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return "GET /health" not in msg and "GET /logs" not in msg

# ── Timeouts ──
TOOL_CALL_TIMEOUT_SEC = 60 * 60  # 1 hour — max duration for any single tool call
SUBAGENT_IDLE_KILL_SEC = 10 * 60  # 10 min idle — trigger interrupt+recovery
PULSE_CHECK_INTERVAL_SEC = 30

# ── Run Limits ──
SESSION_IDLE_TIMEOUT_SEC = 120  # 2 min — nudge orchestrator if no SSE events
IDLE_NUDGE_MAX_ATTEMPTS = 3  # Nudge 3 times with exponential backoff, then kill
# Backstop for runs without a time lock. 128 rounds is enough for a
# very long autonomous session (~8h at ~4 min/round) while still stopping
# a runaway orchestrator that never judges the task done.
MAX_ROUNDS = 128

# ── Agent Models ──
MODEL_OPUS = "opus"
MODEL_SONNET = "sonnet"
DEFAULT_AGENT_ROLE = "worker"
SESSION_PERMISSION_MODE = "bypassPermissions"

# ── Logging ──
PROMPT_SUMMARY_LIMIT = 200  # Custom prompt preview in API responses and audit
RUN_STATE_BASE = "/home/agentuser/.claude/run-state"
ROUND_DIR_PREFIX = "/tmp/round-"
ORCHESTRATOR_REPORT_NAME = "orchestrator.md"
METADATA_PATH = "/tmp/rounds.json"
# Persistent round archive on the agent container's `autofyn-rounds`
# volume. Sandboxes never mount this — the agent pulls/pushes reports
# via file_system HTTP on round boundaries, keeping per-run isolation.
# Lives under agentuser's home so no runtime root is needed — the
# Dockerfile creates + chowns the dir at build time and Docker's named
# volume first-mount copies that ownership into the volume.
ROUND_ARCHIVE_AGENT_DIR = "/home/agentuser/.autofyn/rounds"
LOG_PREVIEW_LIMIT = 200  # One-line log preview of assistant messages

# ── Paths ──
WORK_DIR = "/home/agentuser/repo"
PROMPTS_DIR = Path("/workspace/autofyn/prompts")
PROMPTS_FALLBACK_DIR = Path(__file__).parent.parent / "prompts"

# ── Git ──
BRANCH_NAME_PATTERN = r"^[a-zA-Z0-9][a-zA-Z0-9\-_./]*$"
BRANCH_NAME_MAX_LEN = 256
BRANCH_SLUG_MAX_LEN = 16
GIT_RETRY_ATTEMPTS = 3
GIT_RETRY_DELAY_SEC = 2.0

# ── Session Error Retry ──
SESSION_ERROR_MAX_RETRIES = 3
SESSION_ERROR_BASE_BACKOFF_SEC = 2  # Exponential: 2, 4, 8

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
ACTIVE_RUN_STATUSES = ("starting", "running", "paused")

# ── Sandbox ──
# Defaults — overridden by config.yml sandbox section at runtime.
AGENT_CONTAINER_NAME = "autofyn-agent"
SANDBOX_URL_DEFAULT = "http://sandbox:8080"
SANDBOX_EXEC_TIMEOUT_DEFAULT = 120
SANDBOX_CLONE_TIMEOUT_DEFAULT = 300
SANDBOX_HEALTH_TIMEOUT_DEFAULT = 5
SANDBOX_CLIENT_DEFAULT_TIMEOUT = 300

# ── Token env keys — passed per-run via extra_env, not os.environ ──
ENV_KEY_CLAUDE_TOKEN = "CLAUDE_CODE_OAUTH_TOKEN"
ENV_KEY_GIT_TOKEN = "GIT_TOKEN"
ENV_KEY_INTERNAL_SECRET = "AGENT_INTERNAL_SECRET"

# ── Docker Access ──
DOCKER_SOCKET_PATH = "/var/run/docker.sock"
ENV_KEY_ALLOW_DOCKER = "AF_ALLOW_DOCKER"

# ── Sandbox Pool (per-run containers) ──
SANDBOX_POOL_IMAGE = "autofyn-sandbox"  # built by docker compose
SANDBOX_POOL_NETWORK = "autofyn_default"  # compose default network
SANDBOX_POOL_PORT = 8080
SANDBOX_POOL_HEALTH_POLL_SEC = 2
SANDBOX_POOL_ENV_PASSTHROUGH = [
    "AGENT_INTERNAL_SECRET",
]
