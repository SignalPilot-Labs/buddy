"""Regression tests for unvalidated env vars in save_repo_env (Finding 8).

Verifies:
  1. Valid env vars are accepted (happy path).
  2. Non-string value is rejected (422 via Pydantic ValidationError).
  3. Key with shell special chars is rejected.
  4. Key starting with a digit is rejected.
  5. Value exceeding max length is rejected.
  6. Too many env vars (101) are rejected.
  7. Empty dict is accepted (clears env vars).
  8. Key exceeding max key length is rejected.
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

# Stub out modules that require live services before importing settings endpoint.
if "db.connection" not in sys.modules:
    sys.modules["db.connection"] = MagicMock()
if "db.models" not in sys.modules:
    sys.modules["db.models"] = MagicMock()

_auth_mock = MagicMock()
_auth_mock.verify_api_key = MagicMock(return_value=None)
sys.modules["backend.auth"] = _auth_mock

import backend.endpoints.settings as settings_mod  # noqa: E402
from backend.models import SaveRepoEnvRequest  # noqa: E402
from db.constants import ENV_VAR_MAX_KEY_LEN, ENV_VAR_MAX_VALUE_LEN, MAX_ENV_VARS  # noqa: E402


def _null_session_ctx() -> Any:
    """Return an async context manager yielding a mock session."""
    session_mock = AsyncMock()
    session_mock.get = AsyncMock(return_value=None)
    session_mock.delete = AsyncMock()
    session_mock.commit = AsyncMock()

    @asynccontextmanager
    async def ctx():  # type: ignore[return]
        yield session_mock

    return ctx


class TestEnvVarValidation:
    """Regression tests for env var validation in save_repo_env (Finding 8)."""

    # ── Pydantic model validation tests ─────────────────────────────────────

    def test_valid_env_vars_accepted(self) -> None:
        """Standard POSIX-compliant env var keys and string values must be accepted."""
        req = SaveRepoEnvRequest(env_vars={"MY_VAR": "hello", "ANOTHER_1": "world"})
        assert req.env_vars == {"MY_VAR": "hello", "ANOTHER_1": "world"}

    def test_non_string_value_rejected(self) -> None:
        """A non-string value (e.g. int) must be rejected with ValidationError."""
        with pytest.raises(ValidationError):
            SaveRepoEnvRequest(env_vars={"MY_VAR": 123})  # type: ignore[arg-type]

    def test_key_with_special_chars_rejected(self) -> None:
        """A key containing shell metacharacters (e.g. semicolon) must be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SaveRepoEnvRequest(env_vars={"KEY;DROP": "value"})
        assert "must match" in str(exc_info.value)

    def test_key_starting_with_digit_rejected(self) -> None:
        """A key starting with a digit must be rejected (not valid POSIX)."""
        with pytest.raises(ValidationError) as exc_info:
            SaveRepoEnvRequest(env_vars={"1INVALID": "value"})
        assert "must match" in str(exc_info.value)

    def test_value_exceeding_max_length_rejected(self) -> None:
        """A value longer than ENV_VAR_MAX_VALUE_LEN must be rejected."""
        long_value = "x" * (ENV_VAR_MAX_VALUE_LEN + 1)
        with pytest.raises(ValidationError) as exc_info:
            SaveRepoEnvRequest(env_vars={"MY_VAR": long_value})
        assert "exceeds maximum length" in str(exc_info.value)

    def test_too_many_env_vars_rejected(self) -> None:
        """More than MAX_ENV_VARS entries must be rejected."""
        too_many = {f"KEY_{i}": "val" for i in range(MAX_ENV_VARS + 1)}
        with pytest.raises(ValidationError) as exc_info:
            SaveRepoEnvRequest(env_vars=too_many)
        assert "more than" in str(exc_info.value)

    def test_empty_dict_accepted(self) -> None:
        """An empty dict must be accepted (used to clear all env vars)."""
        req = SaveRepoEnvRequest(env_vars={})
        assert req.env_vars == {}

    def test_key_exceeding_max_key_length_rejected(self) -> None:
        """A key longer than ENV_VAR_MAX_KEY_LEN must be rejected."""
        long_key = "A" * (ENV_VAR_MAX_KEY_LEN + 1)
        with pytest.raises(ValidationError) as exc_info:
            SaveRepoEnvRequest(env_vars={long_key: "value"})
        assert "exceeds maximum length" in str(exc_info.value)

    # ── Endpoint integration tests ───────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_valid_env_vars_endpoint_accepted(self) -> None:
        """PUT /repos/{repo}/env with valid env vars must return ok=True."""
        crypto_mock = MagicMock()
        crypto_mock.encrypt = MagicMock(return_value="encrypted_blob")
        upsert_mock = AsyncMock()

        with (
            patch.object(settings_mod, "session", _null_session_ctx()),
            patch.object(settings_mod, "crypto", crypto_mock),
            patch.object(settings_mod, "upsert_setting", upsert_mock),
        ):
            body = SaveRepoEnvRequest(env_vars={"DB_HOST": "localhost"})
            result = await settings_mod.save_repo_env("owner/repo", body)

        assert result["ok"] is True
        assert result["repo"] == "owner/repo"
        assert result["key_count"] == 1

    @pytest.mark.asyncio
    async def test_empty_env_vars_endpoint_accepted(self) -> None:
        """PUT /repos/{repo}/env with empty dict must return ok=True and key_count=0."""
        with patch.object(settings_mod, "session", _null_session_ctx()):
            body = SaveRepoEnvRequest(env_vars={})
            result = await settings_mod.save_repo_env("owner/repo", body)

        assert result["ok"] is True
        assert result["key_count"] == 0
