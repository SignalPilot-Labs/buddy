"""Tests for run endpoint request/response validation."""

import pytest

from db.constants import DEFAULT_MODEL
from utils.models import StartRequest


class TestStartRequestModel:
    """Tests for the model field on StartRequest."""

    def test_defaults_to_opus(self) -> None:
        req = StartRequest()
        assert req.model == DEFAULT_MODEL

    def test_can_be_set_to_sonnet(self) -> None:
        req = StartRequest(model="claude-sonnet-4-6")
        assert req.model == "claude-sonnet-4-6"

    def test_can_be_set_to_opus_4_5(self) -> None:
        req = StartRequest(model="claude-opus-4-5")
        assert req.model == "claude-opus-4-5"

    def test_rejects_invalid_model(self) -> None:
        with pytest.raises(ValueError, match="must be one of"):
            StartRequest(model="gpt-4")

    def test_rejects_old_alias(self) -> None:
        with pytest.raises(ValueError, match="must be one of"):
            StartRequest(model="opus")

    def test_included_in_serialization(self) -> None:
        req = StartRequest(model="claude-sonnet-4-6")
        data = req.model_dump()
        assert data["model"] == "claude-sonnet-4-6"
