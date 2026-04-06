"""Shared utilities for the agent package — branch validation."""

import re

from utils.constants import BRANCH_NAME_MAX_LEN, BRANCH_NAME_PATTERN

_BRANCH_RE = re.compile(BRANCH_NAME_PATTERN)


def validate_branch_name(name: str) -> None:
    """Validate a branch name to prevent command injection."""
    if not name or len(name) > BRANCH_NAME_MAX_LEN:
        raise ValueError(f"Invalid branch name length: {len(name) if name else 0}")
    if not _BRANCH_RE.match(name):
        raise ValueError("Invalid branch name: contains disallowed characters")
    if '..' in name or name.endswith('.lock') or name.endswith('/'):
        raise ValueError("Invalid branch name format")
