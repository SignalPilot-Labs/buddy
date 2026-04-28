"""Shared constants for the AutoFyn CLI."""

from __future__ import annotations

from pathlib import Path

# AutoFyn home — everything lives here after install
AUTOFYN_HOME: str = str(Path.home() / ".autofyn")

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

# Docker container name for reading secrets from the volume
DASHBOARD_CONTAINER: str = "autofyn-dashboard"
API_KEY_CONTAINER_PATH: str = "/data/api.key"

# Scripts
START_SCRIPT: str = str(Path(AUTOFYN_HOME) / "cli" / "scripts" / "start.sh")
BUILD_SCRIPT: str = str(Path(AUTOFYN_HOME) / "cli" / "scripts" / "build.sh")
UNINSTALL_SCRIPT: str = str(Path(AUTOFYN_HOME) / "cli" / "scripts" / "uninstall.sh")

# Git
GIT_REMOTE_ORIGIN: str = "origin"
GIT_SLUG_SEPARATOR: str = "/"

# Logs
DEFAULT_LOG_TAIL_LINES: int = 100
SIGINT_EXIT_CODE: int = 130

# Docker images
DEFAULT_IMAGE_TAG: str = "main"

# Docker exec
DOCKER_EXEC_TIMEOUT_SECONDS: int = 5

# Run defaults
DEFAULT_BASE_BRANCH: str = "main"
DEFAULT_RUN_BUDGET: float = 0.0
DEFAULT_RUN_DURATION: float = 0.0

# Stop action defaults
STOP_PR_DEFAULT: str = "Y"

# Secret masking — prefix lengths mirror dashboard/backend/constants.py
MASK_PREFIX_DEFAULT: int = 6
MASK_PREFIX_CLAUDE: int = 8
MASK_PREFIX_GIT: int = 7

# Keys that must be masked before printing to stdout
CLI_SECRET_KEYS: frozenset[str] = frozenset(
    {
        "api_key",
        "dashboard_api_key",
        "git_token",
        "claude_token",
    }
)
