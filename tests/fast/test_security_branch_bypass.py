"""Regression tests for SecurityGate branch creation bypass variants.

Covers the case-insensitive flag variants that were previously unblocked:
  git checkout -B  (force-reset branch)
  git switch -C    (force-create branch)
  git switch --force-create  (long-form force-create)
"""

from sdk.security import SecurityGate


REPO = "owner/test-repo"
BRANCH = "autofyn/2026-04-07-abc123"
DENY_MSG = "create branches"


def _make_gate() -> SecurityGate:
    """Build a SecurityGate with standard test config."""
    return SecurityGate(REPO, BRANCH)


class TestSecurityBranchCreationBypass:
    """Verify that all branch-creation variants are blocked."""

    def test_blocks_checkout_uppercase_B(self) -> None:
        """git checkout -B force-branch must be blocked."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "git checkout -B force-branch"})
        assert result is not None
        assert DENY_MSG in result

    def test_blocks_checkout_uppercase_B_with_start_point(self) -> None:
        """git checkout -B force-branch origin/main must be blocked."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash", {"command": "git checkout -B force-branch origin/main"}
        )
        assert result is not None
        assert DENY_MSG in result

    def test_blocks_switch_uppercase_C(self) -> None:
        """git switch -C force-branch must be blocked."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "git switch -C force-branch"})
        assert result is not None
        assert DENY_MSG in result

    def test_blocks_switch_uppercase_C_with_start_point(self) -> None:
        """git switch -C force-branch origin/main must be blocked."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash", {"command": "git switch -C force-branch origin/main"}
        )
        assert result is not None
        assert DENY_MSG in result

    def test_blocks_switch_force_create_long(self) -> None:
        """git switch --force-create new-branch must be blocked."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash", {"command": "git switch --force-create new-branch"}
        )
        assert result is not None
        assert DENY_MSG in result

    def test_blocks_switch_force_create_long_with_start_point(self) -> None:
        """git switch --force-create new-branch origin/main must be blocked."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash", {"command": "git switch --force-create new-branch origin/main"}
        )
        assert result is not None
        assert DENY_MSG in result

    def test_blocks_checkout_lowercase_b(self) -> None:
        """git checkout -b new-branch must still be blocked (existing behavior)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "git checkout -b new-branch"})
        assert result is not None
        assert DENY_MSG in result

    def test_blocks_switch_lowercase_c(self) -> None:
        """git switch -c new-branch must still be blocked (existing behavior)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "git switch -c new-branch"})
        assert result is not None
        assert DENY_MSG in result

    def test_allows_checkout_file_revert(self) -> None:
        """git checkout -- src/file.py must be allowed."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "git checkout -- src/file.py"})
        assert result is None

    def test_allows_git_status(self) -> None:
        """git status must be allowed."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "git status"})
        assert result is None

    def test_allows_switch_dash(self) -> None:
        """git switch - (switch to previous branch) passes through the branch-creation check.

        The existing switch-branch rule blocks `git switch <non-dash-starting-word>`,
        but `git switch -` has `-` as the argument which starts with `-` so the
        existing rule `git\\s+switch\\s+(?!-)\\S` does not match. The command is
        therefore not blocked by branch-creation rules.
        """
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "git switch -"})
        # `git switch -` starts with `-` so the existing positive-branch-name rule
        # doesn't catch it. It may or may not be blocked for another reason but it
        # must NOT be blocked by the branch-creation check.
        if result is not None:
            assert DENY_MSG not in result

    def test_blocks_checkout_combined_flags_fB(self) -> None:
        """git checkout -fB force-branch must be blocked (combined flags)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "git checkout -fB force-branch"})
        assert result is not None
        assert DENY_MSG in result

    def test_blocks_checkout_combined_flags_Bf(self) -> None:
        """git checkout -Bf force-branch must be blocked (combined flags, reversed)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "git checkout -Bf force-branch"})
        assert result is not None
        assert DENY_MSG in result

    def test_blocks_switch_combined_flags_fC(self) -> None:
        """git switch -fC force-branch must be blocked (combined flags)."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "git switch -fC force-branch"})
        assert result is not None
        assert DENY_MSG in result
