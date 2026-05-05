"""Tests for Session._check_mcp_status warning emission.

Uses subprocess isolation to avoid polluting sys.modules for other tests.
The Claude SDK requires native deps not available in the test env, so we
stub it before importing Session.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap


def _run_mcp_test(test_code: str) -> None:
    """Run a test snippet in a subprocess to avoid module pollution."""
    script = textwrap.dedent("""
    import sys, asyncio
    from unittest.mock import AsyncMock, MagicMock

    # Stub only the Claude SDK
    sys.modules["claude_agent_sdk"] = MagicMock()
    sys.modules["claude_agent_sdk.types"] = MagicMock()

    from sdk.session import Session

    def _make_session():
        return Session(session_id="test-session", options_dict={"run_id": "test-run"})

    def _drain_events(s):
        return list(s.event_log._events)

    async def _test():
    """) + textwrap.indent(test_code, "        ") + textwrap.dedent("""

    asyncio.run(_test())
    print("PASS")
    """)
    repo_root = str(__import__("pathlib").Path(__file__).parent.parent.parent)
    sandbox_dir = repo_root + "/sandbox"
    env = {**__import__("os").environ, "PYTHONPATH": sandbox_dir + ":" + repo_root}
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, timeout=10,
        cwd=sandbox_dir, env=env,
    )
    if result.returncode != 0:
        raise AssertionError(f"Test failed:\nstdout: {result.stdout}\nstderr: {result.stderr}")
    assert "PASS" in result.stdout


class TestCheckMcpStatusEmitsWarnings:
    """_check_mcp_status must emit mcp_warning events for failed servers."""

    def test_failed_server_emits_warning(self) -> None:
        _run_mcp_test("""
s = _make_session()
client = AsyncMock()
client.get_mcp_status = AsyncMock(return_value={
    "mcpServers": [{"name": "bad-server", "status": "failed", "error": "ENOENT"}],
})
await s._check_mcp_status(client)
events = _drain_events(s)
assert len(events) == 1
assert events[0].event == "mcp_warning"
assert "bad-server" in events[0].data["message"]
assert "ENOENT" in events[0].data["message"]
""")

    def test_connected_server_no_warning(self) -> None:
        _run_mcp_test("""
s = _make_session()
client = AsyncMock()
client.get_mcp_status = AsyncMock(return_value={
    "mcpServers": [{"name": "good-server", "status": "connected"}],
})
await s._check_mcp_status(client)
assert len(_drain_events(s)) == 0
""")

    def test_multiple_failures(self) -> None:
        _run_mcp_test("""
s = _make_session()
client = AsyncMock()
client.get_mcp_status = AsyncMock(return_value={
    "mcpServers": [
        {"name": "a", "status": "failed", "error": "err-a"},
        {"name": "b", "status": "connected"},
        {"name": "c", "status": "failed", "error": "err-c"},
    ],
})
await s._check_mcp_status(client)
events = _drain_events(s)
assert len(events) == 2
assert "a" in events[0].data["message"]
assert "c" in events[1].data["message"]
""")

    def test_get_mcp_status_exception_swallowed(self) -> None:
        _run_mcp_test("""
s = _make_session()
client = AsyncMock()
client.get_mcp_status = AsyncMock(side_effect=RuntimeError("not supported"))
await s._check_mcp_status(client)
assert len(_drain_events(s)) == 0
""")

    def test_empty_mcp_servers_no_warning(self) -> None:
        _run_mcp_test("""
s = _make_session()
client = AsyncMock()
client.get_mcp_status = AsyncMock(return_value={"mcpServers": []})
await s._check_mcp_status(client)
assert len(_drain_events(s)) == 0
""")

    def test_failed_server_without_error_field(self) -> None:
        _run_mcp_test("""
s = _make_session()
client = AsyncMock()
client.get_mcp_status = AsyncMock(return_value={
    "mcpServers": [{"name": "no-err", "status": "failed"}],
})
await s._check_mcp_status(client)
events = _drain_events(s)
assert len(events) == 1
assert "connection failed" in events[0].data["message"]
""")
