"""Regression tests for prompt size limit on ResumeRequest (agent API)."""

import pytest
from pydantic import ValidationError

from db.constants import PROMPT_MAX_LEN
from utils.models_http import ResumeRequest


class TestResumeRequestPromptLimit:
    """Prompt size validation on the agent ResumeRequest model."""

    def test_accepts_none_prompt(self) -> None:
        req = ResumeRequest(
            run_id="00000000-0000-0000-0000-000000000001",
            prompt=None,
            claude_token=None,
            git_token=None,
            github_repo=None,
            env=None,
        )
        assert req.prompt is None

    def test_accepts_normal_prompt(self) -> None:
        req = ResumeRequest(
            run_id="00000000-0000-0000-0000-000000000001",
            prompt="Continue where you left off",
            claude_token=None,
            git_token=None,
            github_repo=None,
            env=None,
        )
        assert req.prompt == "Continue where you left off"

    def test_rejects_prompt_over_limit(self) -> None:
        with pytest.raises(ValidationError, match="under"):
            ResumeRequest(
                run_id="00000000-0000-0000-0000-000000000001",
                prompt="x" * (PROMPT_MAX_LEN + 1),
                claude_token=None,
                git_token=None,
                github_repo=None,
                env=None,
            )
