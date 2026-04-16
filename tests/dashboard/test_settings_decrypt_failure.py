"""F4: Credential decrypt failure surfaces as HTTP 500 (not 200 with empty values).

Tests at the unit level:
- _decrypt_setting raises CredentialDecryptError on tampered ciphertext.
- The exception handler returns status 500 with master.key in the body.
- get_settings propagates CredentialDecryptError (no swallow).

Avoids importing the full FastAPI app to sidestep the /data/api.key requirement.
"""

import inspect
import sys
import tempfile
import types
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from cryptography.fernet import Fernet
from starlette.requests import Request


def _patch_auth() -> None:
    """Insert a stub backend.auth module before any import touches auth.py."""
    mod = types.ModuleType("backend.auth")
    mod.verify_api_key = lambda: None  # type: ignore[attr-defined]
    sys.modules.setdefault("backend.auth", mod)


_patch_auth()


from backend.crypto import CredentialDecryptError, _reset_fernet_for_testing  # noqa: E402
from backend.endpoints.settings import (  # noqa: E402
    _credential_decrypt_error_handler,
    _decrypt_setting,
    get_settings,
)


class TestSettingsDecryptFailure:
    """_decrypt_setting raises CredentialDecryptError; handler returns 500."""

    def test_tampered_ciphertext_raises(self) -> None:
        """_decrypt_setting on a tampered value raises CredentialDecryptError."""
        tampered = MagicMock()
        tampered.key = "git_token"
        tampered.encrypted = True
        tampered.value = "tampered-not-valid-fernet"

        with tempfile.TemporaryDirectory() as tmpdir:
            key_path = Path(tmpdir) / "master.key"
            key_path.write_bytes(Fernet.generate_key())
            _reset_fernet_for_testing()

            from backend.endpoints import settings as settings_mod
            with patch.object(settings_mod, "MASTER_KEY_PATH", str(key_path)):
                with pytest.raises(CredentialDecryptError):
                    _decrypt_setting(tampered)
        _reset_fernet_for_testing()

    @pytest.mark.asyncio
    async def test_exception_handler_returns_500_with_master_key(self) -> None:
        """The exception handler returns HTTP 500 with master.key in body."""
        exc = CredentialDecryptError(
            "Fernet decryption failed — master.key mismatch or ciphertext tampered. "
            "Check /data/master.key."
        )

        scope: dict[str, Any] = {
            "type": "http",
            "method": "GET",
            "path": "/api/settings",
            "headers": [],
            "query_string": b"",
        }
        mock_request = Request(scope)
        response = await _credential_decrypt_error_handler(mock_request, exc)
        assert response.status_code == 500
        assert b"master.key" in response.body

    def test_no_try_except_in_get_settings(self) -> None:
        """Verify get_settings has no try/except that swallows CredentialDecryptError.

        The structural test: _decrypt_setting must propagate CredentialDecryptError,
        and get_settings must NOT catch it.
        """
        source = inspect.getsource(get_settings)
        # The function should not have a try/except block
        assert "except" not in source, (
            "get_settings must not have try/except — it swallows CredentialDecryptError"
        )
