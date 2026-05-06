"""Regression tests for read_token_pool exception handling.

Previously the except clause was `except (json.JSONDecodeError, TypeError, Exception)`
which silently swallowed all exceptions — DB errors, missing master key,
crypto failures — masking real problems. The fix removes the swallowing entirely:
all errors from decrypt/parse propagate so callers see the real failure.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import InvalidToken

from backend.utils import CredentialDecryptionError, read_token_pool


def _make_session(setting: MagicMock | None) -> MagicMock:
    """Build a mock AsyncSession whose get() returns the given Setting."""
    s = MagicMock()
    s.get = AsyncMock(return_value=setting)
    return s


def _make_setting(value: str) -> MagicMock:
    """Build a mock Setting ORM object with a given value."""
    row = MagicMock()
    row.value = value
    return row


class TestReadTokenPool:
    """Verify read_token_pool raises on all decryption/parse errors, not swallows them."""

    @pytest.mark.asyncio
    async def test_raises_credential_decryption_error_on_invalid_token(self) -> None:
        """InvalidToken from Fernet must raise CredentialDecryptionError, not return []."""
        setting = _make_setting("encrypted-value")
        s = _make_session(setting)

        with patch("backend.utils.crypto.decrypt", side_effect=InvalidToken()):
            with pytest.raises(CredentialDecryptionError, match="Token pool"):
                await read_token_pool(s, for_update=False)

    @pytest.mark.asyncio
    async def test_raises_on_json_decode_error(self) -> None:
        """JSONDecodeError from corrupt decrypted data must propagate, not return []."""
        setting = _make_setting("encrypted-value")
        s = _make_session(setting)

        with patch("backend.utils.crypto.decrypt", side_effect=json.JSONDecodeError("bad", "", 0)):
            with pytest.raises(json.JSONDecodeError):
                await read_token_pool(s, for_update=False)

    @pytest.mark.asyncio
    async def test_raises_on_type_error(self) -> None:
        """TypeError during decrypt must propagate, not return []."""
        setting = _make_setting("encrypted-value")
        s = _make_session(setting)

        with patch("backend.utils.crypto.decrypt", side_effect=TypeError("not a string")):
            with pytest.raises(TypeError):
                await read_token_pool(s, for_update=False)

    @pytest.mark.asyncio
    async def test_propagates_runtime_error(self) -> None:
        """RuntimeError (e.g. bad crypto key) must propagate, not be swallowed."""
        setting = _make_setting("encrypted-value")
        s = _make_session(setting)

        with patch("backend.utils.crypto.decrypt", side_effect=RuntimeError("invalid key")):
            with pytest.raises(RuntimeError, match="invalid key"):
                await read_token_pool(s, for_update=False)

    @pytest.mark.asyncio
    async def test_propagates_connection_error_from_db(self) -> None:
        """ConnectionError from AsyncSession.get() must propagate."""
        s = MagicMock()
        s.get = AsyncMock(side_effect=ConnectionError("db unreachable"))

        with pytest.raises(ConnectionError, match="db unreachable"):
            await read_token_pool(s, for_update=False)

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_setting_row(self) -> None:
        """When no 'claude_tokens' row exists, must return []."""
        s = _make_session(None)
        result = await read_token_pool(s, for_update=False)
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_tokens_on_success(self) -> None:
        """When decrypt + json.loads succeed, must return the token list."""
        tokens = ["sk-ant-token1", "sk-ant-token2"]
        setting = _make_setting("encrypted-value")
        s = _make_session(setting)

        with patch("backend.utils.crypto.decrypt", return_value=json.dumps(tokens)):
            result = await read_token_pool(s, for_update=False)

        assert result == tokens
