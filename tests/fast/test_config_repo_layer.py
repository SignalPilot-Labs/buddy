"""Regression tests for the repo-layer config merge in config/loader.py.

Covers:
- Default values returned by load(None)
- Target repo .autofyn/config.yml merges as layer 4
- Env vars override repo layer (layer 5)
- Missing repo config file does not crash
- agent_config() KeyErrors on missing agent section
- Deep merge preserves sibling keys when repo config is partial
"""

from __future__ import annotations

import pytest

from pathlib import Path

import yaml

import config.loader as loader_module
from config.loader import agent_config, load


class TestConfigRepoLayer:
    """Regression tests for load(repo_path) and agent_config()."""

    def test_load_returns_agent_defaults(self) -> None:
        cfg = load(None)
        agent = cfg["agent"]
        assert agent["max_rounds"] == 128
        assert agent["tool_call_timeout_sec"] == 3600
        assert agent["session_idle_timeout_sec"] == 120
        assert agent["subagent_idle_kill_sec"] == 600
        assert agent["max_concurrent_runs"] == 5
        assert agent["port"] == 8500

    def test_repo_path_overrides_agent_defaults(self, tmp_path: Path) -> None:
        autofyn_dir = tmp_path / ".autofyn"
        autofyn_dir.mkdir()
        repo_config = {"agent": {"max_rounds": 10}}
        (autofyn_dir / "config.yml").write_text(yaml.dump(repo_config))

        cfg = load(tmp_path)

        assert cfg["agent"]["max_rounds"] == 10
        # Other agent keys preserved from defaults
        assert cfg["agent"]["port"] == 8500
        assert cfg["agent"]["tool_call_timeout_sec"] == 3600

    def test_env_var_overrides_repo_layer(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        autofyn_dir = tmp_path / ".autofyn"
        autofyn_dir.mkdir()
        repo_config = {"agent": {"max_rounds": 10}}
        (autofyn_dir / "config.yml").write_text(yaml.dump(repo_config))

        monkeypatch.setenv("AF_MAX_ROUNDS", "50")

        cfg = load(tmp_path)

        assert cfg["agent"]["max_rounds"] == 50

    def test_repo_config_missing_file_no_crash(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "does_not_exist"
        cfg = load(nonexistent)
        # Should return defaults without error
        assert cfg["agent"]["max_rounds"] == 128

    def test_agent_config_direct_access_crashes_on_missing_key(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        minimal_yml = tmp_path / "minimal.yml"
        minimal_yml.write_text(yaml.dump({"database": {"host": "localhost"}}))

        project_config_path = tmp_path / "project.yml"
        project_config_path.write_text("{}")

        monkeypatch.setattr(loader_module, "_DEFAULT_CONFIG", minimal_yml)
        monkeypatch.setattr(loader_module, "_PROJECT_CONFIG", project_config_path)
        monkeypatch.setattr(loader_module, "_GLOBAL_CONFIG", tmp_path / "no_global.yml")

        with pytest.raises(KeyError):
            agent_config(None)

    def test_deep_merge_preserves_sibling_keys(self, tmp_path: Path) -> None:
        autofyn_dir = tmp_path / ".autofyn"
        autofyn_dir.mkdir()
        repo_config = {"agent": {"max_rounds": 5}}
        (autofyn_dir / "config.yml").write_text(yaml.dump(repo_config))

        cfg = load(tmp_path)

        # Repo layer only touched agent — sandbox and database must still be present
        assert "sandbox" in cfg
        assert "database" in cfg
        assert cfg["agent"]["max_rounds"] == 5
