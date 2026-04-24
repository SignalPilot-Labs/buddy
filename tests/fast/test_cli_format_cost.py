"""Regression tests for format_cost in cli/output.py.

Previously format_cost treated zero the same as None (both showed "---"),
violating CLAUDE.md's Fail Fast rule: distinct states must render distinctly.

Fix: format_cost(None) -> "---", format_cost(0) -> "$0.00"
"""

from cli.output import format_cost


class TestFormatCost:
    """format_cost must distinguish missing from confirmed-zero."""

    def test_none_returns_missing(self) -> None:
        assert format_cost(None) == "—"

    def test_zero_returns_zero_dollars(self) -> None:
        """Zero cost is confirmed zero, not missing — must show $0.00."""
        assert format_cost(0) == "$0.00"

    def test_zero_float_returns_zero_dollars(self) -> None:
        assert format_cost(0.0) == "$0.00"

    def test_positive_cost_formatted(self) -> None:
        assert format_cost(1.5) == "$1.50"

    def test_large_cost_formatted(self) -> None:
        assert format_cost(123.456) == "$123.46"

    def test_small_cost_formatted(self) -> None:
        assert format_cost(0.001) == "$0.00"
