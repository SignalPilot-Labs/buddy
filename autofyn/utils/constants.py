"""All magic values for the agent package."""

import logging
from pathlib import Path

from config.loader import agent_config

_agent_cfg = agent_config(None)


# ── Logging ──
class AccessNoiseFilter(logging.Filter):
    """Drop health checks and high-frequency polling from access logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return "GET /health" not in msg and "GET /logs" not in msg and "/diff" not in msg

# ── Timeouts ──
PULSE_CHECK_INTERVAL_SEC = 30

# ── Run Limits ──
IDLE_NUDGE_MAX_ATTEMPTS = 3  # Nudge 3 times with exponential backoff, then kill

# ── Subagent Model Tiers ──
# Each subagent declares a tier ("opus" or "sonnet"). At runtime,
# build_agent_defs resolves the tier to the actual model based on the
# user's selection. See resolve_subagent_model() in prompts/subagent.py.
TIER_OPUS: str = "opus"
TIER_SONNET: str = "sonnet"
DEFAULT_AGENT_ROLE = "worker"
SESSION_PERMISSION_MODE = "bypassPermissions"

# ── Logging ──
PROMPT_SUMMARY_LIMIT = 200  # Custom prompt preview in API responses and audit
RUN_STATE_BASE = "/home/agentuser/.claude/run-state"
ROUND_DIR_PREFIX = "/tmp/round-"
# Strict pattern for round dir names: "round-" followed by one or more digits.
# Used to reject anything that merely starts with "round-" (e.g. "round-..").
ROUND_DIR_NAME_RE = r"^round-\d+$"
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
SERVER_PORT: int = _agent_cfg["port"]
MAX_CONCURRENT_RUNS: int = _agent_cfg["max_concurrent_runs"]
ACTIVE_RUN_STATUSES = ("starting", "running", "paused")
# Bound on the completed-run GitHub-diff LRU. Each entry holds a full
# unified diff blob; capping prevents unbounded growth over the agent's
# lifetime (many completed runs viewed in dashboard).
GITHUB_DIFF_CACHE_MAX = 32

# ── Sandbox ──
AGENT_CONTAINER_NAME = "autofyn-agent"
RUN_ID_LOG_PREFIX_LEN = 8

# ── Token env keys — passed per-run via extra_env, not os.environ ──
ENV_KEY_CLAUDE_TOKEN = "CLAUDE_CODE_OAUTH_TOKEN"
ENV_KEY_GIT_TOKEN = "GIT_TOKEN"
ENV_KEY_INTERNAL_SECRET = "AGENT_INTERNAL_SECRET"
ENV_KEY_SANDBOX_SECRET = "SANDBOX_INTERNAL_SECRET"
ENV_KEY_ANTHROPIC_API = "ANTHROPIC_API_KEY"

# ── HTTP headers ──
# Sync: dashboard/backend/constants.py must define the same constant.
HEADER_GITHUB_TOKEN = "X-GitHub-Token"
INTERNAL_SECRET_HEADER = "X-Internal-Secret"

# ── Docker Access ──
DOCKER_SOCKET_PATH = "/var/run/docker.sock"
ENV_KEY_ALLOW_DOCKER = "AF_ALLOW_DOCKER"

# ── Sandbox Pool (per-run containers) ──
SANDBOX_POOL_IMAGE = "autofyn-sandbox"  # built by docker compose
SANDBOX_POOL_NETWORK = "autofyn_default"  # compose default network
SANDBOX_POOL_PORT = 8080
SANDBOX_POOL_HEALTH_POLL_SEC = 2
SANDBOX_POOL_ENV_PASSTHROUGH = [
    "SANDBOX_INTERNAL_SECRET",
]

# URL pool sandboxes use to reach the agent container on the compose network.
# Static sandbox gets its URL from docker-compose.yml AF_AGENT_URL env var.
SANDBOX_POOL_AGENT_URL = "http://autofyn-agent:8500"

# Env var name for the agent URL passed into sandbox containers.
ENV_KEY_AGENT_URL = "AF_AGENT_URL"
