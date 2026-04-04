"""Shared constants for the Buddy CLI."""

from __future__ import annotations

# HTTP client
HTTP_TIMEOUT_SECONDS: int = 15

# Display truncation lengths
PROMPT_SELECTOR_TRUNCATION: int = 50
PROMPT_LIST_TRUNCATION: int = 40
STREAM_SNIPPET_LENGTH: int = 80
STREAM_DATA_TRUNCATION: int = 100
AUDIT_SNIPPET_LENGTH: int = 60
SHORT_ID_LENGTH: int = 8
ISO_FALLBACK_LENGTH: int = 19

# Query defaults
DEFAULT_QUERY_LIMIT: int = 50
DEFAULT_QUERY_OFFSET: int = 0

# Fuzzy selector
FUZZY_MAX_HEIGHT: str = "70%"

# API
DEFAULT_API_URL: str = "http://localhost:3401"

# Docker container name for reading secrets from the volume
DASHBOARD_CONTAINER: str = "buddy-dashboard"
API_KEY_CONTAINER_PATH: str = "/data/api.key"
