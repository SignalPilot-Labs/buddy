"""Regression tests — _collect_tmp_from_archive includes root-level tmp files.

Before the fix, _collect_tmp_from_archive only iterated subdirectories
(round-N dirs) and missed run_state.md and rounds.json at the archive root.
Completed runs showed "File not found in diff" when clicking these files.
"""

from pathlib import Path

import pytest

from endpoints.diff import _collect_tmp_from_archive


class TestCollectTmpFromArchiveRunState:
    """run_state.md is included from the archive root alongside round dirs."""

    def test_includes_run_state(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        run_id = "test-run-1"
        archive = tmp_path / run_id
        round_dir = archive / "round-1"
        round_dir.mkdir(parents=True)
        (round_dir / "report.md").write_text("done", encoding="utf-8")
        (archive / "run_state.md").write_text("## Goal\n\nShip it.", encoding="utf-8")

        monkeypatch.setattr("endpoints.diff.ROUND_ARCHIVE_AGENT_DIR", str(tmp_path))
        entries = _collect_tmp_from_archive(run_id)
        paths = [e[0] for e in entries]
        assert "tmp/run_state.md" in paths
        state = next(e for e in entries if e[0] == "tmp/run_state.md")
        assert state[1] == "## Goal\n\nShip it."

    def test_excludes_run_state_when_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        run_id = "test-run-2"
        archive = tmp_path / run_id
        round_dir = archive / "round-1"
        round_dir.mkdir(parents=True)
        (round_dir / "report.md").write_text("hi", encoding="utf-8")

        monkeypatch.setattr("endpoints.diff.ROUND_ARCHIVE_AGENT_DIR", str(tmp_path))
        entries = _collect_tmp_from_archive(run_id)
        paths = [e[0] for e in entries]
        assert "tmp/run_state.md" not in paths


class TestCollectTmpFromArchiveRoundsJson:
    """rounds.json is included from the archive root for PR description rebuilding."""

    def test_includes_rounds_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        run_id = "test-run-3"
        archive = tmp_path / run_id
        round_dir = archive / "round-1"
        round_dir.mkdir(parents=True)
        (round_dir / "report.md").write_text("done", encoding="utf-8")
        (archive / "rounds.json").write_text('{"rounds":[]}', encoding="utf-8")

        monkeypatch.setattr("endpoints.diff.ROUND_ARCHIVE_AGENT_DIR", str(tmp_path))
        entries = _collect_tmp_from_archive(run_id)
        paths = [e[0] for e in entries]
        assert "tmp/rounds.json" in paths

    def test_excludes_rounds_json_when_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        run_id = "test-run-4"
        archive = tmp_path / run_id
        round_dir = archive / "round-1"
        round_dir.mkdir(parents=True)
        (round_dir / "report.md").write_text("hi", encoding="utf-8")

        monkeypatch.setattr("endpoints.diff.ROUND_ARCHIVE_AGENT_DIR", str(tmp_path))
        entries = _collect_tmp_from_archive(run_id)
        paths = [e[0] for e in entries]
        assert "tmp/rounds.json" not in paths

    def test_both_root_files_included(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        run_id = "test-run-5"
        archive = tmp_path / run_id
        round_dir = archive / "round-1"
        round_dir.mkdir(parents=True)
        (round_dir / "a.md").write_text("first", encoding="utf-8")
        (archive / "run_state.md").write_text("state", encoding="utf-8")
        (archive / "rounds.json").write_text('{"rounds":[]}', encoding="utf-8")

        monkeypatch.setattr("endpoints.diff.ROUND_ARCHIVE_AGENT_DIR", str(tmp_path))
        entries = _collect_tmp_from_archive(run_id)
        paths = [e[0] for e in entries]
        assert "tmp/run_state.md" in paths
        assert "tmp/rounds.json" in paths
        # Both come after round files
        round_paths = [p for p in paths if p.startswith("tmp/round-")]
        root_paths = [p for p in paths if not p.startswith("tmp/round-")]
        assert paths.index(round_paths[-1]) < paths.index(root_paths[0])
