"""SecurityGate tests — pure check logic, no DB or external deps."""

from tools.security import SecurityGate
from utils.models import RunContext


class TestSecurityGate:
    """Tests for SecurityGate private check methods — pure logic, no DB."""

    def _make_gate(self) -> SecurityGate:
        ctx = RunContext(
            run_id="test-run", agent_role="worker",
            branch_name="test-branch", base_branch="main",
            duration_minutes=30, github_repo="owner/repo",
        )
        return SecurityGate(ctx)

    # ── File tool: credential blocking ──

    def test_file_tool_blocks_dotenv(self):
        gate = self._make_gate()
        result = gate._check_file_tool({"file_path": "/workspace/repo/.env"})
        assert result is not None
        assert "credential" in result.lower()

    def test_file_tool_blocks_dotenv_with_extension(self):
        gate = self._make_gate()
        result = gate._check_file_tool({"file_path": "/workspace/repo/.env.local"})
        assert result is not None

    def test_file_tool_blocks_credentials_json(self):
        gate = self._make_gate()
        result = gate._check_file_tool({"file_path": "/workspace/repo/credentials.json"})
        assert result is not None

    def test_file_tool_blocks_pem_file(self):
        gate = self._make_gate()
        result = gate._check_file_tool({"file_path": "/workspace/certs/server.pem"})
        assert result is not None

    def test_file_tool_blocks_key_file(self):
        gate = self._make_gate()
        result = gate._check_file_tool({"file_path": "/workspace/config/deploy.key"})
        assert result is not None

    def test_file_tool_blocks_secret_file(self):
        gate = self._make_gate()
        result = gate._check_file_tool({"file_path": "/workspace/config/secret.json"})
        assert result is not None

    def test_file_tool_blocks_id_rsa(self):
        gate = self._make_gate()
        result = gate._check_file_tool({"file_path": "/home/agentuser/.ssh/id_rsa"})
        assert result is not None

    def test_file_tool_blocks_ssh_directory(self):
        gate = self._make_gate()
        result = gate._check_file_tool({"file_path": "/home/agentuser/.ssh/known_hosts"})
        assert result is not None

    def test_file_tool_blocks_npmrc(self):
        gate = self._make_gate()
        result = gate._check_file_tool({"file_path": "/workspace/.npmrc"})
        assert result is not None

    def test_file_tool_blocks_docker_config(self):
        gate = self._make_gate()
        result = gate._check_file_tool({"file_path": "/home/agentuser/.docker/config.json"})
        assert result is not None

    # ── File tool: path confinement ──

    def test_file_tool_blocks_etc_passwd(self):
        gate = self._make_gate()
        result = gate._check_file_tool({"file_path": "/etc/passwd"})
        assert result is not None
        assert "outside allowed" in result

    def test_file_tool_blocks_root_path(self):
        gate = self._make_gate()
        result = gate._check_file_tool({"file_path": "/root/.bashrc"})
        assert result is not None

    def test_file_tool_blocks_proc_path(self):
        gate = self._make_gate()
        result = gate._check_file_tool({"file_path": "/proc/version"})
        assert result is not None

    def test_file_tool_blocks_var_path(self):
        gate = self._make_gate()
        result = gate._check_file_tool({"file_path": "/var/log/syslog"})
        assert result is not None

    # ── File tool: allowed paths ──

    def test_file_tool_allows_workspace_path(self):
        gate = self._make_gate()
        result = gate._check_file_tool({"file_path": "/workspace/repo/main.py"})
        assert result is None

    def test_file_tool_allows_home_agentuser_path(self):
        gate = self._make_gate()
        result = gate._check_file_tool({"file_path": "/home/agentuser/repo/buddy/utils/constants.py"})
        assert result is None

    def test_file_tool_allows_tmp_path(self):
        gate = self._make_gate()
        result = gate._check_file_tool({"file_path": "/tmp/current-spec.md"})
        assert result is None

    def test_file_tool_allows_path_key_in_input(self):
        """Glob and Grep use 'path' rather than 'file_path'."""
        gate = self._make_gate()
        result = gate._check_file_tool({"path": "/workspace/repo/src"})
        assert result is None

    def test_file_tool_allows_missing_path_key(self):
        """Some tools may omit the path key entirely — should not block."""
        gate = self._make_gate()
        result = gate._check_file_tool({})
        assert result is None

    # ── Bash: token exposure ──

    def test_bash_blocks_echo_git_token(self):
        gate = self._make_gate()
        result = gate._check_bash("echo $GIT_TOKEN")
        assert result is not None
        assert "credential" in result.lower()

    def test_bash_blocks_echo_anthropic_api_key(self):
        gate = self._make_gate()
        result = gate._check_bash("echo $ANTHROPIC_API_KEY")
        assert result is not None

    def test_bash_blocks_echo_gh_token_braces(self):
        gate = self._make_gate()
        result = gate._check_bash("echo ${GH_TOKEN}")
        assert result is not None

    def test_bash_blocks_cat_dotenv(self):
        gate = self._make_gate()
        result = gate._check_bash("cat /workspace/.env")
        assert result is not None

    def test_bash_blocks_printenv_git_token(self):
        gate = self._make_gate()
        result = gate._check_bash("printenv GIT_TOKEN")
        assert result is not None

    def test_bash_blocks_bare_printenv(self):
        gate = self._make_gate()
        result = gate._check_bash("printenv")
        assert result is not None

    def test_bash_blocks_bare_env(self):
        gate = self._make_gate()
        result = gate._check_bash("env")
        assert result is not None

    def test_bash_blocks_bare_set(self):
        gate = self._make_gate()
        result = gate._check_bash("set")
        assert result is not None

    def test_bash_blocks_bare_export(self):
        gate = self._make_gate()
        result = gate._check_bash("export")
        assert result is not None

    # ── Bash: dangerous commands ──

    def test_bash_blocks_rm_rf_root(self):
        gate = self._make_gate()
        result = gate._check_bash("rm -rf /")
        assert result is not None
        assert "dangerous" in result.lower()

    def test_bash_blocks_mkfs(self):
        gate = self._make_gate()
        result = gate._check_bash("mkfs.ext4 /dev/sda1")
        assert result is not None

    def test_bash_blocks_dd_to_device(self):
        gate = self._make_gate()
        result = gate._check_bash("dd if=/dev/zero of=/dev/sda")
        assert result is not None

    # ── Bash: branch creation ──

    def test_bash_blocks_git_checkout_b(self):
        gate = self._make_gate()
        result = gate._check_bash("git checkout -b new-feature")
        assert result is not None
        assert "branch" in result.lower()

    def test_bash_blocks_git_switch_c(self):
        gate = self._make_gate()
        result = gate._check_bash("git switch -c new-feature")
        assert result is not None

    def test_bash_blocks_git_branch_newname(self):
        gate = self._make_gate()
        result = gate._check_bash("git branch my-new-branch")
        assert result is not None

    def test_bash_blocks_git_switch_to_branch(self):
        gate = self._make_gate()
        result = gate._check_bash("git switch main")
        assert result is not None

    def test_bash_blocks_git_checkout_branch(self):
        gate = self._make_gate()
        result = gate._check_bash("git checkout main")
        assert result is not None

    def test_bash_blocks_git_clean_force(self):
        gate = self._make_gate()
        result = gate._check_bash("git clean -fd")
        assert result is not None

    # ── Bash: allowed git operations ──

    def test_bash_allows_git_status(self):
        gate = self._make_gate()
        result = gate._check_bash("git status")
        assert result is None

    def test_bash_allows_git_diff(self):
        gate = self._make_gate()
        result = gate._check_bash("git diff HEAD")
        assert result is None

    def test_bash_allows_git_log(self):
        gate = self._make_gate()
        result = gate._check_bash("git log --oneline -10")
        assert result is None

    def test_bash_allows_git_add(self):
        gate = self._make_gate()
        result = gate._check_bash("git add -A")
        assert result is None

    def test_bash_allows_git_commit(self):
        gate = self._make_gate()
        result = gate._check_bash("git commit -m 'fix: improve error handling'")
        assert result is None

    def test_bash_allows_git_branch_list_flag(self):
        """git branch -a and similar list flags should be permitted."""
        gate = self._make_gate()
        result = gate._check_bash("git branch -a")
        assert result is None

    def test_bash_allows_git_checkout_file_revert(self):
        """git checkout -- <file> is a safe file revert, not branch switching."""
        gate = self._make_gate()
        result = gate._check_bash("git checkout -- src/main.py")
        assert result is None

    # ── Bash: git clone ──

    def test_bash_blocks_git_clone_other_repo(self):
        gate = self._make_gate()
        result = gate._check_bash("git clone https://github.com/evil/repo.git")
        assert result is not None
        assert "clone" in result.lower() or "repositor" in result.lower()

    def test_bash_allows_git_clone_configured_repo(self):
        gate = self._make_gate()
        result = gate._check_bash("git clone https://github.com/owner/repo.git")
        assert result is None

    # ── Bash: cd restrictions ──

    def test_bash_blocks_cd_to_etc(self):
        gate = self._make_gate()
        result = gate._check_bash("cd /etc")
        assert result is not None
        assert "confined" in result.lower() or "workspace" in result.lower()

    def test_bash_blocks_cd_to_root(self):
        gate = self._make_gate()
        result = gate._check_bash("cd /root")
        assert result is not None

    def test_bash_blocks_cd_to_home_other_user(self):
        gate = self._make_gate()
        result = gate._check_bash("cd /home/otheruser")
        assert result is not None

    def test_bash_allows_cd_to_workspace(self):
        gate = self._make_gate()
        result = gate._check_bash("cd /workspace/repo")
        assert result is None

    def test_bash_allows_cd_to_workspace_subdir(self):
        gate = self._make_gate()
        result = gate._check_bash("cd /workspace/repo/dashboard/frontend")
        assert result is None

    def test_bash_allows_cd_to_tmp(self):
        gate = self._make_gate()
        result = gate._check_bash("cd /tmp")
        assert result is None

    def test_bash_allows_relative_cd(self):
        """Relative cd paths don't start with / and should not be blocked."""
        gate = self._make_gate()
        result = gate._check_bash("cd src/components")
        assert result is None
