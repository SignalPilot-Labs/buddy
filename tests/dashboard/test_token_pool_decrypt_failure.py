"""F4: read_token_pool raises on tampered ciphertext; returns [] when absent."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession

from backend.crypto import CredentialDecryptError, encrypt
from backend.utils import read_token_pool


def _make_setting(value: str, encrypted: bool = True) -> MagicMock:
    setting = MagicMock()
    setting.key = "claude_tokens"
    setting.encrypted = encrypted
    setting.value = value
    return setting


class TestTokenPoolDecryptFailure:
    """read_token_pool raises CredentialDecryptError on tampered ciphertext."""

    @pytest.mark.asyncio
    async def test_absent_pool_returns_empty_list(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.get.return_value = None
        result = await read_token_pool(mock_session)
        assert result == []

    @pytest.mark.asyncio
    async def test_tampered_pool_raises(self) -> None:
        import tempfile
        from pathlib import Path
        from cryptography.fernet import Fernet
        from backend.crypto import _reset_fernet_for_testing
        from unittest.mock import patch

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.get.return_value = _make_setting("tampered-not-valid-fernet")

        with tempfile.TemporaryDirectory() as tmpdir:
            key_path = Path(tmpdir) / "master.key"
            key_path.write_bytes(Fernet.generate_key())
            _reset_fernet_for_testing()

            from backend import utils as utils_mod
            with patch.object(utils_mod, "MASTER_KEY_PATH", str(key_path)):
                with pytest.raises(CredentialDecryptError):
                    await read_token_pool(mock_session)
        _reset_fernet_for_testing()

    @pytest.mark.asyncio
    async def test_valid_pool_returns_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            key_path = Path(tmpdir) / "master.key"
            key_path.write_bytes(Fernet.generate_key())

            tokens = ["token-one", "token-two"]
            ciphertext = encrypt(json.dumps(tokens), str(key_path))

            mock_session = AsyncMock(spec=AsyncSession)
            mock_session.get.return_value = _make_setting(ciphertext)

            with patch("backend.utils.MASTER_KEY_PATH", str(key_path)):
                result = await read_token_pool(mock_session)

        assert result == tokens
