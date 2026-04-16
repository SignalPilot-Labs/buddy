"""F4: CredentialDecryptError raised on decrypt failure; not swallowed."""

import tempfile
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from backend.crypto import CredentialDecryptError, _reset_fernet_for_testing, decrypt, encrypt


class TestCredentialDecryptError:
    """decrypt() raises CredentialDecryptError on wrong key or tampered ciphertext."""

    def setup_method(self) -> None:
        _reset_fernet_for_testing()

    def teardown_method(self) -> None:
        _reset_fernet_for_testing()

    def test_decrypt_with_wrong_key_raises(self) -> None:
        """Encrypting with key A and decrypting with key B raises CredentialDecryptError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            key_a = Path(tmpdir) / "key_a.key"
            key_b = Path(tmpdir) / "key_b.key"
            key_a.write_bytes(Fernet.generate_key())
            key_b.write_bytes(Fernet.generate_key())

            ciphertext = encrypt("secret", str(key_a))
            _reset_fernet_for_testing()  # Force re-read with key_b
            with pytest.raises(CredentialDecryptError):
                decrypt(ciphertext, str(key_b))

    def test_decrypt_garbage_raises(self) -> None:
        """Garbage ciphertext raises CredentialDecryptError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            key_path = Path(tmpdir) / "master.key"
            key_path.write_bytes(Fernet.generate_key())
            with pytest.raises(CredentialDecryptError):
                decrypt("not-valid-fernet-token", str(key_path))

    def test_decrypt_valid_ciphertext_returns_plaintext(self) -> None:
        """Happy path: decrypt returns the original plaintext."""
        with tempfile.TemporaryDirectory() as tmpdir:
            key_path = Path(tmpdir) / "master.key"
            key_path.write_bytes(Fernet.generate_key())
            ciphertext = encrypt("my-secret-value", str(key_path))
            plaintext = decrypt(ciphertext, str(key_path))
            assert plaintext == "my-secret-value"

    def test_invalid_token_not_exposed(self) -> None:
        """cryptography.fernet.InvalidToken must not escape crypto.py."""
        from cryptography.fernet import InvalidToken

        with tempfile.TemporaryDirectory() as tmpdir:
            key_path = Path(tmpdir) / "master.key"
            key_path.write_bytes(Fernet.generate_key())
            with pytest.raises(CredentialDecryptError):
                decrypt("garbage", str(key_path))

            # Verify InvalidToken is NOT raised directly
            try:
                decrypt("garbage", str(key_path))
            except CredentialDecryptError:
                pass  # Expected
            except InvalidToken:
                pytest.fail("InvalidToken crossed the crypto.py boundary")

    def test_credential_decrypt_error_is_runtime_error(self) -> None:
        """CredentialDecryptError must be a subclass of RuntimeError (fail-fast)."""
        assert issubclass(CredentialDecryptError, RuntimeError)
