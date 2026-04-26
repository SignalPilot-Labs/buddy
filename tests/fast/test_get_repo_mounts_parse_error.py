"""Regression test: get_repo_mounts() must raise HTTP 500 on JSON parse failure.

Bug 1: When json.loads() failed for host_mounts, the endpoint silently returned
{"repo": repo, "mounts": []} instead of surfacing the error — hiding data corruption.

Bug 2: log.error() was called without exc_info=True, discarding the stack trace.

Fix: Add exc_info=True to the log.error() call and replace the silent fallback
with raise HTTPException(status_code=500, detail="Failed to parse host mounts").
"""

from __future__ import annotations

import json
import logging
import sys
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

# Stub out modules that require live services before importing settings endpoint.
if "db.connection" not in sys.modules:
    sys.modules["db.connection"] = MagicMock()
if "db.models" not in sys.modules:
    sys.modules["db.models"] = MagicMock()

_auth_mock = MagicMock()
_auth_mock.verify_api_key = MagicMock(return_value=None)
sys.modules["backend.auth"] = _auth_mock

import backend.endpoints.settings as settings_mod  # noqa: E402


def _make_setting(key: str, value: str) -> MagicMock:
    s = MagicMock()
    s.key = key
    s.value = value
    s.encrypted = False
    return s


def _make_session_ctx(setting: MagicMock | None) -> Any:
    """Return an async context manager yielding a session whose .get() returns setting."""
    session_mock = AsyncMock()
    session_mock.get = AsyncMock(return_value=setting)

    @asynccontextmanager
    async def ctx():  # type: ignore[return]
        yield session_mock

    return ctx


class TestGetRepoMountsParseError:
    """get_repo_mounts() must raise HTTPException(500) and log with exc_info when parse fails."""

    @pytest.mark.asyncio
    async def test_corrupt_json_raises_http_500(self) -> None:
        """Corrupted host_mounts JSON must raise HTTPException(500), not return empty list."""
        corrupt_setting = _make_setting("host_mounts:org/repo", "NOT_VALID_JSON{{")

        with (
            patch.object(settings_mod, "session", _make_session_ctx(corrupt_setting)),
            patch.object(settings_mod.json, "loads", side_effect=json.JSONDecodeError("bad", "", 0)),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await settings_mod.get_repo_mounts("org/repo")

        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Failed to parse host mounts"

    @pytest.mark.asyncio
    async def test_log_error_has_exc_info_on_parse_failure(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Stack trace must be attached when JSON parsing fails."""
        corrupt_setting = _make_setting("host_mounts:org/repo", "NOT_VALID_JSON{{")

        with (
            patch.object(settings_mod, "session", _make_session_ctx(corrupt_setting)),
            patch.object(settings_mod.json, "loads", side_effect=json.JSONDecodeError("bad", "", 0)),
            caplog.at_level(logging.ERROR, logger="dashboard.settings"),
        ):
            with pytest.raises(HTTPException):
                await settings_mod.get_repo_mounts("org/repo")

        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert error_records, "Expected at least one ERROR log record"
        record = error_records[0]
        assert record.exc_info is not None, (
            "log.error must be called with exc_info=True so the stack trace is preserved"
        )

    @pytest.mark.asyncio
    async def test_missing_setting_returns_empty_mounts(self) -> None:
        """Absent host_mounts (not in DB) must return empty list, not raise."""
        with patch.object(settings_mod, "session", _make_session_ctx(None)):
            result = await settings_mod.get_repo_mounts("org/repo")

        assert result == {"repo": "org/repo", "mounts": []}
