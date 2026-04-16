"""F5: SecurityGate blocks Write/Edit to git config files.

CONFIG_WRITE_PATTERNS covers .gitconfig, .git/config, .git/hooks/, and
.git/modules/*/config. This is a belt defense; env-layer isolation (F5) is
the structural closure.
"""

import pytest

from session.security import SecurityGate


REPO = "owner/test-repo"
BRANCH = "autofyn/2026-04-07-abc123"


def _make_gate() -> SecurityGate:
    return SecurityGate(REPO, BRANCH)


class TestConfigWritePatterns:
    """Git config file writes must be blocked for Write, Edit, Grep, Glob tools."""

    @pytest.mark.parametrize("tool,input_data", [
        ("Write", {"file_path": "/home/agentuser/.gitconfig"}),
        ("Edit", {"file_path": "/home/agentuser/.gitconfig"}),
        ("Write", {"file_path": "/home/agentuser/repo/.git/config"}),
        ("Edit", {"file_path": "/home/agentuser/repo/.git/config"}),
        ("Write", {"file_path": "/home/agentuser/repo/.git/hooks/pre-commit"}),
        ("Edit", {"file_path": "/home/agentuser/repo/.git/hooks/post-commit"}),
        ("Write", {"file_path": "/home/agentuser/.git/modules/sub/config"}),
        ("Edit", {"file_path": "/home/agentuser/.git/modules/sub/config"}),
    ])
    def test_git_config_paths_blocked(self, tool: str, input_data: dict) -> None:
        gate = _make_gate()
        result = gate.check_permission(tool, input_data)
        assert result is not None, f"{tool} to {input_data} should be denied"

    @pytest.mark.parametrize("tool,input_data", [
        ("Write", {"file_path": "/home/agentuser/repo/README.md"}),
        ("Edit", {"file_path": "/home/agentuser/repo/src/main.py"}),
        ("Write", {"file_path": "/tmp/output.txt"}),
        ("Read", {"file_path": "/home/agentuser/repo/.git/config"}),
    ])
    def test_non_config_write_allowed(self, tool: str, input_data: dict) -> None:
        gate = _make_gate()
        result = gate.check_permission(tool, input_data)
        assert result is None, f"{tool} to {input_data} should be allowed"

    def test_gitconfig_in_nested_path_blocked(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Write", {"file_path": "/tmp/.gitconfig"})
        assert result is not None

    def test_gitconfig_dot_bak_blocked(self) -> None:
        """Pattern covers .gitconfig with a dot suffix."""
        gate = _make_gate()
        result = gate.check_permission("Write", {"file_path": "/home/user/.gitconfig.bak"})
        assert result is not None
