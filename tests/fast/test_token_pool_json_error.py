"""Regression test: read_token_pool raises CredentialDecryptionError on bad JSON.

Previously JSONDecodeError from json.loads propagated uncaught after decryption
succeeded, causing unhandled 500s on token pool endpoints. Now it is caught and
wrapped in CredentialDecryptionError.
"""

import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Stub heavy dependencies before importing the module under test.
if "db.connection" not in sys.modules:
    sys.modules["db.connection"] = MagicMock()

from backend.utils import CredentialDecryptionError, read_token_pool


class TestTokenPoolJsonError:
    """read_token_pool must raise CredentialDecryptionError on corrupt JSON."""

    @pytest.mark.asyncio
    async def test_corrupt_json_raises_credential_error(self) -> None:
        """Decrypted content that is not valid JSON must raise CredentialDecryptionError."""
        mock_setting = MagicMock()
        mock_setting.value = "encrypted-blob"

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_setting)

        with patch("backend.utils.crypto") as mock_crypto:
            mock_crypto.decrypt.return_value = "not valid json {{{{"
            with pytest.raises(CredentialDecryptionError, match="invalid JSON"):
                await read_token_pool(mock_session)

    @pytest.mark.asyncio
    async def test_decrypt_failure_still_raises_credential_error(self) -> None:
        """InvalidToken from decrypt must still raise CredentialDecryptionError."""
        from cryptography.fernet import InvalidToken

        mock_setting = MagicMock()
        mock_setting.value = "encrypted-blob"

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_setting)

        with patch("backend.utils.crypto") as mock_crypto:
            mock_crypto.decrypt.side_effect = InvalidToken()
            with pytest.raises(CredentialDecryptionError, match="cannot be decrypted"):
                await read_token_pool(mock_session)

    @pytest.mark.asyncio
    async def test_valid_json_returns_tokens(self) -> None:
        """Valid encrypted JSON must return the token list."""
        tokens = ["tok-1", "tok-2"]

        mock_setting = MagicMock()
        mock_setting.value = "encrypted-blob"

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_setting)

        with patch("backend.utils.crypto") as mock_crypto:
            mock_crypto.decrypt.return_value = json.dumps(tokens)
            result = await read_token_pool(mock_session)

        assert result == tokens
