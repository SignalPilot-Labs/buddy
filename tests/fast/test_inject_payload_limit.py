"""Tests for inject payload size validation."""

import pytest

from utils.constants import INJECT_PAYLOAD_MAX_LEN
from utils.models import InjectRequest


class TestInjectPayloadLimit:
    """Tests for inject payload size validation."""

    def test_accepts_normal_payload(self) -> None:
        req = InjectRequest(payload="hello")
        assert req.payload == "hello"

    def test_rejects_oversized_payload(self) -> None:
        with pytest.raises(ValueError, match="under"):
            InjectRequest(payload="x" * (INJECT_PAYLOAD_MAX_LEN + 1))

    def test_accepts_none_payload(self) -> None:
        req = InjectRequest(payload=None)
        assert req.payload is None
