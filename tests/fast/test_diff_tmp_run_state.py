"""Regression tests — _collect_tmp_from_sandbox includes run_state.md.

Before the fix, _collect_tmp_from_sandbox only collected /tmp/round-* dirs
and returned early when none existed. /tmp/run_state.md was never fetched,
so clicking it in the dashboard Changes tab returned "File not found".
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from endpoints.diff import _collect_tmp_from_sandbox


class TestCollectTmpFromSandboxRunState:
    """run_state.md is included alongside round files."""

    @pytest.mark.asyncio
    async def test_includes_run_state_md_when_present(self) -> None:
        client = MagicMock()
        client.file_system.ls = AsyncMock(return_value=["round-1"])
        client.file_system.read_dir = AsyncMock(return_value={"architect.md": "plan"})
        client.file_system.read = AsyncMock(return_value="## Goal\n\nFix bugs.")
        entries = await _collect_tmp_from_sandbox(client)
        paths = [e[0] for e in entries]
        assert "tmp/run_state.md" in paths
        state_entry = next(e for e in entries if e[0] == "tmp/run_state.md")
        assert state_entry[1] == "## Goal\n\nFix bugs."

    @pytest.mark.asyncio
    async def test_run_state_appended_after_round_files(self) -> None:
        client = MagicMock()
        client.file_system.ls = AsyncMock(return_value=["round-1"])
        client.file_system.read_dir = AsyncMock(return_value={"report.md": "hi"})
        client.file_system.read = AsyncMock(return_value="state content")
        entries = await _collect_tmp_from_sandbox(client)
        assert entries[-1] == ("tmp/run_state.md", "state content")

    @pytest.mark.asyncio
    async def test_excludes_run_state_when_not_present(self) -> None:
        client = MagicMock()
        client.file_system.ls = AsyncMock(return_value=["round-1"])
        client.file_system.read_dir = AsyncMock(return_value={"report.md": "hi"})
        client.file_system.read = AsyncMock(return_value=None)
        entries = await _collect_tmp_from_sandbox(client)
        paths = [e[0] for e in entries]
        assert "tmp/run_state.md" not in paths

    @pytest.mark.asyncio
    async def test_includes_run_state_even_with_no_round_dirs(self) -> None:
        """run_state.md is fetched even when no round-N dirs exist."""
        client = MagicMock()
        client.file_system.ls = AsyncMock(return_value=["other", "cache"])
        client.file_system.read_dir = AsyncMock(return_value=None)
        client.file_system.read = AsyncMock(return_value="## Goal\n\nStarting.")
        entries = await _collect_tmp_from_sandbox(client)
        assert entries == [("tmp/run_state.md", "## Goal\n\nStarting.")]
        client.file_system.read_dir.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_rounds_and_no_run_state(self) -> None:
        client = MagicMock()
        client.file_system.ls = AsyncMock(return_value=[])
        client.file_system.read = AsyncMock(return_value=None)
        entries = await _collect_tmp_from_sandbox(client)
        assert entries == []
