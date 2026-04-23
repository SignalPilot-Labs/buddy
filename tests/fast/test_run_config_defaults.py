"""Tests for load_run_agent_config: no target-repo config uses base config defaults."""

import pytest

from config.loader import clear_cache
from tests.fast.conftest import _make_sandbox
from utils.run_config import RunAgentConfig, load_run_agent_config


class TestLoadRunAgentConfigDefaults:
    """No target-repo config -> base config defaults apply."""

    def setup_method(self) -> None:
        clear_cache()

    @pytest.mark.asyncio
    async def test_no_config_file_uses_defaults(self) -> None:
        sandbox = _make_sandbox(read_return=None)
        result = await load_run_agent_config(sandbox)

        assert isinstance(result, RunAgentConfig)
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
