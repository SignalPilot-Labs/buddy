"""Shared constants for the Buddy CLI."""

from __future__ import annotations

from pathlib import Path

# Buddy home — everything lives here after install
BUDDY_HOME: str = str(Path.home() / ".buddy")
BUDDY_VENV_PIP: str = str(Path(BUDDY_HOME) / ".venv" / "bin" / "pip")

# HTTP client
HTTP_TIMEOUT_SECONDS: int = 15

# Display truncation lengths
PROMPT_SELECTOR_TRUNCATION: int = 50
PROMPT_LIST_TRUNCATION: int = 40
STREAM_SNIPPET_LENGTH: int = 80
STREAM_DATA_TRUNCATION: int = 100
AUDIT_SNIPPET_LENGTH: int = 60
SHORT_ID_LENGTH: int = 8

# Run label format widths
RUN_LABEL_STATUS_WIDTH: int = 13
RUN_LABEL_PROMPT_WIDTH: int = 52

# Query defaults
DEFAULT_QUERY_LIMIT: int = 50
DEFAULT_QUERY_OFFSET: int = 0

# Fuzzy selector
FUZZY_MAX_HEIGHT: str = "70%"

# API
DEFAULT_API_URL: str = "http://localhost:3401"
DASHBOARD_URL: str = "http://localhost:3400"
DASHBOARD_HEALTH_URL: str = "http://localhost:3401/api/health"
DASHBOARD_HEALTH_TIMEOUT_SECONDS: int = 60

# Docker container name for reading secrets from the volume
DASHBOARD_CONTAINER: str = "buddy-dashboard"
API_KEY_CONTAINER_PATH: str = "/data/api.key"

# Scripts
UP_SCRIPT: str = str(Path(BUDDY_HOME) / "cli" / "scripts" / "up.sh")
BUILD_SCRIPT: str = str(Path(BUDDY_HOME) / "cli" / "scripts" / "build.sh")

# Git
GIT_REMOTE_ORIGIN: str = "origin"
GIT_SLUG_SEPARATOR: str = "/"

# Logs
DEFAULT_LOG_TAIL_LINES: int = 100
SIGINT_EXIT_CODE: int = 130

# Docker exec
DOCKER_EXEC_TIMEOUT_SECONDS: int = 5

# Run defaults
DEFAULT_BASE_BRANCH: str = "main"
DEFAULT_RUN_BUDGET: float = 0.0
DEFAULT_RUN_DURATION: float = 0.0

# Doctor checks
DOCTOR_HTTP_TIMEOUT_SECONDS: int = 5
EXPECTED_COMPOSE_SERVICES: list[str] = ["buddy-dashboard", "buddy-agent", "buddy-db"]
