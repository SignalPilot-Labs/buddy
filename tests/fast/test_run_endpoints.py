"""Tests for run endpoint request/response validation."""

import pytest

from utils.models import StartRequest, InjectRequest
from utils.constants import INJECT_PAYLOAD_MAX_LEN


class TestStartRequestExtendedContext:
    """Tests for the extended_context field on StartRequest."""

    def test_defaults_to_false(self):
        req = StartRequest()
        assert req.extended_context is False

    def test_can_be_set_true(self):
        req = StartRequest(extended_context=True)
        assert req.extended_context is True

    def test_included_in_serialization(self):
        req = StartRequest(extended_context=True)
        data = req.model_dump()
        assert data["extended_context"] is True


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
