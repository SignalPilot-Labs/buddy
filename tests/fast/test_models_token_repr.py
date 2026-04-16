"""Repr of StartRequest / ResumeRequest must not leak token fields."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from utils.models import ResumeRequest, StartRequest


SENTINEL_CLAUDE = "SENTINEL_CLAUDE_TOKEN_ABC_987654321"
SENTINEL_GIT = "SENTINEL_GIT_TOKEN_XYZ_123456789"


class TestModelsTokenRepr:
    """repr() of request models must not contain raw token values."""

    def test_start_request_repr_hides_claude_token(self) -> None:
        r = StartRequest(claude_token=SENTINEL_CLAUDE)
        assert SENTINEL_CLAUDE not in repr(r)

    def test_start_request_repr_hides_git_token(self) -> None:
        r = StartRequest(git_token=SENTINEL_GIT)
        assert SENTINEL_GIT not in repr(r)

    def test_start_request_str_hides_tokens(self) -> None:
        r = StartRequest(claude_token=SENTINEL_CLAUDE, git_token=SENTINEL_GIT)
        s = str(r)
        assert SENTINEL_CLAUDE not in s
        assert SENTINEL_GIT not in s

    def test_start_request_tokens_still_accessible_on_instance(self) -> None:
        """repr=False hides from repr only; attribute access still works."""
        r = StartRequest(claude_token=SENTINEL_CLAUDE, git_token=SENTINEL_GIT)
        assert r.claude_token == SENTINEL_CLAUDE
        assert r.git_token == SENTINEL_GIT

    def test_start_request_model_dump_still_includes_tokens(self) -> None:
        """Serialization (for HTTP dispatch) must NOT be affected by repr=False."""
        r = StartRequest(claude_token=SENTINEL_CLAUDE, git_token=SENTINEL_GIT)
        dumped = r.model_dump()
        assert dumped["claude_token"] == SENTINEL_CLAUDE
        assert dumped["git_token"] == SENTINEL_GIT

    def test_resume_request_repr_hides_tokens(self) -> None:
        r = ResumeRequest(
            run_id="run-1",
            prompt=None,
            claude_token=SENTINEL_CLAUDE,
            git_token=SENTINEL_GIT,
            github_repo="owner/repo",
            env=None,
        )
        rep = repr(r)
        assert SENTINEL_CLAUDE not in rep
        assert SENTINEL_GIT not in rep

    def test_resume_request_tokens_still_required(self) -> None:
        """Field(repr=False) without a default must keep the field required."""
        with pytest.raises(ValidationError):
            ResumeRequest(
                run_id="run-1",
                prompt=None,
                github_repo="owner/repo",
                env=None,
            )  # type: ignore[call-arg]
