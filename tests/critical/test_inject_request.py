"""Tests for InjectRequest pydantic validators."""

import pytest

from utils.models import InjectRequest


class TestInjectRequestValidation:
    """Tests for InjectRequest pydantic validators."""

    def test_valid_payload(self):
        req = InjectRequest(payload="fix the bug")
        assert req.payload == "fix the bug"

    def test_none_payload(self):
        req = InjectRequest()
        assert req.payload is None

    def test_rejects_oversized_payload(self):
        with pytest.raises(ValueError, match="50000"):
            InjectRequest(payload="x" * 50001)

    def test_accepts_max_size_payload(self):
        req = InjectRequest(payload="x" * 50000)
        assert req.payload is not None and len(req.payload) == 50000
