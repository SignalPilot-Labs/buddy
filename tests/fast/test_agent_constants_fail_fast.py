"""Regression tests proving missing agent config keys raise KeyError instead of falling back."""

import importlib
from unittest.mock import patch

import pytest

import autofyn.utils.constants as constants_module

_FULL_AGENT_CFG: dict = {
    "port": 8500,
    "max_budget_usd": 0,
    "max_rounds": 128,
    "tool_call_timeout_sec": 3600,
    "session_idle_timeout_sec": 120,
    "subagent_idle_kill_sec": 600,
    "max_concurrent_runs": 5,
    "cost_per_input_token": 0.000015,
    "cost_per_output_token": 0.000075,
    "cost_per_cache_read_token": 0.0000015,
    "cost_per_cache_write_token": 0.00001875,
    "session_error_max_retries": 3,
    "session_error_base_backoff_sec": 2,
    "idle_nudge_max_attempts": 3,
    "pulse_check_interval_sec": 30,
}


def _reload_constants(agent_cfg: dict) -> None:
    """Reload the constants module with the given config dict."""
    with patch("config.loader.agent_config", return_value=agent_cfg):
        importlib.reload(constants_module)


class TestAgentConstantsFailFast:
    """autofyn/utils/constants.py must raise KeyError if a required config key is absent."""

    def teardown_method(self) -> None:
        """Restore constants module to valid state after each test."""
        _reload_constants(_FULL_AGENT_CFG)

    def test_missing_pulse_check_interval_sec_raises(self) -> None:
        incomplete: dict = {k: v for k, v in _FULL_AGENT_CFG.items() if k != "pulse_check_interval_sec"}
        with pytest.raises(KeyError):
            _reload_constants(incomplete)

    def test_missing_idle_nudge_max_attempts_raises(self) -> None:
        incomplete: dict = {k: v for k, v in _FULL_AGENT_CFG.items() if k != "idle_nudge_max_attempts"}
        with pytest.raises(KeyError):
            _reload_constants(incomplete)

    def test_missing_session_error_max_retries_raises(self) -> None:
        incomplete: dict = {k: v for k, v in _FULL_AGENT_CFG.items() if k != "session_error_max_retries"}
        with pytest.raises(KeyError):
            _reload_constants(incomplete)

    def test_missing_session_error_base_backoff_sec_raises(self) -> None:
        incomplete: dict = {k: v for k, v in _FULL_AGENT_CFG.items() if k != "session_error_base_backoff_sec"}
        with pytest.raises(KeyError):
            _reload_constants(incomplete)

    def test_missing_cost_per_input_token_raises(self) -> None:
        incomplete: dict = {k: v for k, v in _FULL_AGENT_CFG.items() if k != "cost_per_input_token"}
        with pytest.raises(KeyError):
            _reload_constants(incomplete)

    def test_missing_cost_per_output_token_raises(self) -> None:
        incomplete: dict = {k: v for k, v in _FULL_AGENT_CFG.items() if k != "cost_per_output_token"}
        with pytest.raises(KeyError):
            _reload_constants(incomplete)

    def test_missing_cost_per_cache_read_token_raises(self) -> None:
        incomplete: dict = {k: v for k, v in _FULL_AGENT_CFG.items() if k != "cost_per_cache_read_token"}
        with pytest.raises(KeyError):
            _reload_constants(incomplete)

    def test_missing_cost_per_cache_write_token_raises(self) -> None:
        incomplete: dict = {k: v for k, v in _FULL_AGENT_CFG.items() if k != "cost_per_cache_write_token"}
        with pytest.raises(KeyError):
            _reload_constants(incomplete)
