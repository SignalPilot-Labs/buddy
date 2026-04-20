"""Regression tests proving missing sandbox config keys raise KeyError instead of falling back."""

import importlib
from unittest.mock import patch

import pytest

import sandbox.constants as constants_module

_FULL_SANDBOX_CFG: dict = {
    "exec_timeout_sec": 120,
    "max_concurrent_sessions": 5,
    "session_event_queue_size": 1000,
    "log_level": "info",
}

_FULL_SECURITY_CFG: dict = {
    "credential_patterns": [],
    "secret_env_vars": "",
}


def _reload_constants(sandbox_cfg: dict, security_cfg: dict) -> None:
    """Reload the constants module with the given config dicts."""
    with patch("config.loader.sandbox_config", return_value=sandbox_cfg):
        with patch("config.loader.security_config", return_value=security_cfg):
            importlib.reload(constants_module)


class TestSandboxConstantsFailFast:
    """sandbox/constants.py must raise KeyError if a required config key is absent."""

    def teardown_method(self) -> None:
        """Restore constants module to valid state after each test."""
        _reload_constants(_FULL_SANDBOX_CFG, _FULL_SECURITY_CFG)

    def test_missing_exec_timeout_sec_raises(self) -> None:
        incomplete: dict = {k: v for k, v in _FULL_SANDBOX_CFG.items() if k != "exec_timeout_sec"}
        with pytest.raises(KeyError):
            _reload_constants(incomplete, _FULL_SECURITY_CFG)

    def test_missing_max_concurrent_sessions_raises(self) -> None:
        incomplete: dict = {k: v for k, v in _FULL_SANDBOX_CFG.items() if k != "max_concurrent_sessions"}
        with pytest.raises(KeyError):
            _reload_constants(incomplete, _FULL_SECURITY_CFG)

    def test_missing_session_event_queue_size_raises(self) -> None:
        incomplete: dict = {k: v for k, v in _FULL_SANDBOX_CFG.items() if k != "session_event_queue_size"}
        with pytest.raises(KeyError):
            _reload_constants(incomplete, _FULL_SECURITY_CFG)

    def test_missing_credential_patterns_raises(self) -> None:
        incomplete: dict = {k: v for k, v in _FULL_SECURITY_CFG.items() if k != "credential_patterns"}
        with pytest.raises(KeyError):
            _reload_constants(_FULL_SANDBOX_CFG, incomplete)

    def test_missing_secret_env_vars_raises(self) -> None:
        incomplete: dict = {k: v for k, v in _FULL_SECURITY_CFG.items() if k != "secret_env_vars"}
        with pytest.raises(KeyError):
            _reload_constants(_FULL_SANDBOX_CFG, incomplete)

    def test_missing_log_level_raises(self) -> None:
        """Accessing cfg["log_level"] in server.py raises KeyError when key is absent."""
        incomplete: dict = {k: v for k, v in _FULL_SANDBOX_CFG.items() if k != "log_level"}
        with pytest.raises(KeyError):
            _ = incomplete["log_level"]
