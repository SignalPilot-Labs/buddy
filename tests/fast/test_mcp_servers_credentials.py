"""Tests for read_credentials mcp_servers handling."""

from __future__ import annotations

import json
import sys
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import InvalidToken

# Stub out modules that require live services before importing utils.
if "db.connection" not in sys.modules:
    sys.modules["db.connection"] = MagicMock()
if "db.models" not in sys.modules:
    sys.modules["db.models"] = MagicMock()

import backend.utils as utils_mod  # noqa: E402
from backend.utils import CredentialDecryptionError  # noqa: E402


_SAMPLE_MCP_SERVERS: dict[str, dict] = {
    "my-server": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-github"]},
}


def _make_session_with_settings(settings_by_key: dict[str, MagicMock | None]) -> Any:
    """Return an async context manager that yields a session with keyed get() responses."""
    session_mock = AsyncMock()

    async def get_setting(model: Any, key: str) -> MagicMock | None:
        return settings_by_key.get(key)

    session_mock.get = get_setting
    session_mock.commit = AsyncMock()

    @asynccontextmanager
    async def ctx():  # type: ignore[return]
        yield session_mock

    return ctx


def _make_setting(key: str, value: str, encrypted: bool) -> MagicMock:
    s = MagicMock()
    s.key = key
    s.value = value
    s.encrypted = encrypted
    return s


class TestReadCredentialsMcpServers:
    """read_credentials includes/omits/errors on mcp_servers depending on stored state."""

    @pytest.mark.asyncio
    async def test_mcp_servers_included_when_stored(self) -> None:
        """read_credentials must include mcp_servers when stored in DB."""
        encrypted_blob = "FAKE_ENCRYPTED"
        mcp_setting = _make_setting(
            "mcp_servers:org/repo", encrypted_blob, True
        )

        session_ctx = _make_session_with_settings({
            "mcp_servers:org/repo": mcp_setting,
            "claude_tokens": None,
        })

        def fake_decrypt(ciphertext: str, key_path: str) -> str:
            return json.dumps(_SAMPLE_MCP_SERVERS)

        with (
            patch.object(utils_mod, "session", session_ctx),
            patch.object(utils_mod.crypto, "decrypt", side_effect=fake_decrypt),
            patch.object(utils_mod, "read_token_pool", AsyncMock(return_value=[])),
        ):
            creds = await utils_mod.read_credentials("org/repo", None)

        assert "mcp_servers" in creds
        assert creds["mcp_servers"] == _SAMPLE_MCP_SERVERS

    @pytest.mark.asyncio
    async def test_mcp_servers_omitted_when_not_stored(self) -> None:
        """read_credentials must not include mcp_servers key when no DB entry exists."""
        session_ctx = _make_session_with_settings({
            "mcp_servers:org/repo": None,
            "claude_tokens": None,
        })

        with (
            patch.object(utils_mod, "session", session_ctx),
            patch.object(utils_mod, "read_token_pool", AsyncMock(return_value=[])),
        ):
            creds = await utils_mod.read_credentials("org/repo", None)

        assert "mcp_servers" not in creds

    @pytest.mark.asyncio
    async def test_decrypt_error_raises_credential_decryption_error(self) -> None:
        """InvalidToken on mcp_servers decrypt must raise CredentialDecryptionError."""
        mcp_setting = _make_setting("mcp_servers:org/repo", "CORRUPT", True)

        session_ctx = _make_session_with_settings({
            "mcp_servers:org/repo": mcp_setting,
            "claude_tokens": None,
        })

        def fake_decrypt_fail(ciphertext: str, key_path: str) -> str:
            raise InvalidToken()

        with (
            patch.object(utils_mod, "session", session_ctx),
            patch.object(utils_mod.crypto, "decrypt", side_effect=fake_decrypt_fail),
            patch.object(utils_mod, "read_token_pool", AsyncMock(return_value=[])),
        ):
            with pytest.raises(CredentialDecryptionError) as exc_info:
                await utils_mod.read_credentials("org/repo", None)

        assert "mcp_servers:org/repo" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_json_decode_error_raises_credential_decryption_error(self) -> None:
        """Invalid JSON in decrypted mcp_servers must raise CredentialDecryptionError."""
        mcp_setting = _make_setting("mcp_servers:org/repo", "VALID_CIPHER", True)

        session_ctx = _make_session_with_settings({
            "mcp_servers:org/repo": mcp_setting,
            "claude_tokens": None,
        })

        def fake_decrypt_bad_json(ciphertext: str, key_path: str) -> str:
            return "NOT_VALID_JSON{{"

        with (
            patch.object(utils_mod, "session", session_ctx),
            patch.object(utils_mod.crypto, "decrypt", side_effect=fake_decrypt_bad_json),
            patch.object(utils_mod, "read_token_pool", AsyncMock(return_value=[])),
        ):
            with pytest.raises(CredentialDecryptionError) as exc_info:
                await utils_mod.read_credentials("org/repo", None)

        assert "mcp_servers:org/repo" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_no_repo_skips_mcp_servers(self) -> None:
        """read_credentials(repo=None) must not attempt to read mcp_servers."""
        session_ctx = _make_session_with_settings({"claude_tokens": None})

        with (
            patch.object(utils_mod, "session", session_ctx),
            patch.object(utils_mod, "read_token_pool", AsyncMock(return_value=[])),
        ):
            creds = await utils_mod.read_credentials(None, None)

        assert "mcp_servers" not in creds
