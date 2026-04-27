"""Tests for mcp_servers field in StartRequest and threading through _build_base_session_options."""

from __future__ import annotations

from utils.models_http import StartRequest
from utils.models import RunContext


def _make_run_context() -> RunContext:
    return RunContext(
        run_id="abcd1234-0000-0000-0000-000000000000",
        agent_role="worker",
        github_repo="org/repo",
        branch_name="fix/test",
        base_branch="main",
        duration_minutes=60,
        total_cost=0,
        total_input_tokens=0,
        total_output_tokens=0,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
    )


_SAMPLE_MCP_SERVERS: dict[str, dict] = {
    "my-server": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-github"]},
    "my-sse": {"type": "sse", "url": "http://localhost:3000/sse"},
}


class TestStartRequestMcpServers:
    """StartRequest model accepts and validates mcp_servers field."""

    def test_mcp_servers_none_is_valid(self) -> None:
        """mcp_servers=None (omitted) must be accepted."""
        req = StartRequest(
            prompt="fix the bug",
            max_budget_usd=10.0,
            github_repo="org/repo",
            mcp_servers=None,
        )
        assert req.mcp_servers is None

    def test_mcp_servers_dict_is_accepted(self) -> None:
        """mcp_servers dict must be stored as-is."""
        req = StartRequest(
            prompt="fix the bug",
            max_budget_usd=10.0,
            github_repo="org/repo",
            mcp_servers=_SAMPLE_MCP_SERVERS,
        )
        assert req.mcp_servers == _SAMPLE_MCP_SERVERS

    def test_mcp_servers_omitted_defaults_to_none(self) -> None:
        """mcp_servers not present in request must default to None."""
        req = StartRequest(
            prompt="fix the bug",
            max_budget_usd=10.0,
            github_repo="org/repo",
        )
        assert req.mcp_servers is None

    def test_mcp_servers_empty_dict_accepted(self) -> None:
        """Empty mcp_servers dict must be accepted."""
        req = StartRequest(
            prompt="fix the bug",
            max_budget_usd=10.0,
            github_repo="org/repo",
            mcp_servers={},
        )
        assert req.mcp_servers == {}


class TestBuildBaseSessionOptionsMcpServers:
    """_build_base_session_options includes mcp_servers in returned dict."""

    def test_mcp_servers_included_when_provided(self) -> None:
        """mcp_servers must appear in the options dict under key 'mcp_servers'."""
        from lifecycle.bootstrap import _build_base_session_options

        run = _make_run_context()
        opts = _build_base_session_options(
            run=run,
            model="claude-opus-4-6",
            fallback_model=None,
            max_budget_usd=10.0,
            effort="high",
            run_start_time=0.0,
            mcp_servers=_SAMPLE_MCP_SERVERS,
        )
        assert "mcp_servers" in opts
        assert opts["mcp_servers"] == _SAMPLE_MCP_SERVERS

    def test_mcp_servers_none_when_not_provided(self) -> None:
        """mcp_servers=None must be stored in options so sandbox reads None."""
        from lifecycle.bootstrap import _build_base_session_options

        run = _make_run_context()
        opts = _build_base_session_options(
            run=run,
            model="claude-opus-4-6",
            fallback_model=None,
            max_budget_usd=10.0,
            effort="high",
            run_start_time=0.0,
            mcp_servers=None,
        )
        assert "mcp_servers" in opts
        assert opts["mcp_servers"] is None

    def test_existing_options_keys_still_present(self) -> None:
        """Adding mcp_servers must not remove other required option keys."""
        from lifecycle.bootstrap import _build_base_session_options

        run = _make_run_context()
        opts = _build_base_session_options(
            run=run,
            model="claude-opus-4-6",
            fallback_model=None,
            max_budget_usd=0.0,
            effort="high",
            run_start_time=0.0,
            mcp_servers=None,
        )
        for required_key in ("model", "effort", "cwd", "run_id", "github_repo", "session_gate"):
            assert required_key in opts, f"Expected key '{required_key}' missing from session options"
