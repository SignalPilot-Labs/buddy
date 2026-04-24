"""Regression tests for /diff/tmp — sandbox-first, archive-fallback behavior.

During round 1 the archive on the host volume is empty; round files live
inside the live sandbox at /tmp/round-N. Once the run completes, the files
are flushed to the archive and the sandbox is gone. The endpoint must
pick the right source based on whether a sandbox client exists.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from endpoints.diff import (
    _build_tmp_diff,
    _collect_tmp_from_archive,
    _collect_tmp_from_sandbox,
)


class TestBuildTmpDiff:
    """Renders entries into a unified 'new file' diff."""

    def test_empty_entries_returns_empty_string(self) -> None:
        assert _build_tmp_diff([]) == ""

    def test_single_file_renders_correct_header_and_body(self) -> None:
        out = _build_tmp_diff([("tmp/round-1/a.md", "line1\nline2")])
        assert "diff --git a/tmp/round-1/a.md b/tmp/round-1/a.md" in out
        assert "new file mode 100644" in out
        assert "@@ -0,0 +1,2 @@" in out
        assert "+line1" in out
        assert "+line2" in out

    def test_multiple_files_are_separated(self) -> None:
        out = _build_tmp_diff([
            ("tmp/round-1/a.md", "x"),
            ("tmp/round-2/b.md", "y"),
        ])
        assert out.count("diff --git") == 2


class TestCollectTmpFromSandbox:
    """Reads /tmp/round-* from a live sandbox client."""

    @pytest.mark.asyncio
    async def test_filters_non_round_dirs(self) -> None:
        client = MagicMock()
        client.file_system.ls = AsyncMock(return_value=["round-1", "other", "cache"])
        client.file_system.read_dir = AsyncMock(return_value={"report.md": "hi"})
        entries = await _collect_tmp_from_sandbox(client)
        # Only round-1 was processed.
        client.file_system.read_dir.assert_awaited_once_with("/tmp/round-1")
        assert entries == [("tmp/round-1/report.md", "hi")]

    @pytest.mark.asyncio
    async def test_rejects_traversal_and_non_numeric_suffixes(self) -> None:
        client = MagicMock()
        client.file_system.ls = AsyncMock(return_value=[
            "round-..", "round-/etc", "round-abc", "round-", "round-1",
        ])
        client.file_system.read_dir = AsyncMock(return_value={"x.md": "ok"})
        entries = await _collect_tmp_from_sandbox(client)
        # Only the strictly-valid "round-1" is passed to read_dir.
        client.file_system.read_dir.assert_awaited_once_with("/tmp/round-1")
        assert entries == [("tmp/round-1/x.md", "ok")]

    @pytest.mark.asyncio
    async def test_multiple_rounds_are_sorted(self) -> None:
        client = MagicMock()
        client.file_system.ls = AsyncMock(return_value=["round-2", "round-1"])
        client.file_system.read_dir = AsyncMock(side_effect=[
            {"a.md": "one"},   # called for round-1
            {"b.md": "two"},   # called for round-2
        ])
        entries = await _collect_tmp_from_sandbox(client)
        assert entries == [
            ("tmp/round-1/a.md", "one"),
            ("tmp/round-2/b.md", "two"),
        ]

    @pytest.mark.asyncio
    async def test_empty_round_dir_is_skipped(self) -> None:
        client = MagicMock()
        client.file_system.ls = AsyncMock(return_value=["round-1", "round-2"])
        client.file_system.read_dir = AsyncMock(side_effect=[None, {"x.md": "data"}])
        entries = await _collect_tmp_from_sandbox(client)
        assert entries == [("tmp/round-2/x.md", "data")]


class TestCollectTmpFromArchive:
    """Reads archived round files from the agent's host volume."""

    def test_missing_archive_returns_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("endpoints.diff.ROUND_ARCHIVE_AGENT_DIR", str(tmp_path))
        assert _collect_tmp_from_archive("nonexistent-run") == []

    def test_reads_all_rounds_sorted(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("endpoints.diff.ROUND_ARCHIVE_AGENT_DIR", str(tmp_path))
        run_dir = tmp_path / "run-1"
        (run_dir / "round-2").mkdir(parents=True)
        (run_dir / "round-1").mkdir()
        (run_dir / "round-1" / "a.md").write_text("one")
        (run_dir / "round-2" / "b.md").write_text("two")
        entries = _collect_tmp_from_archive("run-1")
        assert entries == [
            ("tmp/round-1/a.md", "one"),
            ("tmp/round-2/b.md", "two"),
        ]

    def test_skips_non_file_entries(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("endpoints.diff.ROUND_ARCHIVE_AGENT_DIR", str(tmp_path))
        run_dir = tmp_path / "run-1" / "round-1"
        run_dir.mkdir(parents=True)
        (run_dir / "keep.md").write_text("yes")
        (run_dir / "subdir").mkdir()  # nested dir — should be ignored
        entries = _collect_tmp_from_archive("run-1")
        assert entries == [("tmp/round-1/keep.md", "yes")]
