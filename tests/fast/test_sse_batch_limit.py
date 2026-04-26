"""Regression test — SSE queries must have a LIMIT to prevent unbounded memory use.

Bug: _fetch_new_tool_calls and _fetch_new_audit_events had no LIMIT clause. On
runs with thousands of events a single SSE poll could load the entire table into
memory, causing OOM. The fix adds .limit(SSE_BATCH_LIMIT) to both queries.
"""

import sys
import inspect
import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.constants import SSE_BATCH_LIMIT


@pytest.fixture(autouse=True)
def _patch_auth():
    """Stub out backend.auth so importing endpoints doesn't need /data/api.key."""
    fake_auth = MagicMock()
    fake_auth.verify_api_key = AsyncMock()
    sys.modules.setdefault("backend.auth", fake_auth)
    yield


class TestSseBatchLimit:
    """SSE_BATCH_LIMIT constant exists and both SSE fetch functions respect it."""

    def test_sse_batch_limit_constant_value(self) -> None:
        """SSE_BATCH_LIMIT must be 500 — change here if the design changes."""
        assert SSE_BATCH_LIMIT == 500

    def test_fetch_new_tool_calls_source_contains_limit(self) -> None:
        """_fetch_new_tool_calls source must reference SSE_BATCH_LIMIT.

        We inspect the source text of the function so this test is immune to
        module-loading order and DB model mocking in other tests.
        """
        from backend.endpoints.streaming import _fetch_new_tool_calls

        source = inspect.getsource(_fetch_new_tool_calls)
        assert "SSE_BATCH_LIMIT" in source, (
            "_fetch_new_tool_calls does not reference SSE_BATCH_LIMIT — "
            "unbounded query will load entire table into memory on large runs."
        )
        assert ".limit(" in source, (
            "_fetch_new_tool_calls does not call .limit() — "
            "the query is unbounded."
        )

    def test_fetch_new_audit_events_source_contains_limit(self) -> None:
        """_fetch_new_audit_events source must reference SSE_BATCH_LIMIT."""
        from backend.endpoints.streaming import _fetch_new_audit_events

        source = inspect.getsource(_fetch_new_audit_events)
        assert "SSE_BATCH_LIMIT" in source, (
            "_fetch_new_audit_events does not reference SSE_BATCH_LIMIT — "
            "unbounded query will load entire table into memory on large runs."
        )
        assert ".limit(" in source, (
            "_fetch_new_audit_events does not call .limit() — "
            "the query is unbounded."
        )
