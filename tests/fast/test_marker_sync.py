"""Verify AF_* marker constants match between config and connector."""

from cli.connector.constants import (
    AF_BOUND_MARKER as CLI_BOUND,
    AF_QUEUED_MARKER as CLI_QUEUED,
    AF_READY_MARKER as CLI_READY,
)
from config.constants import (
    AF_BOUND_MARKER as CFG_BOUND,
    AF_QUEUED_MARKER as CFG_QUEUED,
    AF_READY_MARKER as CFG_READY,
)


class TestMarkerSync:
    """AF_* markers must match between config/ and cli/connector/."""

    def test_bound_marker_matches(self) -> None:
        assert CLI_BOUND == CFG_BOUND

    def test_queued_marker_matches(self) -> None:
        assert CLI_QUEUED == CFG_QUEUED

    def test_ready_marker_matches(self) -> None:
        assert CLI_READY == CFG_READY
