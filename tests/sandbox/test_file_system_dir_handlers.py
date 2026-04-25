"""Tests for the sandbox read_dir / write_dir HTTP handlers.

Exercises the endpoints with an in-memory aiohttp request mock — no real
HTTP server, just the handler functions. Verifies the roundtrip and the
traversal guard that rejects ../ / nested filenames.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from handlers.file_system import handle_read_dir, handle_write_dir


def _request(payload: dict) -> MagicMock:
    """Build a mock aiohttp Request whose .json() returns the given payload."""
    req = MagicMock()
    req.json = AsyncMock(return_value=payload)
    return req


def _parse(response) -> dict:
    """Pull the JSON body out of an aiohttp Response."""
    return json.loads(response.body.decode("utf-8"))


# ── read_dir ─────────────────────────────────────────────────────────


class TestReadDir:
    """Reading a directory as a {name: content} map."""

    @pytest.mark.asyncio
    async def test_read_dir_returns_all_regular_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.md").write_text("alpha")
        (tmp_path / "b.md").write_text("beta")
        (tmp_path / "c.json").write_text("{}")

        resp = await handle_read_dir(_request({"path": str(tmp_path)}))
        body = _parse(resp)

        assert body["exists"] is True
        assert body["files"] == {"a.md": "alpha", "b.md": "beta", "c.json": "{}"}

    @pytest.mark.asyncio
    async def test_read_dir_skips_subdirectories(self, tmp_path: Path) -> None:
        (tmp_path / "file.md").write_text("flat")
        (tmp_path / "nested").mkdir()
        (tmp_path / "nested" / "ignored.md").write_text("deep")

        resp = await handle_read_dir(_request({"path": str(tmp_path)}))
        body = _parse(resp)

        assert body["files"] == {"file.md": "flat"}

    @pytest.mark.asyncio
    async def test_read_dir_missing_path_returns_exists_false(self, tmp_path: Path) -> None:
        resp = await handle_read_dir(
            _request({"path": str(tmp_path / "does-not-exist")}),
        )
        body = _parse(resp)

        assert body["exists"] is False
        assert body["files"] == {}

    @pytest.mark.asyncio
    async def test_read_dir_on_file_path_returns_exists_false(self, tmp_path: Path) -> None:
        file_path = tmp_path / "not-a-dir.md"
        file_path.write_text("x")

        resp = await handle_read_dir(_request({"path": str(file_path)}))
        body = _parse(resp)

        assert body["exists"] is False


# ── write_dir ────────────────────────────────────────────────────────


class TestWriteDir:
    """Writing a {name: content} map into a directory."""

    @pytest.mark.asyncio
    async def test_write_dir_creates_parents_and_writes_files(self, tmp_path: Path) -> None:
        target = tmp_path / "new" / "nested"  # parents don't exist yet

        resp = await handle_write_dir(_request({
            "path": str(target),
            "files": {"a.md": "alpha", "b.md": "beta"},
        }))
        body = _parse(resp)

        assert body == {"ok": True, "count": 2}
        assert (target / "a.md").read_text() == "alpha"
        assert (target / "b.md").read_text() == "beta"

    @pytest.mark.asyncio
    async def test_write_dir_rejects_forward_slash_in_filename(self, tmp_path: Path) -> None:
        resp = await handle_write_dir(_request({
            "path": str(tmp_path),
            "files": {"sub/file.md": "attempt"},
        }))

        assert resp.status == 400
        assert "invalid filename" in _parse(resp)["error"]
        # Guard fires BEFORE any write so the tmp dir stays empty.
        assert list(tmp_path.iterdir()) == []

    @pytest.mark.asyncio
    async def test_write_dir_rejects_parent_dir_name(self, tmp_path: Path) -> None:
        resp = await handle_write_dir(_request({
            "path": str(tmp_path / "inner"),
            "files": {"..": "escape"},
        }))

        assert resp.status == 400
        # No file with name '..' should have been written anywhere near tmp_path.
        assert not (tmp_path / "..").is_file()

    @pytest.mark.asyncio
    async def test_write_dir_rejects_empty_filename(self, tmp_path: Path) -> None:
        resp = await handle_write_dir(_request({
            "path": str(tmp_path),
            "files": {"": "nope"},
        }))

        assert resp.status == 400

    @pytest.mark.asyncio
    async def test_write_dir_rejects_single_dot(self, tmp_path: Path) -> None:
        resp = await handle_write_dir(_request({
            "path": str(tmp_path),
            "files": {".": "nope"},
        }))

        assert resp.status == 400

    @pytest.mark.asyncio
    async def test_write_dir_empty_map_is_noop_with_mkdir(self, tmp_path: Path) -> None:
        target = tmp_path / "fresh"

        resp = await handle_write_dir(_request({
            "path": str(target),
            "files": {},
        }))
        body = _parse(resp)

        assert body == {"ok": True, "count": 0}
        assert target.is_dir()
        assert list(target.iterdir()) == []


# ── Partial write regression ─────────────────────────────────────────


class TestWriteDirPartialWriteRegression:
    """Regression: invalid filename after valid ones must not write anything."""

    @pytest.mark.asyncio
    async def test_invalid_filename_after_valid_writes_nothing(self, tmp_path: Path) -> None:
        target = tmp_path / "output"

        resp = await handle_write_dir(_request({
            "path": str(target),
            "files": {"valid.txt": "data", "../escape.txt": "bad"},
        }))

        assert resp.status == 400
        assert "invalid filename" in _parse(resp)["error"]
        # The directory must not have been created and valid.txt must not exist.
        assert not (target / "valid.txt").exists()


# ── Roundtrip ────────────────────────────────────────────────────────


class TestRoundtrip:
    """write_dir then read_dir must return identical contents."""

    @pytest.mark.asyncio
    async def test_write_then_read_returns_same_files(self, tmp_path: Path) -> None:
        target = tmp_path / "round-1"
        written = {
            "architect.md": "spec content\nwith newlines\n",
            "orchestrator.md": "report with\ttabs and 日本語",
        }

        await handle_write_dir(_request({"path": str(target), "files": written}))
        resp = await handle_read_dir(_request({"path": str(target)}))
        body = _parse(resp)

        assert body["exists"] is True
        assert body["files"] == written
