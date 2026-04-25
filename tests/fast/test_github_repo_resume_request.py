"""Regression tests for github_repo validation on ResumeRequest (agent API)."""

import pytest
from pydantic import ValidationError

from utils.models_http import ResumeRequest

VALID_RUN_ID = "00000000-0000-0000-0000-000000000001"


class TestResumeRequestGithubRepoValidation:
    """github_repo pattern and length validation on the agent ResumeRequest model."""

    def test_accepts_none(self) -> None:
        req = ResumeRequest(
            run_id=VALID_RUN_ID,
            prompt=None,
            claude_token=None,
            git_token=None,
            github_repo=None,
            env=None,
        )
        assert req.github_repo is None

    def test_accepts_valid_repo(self) -> None:
        req = ResumeRequest(
            run_id=VALID_RUN_ID,
            prompt=None,
            claude_token=None,
            git_token=None,
            github_repo="owner/repo",
            env=None,
        )
        assert req.github_repo == "owner/repo"

    def test_rejects_missing_slash(self) -> None:
        with pytest.raises(ValidationError, match="owner/repo format"):
            ResumeRequest(
                run_id=VALID_RUN_ID,
                prompt=None,
                claude_token=None,
                git_token=None,
                github_repo="noslash",
                env=None,
            )

    def test_rejects_path_traversal(self) -> None:
        with pytest.raises(ValidationError, match="owner/repo format"):
            ResumeRequest(
                run_id=VALID_RUN_ID,
                prompt=None,
                claude_token=None,
                git_token=None,
                github_repo="../../etc/passwd",
                env=None,
            )

    def test_rejects_over_max_length(self) -> None:
        too_long = "a" * 200 + "/" + "b" * 57  # 258 chars > 256
        with pytest.raises(ValidationError, match="under"):
            ResumeRequest(
                run_id=VALID_RUN_ID,
                prompt=None,
                claude_token=None,
                git_token=None,
                github_repo=too_long,
                env=None,
            )
