"""Tests for load_run_agent_config: values from untrusted repo config are clamped."""

import pytest

from config.loader import clear_cache
from tests.fast.conftest import _make_sandbox
from utils.run_config import load_run_agent_config


class TestLoadRunAgentConfigClamping:
    """Values from untrusted repo config are clamped to safe bounds."""

    def setup_method(self) -> None:
        clear_cache()

    @pytest.mark.asyncio
    async def test_max_rounds_clamped(self) -> None:
        yaml_content = "agent:\n  max_rounds: 999999\n"
        sandbox = _make_sandbox(read_return=yaml_content)
        result = await load_run_agent_config(sandbox)
        assert result.max_rounds == 512

    @pytest.mark.asyncio
    async def test_subagent_idle_kill_sec_clamped_to_min(self) -> None:
        yaml_content = "agent:\n  subagent_idle_kill_sec: 0\n"
        sandbox = _make_sandbox(read_return=yaml_content)
        result = await load_run_agent_config(sandbox)
        assert result.subagent_idle_kill_sec == 60
