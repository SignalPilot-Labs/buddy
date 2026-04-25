"""Regression test: dashboard/entrypoint.sh must not log the API key in plaintext.

Finding: CRIT-1 — API key printed in plaintext to container logs.
"""

from __future__ import annotations

import re
from pathlib import Path


ENTRYPOINT_PATH = Path(__file__).parents[2] / "dashboard" / "entrypoint.sh"

# Matches lines that are NOT log output (file redirect or curl header).
_EXCLUDED_LINE_PATTERN = re.compile(r">|curl.*-H")

# Matches a bare API_KEY expansion that would print the full key.
_PLAINTEXT_KEY_PATTERN = re.compile(r"\$\{API_KEY\}|\$API_KEY(?!:)")

# Matches the masked substring form that reveals only the tail.
_MASKED_KEY_PATTERN = re.compile(r"\$\{API_KEY:\s*-\d+\}")


class TestEntrypointApiKeyNotLogged:
    """echo lines in entrypoint.sh must not expose the full API key."""

    def test_no_echo_prints_full_api_key(self) -> None:
        """No echo line should contain a bare ${API_KEY} or $API_KEY expansion."""
        lines = ENTRYPOINT_PATH.read_text().splitlines()
        offending: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped.startswith("echo"):
                continue
            if _EXCLUDED_LINE_PATTERN.search(stripped):
                continue
            if _PLAINTEXT_KEY_PATTERN.search(stripped):
                offending.append(stripped)
        assert offending == [], (
            "Found echo lines printing the full API_KEY:\n"
            + "\n".join(f"  {line}" for line in offending)
        )

    def test_masked_echo_line_exists(self) -> None:
        """At least one echo line must contain a masked key reference (not just deleted)."""
        lines = ENTRYPOINT_PATH.read_text().splitlines()
        masked_echo_lines = [
            line.strip()
            for line in lines
            if line.strip().startswith("echo") and _MASKED_KEY_PATTERN.search(line)
        ]
        assert masked_echo_lines, (
            "Expected at least one echo line with a masked API_KEY reference "
            f"(e.g. ${{API_KEY: -4}}) in {ENTRYPOINT_PATH}"
        )
