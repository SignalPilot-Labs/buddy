"""Tests for internal endpoints returning 500 on DB failure.

Verifies:
- /internal/tool-call returns 500 when DB write raises
- /internal/audit returns 500 when DB write raises
- Both return 200 on success
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("AGENT_INTERNAL_SECRET", "test-secret")
os.environ.setdefault("SANDBOX_INTERNAL_SECRET", "test-sandbox-secret")

from fastapi import FastAPI
from fastapi.testclient import TestClient

with patch("docker.from_env", return_value=MagicMock()):
    from internal_endpoints import register_internal_routes

app = FastAPI()
register_internal_routes(app)
client = TestClient(app)


class TestInternalEndpoint500:
    """Internal endpoints must return 500 on DB failure, not 200."""

    def test_tool_call_returns_500_on_db_error(self) -> None:
        with patch("internal_endpoints.log_tool_call_raw", new_callable=AsyncMock, side_effect=RuntimeError("DB down")):
            resp = client.post("/internal/tool-call", json={
                "run_id": "00000000-0000-0000-0000-000000000001",
                "phase": "post",
                "tool_name": "Agent",
                "input_data": None,
                "output_data": None,
                "duration_ms": None,
                "permitted": True,
                "deny_reason": None,
                "agent_role": "worker",
                "tool_use_id": "tuid-1",
                "session_id": "sess-1",
                "agent_id": None,
            })
        assert resp.status_code == 500

    def test_tool_call_returns_200_on_success(self) -> None:
        with patch("internal_endpoints.log_tool_call_raw", new_callable=AsyncMock):
            resp = client.post("/internal/tool-call", json={
                "run_id": "00000000-0000-0000-0000-000000000001",
                "phase": "pre",
                "tool_name": "Read",
                "input_data": None,
                "output_data": None,
                "duration_ms": None,
                "permitted": True,
                "deny_reason": None,
                "agent_role": "worker",
                "tool_use_id": "tuid-2",
                "session_id": "sess-1",
                "agent_id": None,
            })
        assert resp.status_code == 200

    def test_audit_returns_500_on_db_error(self) -> None:
        with patch("internal_endpoints.log_audit_raw", new_callable=AsyncMock, side_effect=RuntimeError("DB down")):
            resp = client.post("/internal/audit", json={
                "run_id": "00000000-0000-0000-0000-000000000001",
                "event_type": "subagent_complete",
                "details": {"agent_id": "a1"},
            })
        assert resp.status_code == 500

    def test_audit_returns_200_on_success(self) -> None:
        with patch("internal_endpoints.log_audit_raw", new_callable=AsyncMock):
            resp = client.post("/internal/audit", json={
                "run_id": "00000000-0000-0000-0000-000000000001",
                "event_type": "run_started",
                "details": {},
            })
        assert resp.status_code == 200
