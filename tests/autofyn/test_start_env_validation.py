"""F2+F3: _validate_start_env rejects blocked env keys at /start boundary."""

import pytest
from fastapi import HTTPException

from endpoints import _validate_start_env


class TestStartEnvValidation:
    """_validate_start_env raises HTTP 422 for blocked env keys."""

    def test_blocked_agent_internal_secret(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            _validate_start_env({"AGENT_INTERNAL_SECRET": "x"})
        assert exc_info.value.status_code == 422
        assert "AGENT_INTERNAL_SECRET" in exc_info.value.detail

    def test_blocked_dashboard_api_key(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            _validate_start_env({"DASHBOARD_API_KEY": "x"})
        assert exc_info.value.status_code == 422

    def test_blocked_ld_preload(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            _validate_start_env({"LD_PRELOAD": "/tmp/evil.so"})
        assert exc_info.value.status_code == 422

    def test_blocked_ld_library_path(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            _validate_start_env({"LD_LIBRARY_PATH": "/tmp/evil"})
        assert exc_info.value.status_code == 422

    def test_blocked_git_config_count_prefix(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            _validate_start_env({"GIT_CONFIG_COUNT": "1"})
        assert exc_info.value.status_code == 422

    def test_blocked_git_config_key_prefix(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            _validate_start_env({"GIT_CONFIG_KEY_0": "credential.helper"})
        assert exc_info.value.status_code == 422

    def test_blocked_git_config_value_prefix(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            _validate_start_env({"GIT_CONFIG_VALUE_0": "evil"})
        assert exc_info.value.status_code == 422

    def test_blocked_ld_prefix_variant(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            _validate_start_env({"LD_AUDIT": "evil"})
        assert exc_info.value.status_code == 422

    def test_allowed_node_env(self) -> None:
        _validate_start_env({"NODE_ENV": "production"})  # Should not raise

    def test_allowed_custom_key(self) -> None:
        _validate_start_env({"MY_APP_SECRET": "value"})  # Should not raise

    def test_empty_env_allowed(self) -> None:
        _validate_start_env({})  # Should not raise

    def test_allowed_mixed_env(self) -> None:
        _validate_start_env({
            "NODE_ENV": "production",
            "DATABASE_URL": "postgres://...",
            "APP_PORT": "3000",
        })  # Should not raise
