"""Tests for the diff stats endpoint and its _stats_response helper."""

import sys
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException


SAMPLE_DIFF_STATS = [
    {"path": "src/main.py", "added": 10, "removed": 2, "status": "modified"},
    {"path": "src/new.py", "added": 25, "removed": 0, "status": "added"},
]


def _import_runs_module():
    """Import backend.endpoints.runs with auth + db stubbed out."""
    auth_mock = MagicMock()
    auth_mock._api_key = "test"
    auth_mock.require_api_key = MagicMock()
    auth_mock.require_api_key_qs = MagicMock()
    sys.modules["backend.auth"] = auth_mock

    sys.modules["backend.db"] = MagicMock()
    sys.modules["db.connection"] = MagicMock()
    sys.modules["db.models"] = MagicMock()

    import backend.endpoints.runs as runs_mod
    return runs_mod


runs = _import_runs_module()
_stats_response = runs._stats_response


class TestStatsResponse:
    """_stats_response packs a list of files + source into the API shape."""

    def test_source_is_passed_through(self) -> None:
        assert _stats_response([], "stored")["source"] == "stored"
        assert _stats_response([], "live")["source"] == "live"
        assert _stats_response([], "unavailable")["source"] == "unavailable"

    def test_counts_files(self) -> None:
        result = _stats_response(SAMPLE_DIFF_STATS, "stored")
        assert result["total_files"] == 2

    def test_sums_added_removed(self) -> None:
        result = _stats_response(SAMPLE_DIFF_STATS, "stored")
        assert result["total_added"] == 35
        assert result["total_removed"] == 2

    def test_empty_list(self) -> None:
        result = _stats_response([], "unavailable")
        assert result["total_files"] == 0
        assert result["total_added"] == 0
        assert result["total_removed"] == 0

    def test_passes_files_through(self) -> None:
        result = _stats_response(SAMPLE_DIFF_STATS, "stored")
        assert result["files"] is SAMPLE_DIFF_STATS


@pytest.fixture
def run_record() -> MagicMock:
    """Minimal Run model stand-in — only the fields get_run_diff reads."""
    r = MagicMock()
    r.diff_stats = None
    return r


@pytest.fixture
def db_session(monkeypatch: pytest.MonkeyPatch, run_record: MagicMock):
    """Patch backend.utils.session so `await s.get(Run, ...)` returns run_record."""
    s = MagicMock()
    s.get = AsyncMock(return_value=run_record)

    class _CtxMgr:
        async def __aenter__(self): return s
        async def __aexit__(self, *a): return None

    monkeypatch.setattr(runs, "session", lambda: _CtxMgr())
    return s


class TestGetRunDiffLivePath:
    """get_run_diff must translate agent /diff/repo/stats outcomes cleanly."""

    @pytest.mark.asyncio
    async def test_stored_stats_short_circuit(
        self, monkeypatch: pytest.MonkeyPatch, db_session, run_record: MagicMock,
    ) -> None:
        # If DB has stored stats, we never call the agent.
        run_record.diff_stats = SAMPLE_DIFF_STATS
        agent = AsyncMock()
        monkeypatch.setattr(runs, "agent_request", agent)
        result = await runs.get_run_diff("run-1")
        agent.assert_not_called()
        assert result["source"] == "stored"
        assert result["total_files"] == 2

    @pytest.mark.asyncio
    async def test_live_path_returns_source_live(
        self, monkeypatch: pytest.MonkeyPatch, db_session, run_record: MagicMock,
    ) -> None:
        run_record.diff_stats = None
        agent = AsyncMock(return_value={"files": SAMPLE_DIFF_STATS})
        monkeypatch.setattr(runs, "agent_request", agent)
        result = await runs.get_run_diff("run-1")
        assert result["source"] == "live"
        assert result["total_files"] == 2
        assert result["total_added"] == 35
        assert result["total_removed"] == 2

    @pytest.mark.asyncio
    async def test_agent_409_maps_to_unavailable(
        self, monkeypatch: pytest.MonkeyPatch, db_session, run_record: MagicMock,
    ) -> None:
        # 409 == no live sandbox. Dashboard must NOT surface this as an error.
        run_record.diff_stats = None
        agent = AsyncMock(side_effect=HTTPException(status_code=409, detail="No active sandbox for run"))
        monkeypatch.setattr(runs, "agent_request", agent)
        result = await runs.get_run_diff("run-1")
        assert result["source"] == "unavailable"
        assert result["total_files"] == 0

    @pytest.mark.asyncio
    async def test_agent_502_propagates(
        self, monkeypatch: pytest.MonkeyPatch, db_session, run_record: MagicMock,
    ) -> None:
        # Agent-down must NOT be collapsed into 'unavailable' — distinct signal.
        run_record.diff_stats = None
        agent = AsyncMock(side_effect=HTTPException(status_code=502, detail="Agent service unavailable"))
        monkeypatch.setattr(runs, "agent_request", agent)
        with pytest.raises(HTTPException) as exc_info:
            await runs.get_run_diff("run-1")
        assert exc_info.value.status_code == 502
