"""Tests for API key auth logic (no DB dependency)."""

import hmac

import pytest
from fastapi import HTTPException


class TestApiKeyAuth:
    """Tests for API key auth logic."""

    @staticmethod
    async def _verify(api_key: str | None, expected_key: str | None) -> None:
        if expected_key is None:
            return
        if not api_key or not hmac.compare_digest(api_key, expected_key):
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

    @pytest.mark.asyncio
    async def test_auth_disabled_when_no_key(self):
        await self._verify(api_key=None, expected_key=None)
        await self._verify(api_key="anything", expected_key=None)

    @pytest.mark.asyncio
    async def test_rejects_missing_key(self):
        with pytest.raises(HTTPException) as exc_info:
            await self._verify(api_key=None, expected_key="secret-key-12345678")
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_rejects_wrong_key(self):
        with pytest.raises(HTTPException) as exc_info:
            await self._verify(api_key="wrong", expected_key="secret-key-12345678")
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_accepts_correct_key(self):
        await self._verify(api_key="secret-key-12345678", expected_key="secret-key-12345678")
