"""Regression tests for load_run_agent_config.

Covers:
1. No .autofyn/config.yml in sandbox → uses defaults from base config.
2. Sandbox has config with full agent overrides → values are overridden.
3. Partial override (only max_rounds) → other values use defaults.
4. Config file exists but has no `agent` section → base config used.
5. Config file is empty YAML → base config used.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from utils.run_config import RunAgentConfig, load_run_agent_config


def _make_sandbox(read_return: str | None) -> MagicMock:
    """Build a minimal mock SandboxClient whose file_system.read() returns read_return."""
    sandbox = MagicMock()
    sandbox.file_system.read = AsyncMock(return_value=read_return)
    return sandbox


class TestLoadRunAgentConfigDefaults:
    """No target-repo config → base config defaults apply."""

    @pytest.mark.asyncio
    async def test_no_config_file_uses_defaults(self) -> None:
        sandbox = _make_sandbox(read_return=None)
        result = await load_run_agent_config(sandbox)

        assert isinstance(result, RunAgentConfig)
        # Values must match config/config.yml agent section defaults.
        assert result.max_rounds == 128
        assert result.tool_call_timeout_sec == 3600
        assert result.session_idle_timeout_sec == 120
        assert result.subagent_idle_kill_sec == 600

    @pytest.mark.asyncio
    async def test_result_is_frozen(self) -> None:
        sandbox = _make_sandbox(read_return=None)
        result = await load_run_agent_config(sandbox)

        with pytest.raises((AttributeError, TypeError)):
            result.max_rounds = 999  # type: ignore[misc]


class TestLoadRunAgentConfigFullOverride:
    """All 4 agent keys overridden by target repo config."""

    @pytest.mark.asyncio
    async def test_full_override(self) -> None:
        yaml_content = (
            "agent:\n"
            "  max_rounds: 10\n"
            "  tool_call_timeout_sec: 300\n"
            "  session_idle_timeout_sec: 60\n"
            "  subagent_idle_kill_sec: 120\n"
        )
        sandbox = _make_sandbox(read_return=yaml_content)
        result = await load_run_agent_config(sandbox)

        assert result.max_rounds == 10
        assert result.tool_call_timeout_sec == 300
        assert result.session_idle_timeout_sec == 60
        assert result.subagent_idle_kill_sec == 120


class TestLoadRunAgentConfigPartialOverride:
    """Only one key overridden — others fall back to base config defaults."""

    @pytest.mark.asyncio
    async def test_partial_override_only_max_rounds(self) -> None:
        yaml_content = "agent:\n  max_rounds: 5\n"
        sandbox = _make_sandbox(read_return=yaml_content)
        result = await load_run_agent_config(sandbox)

        assert result.max_rounds == 5
        # Other values remain at their defaults.
        assert result.tool_call_timeout_sec == 3600
        assert result.session_idle_timeout_sec == 120
        assert result.subagent_idle_kill_sec == 600


class TestLoadRunAgentConfigNoAgentSection:
    """Config file exists but has no `agent` section → base config used."""

    @pytest.mark.asyncio
    async def test_no_agent_section_in_config(self) -> None:
        yaml_content = "sandbox:\n  url: http://custom-sandbox:9090\n"
        sandbox = _make_sandbox(read_return=yaml_content)
        result = await load_run_agent_config(sandbox)

        # Defaults unchanged since there's no agent section to merge.
        assert result.max_rounds == 128
        assert result.tool_call_timeout_sec == 3600

    @pytest.mark.asyncio
    async def test_empty_yaml_content_uses_defaults(self) -> None:
        sandbox = _make_sandbox(read_return="")
        result = await load_run_agent_config(sandbox)

        assert result.max_rounds == 128
        assert result.tool_call_timeout_sec == 3600
