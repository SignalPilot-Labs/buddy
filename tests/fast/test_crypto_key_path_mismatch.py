"""Regression test: crypto._get_fernet raises RuntimeError when key_path changes after first call."""

import tempfile
from pathlib import Path

import pytest

from dashboard.backend import crypto


class TestCryptoKeyPathMismatch:
    """Verify that _get_fernet detects and rejects key_path changes across calls."""

    def setup_method(self) -> None:
        self._orig_fernet = crypto._fernet
        self._orig_path = crypto._cached_key_path

    def teardown_method(self) -> None:
        crypto._fernet = self._orig_fernet
        crypto._cached_key_path = self._orig_path

    def test_mismatched_key_path_raises(self) -> None:
        """Calling encrypt with a different key_path after the first call must raise RuntimeError."""
        crypto._fernet = None
        crypto._cached_key_path = None

        with tempfile.TemporaryDirectory() as tmpdir:
            # Use non-existent file paths so _get_fernet generates fresh keys
            path_a = str(Path(tmpdir) / "key_a.key")
            path_b = str(Path(tmpdir) / "key_b.key")

            crypto.encrypt("test", path_a)

            with pytest.raises(RuntimeError, match="key_path mismatch"):
                crypto.encrypt("test", path_b)

    def test_same_key_path_reuses_fernet(self) -> None:
        """Calling encrypt multiple times with the same key_path must not raise."""
        crypto._fernet = None
        crypto._cached_key_path = None

        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "key.key")

            crypto.encrypt("a", path)
            crypto.encrypt("b", path)
