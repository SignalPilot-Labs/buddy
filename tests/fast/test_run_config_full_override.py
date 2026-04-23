"""Tests for load_run_agent_config: all 4 agent keys overridden by target repo config."""

import pytest

from config.loader import clear_cache
from tests.fast.conftest import _make_sandbox
from utils.run_config import load_run_agent_config


class TestLoadRunAgentConfigFullOverride:
    """All 4 agent keys overridden by target repo config."""

    def setup_method(self) -> None:
        clear_cache()

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
