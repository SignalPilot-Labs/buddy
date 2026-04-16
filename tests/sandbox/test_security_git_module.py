"""Tests for security_git.check_git_config_writes (split module).

Verifies that the git-config write detection logic works correctly after
being extracted to security_git.py.
"""

import pytest

from session.security_git import check_git_config_writes


_DENY_SUBSTRING = "credential"


class TestSecurityGitModule:
    """check_git_config_writes must block credential/helper/sshCommand writes."""

    @pytest.mark.parametrize("cmd", [
        "git config --global credential.helper store",
        "git config credential.https://github.com.helper evil",
        "git config --local credential.helper '!sh -c \"echo $GIT_TOKEN\"'",
        "git config --system credential.helper manager",
        "git config --file /home/agentuser/.gitconfig credential.helper evil",
        "git config core.sshCommand 'ssh -i /tmp/evil'",
        "git config url.https://evil.com.insteadOf https://github.com",
        "git config include.path /tmp/evil.conf",
    ])
    def test_blocked_writes(self, cmd: str) -> None:
        result = check_git_config_writes(cmd)
        assert result is not None, f"Expected deny for: {cmd!r}"
        assert _DENY_SUBSTRING in result

    @pytest.mark.parametrize("cmd", [
        "git config --get user.name",
        "git config --list",
        "git config user.email 'bot@example.com'",
        "git config user.name 'AutoFyn'",
        "git status",
        "git diff",
        "npm test",
    ])
    def test_allowed_commands(self, cmd: str) -> None:
        result = check_git_config_writes(cmd)
        assert result is None, f"Expected allow for: {cmd!r}"

    def test_subshell_git_config_blocked(self) -> None:
        cmd = "echo ok && $(git config --global credential.helper evil)"
        result = check_git_config_writes(cmd)
        assert result is not None

    def test_env_prefix_stripped_then_blocked(self) -> None:
        cmd = "FOO=bar git config --global credential.helper evil"
        result = check_git_config_writes(cmd)
        assert result is not None

    def test_read_flag_allows(self) -> None:
        cmd = "git config --get credential.helper"
        result = check_git_config_writes(cmd)
        assert result is None
