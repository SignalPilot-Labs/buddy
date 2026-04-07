"""Tests for SecurityGate tool-access controls in the sandbox."""

from session.security import SecurityGate


REPO = "owner/test-repo"
BRANCH = "autofyn/2026-04-07-abc123"

def _make_gate() -> SecurityGate:
    """Build a SecurityGate with standard test config."""
    return SecurityGate(REPO, BRANCH)


class TestSecurityGate:
    """Comprehensive tests for SecurityGate access controls."""

    # ── Credential file blocking ──

    def test_blocks_env_file(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Read", {"file_path": "/workspace/.env"})
        assert result is not None
        assert "credential" in result.lower()

    def test_blocks_pem_file(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Write", {"file_path": "/workspace/cert.pem"})
        assert result is not None
        assert "credential" in result.lower()

    def test_blocks_key_file(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Edit", {"file_path": "/workspace/server.key"})
        assert result is not None
        assert "credential" in result.lower()

    def test_blocks_ssh_directory(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Read", {"file_path": "/workspace/.ssh/id_rsa"})
        assert result is not None
        assert "credential" in result.lower()

    def test_blocks_id_rsa(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Read", {"file_path": "/workspace/id_rsa"})
        assert result is not None
        assert "credential" in result.lower()

    def test_blocks_credentials_json(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Read", {"file_path": "/workspace/credentials.json"})
        assert result is not None
        assert "credential" in result.lower()

    def test_blocks_secrets_file(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Read", {"file_path": "/workspace/.secrets"})
        assert result is not None
        assert "credential" in result.lower()

    # ── Non-credential paths are allowed (no path confinement in sandbox) ──

    def test_allows_any_non_credential_path(self) -> None:
        gate = _make_gate()
        assert gate.check_permission("Read", {"file_path": "/etc/passwd"}) is None
        assert gate.check_permission("Read", {"file_path": "/home/user/.bashrc"}) is None
        assert gate.check_permission("Write", {"file_path": "/tmp/scratch.txt"}) is None
        assert gate.check_permission("Glob", {"path": "/workspace/src"}) is None
        assert gate.check_permission("Grep", {"pattern": "TODO"}) is None

    # ── Git branch creation blocking ──

    def test_blocks_checkout_b(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "git checkout -b feature-x"})
        assert result is not None
        assert "create branches" in result.lower()

    def test_blocks_switch_c(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "git switch -c new-branch"})
        assert result is not None
        assert "create branches" in result.lower()

    def test_blocks_git_branch_create(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "git branch my-feature"})
        assert result is not None
        assert "create branches" in result.lower()

    # ── Git branch switching blocking ──

    def test_blocks_git_switch(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "git switch main"})
        assert result is not None
        assert "switch branches" in result.lower()

    def test_blocks_git_checkout_branch(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "git checkout main"})
        assert result is not None
        assert "switch branches" in result.lower()

    def test_allows_git_checkout_file_revert(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "git checkout -- src/file.py"})
        assert result is None

    def test_allows_git_checkout_dot(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "git checkout ."})
        assert result is None

    # ── git clean -f blocking ──

    def test_blocks_git_clean_f(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "git clean -f"})
        assert result is not None
        assert "git clean" in result.lower()

    def test_blocks_git_clean_fd(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "git clean -fd"})
        assert result is not None
        assert "git clean" in result.lower()

    def test_blocks_git_clean_xf(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "git clean -xf"})
        assert result is not None
        assert "git clean" in result.lower()

    # ── Git remote modification blocking ──

    def test_blocks_git_remote_add_other_repo(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "git remote add upstream https://github.com/other/repo"})
        assert result is not None
        assert "remote" in result.lower()

    def test_allows_git_remote_with_configured_repo(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": f"git remote add origin https://github.com/{REPO}"})
        assert result is None

    def test_blocks_git_remote_set_url_other(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "git remote set-url origin https://github.com/evil/repo"})
        assert result is not None
        assert "remote" in result.lower()

    # ── Token exposure detection ──

    def test_blocks_echo_git_token(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "echo $GIT_TOKEN"})
        assert result is not None
        assert "credential" in result.lower()

    def test_blocks_echo_gh_token_braces(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "echo ${GH_TOKEN}"})
        assert result is not None
        assert "credential" in result.lower()

    def test_blocks_cat_env(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "cat .env"})
        assert result is not None
        assert "credential" in result.lower()

    def test_blocks_printenv_specific(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "printenv GIT_TOKEN"})
        assert result is not None
        assert "credential" in result.lower()

    def test_blocks_printenv_all(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "printenv"})
        assert result is not None
        assert "credential" in result.lower()

    def test_blocks_env_command(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "env"})
        assert result is not None
        assert "credential" in result.lower()

    def test_blocks_set_command(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "set"})
        assert result is not None
        assert "credential" in result.lower()

    def test_blocks_export_command(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "export"})
        assert result is not None
        assert "credential" in result.lower()

    # ── Dangerous commands are ALLOWED (sandbox is isolated by gVisor) ──

    def test_allows_rm_rf(self) -> None:
        gate = _make_gate()
        assert gate.check_permission("Bash", {"command": "rm -rf / --no-preserve-root"}) is None

    def test_allows_dd(self) -> None:
        gate = _make_gate()
        assert gate.check_permission("Bash", {"command": "dd if=/dev/zero of=/dev/sda bs=1M"}) is None

    # ── Repo exploration blocking ──

    def test_blocks_clone_other_repo(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "git clone https://github.com/evil/repo"})
        assert result is not None
        assert "clone" in result.lower()

    def test_allows_clone_configured_repo(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": f"git clone https://github.com/{REPO}"})
        assert result is None

    def test_blocks_clone_when_no_repo_configured(self) -> None:
        gate = SecurityGate("", BRANCH)
        result = gate.check_permission("Bash", {"command": "git clone https://github.com/any/repo"})
        assert result is not None
        assert "clone" in result.lower()

    # ── cd is ALLOWED everywhere (sandbox is isolated) ──

    def test_allows_cd_anywhere(self) -> None:
        gate = _make_gate()
        assert gate.check_permission("Bash", {"command": "cd /root"}) is None
        assert gate.check_permission("Bash", {"command": "cd /etc"}) is None
        assert gate.check_permission("Bash", {"command": "cd src/components"}) is None

    # ── Allowed commands pass through ──

    def test_allows_npm_test(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "npm test"})
        assert result is None

    def test_allows_git_status(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "git status"})
        assert result is None

    def test_allows_git_diff(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "git diff"})
        assert result is None

    def test_allows_git_log(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "git log --oneline -5"})
        assert result is None

    def test_allows_git_add(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "git add src/main.py"})
        assert result is None

    def test_allows_git_commit(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "git commit -m 'fix bug'"})
        assert result is None

    def test_allows_python_run(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "python main.py"})
        assert result is None

    def test_allows_ls(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "ls -la"})
        assert result is None

    # ── Non-bash tools pass through with valid paths ──

    def test_unknown_tool_passes_through(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("CustomTool", {"data": "anything"})
        assert result is None

    def test_read_valid_path_passes(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Read", {"file_path": "/workspace/README.md"})
        assert result is None

    def test_write_valid_path_passes(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Write", {"file_path": "/workspace/src/app.ts"})
        assert result is None

    def test_edit_valid_path_passes(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Edit", {"file_path": "/tmp/draft.txt"})
        assert result is None

    # ── Git push branch restriction ──

    def test_allows_push_origin_head(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "git push origin HEAD"})
        assert result is None

    def test_allows_push_to_working_branch(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": f"git push origin {BRANCH}"})
        assert result is None

    def test_blocks_push_to_main(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "git push origin main"})
        assert result is not None
        assert "working branch" in result.lower()

    def test_blocks_push_to_other_branch(self) -> None:
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "git push origin some-other-branch"})
        assert result is not None
        assert "working branch" in result.lower()

    def test_blocks_push_when_no_branch_configured(self) -> None:
        gate = SecurityGate(REPO, "")
        result = gate.check_permission("Bash", {"command": "git push origin HEAD"})
        assert result is not None
        assert "blocked" in result.lower()
