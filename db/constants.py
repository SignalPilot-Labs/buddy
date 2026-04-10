"""Shared constants importable from both the agent and dashboard containers.

The `db` package is the only Python package imported by both `autofyn/` and
`dashboard/backend/`, so cross-container constants that must not drift live here.
"""

# Valid Claude model identifiers accepted at the run-start boundary.
# Source of truth for: agent validation, dashboard Pydantic regex, fallback map.
VALID_MODELS: tuple[str, ...] = ("opus", "sonnet", "haiku")

# Default model used when the caller does not specify one.
DEFAULT_MODEL: str = "opus"

# Pydantic/regex-friendly alternation pattern built from VALID_MODELS.
VALID_MODELS_PATTERN: str = f"^({'|'.join(VALID_MODELS)})$"
