"""Regression tests for prompt size limit on StartRunRequest (dashboard API)."""

import pytest
from pydantic import ValidationError

from db.constants import PROMPT_MAX_LEN
from dashboard.backend.models import StartRunRequest


class TestStartRunRequestPromptLimit:
    """Prompt size validation on the dashboard StartRunRequest model."""

    def test_accepts_none_prompt(self) -> None:
        req = StartRunRequest(prompt=None, preset=None, repo=None)
        assert req.prompt is None

    def test_accepts_normal_prompt(self) -> None:
        req = StartRunRequest(prompt="Fix the tests", preset=None, repo=None)
        assert req.prompt == "Fix the tests"

    def test_accepts_prompt_at_exact_limit(self) -> None:
        req = StartRunRequest(prompt="x" * PROMPT_MAX_LEN, preset=None, repo=None)
        assert req.prompt is not None
        assert len(req.prompt) == PROMPT_MAX_LEN

    def test_rejects_prompt_over_limit(self) -> None:
        with pytest.raises(ValidationError, match="under"):
            StartRunRequest(prompt="x" * (PROMPT_MAX_LEN + 1), preset=None, repo=None)
