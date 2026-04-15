"""Verify that all log_audit() calls use event types from the canonical set.

The canonical set lives in db.constants.AUDIT_EVENT_TYPES. This test greps
the Python source for log_audit() calls and asserts every event_type string
literal is present in the canonical set.  A companion TypeScript test
(audit-event-sync.test.ts) verifies the frontend AuditEventType union
matches the same set.
"""

import re
import subprocess

from db.constants import AUDIT_EVENT_TYPES

# Directories that emit audit events.
SEARCH_DIRS = ["autofyn", "sandbox", "dashboard/backend"]

# Matches: log_audit(anything, "event_type" across multiple lines
MULTI_LINE_PATTERN = re.compile(r'log_audit\([^,]+,\s*"([^"]+)"', re.DOTALL)


class TestAuditEventSync:
    """All log_audit calls must use types from AUDIT_EVENT_TYPES."""

    def _collect_emitted_types(self) -> set[str]:
        """Read Python source files and extract event types from log_audit calls.

        Handles both single-line and multi-line call patterns.
        """
        found: set[str] = set()
        # Read all Python files and search for log_audit calls
        for d in SEARCH_DIRS:
            result = subprocess.run(
                ["find", d, "-name", "*.py", "-type", "f"],
                capture_output=True,
                text=True,
            )
            for filepath in result.stdout.strip().splitlines():
                if not filepath:
                    continue
                with open(filepath) as f:
                    content = f.read()
                # Match log_audit( ... , "event_type" across lines
                for m in MULTI_LINE_PATTERN.finditer(content):
                    found.add(m.group(1))
        return found

    def test_all_emitted_types_are_in_canonical_set(self) -> None:
        emitted = self._collect_emitted_types()
        assert emitted, "Should find at least one log_audit call"
        unknown = emitted - AUDIT_EVENT_TYPES
        assert not unknown, f"log_audit() uses types not in AUDIT_EVENT_TYPES: {unknown}"

    def test_canonical_set_is_nonempty(self) -> None:
        assert len(AUDIT_EVENT_TYPES) > 20, "Expected 20+ event types"

    def test_emitted_types_are_substantial(self) -> None:
        emitted = self._collect_emitted_types()
        assert len(emitted) >= 15, f"Expected 15+ emitted types, got {len(emitted)}"
