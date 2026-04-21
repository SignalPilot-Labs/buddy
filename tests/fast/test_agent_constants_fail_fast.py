"""Regression tests proving missing agent config keys raise KeyError via lazy accessors."""

from unittest.mock import patch

import pytest

from config.loader import clear_cache


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


def _patch_and_call(missing_key: str, fn_name: str) -> None:
    """Remove a key from config, reset lazy cache, call the accessor — expect KeyError."""
    import autofyn.utils.constants as mod

    incomplete = {k: v for k, v in _FULL_AGENT_CFG.items() if k != missing_key}
    # Reset the lazy cache so the next call re-reads config
    mod._cached_agent_cfg = None
    with patch("autofyn.utils.constants.agent_config", return_value=incomplete):
        with pytest.raises(KeyError):
            getattr(mod, fn_name)()


class TestAgentConstantsFailFast:
    """Lazy accessor functions must raise KeyError if a required config key is absent."""

    def teardown_method(self) -> None:
        """Reset lazy cache to valid state after each test."""
        import autofyn.utils.constants as mod
        mod._cached_agent_cfg = None
        clear_cache()

    def test_missing_pulse_check_interval_sec_raises(self) -> None:
        _patch_and_call("pulse_check_interval_sec", "pulse_check_interval_sec")

    def test_missing_idle_nudge_max_attempts_raises(self) -> None:
        _patch_and_call("idle_nudge_max_attempts", "idle_nudge_max_attempts")

    def test_missing_session_error_max_retries_raises(self) -> None:
        _patch_and_call("session_error_max_retries", "session_error_max_retries")

    def test_missing_session_error_base_backoff_sec_raises(self) -> None:
        _patch_and_call("session_error_base_backoff_sec", "session_error_base_backoff_sec")

    def test_missing_cost_per_input_token_raises(self) -> None:
        _patch_and_call("cost_per_input_token", "cost_per_input")

    def test_missing_cost_per_output_token_raises(self) -> None:
        _patch_and_call("cost_per_output_token", "cost_per_output")

    def test_missing_cost_per_cache_read_token_raises(self) -> None:
        _patch_and_call("cost_per_cache_read_token", "cost_per_cache_read")

    def test_missing_cost_per_cache_write_token_raises(self) -> None:
        _patch_and_call("cost_per_cache_write_token", "cost_per_cache_write")
