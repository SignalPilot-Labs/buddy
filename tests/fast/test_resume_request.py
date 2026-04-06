"""Tests for ResumeRequest pydantic validators."""

import pytest

from utils.models import ResumeRequest


class TestResumeRequestValidation:
    """Tests for ResumeRequest pydantic validators."""

    def test_valid_resume(self):
        req = ResumeRequest(run_id="abc-123")
        assert req.run_id == "abc-123"
        assert req.max_budget_usd == 0

    def test_rejects_negative_budget(self):
        with pytest.raises(ValueError, match="non-negative"):
            ResumeRequest(run_id="abc-123", max_budget_usd=-10)

    def test_rejects_empty_run_id(self):
        with pytest.raises(ValueError, match="empty"):
            ResumeRequest(run_id="")

    def test_rejects_whitespace_run_id(self):
        with pytest.raises(ValueError, match="empty"):
            ResumeRequest(run_id="   ")

    def test_strips_run_id_whitespace(self):
        req = ResumeRequest(run_id="  abc-123  ")
        assert req.run_id == "abc-123"
