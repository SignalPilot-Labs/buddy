"""Tests for the pure parse helpers in sandbox.handlers.repo_parse.

These tests use exact git output format strings (tab-separated fields,
R100 for rename score) to ensure the parsers never regress against real
git output.
"""

from repo.parsers import (
    normalize_rename_path,
    parse_name_status,
    parse_numstat,
)


class TestNormalizeRenamePath:
    """Tests for normalize_rename_path."""

    def test_plain_path_unchanged(self) -> None:
        assert normalize_rename_path("src/file.ts") == "src/file.ts"

    def test_rename_in_filename(self) -> None:
        assert normalize_rename_path("src/{old.ts => new.ts}") == "src/new.ts"

    def test_rename_in_directory(self) -> None:
        assert normalize_rename_path("{old => new}/file.ts") == "new/file.ts"

    def test_rename_mid_path(self) -> None:
        assert normalize_rename_path("a/{b => c}/d.ts") == "a/c/d.ts"

    def test_no_braces(self) -> None:
        assert normalize_rename_path("components/Button.tsx") == "components/Button.tsx"

    def test_deeply_nested_rename(self) -> None:
        assert normalize_rename_path("src/lib/{utils => helpers}/index.ts") == "src/lib/helpers/index.ts"

    def test_empty_string(self) -> None:
        assert normalize_rename_path("") == ""


class TestParseNameStatus:
    """Tests for parse_name_status."""

    def test_modified_file(self) -> None:
        result = parse_name_status("M\tsrc/file.ts")
        assert result == {"src/file.ts": "modified"}

    def test_added_file(self) -> None:
        result = parse_name_status("A\tnew.ts")
        assert result == {"new.ts": "added"}

    def test_deleted_file(self) -> None:
        result = parse_name_status("D\told.ts")
        assert result == {"old.ts": "deleted"}

    def test_renamed_file_r100(self) -> None:
        result = parse_name_status("R100\told.ts\tnew.ts")
        assert result == {"new.ts": "renamed"}

    def test_renamed_file_partial_score(self) -> None:
        result = parse_name_status("R085\tsrc/old.ts\tsrc/new.ts")
        assert result == {"src/new.ts": "renamed"}

    def test_empty_input(self) -> None:
        result = parse_name_status("")
        assert result == {}

    def test_multiple_files(self) -> None:
        raw = "M\tsrc/a.ts\nA\tsrc/b.ts\nD\tsrc/c.ts"
        result = parse_name_status(raw)
        assert result == {
            "src/a.ts": "modified",
            "src/b.ts": "added",
            "src/c.ts": "deleted",
        }

    def test_unknown_status_code_defaults_to_modified(self) -> None:
        result = parse_name_status("X\tsrc/file.ts")
        assert result == {"src/file.ts": "modified"}

    def test_skips_blank_lines(self) -> None:
        raw = "M\tsrc/a.ts\n\nA\tsrc/b.ts\n"
        result = parse_name_status(raw)
        assert result == {"src/a.ts": "modified", "src/b.ts": "added"}

    def test_skips_line_starting_with_tab(self) -> None:
        """Line starting with tab (empty status) must not raise IndexError."""
        result = parse_name_status("\tsrc/file.ts")
        assert result == {}

    def test_skips_empty_status_in_mixed_input(self) -> None:
        """Empty status line among valid lines must be skipped, not crash."""
        raw = "M\tsrc/a.ts\n\tsrc/bad.ts\nA\tsrc/b.ts"
        result = parse_name_status(raw)
        assert result == {"src/a.ts": "modified", "src/b.ts": "added"}


