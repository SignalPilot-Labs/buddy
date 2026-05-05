"""All magic values for the agent package.

Server-level constants are loaded lazily from config on first access
via _agent_cfg(). The config is cached in config.loader after the first
load() call, so repeated access is a dict lookup — not YAML I/O.
"""

import logging
from pathlib import Path

from config.loader import agent_config

_cached_agent_cfg: dict | None = None


def _agent_cfg() -> dict:
    """Lazy accessor for the agent config section. Cached after first call."""
    global _cached_agent_cfg
    if _cached_agent_cfg is None:
        _cached_agent_cfg = agent_config()
    return _cached_agent_cfg


# ── Logging ──
_NOISY_PATHS: tuple[str, ...] = (
    "GET /health",
    "GET /logs",
    "/diff",
    "/file_system/ls",
    "/file_system/read_dir",
)


class AccessNoiseFilter(logging.Filter):
    """Drop health checks and high-frequency polling from access and httpx logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return all(path not in msg for path in _NOISY_PATHS)


# ── Timeouts ──
# Accessed via function to avoid import-time YAML I/O.
def pulse_check_interval_sec() -> int:
    """Pulse watchdog check interval in seconds."""
    return _agent_cfg()["pulse_check_interval_sec"]



# ── Run Limits ──
def idle_nudge_max_attempts() -> int:
    """Max idle nudges before killing the session."""
    return _agent_cfg()["idle_nudge_max_attempts"]


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
RUN_STATE_PATH = "/tmp/run_state.md"
RUN_STATE_REL_PATH = "tmp/run_state.md"
ROUNDS_JSON_REL_PATH = "tmp/rounds.json"

# Single source of truth: root-level /tmp files to include in diffs.
# (rel_path for diff output, abs_path for sandbox reads, filename for archive reads)
TMP_ROOT_FILES: tuple[tuple[str, str, str], ...] = (
    (RUN_STATE_REL_PATH, RUN_STATE_PATH, "run_state.md"),
    (ROUNDS_JSON_REL_PATH, METADATA_PATH, "rounds.json"),
)
RUN_STATE_TEMPLATE = """\
## Goal

## Goal Updates

## Eval History

## Rules

## State
"""
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
def session_error_max_retries() -> int:
    """Max retries for session errors."""
    return _agent_cfg()["session_error_max_retries"]


def session_error_base_backoff_sec() -> int:
    """Base backoff seconds for session error retry (exponential)."""
    return _agent_cfg()["session_error_base_backoff_sec"]


# ── Input Limits ──
INJECT_PAYLOAD_MAX_LEN = 50000

# ── Usage Tracking ──
USAGE_EMIT_INTERVAL = 10  # Emit usage audit event every N assistant messages

# ── SSE Event Processing ──
SSE_TRIM_INTERVAL = 100  # Trim processed events from sandbox memory every N events


# ── Cost Estimation (per-token, USD · Opus rates as upper bound) ──
def cost_per_input() -> float:
    """Cost per input token in USD."""
    return _agent_cfg()["cost_per_input_token"]


def cost_per_output() -> float:
    """Cost per output token in USD."""
    return _agent_cfg()["cost_per_output_token"]


def cost_per_cache_write() -> float:
    """Cost per cache write token in USD."""
    return _agent_cfg()["cost_per_cache_write_token"]


def cost_per_cache_read() -> float:
    """Cost per cache read token in USD."""
    return _agent_cfg()["cost_per_cache_read_token"]


# ── Server ──
SERVER_HOST = "0.0.0.0"


def server_port() -> int:
    """Agent HTTP server port."""
    return _agent_cfg()["port"]


def max_concurrent_runs() -> int:
    """Max simultaneous agent runs."""
    return _agent_cfg()["max_concurrent_runs"]


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

# ── GitHub API ──
GITHUB_API_BASE_URL = "https://api.github.com"
GITHUB_API_TIMEOUT_SEC = 10
GITHUB_BRANCHES_PER_PAGE = 100
GITHUB_ERROR_PREVIEW_LEN = 200

# ── Docker Access ──
DOCKER_SOCKET_PATH = "/var/run/docker.sock"
ENV_KEY_ALLOW_DOCKER = "AF_ALLOW_DOCKER"

# ── Agent Tool Names ──
AGENT_TOOL_NAME = "Agent"

# ── Sandbox ──
SANDBOX_LOG_TAIL_LINES = 200
ENV_KEY_MAX_BUDGET_USD = "MAX_BUDGET_USD"
DEFAULT_BUDGET_USD: str = "0"

# ── Sandbox Pool (per-run containers) ──
SANDBOX_POOL_IMAGE_BASE: str = "ghcr.io/signalpilot-labs/autofyn-sandbox"
ENV_KEY_IMAGE_TAG: str = "AF_IMAGE_TAG"
SANDBOX_POOL_NETWORK = "autofyn_default"  # compose default network
SANDBOX_POOL_PORT = 8080
SANDBOX_POOL_HEALTH_POLL_SEC = 2
SANDBOX_POOL_BIND_HOST: str = "0.0.0.0"
SANDBOX_POOL_ENV_PASSTHROUGH = [
    "SANDBOX_INTERNAL_SECRET",
]

# ── Connector (remote sandbox) ──
ENV_KEY_CONNECTOR_URL: str = "CONNECTOR_URL"
ENV_KEY_CONNECTOR_SECRET: str = "CONNECTOR_SECRET"

