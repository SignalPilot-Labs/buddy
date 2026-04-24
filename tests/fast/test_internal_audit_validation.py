"""Regression tests for input validation on /internal/* endpoints and log_audit_raw.

Covers:
- /internal/audit rejects invalid event_type (Finding #5)
- /internal/audit rejects invalid run_id (Finding #5)
- /internal/audit accepts valid payload
- /internal/tool-call rejects invalid phase (Finding #5)
- /internal/tool-call rejects invalid run_id (Finding #5)
- log_audit_raw() rejects invalid event_type directly (Finding #17)
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("AGENT_INTERNAL_SECRET", "test-secret")
os.environ.setdefault("SANDBOX_INTERNAL_SECRET", "test-sandbox-secret")

with patch("docker.from_env", return_value=MagicMock()):
    from internal_endpoints import register_internal_routes
    from utils.db_logging import log_audit_raw

_app = FastAPI()
register_internal_routes(_app)
_client = TestClient(_app)

_VALID_UUID = "00000000-0000-0000-0000-000000000001"

_VALID_AUDIT_PAYLOAD = {
    "run_id": _VALID_UUID,
    "event_type": "run_started",
    "details": {},
}

_VALID_TOOL_CALL_PAYLOAD = {
    "run_id": _VALID_UUID,
    "phase": "pre",
    "tool_name": "Bash",
    "input_data": None,
    "output_data": None,
    "duration_ms": None,
    "permitted": True,
    "deny_reason": None,
    "agent_role": "worker",
    "tool_use_id": "toolu_1",
    "session_id": "sess-1",
    "agent_id": None,
}


class TestInternalInputValidation:
    """Regression tests for input validation on internal endpoints and log_audit_raw."""

    def test_audit_rejects_invalid_event_type(self) -> None:
        payload = {**_VALID_AUDIT_PAYLOAD, "event_type": "evil_injection"}
        resp = _client.post("/internal/audit", json=payload)
        assert resp.status_code == 422

    def test_audit_rejects_invalid_run_id(self) -> None:
        payload = {**_VALID_AUDIT_PAYLOAD, "run_id": "not-a-uuid"}
        resp = _client.post("/internal/audit", json=payload)
        assert resp.status_code == 422

    def test_audit_accepts_valid_event_type(self) -> None:
        with patch("internal_endpoints.log_audit_raw", new_callable=AsyncMock):
            resp = _client.post("/internal/audit", json=_VALID_AUDIT_PAYLOAD)
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    def test_tool_call_rejects_invalid_phase(self) -> None:
        payload = {**_VALID_TOOL_CALL_PAYLOAD, "phase": "during"}
        resp = _client.post("/internal/tool-call", json=payload)
        assert resp.status_code == 422

    def test_tool_call_rejects_invalid_run_id(self) -> None:
        payload = {**_VALID_TOOL_CALL_PAYLOAD, "run_id": "../etc/passwd"}
        resp = _client.post("/internal/tool-call", json=payload)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_log_audit_raw_rejects_invalid_event_type(self) -> None:
        with patch("utils.db_logging.get_session_factory"):
            with pytest.raises(ValueError, match="Unknown audit event type"):
                await log_audit_raw(_VALID_UUID, "bogus", None)
