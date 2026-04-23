"""Tests for load_run_agent_config: config file exists but has no agent section."""

import pytest

from config.loader import clear_cache
from tests.fast.conftest import _make_sandbox
from utils.run_config import load_run_agent_config


class TestLoadRunAgentConfigNoAgentSection:
    """Config file exists but has no `agent` section -> base config used."""

    def setup_method(self) -> None:
        clear_cache()

    @pytest.mark.asyncio
    async def test_no_agent_section_in_config(self) -> None:
        yaml_content = "sandbox:\n  url: http://custom-sandbox:9090\n"
        sandbox = _make_sandbox(read_return=yaml_content)
        result = await load_run_agent_config(sandbox)

        assert result.max_rounds == 128
        assert result.tool_call_timeout_sec == 3600

    @pytest.mark.asyncio
    async def test_empty_yaml_content_uses_defaults(self) -> None:
        sandbox = _make_sandbox(read_return="")
        result = await load_run_agent_config(sandbox)

        assert result.max_rounds == 128
        assert result.tool_call_timeout_sec == 3600
