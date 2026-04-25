"""Regression tests for prompt size limit on StartRequest (agent API)."""

import pytest
from pydantic import ValidationError

from db.constants import PROMPT_MAX_LEN
from utils.models_http import StartRequest


class TestStartRequestPromptLimit:
    """Prompt size validation on the agent StartRequest model."""

    def test_accepts_none_prompt(self) -> None:
        req = StartRequest(prompt=None)
        assert req.prompt is None

    def test_accepts_normal_prompt(self) -> None:
        req = StartRequest(prompt="Fix the tests")
        assert req.prompt == "Fix the tests"

    def test_accepts_prompt_at_exact_limit(self) -> None:
        req = StartRequest(prompt="x" * PROMPT_MAX_LEN)
        assert req.prompt is not None
        assert len(req.prompt) == PROMPT_MAX_LEN

    def test_rejects_prompt_over_limit(self) -> None:
        with pytest.raises(ValidationError, match="under"):
            StartRequest(prompt="x" * (PROMPT_MAX_LEN + 1))
