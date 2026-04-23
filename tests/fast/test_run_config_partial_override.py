"""Tests for load_run_agent_config: only one key overridden, others use defaults."""

import pytest

from config.loader import clear_cache
from tests.fast.conftest import _make_sandbox
from utils.run_config import load_run_agent_config


class TestLoadRunAgentConfigPartialOverride:
    """Only one key overridden -- others fall back to base config defaults."""

    def setup_method(self) -> None:
        clear_cache()

    @pytest.mark.asyncio
    async def test_partial_override_only_max_rounds(self) -> None:
        yaml_content = "agent:\n  max_rounds: 5\n"
        sandbox = _make_sandbox(read_return=yaml_content)
        result = await load_run_agent_config(sandbox)

        assert result.max_rounds == 5
        assert result.tool_call_timeout_sec == 3600
        assert result.session_idle_timeout_sec == 120
        assert result.subagent_idle_kill_sec == 600
