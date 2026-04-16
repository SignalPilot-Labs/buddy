"""Credential redactor for agent log lines.

Scrubs known credential patterns from log strings before they are
returned by any log endpoint. Patterns are compiled once at module load.
"""

import re
from collections.abc import Iterable

# ── Pattern strings (no magic values inline in functions) ──────────────────

_CLAUDE_API_KEY_PATTERN = r"sk-ant-[A-Za-z0-9_\-]{20,}"
_GITHUB_PAT_PATTERN = r"ghp_[A-Za-z0-9]{20,}"
_GITHUB_PAT_LONG_PATTERN = r"github_pat_[A-Za-z0-9_]{20,}"
_BEARER_HEADER_PATTERN = r"(?:X-API-Key|X-Internal-Secret|Authorization):\s*.+"
_AGENT_SECRET_PATTERN = r"AGENT_INTERNAL_SECRET[=:]\s*\S+"
_API_KEY_QUERY_PATTERN = r"api_key=[A-Za-z0-9%\-_]{8,}"
_DASHBOARD_API_KEY_LOG_PATTERN = r"\[dashboard\] API key: [A-Za-z0-9_\-]{20,}"

_REDACTED = "[REDACTED]"

# ── Compiled patterns (module-level, compiled once) ─────────────────────────

_PATTERNS: list[re.Pattern[str]] = [
    re.compile(_CLAUDE_API_KEY_PATTERN),
    re.compile(_GITHUB_PAT_PATTERN),
    re.compile(_GITHUB_PAT_LONG_PATTERN),
    re.compile(_BEARER_HEADER_PATTERN),
    re.compile(_AGENT_SECRET_PATTERN),
    re.compile(_API_KEY_QUERY_PATTERN),
    re.compile(_DASHBOARD_API_KEY_LOG_PATTERN),
]


def scrub_line(line: str) -> str:
    """Return `line` with all credential-matching substrings replaced by [REDACTED]."""
    for pattern in _PATTERNS:
        line = pattern.sub(_REDACTED, line)
    return line


def scrub_lines(lines: Iterable[str]) -> list[str]:
    """Return a new list with every line passed through `scrub_line`."""
    return [scrub_line(line) for line in lines]
