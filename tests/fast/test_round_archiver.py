"""Tests for RoundArchiver — the agent-side round report archive.

Exercises the sandbox /tmp ↔ persistent volume roundtrip with an in-memory
fake SandboxClient so the tests are fast and have no Docker dependency.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from memory.archiver import RoundArchiver


# ── Fake sandbox client ─────────────────────────────────────────────


class _FakeFileSystem:
    """In-memory FileSystem handler that mirrors the real client API."""

    def __init__(self) -> None:
        # path → content for single files
        self.files: dict[str, str] = {}
        # dir path → {name: content} for directories
        self.dirs: dict[str, dict[str, str]] = {}

    async def read(self, path: str) -> str | None:
        return self.files.get(path)

    async def write(self, path: str, content: str, append: bool) -> None:
        self.files[path] = content

    async def read_dir(self, path: str) -> dict[str, str] | None:
        return self.dirs.get(path)

    async def write_dir(self, path: str, files: dict[str, str]) -> None:
        self.dirs[path] = dict(files)


class _FakeSandbox:
    """Minimal stand-in for SandboxClient — only file_system is touched."""

    def __init__(self) -> None:
        self.file_system = _FakeFileSystem()


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def fake_sandbox() -> _FakeSandbox:
    return _FakeSandbox()


@pytest.fixture
def archive_root(tmp_path: Path):
    """Point ROUND_ARCHIVE_AGENT_DIR at a tmp_path for the test."""
    with patch("memory.archiver.ROUND_ARCHIVE_AGENT_DIR", str(tmp_path)):
        yield tmp_path


# ── archive_round ────────────────────────────────────────────────────


class TestArchiveRound:
    """Pulling /tmp/round-N from sandbox into the persistent volume."""

    @pytest.mark.asyncio
    async def test_archive_round_writes_every_file_to_host(
        self, fake_sandbox: _FakeSandbox, archive_root: Path,
    ) -> None:
        fake_sandbox.file_system.dirs["/tmp/round-1"] = {
            "architect.md": "spec content",
            "orchestrator.md": "round 1 report",
            "code-reviewer.md": "verdict: APPROVE",
        }
        fake_sandbox.file_system.files["/tmp/rounds.json"] = '{"rounds": []}'

        archiver = RoundArchiver(fake_sandbox, run_id="run-abc")  # type: ignore[arg-type]
        await archiver.archive_round(1)

        host_round = archive_root / "run-abc" / "round-1"
        assert (host_round / "architect.md").read_text() == "spec content"
        assert (host_round / "orchestrator.md").read_text() == "round 1 report"
        assert (host_round / "code-reviewer.md").read_text() == "verdict: APPROVE"

    @pytest.mark.asyncio
    async def test_archive_round_captures_rounds_json_alongside(
        self, fake_sandbox: _FakeSandbox, archive_root: Path,
    ) -> None:
        fake_sandbox.file_system.dirs["/tmp/round-1"] = {"x.md": "x"}
        fake_sandbox.file_system.files["/tmp/rounds.json"] = '{"pr_title": "feat"}'

        archiver = RoundArchiver(fake_sandbox, run_id="run-abc")  # type: ignore[arg-type]
        await archiver.archive_round(1)

        rounds_json = archive_root / "run-abc" / "rounds.json"
        assert rounds_json.read_text() == '{"pr_title": "feat"}'

    @pytest.mark.asyncio
    async def test_archive_round_missing_sandbox_dir_is_noop(
        self, fake_sandbox: _FakeSandbox, archive_root: Path,
    ) -> None:
        # Sandbox has no /tmp/round-5 — archiver should log and return.
        archiver = RoundArchiver(fake_sandbox, run_id="run-abc")  # type: ignore[arg-type]
        await archiver.archive_round(5)

        assert not (archive_root / "run-abc" / "round-5").exists()

    @pytest.mark.asyncio
    async def test_archive_round_runs_isolated_from_each_other(
        self, fake_sandbox: _FakeSandbox, archive_root: Path,
    ) -> None:
        """Two archivers with different run_ids must not stomp each other."""
        fake_sandbox.file_system.dirs["/tmp/round-1"] = {"a.md": "run-a round 1"}

        archiver_a = RoundArchiver(fake_sandbox, run_id="run-a")  # type: ignore[arg-type]
        await archiver_a.archive_round(1)

        fake_sandbox.file_system.dirs["/tmp/round-1"] = {"a.md": "run-b round 1"}
        archiver_b = RoundArchiver(fake_sandbox, run_id="run-b")  # type: ignore[arg-type]
        await archiver_b.archive_round(1)

        assert (archive_root / "run-a" / "round-1" / "a.md").read_text() == "run-a round 1"
        assert (archive_root / "run-b" / "round-1" / "a.md").read_text() == "run-b round 1"


# ── restore_all ──────────────────────────────────────────────────────


class TestRestoreAll:
    """Pushing persisted rounds back into a freshly started sandbox."""

    @pytest.mark.asyncio
    async def test_restore_all_empty_returns_zero(
        self, fake_sandbox: _FakeSandbox, archive_root: Path,
    ) -> None:
        archiver = RoundArchiver(fake_sandbox, run_id="run-abc")  # type: ignore[arg-type]
        result = await archiver.restore_all()

        assert result == 0
        assert fake_sandbox.file_system.dirs == {}
        assert fake_sandbox.file_system.files == {}

    @pytest.mark.asyncio
    async def test_restore_all_pushes_every_round_back(
        self, fake_sandbox: _FakeSandbox, archive_root: Path,
    ) -> None:
        run_root = archive_root / "run-abc"
        (run_root / "round-1").mkdir(parents=True)
        (run_root / "round-1" / "architect.md").write_text("R1 spec")
        (run_root / "round-2").mkdir(parents=True)
        (run_root / "round-2" / "architect.md").write_text("R2 spec")
        (run_root / "round-2" / "code-reviewer.md").write_text("R2 review")
        (run_root / "round-3").mkdir(parents=True)
        (run_root / "round-3" / "orchestrator.md").write_text("R3 report")
        (run_root / "rounds.json").write_text('{"rounds": [1,2,3]}')

        archiver = RoundArchiver(fake_sandbox, run_id="run-abc")  # type: ignore[arg-type]
        highest = await archiver.restore_all()

        assert highest == 3
        assert fake_sandbox.file_system.dirs["/tmp/round-1"] == {"architect.md": "R1 spec"}
        assert fake_sandbox.file_system.dirs["/tmp/round-2"] == {
            "architect.md": "R2 spec",
            "code-reviewer.md": "R2 review",
        }
        assert fake_sandbox.file_system.dirs["/tmp/round-3"] == {"orchestrator.md": "R3 report"}
        assert fake_sandbox.file_system.files["/tmp/rounds.json"] == '{"rounds": [1,2,3]}'

    @pytest.mark.asyncio
    async def test_restore_all_ignores_non_round_entries(
        self, fake_sandbox: _FakeSandbox, archive_root: Path,
    ) -> None:
        """Stray files/dirs under run_id should not break restore."""
        run_root = archive_root / "run-abc"
        (run_root / "round-1").mkdir(parents=True)
        (run_root / "round-1" / "x.md").write_text("one")
        (run_root / "junk").mkdir()  # not a round dir
        (run_root / "stray.txt").write_text("nope")  # not rounds.json
        (run_root / "rounds.json").write_text("{}")

        archiver = RoundArchiver(fake_sandbox, run_id="run-abc")  # type: ignore[arg-type]
        highest = await archiver.restore_all()

        assert highest == 1
        assert "/tmp/round-1" in fake_sandbox.file_system.dirs
        # junk and stray.txt are silently skipped
        assert len(fake_sandbox.file_system.dirs) == 1

    @pytest.mark.asyncio
    async def test_restore_all_without_rounds_json_still_works(
        self, fake_sandbox: _FakeSandbox, archive_root: Path,
    ) -> None:
        run_root = archive_root / "run-abc"
        (run_root / "round-1").mkdir(parents=True)
        (run_root / "round-1" / "x.md").write_text("one")

        archiver = RoundArchiver(fake_sandbox, run_id="run-abc")  # type: ignore[arg-type]
        highest = await archiver.restore_all()

        assert highest == 1
        assert "/tmp/rounds.json" not in fake_sandbox.file_system.files


# ── Full roundtrip ──────────────────────────────────────────────────


class TestRoundtrip:
    """archive → destroy sandbox → fresh sandbox → restore → identical state."""

    @pytest.mark.asyncio
    async def test_archive_then_restore_produces_identical_sandbox_state(
        self, archive_root: Path,
    ) -> None:
        first_sandbox = _FakeSandbox()
        first_sandbox.file_system.dirs["/tmp/round-1"] = {
            "architect.md": "spec",
            "orchestrator.md": "report",
        }
        first_sandbox.file_system.dirs["/tmp/round-2"] = {"orchestrator.md": "R2"}
        first_sandbox.file_system.files["/tmp/rounds.json"] = '{"rounds": [1,2]}'

        archiver = RoundArchiver(first_sandbox, run_id="run-xyz")  # type: ignore[arg-type]
        await archiver.archive_round(1)
        await archiver.archive_round(2)

        # Simulate: sandbox dies, new sandbox comes up, same run_id.
        second_sandbox = _FakeSandbox()
        archiver2 = RoundArchiver(second_sandbox, run_id="run-xyz")  # type: ignore[arg-type]
        highest = await archiver2.restore_all()

        assert highest == 2
        assert second_sandbox.file_system.dirs["/tmp/round-1"] == first_sandbox.file_system.dirs["/tmp/round-1"]
        assert second_sandbox.file_system.dirs["/tmp/round-2"] == first_sandbox.file_system.dirs["/tmp/round-2"]
        assert second_sandbox.file_system.files["/tmp/rounds.json"] == first_sandbox.file_system.files["/tmp/rounds.json"]
