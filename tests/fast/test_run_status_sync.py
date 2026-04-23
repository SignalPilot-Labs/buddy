"""Verify that RUN_STATUSES in db.constants stays in sync with the TypeScript RunStatus union.

The canonical set lives in db.constants.RUN_STATUSES. This test reads the
TypeScript types.ts file to extract the RunStatus union members and asserts
they match. A companion test verifies all run-status assignments in Python
source use only values from the canonical set.
"""

import re
from pathlib import Path

from db.constants import RUN_STATUSES

_TYPES_TS_PATH = Path("dashboard/frontend/lib/types.ts")

# Matches each string in the RunStatus union, e.g. | "starting"
_TS_STATUS_PATTERN = re.compile(r'^\s*\|\s*"([^"]+)"', re.MULTILINE)


class TestRunStatusSync:
    """RUN_STATUSES must match the TypeScript RunStatus union."""

    def _extract_ts_statuses(self) -> set[str]:
        """Parse the RunStatus union from types.ts and return the member strings."""
        content = _TYPES_TS_PATH.read_text()
        # Find the RunStatus block between "export type RunStatus =" and the closing ";"
        match = re.search(r"export type RunStatus\s*=\s*(.*?);", content, re.DOTALL)
        assert match, f"Could not find RunStatus union in {_TYPES_TS_PATH}"
        union_body = match.group(1)
        found = _TS_STATUS_PATTERN.findall(union_body)
        return set(found)

    def test_python_and_typescript_sets_match(self) -> None:
        """Every Python RUN_STATUS must appear in the TypeScript RunStatus union."""
        ts_statuses = self._extract_ts_statuses()
        assert ts_statuses, "Should find at least one RunStatus member in types.ts"

        missing_in_ts = RUN_STATUSES - ts_statuses
        assert not missing_in_ts, (
            f"Python RUN_STATUSES has values not in TypeScript RunStatus: {missing_in_ts}"
        )

        missing_in_python = ts_statuses - RUN_STATUSES
        assert not missing_in_python, (
            f"TypeScript RunStatus has values not in Python RUN_STATUSES: {missing_in_python}"
        )

    def test_canonical_set_is_complete(self) -> None:
        """RUN_STATUSES must contain all ten expected status values."""
        expected = {
            "starting", "running", "paused", "rate_limited",
            "completed", "completed_no_changes", "stopped",
            "error", "crashed", "killed",
        }
        assert RUN_STATUSES == expected, (
            f"RUN_STATUSES differs from expected set.\n"
            f"Extra: {RUN_STATUSES - expected}\n"
            f"Missing: {expected - RUN_STATUSES}"
        )

    def test_derived_groups_are_subsets(self) -> None:
        """ACTIVE_RUN_STATUSES and TERMINAL_RUN_STATUSES must be subsets of RUN_STATUSES."""
        from db.constants import ACTIVE_RUN_STATUSES, CLEANABLE_RUN_STATUSES, TERMINAL_RUN_STATUSES

        assert ACTIVE_RUN_STATUSES <= RUN_STATUSES, (
            f"ACTIVE_RUN_STATUSES not a subset of RUN_STATUSES: {ACTIVE_RUN_STATUSES - RUN_STATUSES}"
        )
        assert TERMINAL_RUN_STATUSES <= RUN_STATUSES, (
            f"TERMINAL_RUN_STATUSES not a subset of RUN_STATUSES: {TERMINAL_RUN_STATUSES - RUN_STATUSES}"
        )
        assert CLEANABLE_RUN_STATUSES <= RUN_STATUSES, (
            f"CLEANABLE_RUN_STATUSES not a subset of RUN_STATUSES: {CLEANABLE_RUN_STATUSES - RUN_STATUSES}"
        )
        assert not (ACTIVE_RUN_STATUSES & TERMINAL_RUN_STATUSES), (
            f"ACTIVE and TERMINAL overlap: {ACTIVE_RUN_STATUSES & TERMINAL_RUN_STATUSES}"
        )
