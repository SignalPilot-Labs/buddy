"""Regression tests for github_repo validation on StartRequest (agent API)."""

import pytest
from pydantic import ValidationError

from db.constants import GITHUB_REPO_MAX_LEN
from utils.models_http import StartRequest


class TestStartRequestGithubRepoValidation:
    """github_repo pattern and length validation on the agent StartRequest model."""

    def test_accepts_none(self) -> None:
        req = StartRequest(max_budget_usd=0, github_repo=None)
        assert req.github_repo is None

    def test_accepts_valid_repo(self) -> None:
        req = StartRequest(max_budget_usd=0, github_repo="owner/repo")
        assert req.github_repo == "owner/repo"

        req2 = StartRequest(max_budget_usd=0, github_repo="my-org/my.project")
        assert req2.github_repo == "my-org/my.project"

    def test_rejects_missing_slash(self) -> None:
        with pytest.raises(ValidationError, match="owner/repo format"):
            StartRequest(max_budget_usd=0, github_repo="noslash")

    def test_rejects_empty_string(self) -> None:
        with pytest.raises(ValidationError, match="owner/repo format"):
            StartRequest(max_budget_usd=0, github_repo="")

    def test_rejects_path_traversal(self) -> None:
        with pytest.raises(ValidationError, match="owner/repo format"):
            StartRequest(max_budget_usd=0, github_repo="../../etc/passwd")

        with pytest.raises(ValidationError, match="owner/repo format"):
            StartRequest(max_budget_usd=0, github_repo="owner/repo; rm -rf /")

    def test_rejects_spaces(self) -> None:
        with pytest.raises(ValidationError, match="owner/repo format"):
            StartRequest(max_budget_usd=0, github_repo="owner /repo")

    def test_rejects_over_max_length(self) -> None:
        too_long = "a" * 200 + "/" + "b" * 57  # 258 chars > 256
        with pytest.raises(ValidationError, match="under"):
            StartRequest(max_budget_usd=0, github_repo=too_long)

    def test_accepts_at_max_length(self) -> None:
        # Exactly 256 chars: 127 + "/" + 128
        slug = "a" * 127 + "/" + "b" * 128
        assert len(slug) == GITHUB_REPO_MAX_LEN
        req = StartRequest(max_budget_usd=0, github_repo=slug)
        assert req.github_repo == slug
