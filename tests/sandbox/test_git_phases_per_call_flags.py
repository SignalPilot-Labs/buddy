"""F5: _git prepends PER_CALL_GIT_CONFIG_FLAGS between 'git' and the subcommand."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from constants import PER_CALL_GIT_CONFIG_FLAGS
from handlers.repo_env import clear_git_token, set_git_token
from handlers.repo_phases import _git, _gh


class TestGitPerCallFlags:
    """PER_CALL_GIT_CONFIG_FLAGS must be prepended to every _git call."""

    def setup_method(self) -> None:
        clear_git_token()
        set_git_token("test-token")

    def teardown_method(self) -> None:
        clear_git_token()

    @pytest.mark.asyncio
    async def test_git_fetch_has_per_call_flags(self) -> None:
        captured_args: list[list[str]] = []

        async def fake_exec(*args, **kwargs):
            captured_args.append(list(args))
            proc = MagicMock()
            proc.communicate = AsyncMock(return_value=(b"", b""))
            proc.returncode = 0
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            await _git(["fetch", "origin"], timeout=10, with_token=True)

        assert len(captured_args) == 1
        argv = captured_args[0]
        assert argv[0] == "git"
        # PER_CALL_GIT_CONFIG_FLAGS should appear before "fetch"
        flags_list = list(PER_CALL_GIT_CONFIG_FLAGS)
        fetch_idx = argv.index("fetch")
        # Flags start at index 1 (after "git")
        assert argv[1:fetch_idx] == flags_list

    @pytest.mark.asyncio
    async def test_git_push_has_per_call_flags(self) -> None:
        captured_args: list[list[str]] = []

        async def fake_exec(*args, **kwargs):
            captured_args.append(list(args))
            proc = MagicMock()
            proc.communicate = AsyncMock(return_value=(b"", b""))
            proc.returncode = 0
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            await _git(["push", "-u", "origin", "HEAD"], timeout=10, with_token=True)

        assert len(captured_args) == 1
        argv = captured_args[0]
        assert argv[0] == "git"
        flags_list = list(PER_CALL_GIT_CONFIG_FLAGS)
        push_idx = argv.index("push")
        assert argv[1:push_idx] == flags_list

    @pytest.mark.asyncio
    async def test_gh_does_not_get_per_call_flags(self) -> None:
        """_gh must NOT prepend PER_CALL_GIT_CONFIG_FLAGS — gh handles git internally."""
        captured_args: list[list[str]] = []

        async def fake_exec(*args, **kwargs):
            captured_args.append(list(args))
            proc = MagicMock()
            proc.communicate = AsyncMock(return_value=(b"", b""))
            proc.returncode = 0
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            await _gh(["pr", "list"], timeout=10)

        assert len(captured_args) == 1
        argv = captured_args[0]
        assert argv[0] == "gh"
        # No -c flags should appear in a gh call
        assert "-c" not in argv

    @pytest.mark.asyncio
    async def test_per_call_flags_include_credential_helper(self) -> None:
        """credential.helper must be in PER_CALL_GIT_CONFIG_FLAGS."""
        flags_str = " ".join(PER_CALL_GIT_CONFIG_FLAGS)
        assert "credential.helper" in flags_str

    def test_per_call_flags_include_include_path(self) -> None:
        """include.path=/dev/null must be in PER_CALL_GIT_CONFIG_FLAGS."""
        flags_str = " ".join(PER_CALL_GIT_CONFIG_FLAGS)
        assert "include.path=/dev/null" in flags_str

    def test_per_call_flags_include_ssh_command(self) -> None:
        """core.sshCommand=/bin/false must be in PER_CALL_GIT_CONFIG_FLAGS."""
        flags_str = " ".join(PER_CALL_GIT_CONFIG_FLAGS)
        assert "core.sshCommand=/bin/false" in flags_str

    def test_per_call_flags_include_protocol_ext(self) -> None:
        """protocol.ext.allow=never must be in PER_CALL_GIT_CONFIG_FLAGS."""
        flags_str = " ".join(PER_CALL_GIT_CONFIG_FLAGS)
        assert "protocol.ext.allow=never" in flags_str
