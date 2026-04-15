"""Tests for _build_stored_diff helper in the diff stats endpoint."""

import sys
from unittest.mock import MagicMock


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
