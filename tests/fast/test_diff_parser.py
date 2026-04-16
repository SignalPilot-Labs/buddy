"""Tests for dashboard/backend/diff_parser.py.

The live-run Changes panel depends on parse_diff_stats extracting the
same shape as the stored post-teardown diff_stats so the frontend
renders both uniformly. Pins status classification, path extraction,
and line counting.
"""

from backend.diff_parser import parse_diff_stats


def _new_file(path: str, lines: list[str]) -> str:
    """Build a minimal `new file` unified diff section."""
    body = [f"+{line}" for line in lines]
    return (
        f"diff --git a/{path} b/{path}\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        f"+++ b/{path}\n"
        f"@@ -0,0 +1,{len(lines)} @@\n"
        + "\n".join(body)
    )


def _modified_file(path: str, added: list[str], removed: list[str]) -> str:
    """Build a simple modification section with + and - lines."""
    plus = [f"+{line}" for line in added]
    minus = [f"-{line}" for line in removed]
    hunk_old = len(removed) or 1
    hunk_new = len(added) or 1
    return (
        f"diff --git a/{path} b/{path}\n"
        "index 1111111..2222222 100644\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        f"@@ -1,{hunk_old} +1,{hunk_new} @@\n"
        + "\n".join(minus + plus)
    )


class TestParseDiffStats:
    """parse_diff_stats extracts per-file entries from unified diffs."""

    def test_empty_input_returns_empty_list(self) -> None:
        assert parse_diff_stats("") == []

    def test_single_new_file(self) -> None:
        diff = _new_file("src/new.py", ["line a", "line b", "line c"])
        stats = parse_diff_stats(diff)
        assert stats == [
            {"path": "src/new.py", "added": 3, "removed": 0, "status": "added"},
        ]

    def test_modified_file(self) -> None:
        diff = _modified_file("src/main.py", ["new1", "new2"], ["old1"])
        stats = parse_diff_stats(diff)
        assert stats == [
            {"path": "src/main.py", "added": 2, "removed": 1, "status": "modified"},
        ]

    def test_deleted_file(self) -> None:
        diff = (
            "diff --git a/src/gone.py b/src/gone.py\n"
            "deleted file mode 100644\n"
            "--- a/src/gone.py\n"
            "+++ /dev/null\n"
            "@@ -1,2 +0,0 @@\n"
            "-line 1\n"
            "-line 2"
        )
        stats = parse_diff_stats(diff)
        assert stats == [
            {"path": "src/gone.py", "added": 0, "removed": 2, "status": "deleted"},
        ]

    def test_renamed_file_is_classified_as_renamed(self) -> None:
        diff = (
            "diff --git a/old.py b/new.py\n"
            "similarity index 100%\n"
            "rename from old.py\n"
            "rename to new.py"
        )
        stats = parse_diff_stats(diff)
        assert len(stats) == 1
        assert stats[0]["path"] == "new.py"
        assert stats[0]["status"] == "renamed"

    def test_multiple_files_in_one_diff(self) -> None:
        diff = "\n".join([
            _new_file("a.py", ["x"]),
            _modified_file("b.py", ["new"], ["old"]),
            _new_file("tmp/round-1/report.md", ["line 1", "line 2"]),
        ])
        stats = parse_diff_stats(diff)
        assert [s["path"] for s in stats] == ["a.py", "b.py", "tmp/round-1/report.md"]
        assert [s["status"] for s in stats] == ["added", "modified", "added"]

    def test_plus_plus_plus_header_not_counted_as_added_line(self) -> None:
        # `+++ b/...` is part of the file header, not a content addition.
        diff = _new_file("x.py", ["real content line"])
        stats = parse_diff_stats(diff)
        assert stats[0]["added"] == 1  # Not 2.

    def test_minus_minus_minus_header_not_counted_as_removed_line(self) -> None:
        diff = _modified_file("x.py", [], ["gone"])
        stats = parse_diff_stats(diff)
        assert stats[0]["removed"] == 1  # Not 2.

    def test_paths_with_spaces_extracted_correctly(self) -> None:
        # Git quotes paths with spaces, but the b/ prefix still anchors it.
        diff = _new_file("tmp/round-2/security reviewer.md", ["a"])
        stats = parse_diff_stats(diff)
        assert stats[0]["path"] == "tmp/round-2/security reviewer.md"

    def test_tmp_round_file_classified_as_added(self) -> None:
        # Exercises the actual bug that caused tmp files to show "M" in the UI.
        diff = _new_file("tmp/round-1/architect.md", ["spec line"])
        stats = parse_diff_stats(diff)
        assert stats[0]["status"] == "added"
