"""Regression tests for credential decryption failure handling.

Bug: read_credentials() and read_token_pool() silently swallowed decryption errors
and returned partial/empty results, making it impossible for callers to distinguish
'credential not configured' from 'credential set but broken'.

Fix: Let InvalidToken propagate wrapped in CredentialDecryptionError.
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import InvalidToken

# Stub out modules that require live services before importing backend.utils.
if "db.connection" not in sys.modules:
    sys.modules["db.connection"] = MagicMock()


import backend.utils as utils_mod  # noqa: E402
from backend.utils import CredentialDecryptionError  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_setting(key: str, value: str, encrypted: bool) -> MagicMock:
    s = MagicMock()
    s.key = key
    s.value = value
    s.encrypted = encrypted
    return s


def _make_session_ctx(get_map: dict[str, MagicMock | None]) -> Any:
    """Return an async context manager that yields a session whose .get() uses get_map."""
    session_mock = AsyncMock()
    session_mock.get = AsyncMock(side_effect=lambda model, key: get_map.get(key))
    session_mock.commit = AsyncMock()

    @asynccontextmanager
    async def ctx():
        yield session_mock

    return ctx


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCredentialDecryptError:
    """read_credentials() and read_token_pool() must raise on decryption failure."""

    @pytest.mark.asyncio
    async def test_read_credentials_git_token_decrypt_failure_raises(self) -> None:
        """Corrupt git_token ciphertext must raise CredentialDecryptionError, not return {}."""
        corrupt_setting = _make_setting("git_token", "CORRUPT_CIPHERTEXT", encrypted=True)
        get_map: dict[str, MagicMock | None] = {
            "git_token": corrupt_setting,
            "github_repo": None,
            "claude_tokens": None,
        }

        def fake_decrypt_fail(ciphertext: str, key_path: str) -> str:
            raise InvalidToken()

        with (
            patch.object(utils_mod, "session", _make_session_ctx(get_map)),
            patch.object(utils_mod.crypto, "decrypt", side_effect=fake_decrypt_fail),
        ):
            with pytest.raises(CredentialDecryptionError, match="git_token"):
                await utils_mod.read_credentials(None)

    @pytest.mark.asyncio
    async def test_read_credentials_github_repo_decrypt_failure_raises(self) -> None:
        """Corrupt github_repo ciphertext must raise CredentialDecryptionError."""
        corrupt_setting = _make_setting("github_repo", "CORRUPT_CIPHERTEXT", encrypted=True)
        get_map: dict[str, MagicMock | None] = {
            "git_token": None,
            "github_repo": corrupt_setting,
            "claude_tokens": None,
        }

        def fake_decrypt_fail(ciphertext: str, key_path: str) -> str:
            raise InvalidToken()

        with (
            patch.object(utils_mod, "session", _make_session_ctx(get_map)),
            patch.object(utils_mod.crypto, "decrypt", side_effect=fake_decrypt_fail),
        ):
            with pytest.raises(CredentialDecryptionError, match="github_repo"):
                await utils_mod.read_credentials(None)

    @pytest.mark.asyncio
    async def test_read_credentials_env_vars_decrypt_failure_raises(self) -> None:
        """Corrupt env_vars ciphertext must raise CredentialDecryptionError."""
        env_setting = _make_setting("env_vars:org/repo", "CORRUPT_ENV", encrypted=True)
        get_map: dict[str, MagicMock | None] = {
            "git_token": None,
            "github_repo": None,
            "claude_tokens": None,
            "env_vars:org/repo": env_setting,
            "host_mounts:org/repo": None,
        }

        def fake_decrypt_fail(ciphertext: str, key_path: str) -> str:
            raise InvalidToken()

        with (
            patch.object(utils_mod, "session", _make_session_ctx(get_map)),
            patch.object(utils_mod.crypto, "decrypt", side_effect=fake_decrypt_fail),
        ):
            with pytest.raises(CredentialDecryptionError, match="env_vars:org/repo"):
                await utils_mod.read_credentials("org/repo")

    @pytest.mark.asyncio
    async def test_read_credentials_host_mounts_corrupt_json_raises(self) -> None:
        """Corrupt host_mounts JSON must raise CredentialDecryptionError."""
        mounts_setting = _make_setting("host_mounts:org/repo", "NOT_VALID_JSON{{", encrypted=False)
        get_map: dict[str, MagicMock | None] = {
            "git_token": None,
            "github_repo": None,
            "claude_tokens": None,
            "env_vars:org/repo": None,
            "host_mounts:org/repo": mounts_setting,
        }

        with (
            patch.object(utils_mod, "session", _make_session_ctx(get_map)),
        ):
            with pytest.raises(CredentialDecryptionError, match="host_mounts:org/repo"):
                await utils_mod.read_credentials("org/repo")

    @pytest.mark.asyncio
    async def test_read_credentials_env_vars_corrupt_json_raises(self) -> None:
        """Corrupt env_vars JSON (decrypts OK but not valid JSON) must raise CredentialDecryptionError."""
        env_setting = _make_setting("env_vars:org/repo", "CORRUPT_ENV", encrypted=True)
        get_map: dict[str, MagicMock | None] = {
            "git_token": None,
            "github_repo": None,
            "claude_tokens": None,
            "env_vars:org/repo": env_setting,
            "host_mounts:org/repo": None,
        }

        def fake_decrypt_corrupt_json(ciphertext: str, key_path: str) -> str:
            return "NOT_VALID_JSON{{"

        with (
            patch.object(utils_mod, "session", _make_session_ctx(get_map)),
            patch.object(utils_mod.crypto, "decrypt", side_effect=fake_decrypt_corrupt_json),
        ):
            with pytest.raises(CredentialDecryptionError, match="env_vars:org/repo"):
                await utils_mod.read_credentials("org/repo")

    @pytest.mark.asyncio
    async def test_read_token_pool_decrypt_failure_raises(self) -> None:
        """Corrupt token pool ciphertext must raise CredentialDecryptionError, not return []."""
        pool_setting = _make_setting("claude_tokens", "CORRUPT_POOL", encrypted=True)
        session_mock = AsyncMock()
        session_mock.get = AsyncMock(return_value=pool_setting)

        def fake_decrypt_fail(ciphertext: str, key_path: str) -> str:
            raise InvalidToken()

        with patch.object(utils_mod.crypto, "decrypt", side_effect=fake_decrypt_fail):
            with pytest.raises(CredentialDecryptionError, match="Token pool"):
                await utils_mod.read_token_pool(session_mock)

    @pytest.mark.asyncio
    async def test_read_credentials_missing_key_returns_empty(self) -> None:
        """Absent credential (not in DB) must still return empty dict, not raise."""
        get_map: dict[str, MagicMock | None] = {
            "git_token": None,
            "github_repo": None,
            "claude_tokens": None,
        }

        with patch.object(utils_mod, "session", _make_session_ctx(get_map)):
            result = await utils_mod.read_credentials(None)

        assert result == {}

    @pytest.mark.asyncio
    async def test_read_token_pool_empty_returns_empty_list(self) -> None:
        """Missing token pool (not in DB) must return [], not raise."""
        session_mock = AsyncMock()
        session_mock.get = AsyncMock(return_value=None)

        result = await utils_mod.read_token_pool(session_mock)

        assert result == []
