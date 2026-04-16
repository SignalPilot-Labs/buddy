"""Tests for the _stats_response helper in the diff stats endpoint."""

import sys
from unittest.mock import MagicMock


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
