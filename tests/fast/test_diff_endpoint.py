"""Tests for build_stats_response in the diff stats endpoint."""

from backend.diff_parser import build_stats_response


SAMPLE_DIFF_STATS = [
    {"path": "src/main.py", "added": 10, "removed": 2, "status": "modified"},
    {"path": "src/new.py", "added": 25, "removed": 0, "status": "added"},
]


class TestBuildStatsResponse:
    """build_stats_response must return correct totals and source."""

    def test_returns_source(self) -> None:
        result = build_stats_response(SAMPLE_DIFF_STATS, "stored")
        assert result["source"] == "stored"

    def test_source_is_passed_through(self) -> None:
        assert build_stats_response([], "live")["source"] == "live"
        assert build_stats_response([], "unavailable")["source"] == "unavailable"

    def test_counts_files(self) -> None:
        result = build_stats_response(SAMPLE_DIFF_STATS, "stored")
        assert result["total_files"] == 2

    def test_sums_added_removed(self) -> None:
        result = build_stats_response(SAMPLE_DIFF_STATS, "stored")
        assert result["total_added"] == 35
        assert result["total_removed"] == 2

    def test_empty_list(self) -> None:
        result = build_stats_response([], "unavailable")
        assert result["total_files"] == 0
        assert result["total_added"] == 0
        assert result["total_removed"] == 0

    def test_passes_files_through(self) -> None:
        result = build_stats_response(SAMPLE_DIFF_STATS, "stored")
        assert result["files"] is SAMPLE_DIFF_STATS
