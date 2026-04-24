"""Regression tests for format_duration in cli/output.py.

Previously format_duration treated zero (unlimited) the same as None (missing),
violating CLAUDE.md's Fail Fast rule: distinct states must render distinctly.

Fix: format_duration(None) -> "---", format_duration(0) -> "unlimited"
"""

from cli.output import format_duration


class TestFormatDuration:
    """format_duration must distinguish missing from unlimited (zero)."""

    def test_none_returns_missing(self) -> None:
        assert format_duration(None) == "—"

    def test_zero_returns_unlimited(self) -> None:
        """duration_minutes=0 means unlimited per API convention."""
        assert format_duration(0) == "unlimited"

    def test_30_minutes(self) -> None:
        assert format_duration(30) == "30m"

    def test_60_minutes(self) -> None:
        assert format_duration(60) == "1h"

    def test_90_minutes(self) -> None:
        assert format_duration(90) == "1h30m"

    def test_120_minutes(self) -> None:
        assert format_duration(120) == "2h"
