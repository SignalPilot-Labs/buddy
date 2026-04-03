"""Dashboard backend constants."""

from config.loader import load as _load_config

APP_TITLE = "Buddy Dashboard API"

# Encryption key file path (inside Docker volume)
MASTER_KEY_PATH = "/data/master.key"

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
SECRET_KEYS = frozenset({"claude_token", "git_token", "dashboard_api_key"})

# Default values
DEFAULT_BASE_BRANCH = "main"
DEFAULT_STOP_REASON = "Operator requested stop"

# Tunnel (Cloudflare)
TUNNEL_CONTAINER = "buddy-tunnel"
TUNNEL_IMAGE = "cloudflare/cloudflared:latest"
TUNNEL_COMMAND = "tunnel --no-autoupdate --url http://localhost:3400"
TUNNEL_URL_PATTERN = r"https://[a-zA-Z0-9-]+\.trycloudflare\.com"
TUNNEL_NETWORK_TARGET = "buddy-dashboard"
TUNNEL_LOG_TAIL_LINES = 50
TUNNEL_STOP_TIMEOUT = 5
POLL_LIMIT_DEFAULT = 100
