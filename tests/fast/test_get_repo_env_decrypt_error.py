"""Regression test: get_repo_env must raise HTTPException on decryption failure.

Bug: When crypto.decrypt raised an exception for corrupted env vars, the endpoint
silently returned {"repo": repo, "env_vars": {}} — hiding the failure and making
it indistinguishable from "no env vars configured".

Fix: Replace the silent fallback with raise HTTPException(status_code=500).
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import InvalidToken
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
    s.encrypted = True
    return s


def _make_session_ctx(setting: MagicMock | None) -> Any:
    """Return an async context manager that yields a session whose .get() returns setting."""
    session_mock = AsyncMock()
    session_mock.get = AsyncMock(return_value=setting)

    @asynccontextmanager
    async def ctx():  # type: ignore[return]
        yield session_mock

    return ctx


class TestGetRepoEnvDecryptError:
    """get_repo_env must raise HTTPException(500) when decryption fails."""

    @pytest.mark.asyncio
    async def test_decrypt_failure_raises_http_500(self) -> None:
        """Corrupted env var ciphertext must raise HTTPException(500), not return {}."""
        corrupt_setting = _make_setting("env_vars:org/repo", "CORRUPT_CIPHERTEXT")

        def fake_decrypt_fail(ciphertext: str, key_path: str) -> str:
            raise InvalidToken()

        with (
            patch.object(settings_mod, "session", _make_session_ctx(corrupt_setting)),
            patch.object(settings_mod.crypto, "decrypt", side_effect=fake_decrypt_fail),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await settings_mod.get_repo_env("org/repo")

        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Failed to decrypt env vars"

    @pytest.mark.asyncio
    async def test_missing_setting_returns_empty_env_vars(self) -> None:
        """Absent env vars (not in DB) must return empty dict, not raise."""
        with patch.object(settings_mod, "session", _make_session_ctx(None)):
            result = await settings_mod.get_repo_env("org/repo")

        assert result == {"repo": "org/repo", "env_vars": {}}

    @pytest.mark.asyncio
    async def test_corrupt_json_raises_http_500(self) -> None:
        """Env vars that decrypt OK but contain invalid JSON must raise HTTPException(500)."""
        setting = _make_setting("env_vars:org/repo", "VALID_CIPHERTEXT")

        def fake_decrypt_bad_json(ciphertext: str, key_path: str) -> str:
            return "NOT_VALID_JSON{{"

        with (
            patch.object(settings_mod, "session", _make_session_ctx(setting)),
            patch.object(settings_mod.crypto, "decrypt", side_effect=fake_decrypt_bad_json),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await settings_mod.get_repo_env("org/repo")

        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Failed to decrypt env vars"
