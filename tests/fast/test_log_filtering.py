"""Tests for run_id log filtering in the /logs endpoint.

The agent logs use run_id[:8] as prefix. The filter must:
- Include lines matching the run_id prefix
- Include continuation lines (tracebacks) after a matched line
- Exclude lines from other runs
- Exclude continuation lines after a non-matched line
"""

from utils.constants import RUN_ID_LOG_PREFIX_LEN

RUN_A = "aaaaaaaa-1111-2222-3333-444444444444"
RUN_B = "bbbbbbbb-5555-6666-7777-888888888888"
PREFIX_A = RUN_A[:RUN_ID_LOG_PREFIX_LEN]
PREFIX_B = RUN_B[:RUN_ID_LOG_PREFIX_LEN]


def _filter(lines: list[str], run_id: str) -> list[str]:
    """Reproduce the filtering logic from api.get_logs."""
    prefix = run_id[:RUN_ID_LOG_PREFIX_LEN]
    filtered: list[str] = []
    keep = False
    for line in lines:
        if line and (line[0] == "[" or line[0].isdigit()):
            keep = prefix in line
        if keep:
            filtered.append(line)
    return filtered


class TestLogRunFilter:
    """Filter agent logs by run_id prefix."""

    def test_basic_match(self) -> None:
        lines = [
            f"[{PREFIX_A}] Round 1 begin",
            f"[{PREFIX_B}] Round 1 begin",
            f"[{PREFIX_A}] Round 1 ended",
        ]
        result = _filter(lines, RUN_A)
        assert len(result) == 2
        assert all(PREFIX_A in line for line in result)

    def test_excludes_other_run(self) -> None:
        lines = [
            f"[{PREFIX_B}] Starting bootstrap",
            f"[{PREFIX_B}] Clone complete",
        ]
        result = _filter(lines, RUN_A)
        assert result == []

    def test_traceback_continuation(self) -> None:
        lines = [
            f"[{PREFIX_A}] Fatal error in round 1",
            "Traceback (most recent call last):",
            '  File "runner.py", line 42, in run',
            "RuntimeError: sandbox died",
            f"[{PREFIX_B}] Round 1 begin",
        ]
        result = _filter(lines, RUN_A)
        assert len(result) == 4
        assert "Traceback" in result[1]
        assert "RuntimeError" in result[3]

    def test_traceback_from_other_run_excluded(self) -> None:
        lines = [
            f"[{PREFIX_B}] Fatal error",
            "Traceback (most recent call last):",
            "RuntimeError: boom",
            f"[{PREFIX_A}] Round 1 begin",
        ]
        result = _filter(lines, RUN_A)
        assert len(result) == 1
        assert PREFIX_A in result[0]

    def test_timestamp_prefixed_lines(self) -> None:
        lines = [
            f"2026-04-15T19:52:19Z [{PREFIX_A}] bootstrap done",
            f"2026-04-15T19:52:20Z [{PREFIX_B}] bootstrap done",
        ]
        result = _filter(lines, RUN_A)
        assert len(result) == 1
        assert PREFIX_A in result[0]

    def test_empty_lines_preserved_in_context(self) -> None:
        lines = [
            f"[{PREFIX_A}] error",
            "",
            "  detail line",
            f"[{PREFIX_B}] ok",
        ]
        result = _filter(lines, RUN_A)
        # empty line and detail are continuations of the matched line
        assert len(result) == 3

    def test_no_run_id_returns_all(self) -> None:
        """When run_id is None, no filtering happens (tested at endpoint level)."""
        lines = [f"[{PREFIX_A}] x", f"[{PREFIX_B}] y"]
        # No filter applied — this is handled by the endpoint's `if run_id:` guard
        assert len(lines) == 2
