"""Tests for GET/PUT /repos/{repo}/mcp-servers endpoints."""

from __future__ import annotations

import json
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
from backend.models import SaveMcpServersRequest  # noqa: E402
from db.constants import MAX_MCP_SERVERS  # noqa: E402


def _make_setting(key: str, value: str, encrypted: bool) -> MagicMock:
    s = MagicMock()
    s.key = key
    s.value = value
    s.encrypted = encrypted
    return s


def _make_session_ctx(setting: MagicMock | None) -> Any:
    """Return an async context manager yielding a session whose .get() returns setting."""
    session_mock = AsyncMock()
    session_mock.get = AsyncMock(return_value=setting)
    session_mock.delete = AsyncMock()
    session_mock.commit = AsyncMock()

    @asynccontextmanager
    async def ctx():  # type: ignore[return]
        yield session_mock

    return ctx


_SAMPLE_SERVERS: dict[str, dict] = {
    "my-server": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-github"]},
    "my-sse": {"type": "sse", "url": "http://localhost:3000/sse"},
}


class TestGetRepoMcpServers:
    """GET /repos/{repo}/mcp-servers endpoint tests."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_setting(self) -> None:
        """Absent MCP config must return empty dict, not raise."""
        with patch.object(settings_mod, "session", _make_session_ctx(None)):
            result = await settings_mod.get_repo_mcp_servers("org/repo")

        assert result == {"repo": "org/repo", "servers": {}}

    @pytest.mark.asyncio
    async def test_returns_decrypted_servers(self) -> None:
        """Stored encrypted MCP config must be decrypted and returned."""
        encrypted_blob = "FAKE_ENCRYPTED"
        setting = _make_setting("mcp_servers:org/repo", encrypted_blob, True)

        def fake_decrypt(ciphertext: str, key_path: str) -> str:
            return json.dumps(_SAMPLE_SERVERS)

        with (
            patch.object(settings_mod, "session", _make_session_ctx(setting)),
            patch.object(settings_mod.crypto, "decrypt", side_effect=fake_decrypt),
        ):
            result = await settings_mod.get_repo_mcp_servers("org/repo")

        assert result["repo"] == "org/repo"
        assert result["servers"] == _SAMPLE_SERVERS

    @pytest.mark.asyncio
    async def test_decrypt_failure_raises_http_500(self) -> None:
        """Corrupted MCP config ciphertext must raise HTTPException(500)."""
        from cryptography.fernet import InvalidToken

        setting = _make_setting("mcp_servers:org/repo", "CORRUPT", True)

        def fake_decrypt_fail(ciphertext: str, key_path: str) -> str:
            raise InvalidToken()

        with (
            patch.object(settings_mod, "session", _make_session_ctx(setting)),
            patch.object(settings_mod.crypto, "decrypt", side_effect=fake_decrypt_fail),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await settings_mod.get_repo_mcp_servers("org/repo")

        assert exc_info.value.status_code == 500
        assert "Failed to decrypt MCP servers" in exc_info.value.detail


class TestSaveRepoMcpServers:
    """PUT /repos/{repo}/mcp-servers endpoint tests."""

    @pytest.mark.asyncio
    async def test_save_servers_encrypts_and_upserts(self) -> None:
        """Non-empty servers dict must be encrypted and upserted."""
        session_mock = AsyncMock()
        session_mock.get = AsyncMock(return_value=None)
        session_mock.commit = AsyncMock()

        @asynccontextmanager
        async def ctx():  # type: ignore[return]
            yield session_mock

        encrypted_blob = "FAKE_ENCRYPTED_OUTPUT"

        def fake_encrypt(plaintext: str, key_path: str) -> str:
            return encrypted_blob

        with (
            patch.object(settings_mod, "session", ctx),
            patch.object(settings_mod.crypto, "encrypt", side_effect=fake_encrypt),
            patch.object(settings_mod, "upsert_setting", AsyncMock()) as mock_upsert,
        ):
            body = SaveMcpServersRequest(servers=_SAMPLE_SERVERS)
            result = await settings_mod.save_repo_mcp_servers("org/repo", body)

        assert result["ok"] is True
        assert result["server_count"] == len(_SAMPLE_SERVERS)
        mock_upsert.assert_called_once()
        call_args = mock_upsert.call_args[0]
        assert call_args[1] == "mcp_servers:org/repo"
        assert call_args[2] == encrypted_blob
        assert call_args[3] is True  # encrypted flag

    @pytest.mark.asyncio
    async def test_empty_servers_deletes_existing(self) -> None:
        """Empty servers dict must delete the existing setting row."""
        existing = _make_setting("mcp_servers:org/repo", "old_data", True)
        session_mock = AsyncMock()
        session_mock.get = AsyncMock(return_value=existing)
        session_mock.delete = AsyncMock()
        session_mock.commit = AsyncMock()

        @asynccontextmanager
        async def ctx():  # type: ignore[return]
            yield session_mock

        with patch.object(settings_mod, "session", ctx):
            body = SaveMcpServersRequest(servers={})
            result = await settings_mod.save_repo_mcp_servers("org/repo", body)

        assert result["ok"] is True
        assert result["server_count"] == 0
        session_mock.delete.assert_called_once_with(existing)

    @pytest.mark.asyncio
    async def test_empty_servers_no_existing_noop(self) -> None:
        """Empty servers dict with no existing row must not error."""
        session_mock = AsyncMock()
        session_mock.get = AsyncMock(return_value=None)
        session_mock.delete = AsyncMock()
        session_mock.commit = AsyncMock()

        @asynccontextmanager
        async def ctx():  # type: ignore[return]
            yield session_mock

        with patch.object(settings_mod, "session", ctx):
            body = SaveMcpServersRequest(servers={})
            result = await settings_mod.save_repo_mcp_servers("org/repo", body)

        assert result["ok"] is True
        session_mock.delete.assert_not_called()


class TestSaveMcpServersRequestValidation:
    """SaveMcpServersRequest model validation tests."""

    def test_max_servers_accepted(self) -> None:
        """Exactly MAX_MCP_SERVERS entries must be accepted."""
        servers = {f"server-{i}": {"command": "cmd"} for i in range(MAX_MCP_SERVERS)}
        req = SaveMcpServersRequest(servers=servers)
        assert len(req.servers) == MAX_MCP_SERVERS

    def test_over_max_servers_rejected(self) -> None:
        """More than MAX_MCP_SERVERS entries must raise ValueError."""
        import pydantic

        servers = {f"server-{i}": {"command": "cmd"} for i in range(MAX_MCP_SERVERS + 1)}
        with pytest.raises(pydantic.ValidationError):
            SaveMcpServersRequest(servers=servers)

    def test_empty_servers_accepted(self) -> None:
        """Empty servers dict must be accepted."""
        req = SaveMcpServersRequest(servers={})
        assert req.servers == {}


class TestGetSettingsExcludesMcpServers:
    """General GET /settings must not expose mcp_servers: prefixed keys."""

    @pytest.mark.asyncio
    async def test_mcp_servers_key_excluded(self) -> None:
        """mcp_servers: prefixed keys must not appear in GET /settings response."""
        mcp_setting = MagicMock()
        mcp_setting.key = "mcp_servers:org/repo"
        mcp_setting.value = "encrypted_data"
        mcp_setting.encrypted = True

        normal_setting = MagicMock()
        normal_setting.key = "some_key"
        normal_setting.value = "some_value"
        normal_setting.encrypted = False

        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [mcp_setting, normal_setting]

        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock

        session_mock = AsyncMock()
        session_mock.execute = AsyncMock(return_value=result_mock)

        @asynccontextmanager
        async def ctx():  # type: ignore[return]
            yield session_mock

        with patch.object(settings_mod, "session", ctx):
            result = await settings_mod.get_settings()

        assert "mcp_servers:org/repo" not in result
        assert "some_key" in result
