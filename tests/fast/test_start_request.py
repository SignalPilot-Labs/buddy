"""Tests for StartRequest pydantic validators."""

import pytest

from utils.models_http import StartRequest


class TestStartRequestValidation:
    """Tests for StartRequest pydantic validators."""

    def test_valid_defaults(self):
        req = StartRequest()
        assert req.max_budget_usd == 0
        assert req.duration_minutes == 0
        assert req.base_branch == "main"

    def test_valid_custom_values(self):
        req = StartRequest(max_budget_usd=50.0, duration_minutes=30, base_branch="staging")
        assert req.max_budget_usd == 50.0
        assert req.duration_minutes == 30
        assert req.base_branch == "staging"

    def test_rejects_negative_budget(self):
        with pytest.raises(ValueError, match="non-negative"):
            StartRequest(max_budget_usd=-1.0)

    def test_rejects_negative_duration(self):
        with pytest.raises(ValueError, match="non-negative"):
            StartRequest(duration_minutes=-5)

    def test_rejects_empty_base_branch(self):
        with pytest.raises(ValueError, match="empty"):
            StartRequest(base_branch="")

    def test_rejects_whitespace_base_branch(self):
        with pytest.raises(ValueError, match="empty"):
            StartRequest(base_branch="   ")

    def test_strips_base_branch_whitespace(self):
        req = StartRequest(base_branch="  main  ")
        assert req.base_branch == "main"

    def test_default_effort_is_high(self):
        req = StartRequest()
        assert req.effort == "high"

    def test_accepts_valid_effort_values(self):
        for val in ("medium", "high", "max"):
            req = StartRequest(effort=val)
            assert req.effort == val

    def test_rejects_invalid_effort(self):
        with pytest.raises(ValueError, match="effort must be one of"):
            StartRequest(effort="turbo")
