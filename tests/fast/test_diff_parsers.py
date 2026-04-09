"""Tests for git diff pure helper functions from sandbox_manager.repo_ops."""


from sandbox_manager.repo_ops import _parse_name_status, _parse_numstat, _aggregate_live_diff


class TestDiffParsers:
    """Tests for _parse_name_status, _parse_numstat, and _aggregate_live_diff."""

    # -- _parse_name_status --

    def test_name_status_normal(self):
        raw = "A\tsrc/new.py\nM\tsrc/main.py\nD\told.py"
        result = _parse_name_status(raw)
        assert result == {
            "src/new.py": "added",
            "src/main.py": "modified",
            "old.py": "deleted",
        }

    def test_name_status_renamed(self):
        raw = "R100\told_name.py\tnew_name.py"
        result = _parse_name_status(raw)
        assert result["new_name.py"] == "renamed"

    def test_name_status_empty(self):
        result = _parse_name_status("")
        assert result == {}

    def test_name_status_unknown_code_defaults_to_modified(self):
        raw = "X\tsome_file.py"
        result = _parse_name_status(raw)
        assert result["some_file.py"] == "modified"

    # -- _parse_numstat --

    def test_numstat_normal(self):
        raw = "10\t5\tsrc/main.py\n3\t0\tsrc/new.py"
        status_map = {"src/main.py": "modified", "src/new.py": "added"}
        result = _parse_numstat(raw, status_map)
        assert result == [
            {"path": "src/main.py", "added": 10, "removed": 5, "status": "modified"},
            {"path": "src/new.py", "added": 3, "removed": 0, "status": "added"},
        ]

    def test_numstat_binary_files(self):
        raw = "-\t-\timage.png"
        status_map = {"image.png": "added"}
        result = _parse_numstat(raw, status_map)
        assert result == [
            {"path": "image.png", "added": 0, "removed": 0, "status": "added"},
        ]

    def test_numstat_empty(self):
        result = _parse_numstat("", {})
        assert result == []

    def test_numstat_missing_status_defaults_to_modified(self):
        raw = "7\t2\tunknown.py"
        result = _parse_numstat(raw, {})
        assert result == [
            {"path": "unknown.py", "added": 7, "removed": 2, "status": "modified"},
        ]

    def test_numstat_skips_malformed_lines(self):
        raw = "10\t5\tok.py\nbadline\n3\t0\talso_ok.py"
        result = _parse_numstat(raw, {})
        assert len(result) == 2
        assert result[0]["path"] == "ok.py"
        assert result[1]["path"] == "also_ok.py"

    # -- _aggregate_live_diff --

    def test_aggregate_committed_and_uncommitted(self):
        all_lines = "10\t2\tapp.py\n5\t1\tapp.py"
        result = _aggregate_live_diff(all_lines)
        assert len(result) == 1
        assert result[0] == {
            "path": "app.py",
            "added": 15,
            "removed": 3,
            "status": "modified",
        }

    def test_aggregate_distinct_files(self):
        all_lines = "4\t0\ta.py\n0\t3\tb.py"
        result = _aggregate_live_diff(all_lines)
        assert len(result) == 2
        paths = {r["path"] for r in result}
        assert paths == {"a.py", "b.py"}

    def test_aggregate_empty(self):
        result = _aggregate_live_diff("")
        assert result == []

    def test_aggregate_binary_files(self):
        all_lines = "-\t-\tlogo.png"
        result = _aggregate_live_diff(all_lines)
        assert result == [
            {"path": "logo.png", "added": 0, "removed": 0, "status": "modified"},
        ]

    def test_aggregate_skips_malformed_lines(self):
        all_lines = "10\t2\tok.py\nbroken"
        result = _aggregate_live_diff(all_lines)
        assert len(result) == 1
        assert result[0]["path"] == "ok.py"
