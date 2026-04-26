"""Regression test: get_settings() log.error must include exc_info=True.

Bug: When _decrypt_setting() raised an exception, log.error() was called without
exc_info=True, discarding the stack trace and making decryption errors hard to diagnose.

Fix: Add exc_info=True to the log.error() call in get_settings().
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import InvalidToken

# Stub out modules that require live services before importing settings endpoint.
if "db.connection" not in sys.modules:
    sys.modules["db.connection"] = MagicMock()
if "db.models" not in sys.modules:
    sys.modules["db.models"] = MagicMock()

_auth_mock = MagicMock()
_auth_mock.verify_api_key = MagicMock(return_value=None)
sys.modules["backend.auth"] = _auth_mock

import backend.endpoints.settings as settings_mod  # noqa: E402


def _make_encrypted_setting(key: str, value: str) -> MagicMock:
    s = MagicMock()
    s.key = key
    s.value = value
    s.encrypted = True
    return s


def _make_session_ctx(settings_list: list[MagicMock]) -> Any:
    """Return an async context manager yielding a session with scalars returning given settings."""
    session_mock = AsyncMock()
    scalars_mock = MagicMock()
    scalars_mock.all = MagicMock(return_value=settings_list)
    execute_result = MagicMock()
    execute_result.scalars = MagicMock(return_value=scalars_mock)
    session_mock.execute = AsyncMock(return_value=execute_result)

    @asynccontextmanager
    async def ctx():  # type: ignore[return]
        yield session_mock

    return ctx


class TestGetSettingsDecryptErrorExcInfo:
    """get_settings() must log with exc_info=True when _decrypt_setting() raises."""

    @pytest.mark.asyncio
    async def test_log_error_has_exc_info_on_decrypt_failure(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Stack trace must be attached when setting decryption raises an exception."""
        corrupt_setting = _make_encrypted_setting("git_token", "CORRUPT_CIPHERTEXT")

        def fake_decrypt_fail(ciphertext: str, key_path: str) -> str:
            raise InvalidToken()

        with (
            patch.object(settings_mod, "session", _make_session_ctx([corrupt_setting])),
            patch.object(settings_mod.crypto, "decrypt", side_effect=fake_decrypt_fail),
            caplog.at_level(logging.ERROR, logger="dashboard.settings"),
        ):
            result = await settings_mod.get_settings()

        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert error_records, "Expected at least one ERROR log record"
        record = error_records[0]
        assert record.exc_info is not None, (
            "log.error must be called with exc_info=True so the stack trace is preserved"
        )
        # The key is still present in the result, masked
        assert "git_token" in result