class TestParseNumstat:
    """Tests for parse_numstat."""

    def test_empty_input(self) -> None:
        result = parse_numstat("", {})
        assert result == []

    def test_regular_modified_file(self) -> None:
        result = parse_numstat(
            "10\t2\tsrc/app.ts",
            {"src/app.ts": "modified"},
        )
        assert result == [{"path": "src/app.ts", "added": 10, "removed": 2, "status": "modified"}]

    def test_binary_file(self) -> None:
        result = parse_numstat(
            "-\t-\tsrc/image.png",
            {"src/image.png": "modified"},
        )
        assert result == [{"path": "src/image.png", "added": 0, "removed": 0, "status": "modified"}]

    def test_added_file(self) -> None:
        result = parse_numstat(
            "50\t0\tnew-file.ts",
            {"new-file.ts": "added"},
        )
        assert result == [{"path": "new-file.ts", "added": 50, "removed": 0, "status": "added"}]

    def test_deleted_file(self) -> None:
        result = parse_numstat(
            "0\t30\told-file.ts",
            {"old-file.ts": "deleted"},
        )
        assert result == [{"path": "old-file.ts", "added": 0, "removed": 30, "status": "deleted"}]

    def test_missing_status_map_entry_defaults_to_modified(self) -> None:
        result = parse_numstat("5\t1\tsrc/unknown.ts", {})
        assert result == [{"path": "src/unknown.ts", "added": 5, "removed": 1, "status": "modified"}]

    def test_skips_blank_lines(self) -> None:
        raw = "10\t2\tsrc/a.ts\n\n5\t1\tsrc/b.ts\n"
        result = parse_numstat(raw, {"src/a.ts": "modified", "src/b.ts": "added"})
        assert len(result) == 2

    def test_skips_malformed_lines(self) -> None:
        raw = "10\t2\tsrc/a.ts\nbadline\n5\t1\tsrc/b.ts"
        result = parse_numstat(raw, {})
        assert len(result) == 2

    def test_multiple_files(self) -> None:
        raw = "10\t2\tsrc/a.ts\n50\t0\tsrc/b.ts\n0\t15\tsrc/c.ts"
        status_map = {"src/a.ts": "modified", "src/b.ts": "added", "src/c.ts": "deleted"}
        result = parse_numstat(raw, status_map)
        assert len(result) == 3
        assert result[0] == {"path": "src/a.ts", "added": 10, "removed": 2, "status": "modified"}
        assert result[1] == {"path": "src/b.ts", "added": 50, "removed": 0, "status": "added"}
        assert result[2] == {"path": "src/c.ts", "added": 0, "removed": 15, "status": "deleted"}

    def test_non_numeric_values_default_to_zero(self) -> None:
        """Non-numeric, non-'-' content (e.g. encoding corruption) must not raise ValueError."""
        result = parse_numstat(
            "abc\t123\tfile.ts",
            {"file.ts": "modified"},
        )
        assert result == [{"path": "file.ts", "added": 0, "removed": 123, "status": "modified"}]

    def test_empty_values_default_to_zero(self) -> None:
        """Empty first field among valid lines must not raise ValueError."""
        raw = "10\t2\tsrc/a.ts\n\t5\tsrc/b.ts\n3\t1\tsrc/c.ts"
        result = parse_numstat(raw, {"src/a.ts": "modified", "src/b.ts": "modified", "src/c.ts": "modified"})
        b_entry = next((e for e in result if e["path"] == "src/b.ts"), None)
        assert b_entry is not None
        assert b_entry["added"] == 0
        assert b_entry["removed"] == 5


class TestParseNumstatWithRename:
    """Integration tests for parse_numstat + parse_name_status with renames.

    These verify the core bug fix: numstat uses {old => new} rename syntax
    but name-status stores only the plain new path. After normalization both
    must agree.
    """

    def test_rename_path_resolves_correctly(self) -> None:
        name_status_raw = "R100\tsrc/old.ts\tsrc/new.ts"
        numstat_raw = "5\t3\tsrc/{old.ts => new.ts}"

        status_map = parse_name_status(name_status_raw)
        result = parse_numstat(numstat_raw, status_map)

        assert len(result) == 1
        entry = result[0]
        assert entry["path"] == "src/new.ts"
        assert entry["status"] == "renamed"
        assert entry["added"] == 5
        assert entry["removed"] == 3

    def test_directory_rename_resolves_correctly(self) -> None:
        name_status_raw = "R100\told/file.ts\tnew/file.ts"
        numstat_raw = "2\t1\t{old => new}/file.ts"

        status_map = parse_name_status(name_status_raw)
        result = parse_numstat(numstat_raw, status_map)

        assert len(result) == 1
        entry = result[0]
        assert entry["path"] == "new/file.ts"
        assert entry["status"] == "renamed"
        assert entry["added"] == 2
        assert entry["removed"] == 1

    def test_mixed_rename_and_modify(self) -> None:
        name_status_raw = "R100\tsrc/old.ts\tsrc/new.ts\nM\tsrc/other.ts"
        numstat_raw = "5\t3\tsrc/{old.ts => new.ts}\n10\t2\tsrc/other.ts"

        status_map = parse_name_status(name_status_raw)
        result = parse_numstat(numstat_raw, status_map)

        assert len(result) == 2
        rename_entry = next(e for e in result if e["path"] == "src/new.ts")
        modify_entry = next(e for e in result if e["path"] == "src/other.ts")

        assert rename_entry["status"] == "renamed"
        assert rename_entry["added"] == 5
        assert rename_entry["removed"] == 3

        assert modify_entry["status"] == "modified"
        assert modify_entry["added"] == 10
        assert modify_entry["removed"] == 2
