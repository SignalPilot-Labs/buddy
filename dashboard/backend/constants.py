"""Dashboard backend constants."""

from config.loader import load as _load_config

APP_TITLE = "AutoFyn Dashboard API"

# Secret files (inside Docker volume — autofyn-keys:/data)
MASTER_KEY_PATH = "/data/master.key"
API_KEY_PATH = "/data/api.key"

# Agent service URL (Docker network) — port from config/config.yml
AGENT_API_URL = f"http://agent:{_load_config().get('agent', {}).get('port', 8500)}"

# Pagination
RUNS_PAGE_SIZE = 50
QUERY_MAX_LIMIT = 1000

# SSE
SSE_POLL_INTERVAL_SEC = 0.5

# HTTP client timeouts (seconds)
AGENT_TIMEOUT_SHORT = 5
AGENT_TIMEOUT_LONG = 10

# Credential masking
MASK_PREFIX_CLAUDE_TOKEN = 8
MASK_PREFIX_DEFAULT = 6

# Settings keys that must be encrypted at rest
SECRET_KEYS = frozenset({"claude_token", "git_token"})

# Default values
DEFAULT_BASE_BRANCH = "main"
DEFAULT_STOP_REASON = "Operator requested stop"


# Network / ports
UI_PORT = 3400
HOST_IP_ENV = "HOST_IP"

# Polling (incremental — frontend HISTORY_FETCH_LIMIT=500 is for initial load)
POLL_LIMIT_DEFAULT = 100
