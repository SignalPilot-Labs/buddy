"""Dashboard backend constants."""

APP_TITLE = "Buddy Dashboard API"

# Encryption key file path (inside Docker volume)
MASTER_KEY_PATH = "/data/master.key"

# Agent service URL (Docker network)
AGENT_API_URL = "http://agent:8500"

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
