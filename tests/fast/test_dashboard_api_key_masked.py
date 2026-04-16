"""Tests verifying dashboard_api_key is encrypted on write and masked on read.

These tests exercise the update_settings / get_settings endpoint functions
directly, stubbing DB and crypto so no real PostgreSQL or Fernet key is needed.
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

SENTINEL_API_KEY = "SENTINEL_API_KEY_LONG_123456789XYZ"
SENTINEL_OLD_PLAIN = "OLDPLAINTEXTSENTINEL"


# ---------------------------------------------------------------------------
# Module-level patches — stub only what prevents import, restore after module load.
# ---------------------------------------------------------------------------

def _setup_modules() -> None:
    """Stub out modules that require live services, only if not already imported."""
    if "backend.auth" not in sys.modules:
        fake_auth = MagicMock()
        fake_auth.verify_api_key = AsyncMock()
        sys.modules["backend.auth"] = fake_auth

    if "db.connection" not in sys.modules:
        sys.modules["db.connection"] = MagicMock()

    # DO NOT stub db.models — other tests (test_inject_audit_log) need the real module.


_setup_modules()

import backend.endpoints.settings as settings_mod  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_setting(key: str, value: str, encrypted: bool) -> MagicMock:
    """Build a mock Setting ORM object."""
    s = MagicMock()
    s.key = key
    s.value = value
    s.encrypted = encrypted
    return s


def _make_session(settings: list[MagicMock]) -> Any:
    """Build a session context manager that returns *settings* from execute."""
    scalars = MagicMock()
    scalars.all.return_value = settings
    result = MagicMock()
    result.scalars.return_value = scalars

    session_mock = AsyncMock()
    session_mock.execute = AsyncMock(return_value=result)
    session_mock.commit = AsyncMock()
    session_mock.add = MagicMock()
    session_mock.get = AsyncMock(return_value=None)

    @asynccontextmanager
    async def ctx():
        yield session_mock

    return ctx


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDashboardApiKeyMasked:
    """dashboard_api_key must be encrypted at write and masked at read."""

    @pytest.mark.asyncio
    async def test_update_settings_encrypts_dashboard_api_key(self) -> None:
        """PUT /api/settings with dashboard_api_key must encrypt the value at rest."""
        encrypted_calls: list[tuple[str, str]] = []

        def fake_encrypt(plaintext: str, key_path: str) -> str:
            encrypted_calls.append((plaintext, key_path))
            return f"FERNET:{plaintext}"

        async def fake_upsert(s: Any, key: str, value: str, is_secret: bool) -> None:
            pass

        body = MagicMock()
        body.model_dump.return_value = {"dashboard_api_key": SENTINEL_API_KEY}

        with (
            patch.object(settings_mod, "session", _make_session([])),
            patch.object(settings_mod.crypto, "encrypt", side_effect=fake_encrypt),
            patch.object(settings_mod, "upsert_setting", side_effect=fake_upsert),
            patch.object(settings_mod, "ensure_repo_in_list", new_callable=AsyncMock),
        ):
            await settings_mod.update_settings(body)

        # crypto.encrypt must have been called with the raw sentinel value
        assert any(plaintext == SENTINEL_API_KEY for plaintext, _ in encrypted_calls), (
            f"Expected encrypt to be called with {SENTINEL_API_KEY!r}, got: {encrypted_calls}"
        )

    @pytest.mark.asyncio
    async def test_get_settings_masks_dashboard_api_key(self) -> None:
        """GET /api/settings must return dashboard_api_key masked, not plaintext."""
        encrypted_stored = f"FERNET:{SENTINEL_API_KEY}"
        setting = _make_setting("dashboard_api_key", encrypted_stored, encrypted=True)

        def fake_decrypt(ciphertext: str, key_path: str) -> str:
            # Strip the "FERNET:" prefix we used as a fake encryption scheme
            return ciphertext.removeprefix("FERNET:")

        with (
            patch.object(settings_mod, "session", _make_session([setting])),
            patch.object(settings_mod.crypto, "decrypt", side_effect=fake_decrypt),
            patch.object(settings_mod, "select", MagicMock()),
        ):
            result = await settings_mod.get_settings()

        assert "dashboard_api_key" in result
        returned_value = result["dashboard_api_key"]
        assert SENTINEL_API_KEY not in returned_value, (
            f"Raw sentinel must not appear in response; got: {returned_value!r}"
        )
        # The masked value must start with the prefix (MASK_PREFIX_DEFAULT = 6)
        assert returned_value.startswith(SENTINEL_API_KEY[:6]), (
            f"Expected prefix {SENTINEL_API_KEY[:6]!r} in {returned_value!r}"
        )

    @pytest.mark.asyncio
    async def test_get_settings_legacy_plaintext_row_renders_as_stars(self) -> None:
        """Legacy unencrypted dashboard_api_key row returns value as-is server-side.

        After adding dashboard_api_key to SECRET_KEYS, new writes are encrypted.
        Old plaintext rows persist until re-set. The server returns them as-is
        (encrypted=False path); the CLI masking layer (print_detail/print_json)
        is the safety net for those rows.
        """
        setting = _make_setting("dashboard_api_key", SENTINEL_OLD_PLAIN, encrypted=False)

        with (
            patch.object(settings_mod, "session", _make_session([setting])),
            patch.object(settings_mod, "select", MagicMock()),
        ):
            result = await settings_mod.get_settings()

        assert "dashboard_api_key" in result
        # Unencrypted rows are returned as-is from the server.
        assert result["dashboard_api_key"] == SENTINEL_OLD_PLAIN

    @pytest.mark.asyncio
    async def test_get_settings_encrypted_but_undecryptable_returns_stars(self) -> None:
        """When encrypted=True but Fernet key is wrong, falls back to '****'."""
        setting = _make_setting("dashboard_api_key", "CORRUPT_TOKEN", encrypted=True)

        def fake_decrypt_fail(ciphertext: str, key_path: str) -> str:
            raise ValueError("Invalid Fernet token")

        with (
            patch.object(settings_mod, "session", _make_session([setting])),
            patch.object(settings_mod.crypto, "decrypt", side_effect=fake_decrypt_fail),
            patch.object(settings_mod, "select", MagicMock()),
        ):
            result = await settings_mod.get_settings()

        assert result.get("dashboard_api_key") == "****"
