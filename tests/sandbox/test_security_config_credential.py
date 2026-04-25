"""Regression tests for CRIT-4: SecurityGate must block access to
/opt/autofyn/config/ (contains DB password in config.yml).
"""

from session.security import SecurityGate


REPO = "owner/test-repo"
BRANCH = "autofyn/2026-04-07-abc123"


def _make_gate() -> SecurityGate:
    """Build a SecurityGate with standard test config."""
    return SecurityGate(REPO, BRANCH)


class TestSecurityConfigCredential:
    """Verify SecurityGate blocks Read/Write/Edit/Grep/Glob to /opt/autofyn/config/."""

    # ── Read blocks ──

    def test_blocks_read_config_yml(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Read", {"file_path": "/opt/autofyn/config/config.yml"})
        assert result is not None
        assert "credential" in result.lower()

    def test_blocks_read_config_yaml(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Read", {"file_path": "/opt/autofyn/config/config.yaml"})
        assert result is not None
        assert "credential" in result.lower()

    def test_blocks_read_any_file_in_config_dir(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Read", {"file_path": "/opt/autofyn/config/other.conf"})
        assert result is not None
        assert "credential" in result.lower()

    # ── Write blocks ──

    def test_blocks_write_config_yml(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Write", {"file_path": "/opt/autofyn/config/config.yml"})
        assert result is not None
        assert "credential" in result.lower()

    # ── Edit blocks ──

    def test_blocks_edit_config_yml(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Edit", {"file_path": "/opt/autofyn/config/config.yml"})
        assert result is not None
        assert "credential" in result.lower()

    # ── Grep blocks ──

    def test_blocks_grep_in_config_dir(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Grep", {"path": "/opt/autofyn/config/config.yml"})
        assert result is not None
        assert "credential" in result.lower()

    # ── Glob blocks ──

    def test_blocks_glob_in_config_dir(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Glob", {"path": "/opt/autofyn/config/"})
        assert result is not None
        assert "credential" in result.lower()

    # ── Bash bypass prevention ──

    def test_blocks_bash_cat_config_yml(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "cat /opt/autofyn/config/config.yml"})
        assert result is not None

    def test_blocks_bash_head_config_yml(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "head -n 20 /opt/autofyn/config/config.yml"})
        assert result is not None

    def test_blocks_bash_grep_config_dir(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "grep password /opt/autofyn/config/config.yml"})
        assert result is not None

    def test_blocks_bash_python_open_config(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "python3 -c \"print(open('/opt/autofyn/config/config.yml').read())\""})
        assert result is not None

    # ── Glob trailing-slash bypass prevention ──

    def test_blocks_glob_config_dir_no_trailing_slash(self) -> None:
        """Glob with path='/opt/autofyn/config' (no trailing slash) must also be blocked."""
        gate = _make_gate()
        result = gate.check_permission("Glob", {"path": "/opt/autofyn/config"})
        assert result is not None

    # ── Unrelated config files must still be accessible ──

    def test_allows_config_yml_in_repo(self) -> None:
        """User repos legitimately contain config.yml — must not be blocked."""
        gate = _make_gate()
        result = gate.check_permission("Read", {"file_path": "/home/agentuser/repo/myapp/config.yml"})
        assert result is None

    def test_allows_config_yml_in_tmp(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Read", {"file_path": "/tmp/config.yml"})
        assert result is None

    def test_allows_config_yml_in_workspace(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Read", {"file_path": "/workspace/config/config.yml"})
        assert result is None

    def test_allows_other_opt_autofyn_paths(self) -> None:
        """Other /opt/autofyn/ paths not under config/ remain accessible."""
        gate = _make_gate()
        result = gate.check_permission("Read", {"file_path": "/opt/autofyn/sandbox/app.py"})
        assert result is None
