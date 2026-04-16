"""Fernet encryption for credential storage.

Uses AES-128-CBC with HMAC-SHA256 via the cryptography library's Fernet
implementation. The master key is auto-generated on first boot and stored
in a file on the shared Docker volume.
"""

import logging
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

log = logging.getLogger("backend.crypto")


class CredentialDecryptError(RuntimeError):
    """Raised when Fernet decryption fails due to wrong key or tampered ciphertext.

    Wraps cryptography.fernet.InvalidToken so that the caller never needs to
    import or catch InvalidToken directly. This keeps the error type stable
    regardless of the underlying crypto library version.
    """


_fernet: Fernet | None = None


def _reset_fernet_for_testing() -> None:
    """Reset the cached Fernet instance. For use in tests only."""
    global _fernet
    _fernet = None


def _get_fernet(key_path: str) -> Fernet:
    """Get or create the Fernet instance, generating a key if needed."""
    global _fernet
    if _fernet is not None:
        return _fernet

    p = Path(key_path)
    if p.exists():
        key = p.read_bytes().strip()
        try:
            mode = os.stat(str(p)).st_mode & 0o777
            if mode & 0o077:  # Group or world readable/writable
                log.warning("Key file %s has overly permissive mode %o — should be 0600", p, mode)
        except OSError:
            pass
    else:
        key = Fernet.generate_key()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(key)
        try:
            os.chmod(str(p), 0o600)
        except OSError as exc:
            log.warning("Could not set secure permissions on %s: %s", p, exc)

    _fernet = Fernet(key)
    return _fernet


def encrypt(plaintext: str, key_path: str) -> str:
    """Encrypt a plaintext string. Returns a Fernet token as a UTF-8 string."""
    f = _get_fernet(key_path)
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(ciphertext: str, key_path: str) -> str:
    """Decrypt a Fernet token back to plaintext.

    Raises CredentialDecryptError if the ciphertext is invalid (wrong key or
    tampered). InvalidToken never crosses this module boundary.
    """
    f = _get_fernet(key_path)
    try:
        return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise CredentialDecryptError(
            "Fernet decryption failed — master.key mismatch or ciphertext tampered. "
            "Check /data/master.key."
        ) from exc


def mask(value: str, prefix_len: int) -> str:
    """Mask a secret value, showing only the first *prefix_len* characters."""
    if len(value) <= prefix_len:
        return "****"
    return value[:prefix_len] + "*" * (len(value) - prefix_len)
