"""Tests for render_environment and its host-mounts helper.

The environment query is prepended to every orchestrator and subagent
prompt, so its substitution logic is load-bearing. These tests pin the
placeholder contract so future refactors of `prompts/loader.py` can't
silently break host-mount rendering or timeout substitution.
"""

from prompts.loader import _host_mounts_block, _user_env_block, render_environment


class TestHostMountsBlock:
    """_host_mounts_block renders a bullet list or empty string."""

    def test_none_returns_empty_string(self) -> None:
        assert _host_mounts_block(None) == ""

    def test_empty_list_returns_empty_string(self) -> None:
        assert _host_mounts_block([]) == ""

    def test_ro_mode_renders_as_read_only(self) -> None:
        out = _host_mounts_block([{"container_path": "/data", "mode": "ro"}])
        assert "`/data` (read-only)" in out
        assert out.startswith("Host mounts:")

    def test_rw_mode_renders_as_read_write(self) -> None:
        out = _host_mounts_block([{"container_path": "/cache", "mode": "rw"}])
        assert "`/cache` (read-write)" in out

    def test_missing_mode_defaults_to_ro(self) -> None:
        # Agents shouldn't assume write access if mode is omitted.
        out = _host_mounts_block([{"container_path": "/foo"}])
        assert "(read-only)" in out

    def test_multiple_mounts_are_listed_in_order(self) -> None:
        out = _host_mounts_block([
            {"container_path": "/a", "mode": "rw"},
            {"container_path": "/b", "mode": "ro"},
        ])
        lines = out.splitlines()
        assert lines[0] == "Host mounts:"
        assert lines[1] == "- `/a` (read-write)"
        assert lines[2] == "- `/b` (read-only)"


class TestUserEnvBlock:
    """_user_env_block renders env var names or empty string."""

    def test_empty_keys_returns_empty(self) -> None:
        assert _user_env_block([]) == ""

    def test_single_key(self) -> None:
        result = _user_env_block(["MY_API_KEY"])
        assert "`MY_API_KEY`" in result
        assert "User-provided" in result

    def test_multiple_keys(self) -> None:
        result = _user_env_block(["FOO", "BAR"])
        assert "`FOO`" in result
        assert "`BAR`" in result


class TestRenderEnvironment:
    """render_environment substitutes all placeholders."""

    def test_substitutes_round_number(self) -> None:
        out = render_environment(round_number=7, tool_call_timeout_min=60, host_mounts=None, user_env_keys=[])
        assert "/tmp/round-7/" in out
        assert "{ROUND_NUMBER}" not in out

    def test_substitutes_tool_call_timeout(self) -> None:
        out = render_environment(round_number=1, tool_call_timeout_min=42, host_mounts=None, user_env_keys=[])
        assert "42 min" in out
        assert "{TOOL_CALL_TIMEOUT_MIN}" not in out

    def test_no_host_mounts_placeholder_removed(self) -> None:
        out = render_environment(round_number=1, tool_call_timeout_min=60, host_mounts=None, user_env_keys=[])
        assert "{HOST_MOUNTS_BLOCK}" not in out
        assert "Host mounts:" not in out

    def test_host_mounts_rendered_inline(self) -> None:
        out = render_environment(
            round_number=1,
            tool_call_timeout_min=60,
            host_mounts=[{"container_path": "/workspace", "mode": "rw"}],
            user_env_keys=[],
        )
        assert "Host mounts:" in out
        assert "`/workspace` (read-write)" in out

    def test_user_env_keys_rendered(self) -> None:
        out = render_environment(
            round_number=1,
            tool_call_timeout_min=60,
            host_mounts=None,
            user_env_keys=["CUSTOM_TOKEN", "DB_URL"],
        )
        assert "`CUSTOM_TOKEN`" in out
        assert "`DB_URL`" in out
        assert "{USER_ENV_BLOCK}" not in out

    def test_no_user_env_placeholder_removed(self) -> None:
        out = render_environment(round_number=1, tool_call_timeout_min=60, host_mounts=None, user_env_keys=[])
        assert "{USER_ENV_BLOCK}" not in out
