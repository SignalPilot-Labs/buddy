"""Regression tests for SecurityGate git remote subcommand filtering.

Read-only commands like `git remote -v` and `git remote show` must be allowed.
Write subcommands like `git remote add` and `git remote set-url` must be blocked
when the target repo is not the configured repo.
"""

from sdk.security import SecurityGate


REPO = "owner/repo"
BRANCH = "autofyn/2026-04-26-abc123"


def _make_gate() -> SecurityGate:
    """Build a SecurityGate with standard test config."""
    return SecurityGate(REPO, BRANCH)


class TestSecurityGitRemote:
    """Verify git remote write subcommands are blocked, read-only allowed."""

    def test_git_remote_v_allowed(self) -> None:
        """`git remote -v` must be allowed — it is read-only."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "git remote -v"})
        assert result is None

    def test_git_remote_show_origin_allowed(self) -> None:
        """`git remote show origin` must be allowed — it is read-only."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "git remote show origin"})
        assert result is None

    def test_git_remote_get_url_allowed(self) -> None:
        """`git remote get-url origin` must be allowed — it is read-only."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "git remote get-url origin"})
        assert result is None

    def test_git_remote_add_blocked_wrong_repo(self) -> None:
        """`git remote add evil <url>` must be blocked when repo is configured."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash", {"command": "git remote add evil https://evil.com"}
        )
        assert result is not None
        assert REPO in result

    def test_git_remote_set_url_blocked_wrong_repo(self) -> None:
        """`git remote set-url origin <other>` must be blocked."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash", {"command": "git remote set-url origin https://other.com"}
        )
        assert result is not None
        assert REPO in result

    def test_git_remote_add_allowed_correct_repo(self) -> None:
        """`git remote add origin https://github.com/owner/repo` must be allowed."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash",
            {"command": f"git remote add origin https://github.com/{REPO}"},
        )
        assert result is None

    def test_git_remote_remove_blocked(self) -> None:
        """`git remote remove origin` must be blocked when repo is not in command."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash", {"command": "git remote remove origin"}
        )
        assert result is not None
        assert REPO in result
