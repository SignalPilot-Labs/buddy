"""Dashboard backend constants."""

from config.loader import load as _load_config

APP_TITLE = "AutoFyn Dashboard API"

# Secret files (inside Docker volume — autofyn-keys:/data)
MASTER_KEY_PATH = "/data/master.key"
API_KEY_PATH = "/data/api.key"

# Agent service URL (Docker network) — port from config/config.yml
AGENT_API_URL = f"http://agent:{_load_config().get('agent', {}).get('port', 8500)}"

# Pagination
RUNS_PAGE_SIZE = 15
QUERY_MAX_LIMIT = 5001

# SSE
SSE_POLL_INTERVAL_SEC = 0.5

# HTTP client timeouts (seconds)
AGENT_TIMEOUT_SHORT = 5
AGENT_TIMEOUT_LONG = 10

# Credential masking
MASK_PREFIX_CLAUDE_TOKEN = 8
MASK_PREFIX_DEFAULT = 6

# Settings keys that must be encrypted at rest
SECRET_KEYS = frozenset({"git_token"})

# Mask value used in GET /settings for encrypted env var values
ENV_VARS_MASK_CHAR = "****"

# Default values
DEFAULT_BASE_BRANCH = "main"
DEFAULT_STOP_REASON = "User requested stop"


# Network / ports
UI_PORT = 3400
HOST_IP_ENV = "HOST_IP"

# Polling (incremental — frontend HISTORY_FETCH_LIMIT=500 is for initial load)
POLL_LIMIT_DEFAULT = 100

# Event type priority for interleaved sort: audits sort before tools at same timestamp
TYPE_PRIORITY_AUDIT = 0
TYPE_PRIORITY_TOOL = 1

# Query defaults
QUERY_DEFAULT_LIMIT: int = 200
LOG_TAIL_DEFAULT: int = 500
LOG_TAIL_MAX: int = 5000

# Signal → agent endpoint path mapping (used by send_control_signal)
SIGNAL_AGENT_PATHS: dict[str, str] = {
    "pause": "/pause",
    "resume": "/resume",
    "stop": "/stop",
    "unlock": "/unlock",
    "inject": "/inject",
}

# Run status sets — single source of truth for the runs endpoints. Add a new
# status here, not inline in runs.py.
RESTARTABLE_STATUSES: frozenset[str] = frozenset(
    {
        "completed",
        "completed_no_changes",
        "stopped",
        "error",
        "crashed",
        "killed",
    }
)

ACTIVE_STATUSES: frozenset[str] = frozenset({"running", "paused", "rate_limited"})

# Statuses that allow injecting into a stopped run by spawning a fresh resume.
INJECTABLE_TERMINAL_STATUSES: frozenset[str] = frozenset(
    {"completed", "stopped", "error"}
)

# ── HTTP headers ──
# Sync: autofyn/utils/constants.py must define the same constant.
HEADER_GITHUB_TOKEN = "X-GitHub-Token"

# ── Host-header allowlist for DNS-rebinding protection ──────────────────────
# Do NOT add "dashboard" or "dashboard:3401" — Next.js calls FastAPI via
# http://localhost:${API_PORT}, so the Host header is always localhost:3401.
# Adding the Docker service name would expand attack surface for zero benefit.
ALLOWED_HOSTS: frozenset[str] = frozenset(
    {"localhost", "localhost:3401", "127.0.0.1", "127.0.0.1:3401"}
)
