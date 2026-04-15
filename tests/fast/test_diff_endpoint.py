"""Tests for the diff endpoint fallback logic.

Verifies _build_stored_diff totals and _fetch_live_or_agent_diff
source selection: stored → live → agent → unavailable.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import sys


SAMPLE_DIFF_STATS = [
    {"path": "src/main.py", "added": 10, "removed": 2, "status": "modified"},
    {"path": "src/new.py", "added": 25, "removed": 0, "status": "added"},
]


def _import_runs_module():
    """Import backend.endpoints.runs with auth stubbed out."""
    auth_mock = MagicMock()
    auth_mock._api_key = "test"
    auth_mock.require_api_key = MagicMock()
    auth_mock.require_api_key_qs = MagicMock()
    sys.modules["backend.auth"] = auth_mock

    db_mock = MagicMock()
    sys.modules["backend.db"] = db_mock
    sys.modules["db.connection"] = MagicMock()
    sys.modules["db.models"] = MagicMock()

    import backend.endpoints.runs as runs_mod
    return runs_mod


runs = _import_runs_module()
_build_stored_diff = runs._build_stored_diff
_fetch_live_or_agent_diff = runs._fetch_live_or_agent_diff


class TestBuildStoredDiff:
    """_build_stored_diff must return correct totals and source."""

    def test_returns_stored_source(self) -> None:
        result = _build_stored_diff(SAMPLE_DIFF_STATS)
        assert result["source"] == "stored"

    def test_counts_files(self) -> None:
        result = _build_stored_diff(SAMPLE_DIFF_STATS)
        assert result["total_files"] == 2

    def test_sums_added_removed(self) -> None:
        result = _build_stored_diff(SAMPLE_DIFF_STATS)
        assert result["total_added"] == 35
        assert result["total_removed"] == 2

    def test_empty_list(self) -> None:
        result = _build_stored_diff([])
        assert result["total_files"] == 0
        assert result["total_added"] == 0
        assert result["total_removed"] == 0
        assert result["source"] == "stored"

    def test_passes_files_through(self) -> None:
        result = _build_stored_diff(SAMPLE_DIFF_STATS)
        assert result["files"] is SAMPLE_DIFF_STATS


class TestFetchLiveOrAgentDiff:
    """_fetch_live_or_agent_diff must try live first, then agent, then None."""

    @pytest.mark.asyncio
    async def test_active_run_returns_live(self) -> None:
        """Active run fetches /diff/live and tags source as live."""
        live_data = {"files": [{"path": "a.py"}], "total_files": 1}
        with patch(
            "backend.endpoints.runs.agent_request",
            new_callable=AsyncMock,
            return_value=live_data,
        ):
            result = await _fetch_live_or_agent_diff(True, "feat-branch", "main")
            assert result is not None
            assert result["source"] == "live"

    @pytest.mark.asyncio
    async def test_inactive_run_skips_live_uses_agent(self) -> None:
        """Inactive run skips live, fetches by branch name."""
        agent_data = {"files": [{"path": "b.py"}], "total_files": 1}
        with patch(
            "backend.endpoints.runs.agent_request",
            new_callable=AsyncMock,
            return_value=agent_data,
        ):
            result = await _fetch_live_or_agent_diff(False, "feat-branch", "main")
            assert result is not None
            assert result["source"] == "agent"

    @pytest.mark.asyncio
    async def test_active_live_fails_falls_to_agent(self) -> None:
        """If live diff returns None, try agent by branch name."""
        agent_data = {"files": [{"path": "c.py"}], "total_files": 1}

        call_count = 0

        async def mock_agent(*args: object, **kwargs: object) -> dict | None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return None  # live diff fails
            return agent_data

        with patch("backend.endpoints.runs.agent_request", side_effect=mock_agent):
            result = await _fetch_live_or_agent_diff(True, "feat-branch", "main")
            assert result is not None
            assert result["source"] == "agent"

    @pytest.mark.asyncio
    async def test_both_fail_returns_none(self) -> None:
        """Active run, both live and agent fail → None."""
        with patch(
            "backend.endpoints.runs.agent_request",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await _fetch_live_or_agent_diff(True, "feat-branch", "main")
            assert result is None

    @pytest.mark.asyncio
    async def test_inactive_agent_fails_returns_none(self) -> None:
        """Inactive run, agent unreachable → None (branch deleted or offline)."""
        with patch(
            "backend.endpoints.runs.agent_request",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await _fetch_live_or_agent_diff(False, "deleted-branch", "main")
            assert result is None
