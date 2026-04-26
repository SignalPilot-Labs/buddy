"""Regression tests: CLI duration_ms=0 must render as "0ms", not as blank/missing.

Bug: `if dur` and `if tc.get("duration_ms")` both treat 0 as falsy, so a
real 0ms duration was displayed as blank in _print_tool_call_event and as "—"
in show_tools — indistinguishable from missing data.

Fix:
- Line 62: `if dur is not None` instead of `if dur`
- Line 88: `if tc.get('duration_ms') is not None` instead of `if tc.get('duration_ms')`
"""

from __future__ import annotations

from unittest.mock import patch

from cli.commands.run_helpers import _print_tool_call_event


class TestCliDurationZeroMs:
    """duration_ms=0 must render visibly; None must render as absent/dash."""

    def test_zero_ms_prints_duration_string(self) -> None:
        """_print_tool_call_event with duration_ms=0 must include '(0ms)' in output."""
        data = {"tool_name": "Bash", "phase": "build", "duration_ms": 0, "permitted": True}
        with patch("cli.commands.run_helpers.console") as mock_console:
            _print_tool_call_event(data)
        call_args = mock_console.print.call_args[0][0]
        assert "(0ms)" in call_args, f"Expected '(0ms)' in output, got: {call_args!r}"

    def test_none_ms_omits_duration_string(self) -> None:
        """_print_tool_call_event with duration_ms=None must not show any duration."""
        data = {"tool_name": "Bash", "phase": "build", "duration_ms": None, "permitted": True}
        with patch("cli.commands.run_helpers.console") as mock_console:
            _print_tool_call_event(data)
        call_args = mock_console.print.call_args[0][0]
        assert "ms)" not in call_args, f"Expected no duration in output, got: {call_args!r}"

    def test_missing_duration_key_omits_duration_string(self) -> None:
        """_print_tool_call_event with no duration_ms key must not show any duration."""
        data = {"tool_name": "Bash", "phase": "build", "permitted": True}
        with patch("cli.commands.run_helpers.console") as mock_console:
            _print_tool_call_event(data)
        call_args = mock_console.print.call_args[0][0]
        assert "ms)" not in call_args, f"Expected no duration in output, got: {call_args!r}"

    def test_show_tools_zero_ms_renders_zero_not_dash(self) -> None:
        """show_tools row with duration_ms=0 must render '0ms', not '—'."""
        from unittest.mock import MagicMock
        from cli.commands.run_helpers import show_tools
        from cli.config import state

        state.json_mode = False

        fake_data = [
            {
                "id": "abc",
                "ts": None,
                "tool_name": "Read",
                "phase": "explore",
                "duration_ms": 0,
                "permitted": True,
            }
        ]

        captured_rows: list[list[dict]] = []

        def capture_print_table(rows: list, cols: list, title: str = "") -> None:
            captured_rows.append(rows)

        with (
            patch("cli.commands.run_helpers.get_client") as mock_client,
            patch("cli.commands.run_helpers.print_table", side_effect=capture_print_table),
            patch("cli.commands.run_helpers.relative_time", return_value="just now"),
            patch("cli.commands.run_helpers.short_id", return_value="abc123"),
        ):
            mock_client.return_value.get = MagicMock(return_value=fake_data)
            show_tools(run_id="abc", limit=10, offset=0)

        assert captured_rows, "Expected print_table to be called"
        row = captured_rows[0][0]
        assert row["duration"] == "0ms", f"Expected '0ms', got: {row['duration']!r}"

    def test_show_tools_missing_duration_renders_dash(self) -> None:
        """show_tools row without duration_ms must render '—'."""
        from unittest.mock import MagicMock
        from cli.commands.run_helpers import show_tools
        from cli.config import state

        state.json_mode = False

        fake_data = [
            {
                "id": "abc",
                "ts": None,
                "tool_name": "Read",
                "phase": "explore",
                "permitted": True,
            }
        ]

        captured_rows: list[list[dict]] = []

        def capture_print_table(rows: list, cols: list, title: str = "") -> None:
            captured_rows.append(rows)

        with (
            patch("cli.commands.run_helpers.get_client") as mock_client,
            patch("cli.commands.run_helpers.print_table", side_effect=capture_print_table),
            patch("cli.commands.run_helpers.relative_time", return_value="just now"),
            patch("cli.commands.run_helpers.short_id", return_value="abc123"),
        ):
            mock_client.return_value.get = MagicMock(return_value=fake_data)
            show_tools(run_id="abc", limit=10, offset=0)

        assert captured_rows, "Expected print_table to be called"
        row = captured_rows[0][0]
        assert row["duration"] == "—", f"Expected '—', got: {row['duration']!r}"
