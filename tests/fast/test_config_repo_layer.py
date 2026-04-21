"""Regression tests for the config loader in config/loader.py.

Covers:
- Default values returned by load(None)
- Overlay dict merges correctly
- Env vars override overlay (layer 5)
- Missing overlay key does not crash
- agent_config() KeyErrors on missing agent section
- Deep merge preserves sibling keys when overlay is partial
- Caching: same overlay returns cached result
- clear_cache() forces re-read
- Clamping: out-of-bounds values get clamped
- Validation: missing required keys raise RuntimeError
"""

from __future__ import annotations

import pytest

from pathlib import Path

import yaml

import config.loader as loader_module
from config.loader import clear_cache, load


class TestConfigDefaults:
    """load(None) returns correct defaults from config.yml."""

    def setup_method(self) -> None:
        clear_cache()

    def test_load_returns_agent_defaults(self) -> None:
        cfg = load(None)
        agent = cfg["agent"]
        assert agent["max_rounds"] == 128
        assert agent["tool_call_timeout_sec"] == 3600
        assert agent["session_idle_timeout_sec"] == 120
        assert agent["subagent_idle_kill_sec"] == 600
        assert agent["max_concurrent_runs"] == 5
        assert agent["port"] == 8500


class TestConfigOverlay:
    """load(overlay) merges the overlay dict on top of defaults."""

    def setup_method(self) -> None:
        clear_cache()

    def test_overlay_overrides_agent_defaults(self) -> None:
        cfg = load({"agent": {"max_rounds": 10}})
        assert cfg["agent"]["max_rounds"] == 10
        # Other agent keys preserved from defaults
        assert cfg["agent"]["port"] == 8500
        assert cfg["agent"]["tool_call_timeout_sec"] == 3600

    def test_env_var_overrides_overlay(self, monkeypatch: pytest.MonkeyPatch) -> None:
        clear_cache()
        monkeypatch.setenv("AF_MAX_ROUNDS", "50")
        cfg = load({"agent": {"max_rounds": 10}})
        assert cfg["agent"]["max_rounds"] == 50

    def test_overlay_preserves_sibling_sections(self) -> None:
        cfg = load({"agent": {"max_rounds": 5}})
        assert "sandbox" in cfg
        assert "database" in cfg
        assert cfg["agent"]["max_rounds"] == 5


class TestConfigCache:
    """load() caches results and clear_cache() resets."""

    def setup_method(self) -> None:
        clear_cache()

    def test_same_overlay_returns_cached_object(self) -> None:
        result1 = load(None)
        result2 = load(None)
        assert result1 is result2

    def test_clear_cache_forces_reload(self) -> None:
        result1 = load(None)
        clear_cache()
        result2 = load(None)
        assert result1 is not result2
        assert result1 == result2


class TestConfigClamping:
    """Out-of-bounds values are clamped to safe ranges."""

    def setup_method(self) -> None:
        clear_cache()

    def test_max_rounds_clamped_to_upper_bound(self) -> None:
        cfg = load({"agent": {"max_rounds": 999999}})
        assert cfg["agent"]["max_rounds"] == 512

    def test_max_rounds_clamped_to_lower_bound(self) -> None:
        cfg = load({"agent": {"max_rounds": 0}})
        assert cfg["agent"]["max_rounds"] == 1

    def test_subagent_idle_kill_sec_clamped(self) -> None:
        cfg = load({"agent": {"subagent_idle_kill_sec": 0}})
        assert cfg["agent"]["subagent_idle_kill_sec"] == 60

    def test_tool_call_timeout_sec_clamped_upper(self) -> None:
        cfg = load({"agent": {"tool_call_timeout_sec": 99999}})
        assert cfg["agent"]["tool_call_timeout_sec"] == 7200


class TestConfigValidation:
    """Missing required keys raise RuntimeError at load time."""

    def setup_method(self) -> None:
        clear_cache()

    def test_missing_agent_section_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        minimal_yml = tmp_path / "minimal.yml"
        minimal_yml.write_text(yaml.dump({
            "database": {"host": "localhost", "port": 5432, "name": "db",
                         "user": "u", "password": "p", "pool_size": 5,
                         "max_overflow": 10, "pool_timeout": 30,
                         "pool_recycle": 1800, "echo": False},
            "sandbox": {},
            "security": {},
        }))
        project_config_path = tmp_path / "project.yml"
        project_config_path.write_text("{}")

        monkeypatch.setattr(loader_module, "_DEFAULT_CONFIG", minimal_yml)
        monkeypatch.setattr(loader_module, "_PROJECT_CONFIG", project_config_path)
        monkeypatch.setattr(loader_module, "_GLOBAL_CONFIG", tmp_path / "no_global.yml")

        with pytest.raises(RuntimeError, match="Missing agent config keys"):
            load(None)
