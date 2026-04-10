"""Tests for run endpoint request/response validation."""

import pytest

from utils.models import DEFAULT_MODEL, StartRequest, InjectRequest
from utils.constants import INJECT_PAYLOAD_MAX_LEN


class TestStartRequestModel:
    """Tests for the model field on StartRequest."""

    def test_defaults_to_opus(self) -> None:
        req = StartRequest()
        assert req.model == DEFAULT_MODEL

    def test_can_be_set_to_sonnet(self) -> None:
        req = StartRequest(model="sonnet")
        assert req.model == "sonnet"

    def test_can_be_set_to_opus_4_5(self) -> None:
        req = StartRequest(model="opus-4-5")
        assert req.model == "opus-4-5"

    def test_rejects_invalid_model(self) -> None:
        with pytest.raises(ValueError, match="must be one of"):
            StartRequest(model="gpt-4")

    def test_included_in_serialization(self) -> None:
        req = StartRequest(model="sonnet")
        data = req.model_dump()
        assert data["model"] == "sonnet"


class TestInjectPayloadLimit:
    """Tests for inject payload size validation."""

    def test_accepts_normal_payload(self):
        req = InjectRequest(payload="hello")
        assert req.payload == "hello"

    def test_rejects_oversized_payload(self):
        with pytest.raises(ValueError, match="under"):
            InjectRequest(payload="x" * (INJECT_PAYLOAD_MAX_LEN + 1))

    def test_accepts_none_payload(self):
        req = InjectRequest(payload=None)
        assert req.payload is None
