"""Regression tests for SecurityGate refspec push detection.

The colon check for blocking refspec pushes must only examine text after
'push' — not the whole command. Commands like:
  git -c http.proxy=http://proxy:8080 push origin HEAD
have a colon before 'push' (in the git config value) but are NOT refspec
pushes and must be allowed.
"""

from session.security import SecurityGate


REPO = "owner/test-repo"
BRANCH = "autofyn/2026-04-07-abc123"


def _make_gate() -> SecurityGate:
    """Build a SecurityGate with standard test config."""
    return SecurityGate(REPO, BRANCH)


class TestSecurityPushRefspec:
    """Verify refspec detection is scoped to push arguments only."""

    def test_blocks_refspec_push_head_to_main(self) -> None:
        """git push origin HEAD:main must still be blocked."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "git push origin HEAD:main"})
        assert result is not None
        assert "refspec" in result.lower()

    def test_blocks_refspec_push_head_to_refs(self) -> None:
        """git push origin HEAD:refs/heads/main must still be blocked."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash", {"command": "git push origin HEAD:refs/heads/main"}
        )
        assert result is not None
        assert "refspec" in result.lower()

    def test_blocks_refspec_push_branch_to_branch(self) -> None:
        """git push origin feature:main must still be blocked."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "git push origin feature:main"})
        assert result is not None
        assert "refspec" in result.lower()

    def test_allows_push_with_colon_in_git_config_before_push(self) -> None:
        """git -c http.proxy=http://proxy:8080 push origin HEAD must be allowed.

        The colon appears in the git config value before 'push', not in
        the refspec arguments after 'push'.
        """
        gate = _make_gate()
        result = gate.check_permission(
            "Bash",
            {"command": "git -c http.proxy=http://proxy:8080 push origin HEAD"},
        )
        assert result is None

    def test_allows_push_with_config_url_containing_port(self) -> None:
        """git -c url.https://github.com.insteadOf=... push origin HEAD must be allowed."""
        gate = _make_gate()
        result = gate.check_permission(
            "Bash",
            {"command": "git -c url.https://github.com/.insteadOf=git://github.com/ push origin HEAD"},
        )
        assert result is None

    def test_allows_push_u_origin_head_no_colon(self) -> None:
        """git push -u origin HEAD with no colon must be allowed."""
        gate = _make_gate()
        result = gate.check_permission("Bash", {"command": "git push -u origin HEAD"})
        assert result is None
