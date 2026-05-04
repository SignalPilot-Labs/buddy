"""Connector constants — all magic values for the connector package."""

import re

CONNECTOR_DEFAULT_PORT: int = 9400
CONNECTOR_BIND_HOST: str = "127.0.0.1"

CONNECTOR_SECRET_HEADER: str = "X-Connector-Secret"
CONNECTOR_SECRET_ENV: str = "CONNECTOR_SECRET"
SANDBOX_SECRET_HEADER: str = "X-Internal-Secret"

TUNNEL_HEALTH_PROBE_INTERVAL_SEC: int = 30
HEARTBEAT_INTERVAL_SEC: int = 60
HEARTBEAT_CLIENT_TIMEOUT_SEC: int = 10
HEARTBEAT_MAX_FAILURES: int = 5

SHUTDOWN_TIMEOUT_SEC: int = 60

SSH_CONNECT_TIMEOUT_SEC: int = 30
SSH_KEEPALIVE_INTERVAL_SEC: int = 15
SSH_KEEPALIVE_COUNT_MAX: int = 3
KILL_WAIT_TIMEOUT_SEC: int = 5

RING_BUFFER_MAX_LINES: int = 100
DEFAULT_LOG_TAIL: int = 100

AF_QUEUED_MARKER: str = "AF_QUEUED"
AF_READY_MARKER: str = "AF_READY"

DEFAULT_SECRET_DIR: str = "~/.autofyn/secrets"

PROXY_TIMEOUT_SEC: int = 300
PROXY_KEEPALIVE_TIMEOUT_SEC: int = 10

SSH_TUNNEL_READY_TIMEOUT_SEC: int = 5

# Allowlist regex for paths passed to SSH commands (secret_dir, run_key, etc.)
SAFE_PATH_RE: re.Pattern[str] = re.compile(r"^[a-zA-Z0-9._/~\-]+$")
