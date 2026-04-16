"""Tests for /internal/audit and /internal/tool-call endpoints on the agent.

Covers:
- Valid payloads accepted and DB functions called.
- Missing required fields return 422.
- Auth middleware: agent secret accepted, sandbox secret accepted,
  wrong secret rejected, empty secret rejected.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("AGENT_INTERNAL_SECRET", "agent-test-secret")
os.environ.setdefault("SANDBOX_INTERNAL_SECRET", "sandbox-test-secret")

with patch("docker.from_env", return_value=MagicMock()):
    from server import _server

from utils.constants import INTERNAL_SECRET_HEADER

_AGENT_SECRET = "agent-test-secret"
_SANDBOX_SECRET = "sandbox-test-secret"
_WRONG_SECRET = "wrong-secret"

_AUDIT_PAYLOAD = {
    "run_id": "run-1",
    "event_type": "tool_timeout",
    "details": {"tool": "Bash"},
}

_TOOL_CALL_PAYLOAD = {
    "run_id": "run-1",
    "phase": "pre",
    "tool_name": "Bash",
    "input_data": {"command": "ls"},
    "output_data": None,
    "duration_ms": None,
    "permitted": True,
    "deny_reason": None,
    "agent_role": "worker",
    "tool_use_id": "toolu_1",
    "session_id": "sess-1",
    "agent_id": None,
}


@pytest.fixture()
def client() -> TestClient:
    return TestClient(_server.app, raise_server_exceptions=False)


class TestInternalAuditEndpoint:
    """POST /internal/audit — DB call and validation."""

    def test_valid_payload_calls_log_audit(self, client: TestClient) -> None:
        with patch("internal_endpoints.db.log_audit", new_callable=AsyncMock) as mock:
            resp = client.post(
                "/internal/audit",
                json=_AUDIT_PAYLOAD,
                headers={INTERNAL_SECRET_HEADER: _AGENT_SECRET},
            )
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        mock.assert_awaited_once_with("run-1", "tool_timeout", {"tool": "Bash"})

    def test_missing_run_id_returns_422(self, client: TestClient) -> None:
        payload = {k: v for k, v in _AUDIT_PAYLOAD.items() if k != "run_id"}
        resp = client.post(
            "/internal/audit",
            json=payload,
            headers={INTERNAL_SECRET_HEADER: _AGENT_SECRET},
        )
        assert resp.status_code == 422

    def test_missing_event_type_returns_422(self, client: TestClient) -> None:
        payload = {k: v for k, v in _AUDIT_PAYLOAD.items() if k != "event_type"}
        resp = client.post(
            "/internal/audit",
            json=payload,
            headers={INTERNAL_SECRET_HEADER: _AGENT_SECRET},
        )
        assert resp.status_code == 422


class TestInternalToolCallEndpoint:
    """POST /internal/tool-call — DB call and validation."""

    def test_valid_payload_calls_log_tool_call(self, client: TestClient) -> None:
        with patch("internal_endpoints.db.log_tool_call", new_callable=AsyncMock) as mock:
            resp = client.post(
                "/internal/tool-call",
                json=_TOOL_CALL_PAYLOAD,
                headers={INTERNAL_SECRET_HEADER: _AGENT_SECRET},
            )
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        mock.assert_awaited_once_with(
            "run-1",
            "pre",
            "Bash",
            {"command": "ls"},
            None,
            None,
            True,
            None,
            "worker",
            "toolu_1",
            "sess-1",
            None,
        )

    def test_missing_run_id_returns_422(self, client: TestClient) -> None:
        payload = {k: v for k, v in _TOOL_CALL_PAYLOAD.items() if k != "run_id"}
        resp = client.post(
            "/internal/tool-call",
            json=payload,
            headers={INTERNAL_SECRET_HEADER: _AGENT_SECRET},
        )
        assert resp.status_code == 422

    def test_missing_phase_returns_422(self, client: TestClient) -> None:
        payload = {k: v for k, v in _TOOL_CALL_PAYLOAD.items() if k != "phase"}
        resp = client.post(
            "/internal/tool-call",
            json=payload,
            headers={INTERNAL_SECRET_HEADER: _AGENT_SECRET},
        )
        assert resp.status_code == 422


class TestDualSecretAuth:
    """Auth middleware accepts agent secret, sandbox secret; rejects others."""

    def test_agent_secret_accepted(self, client: TestClient) -> None:
        with patch("internal_endpoints.db.log_audit", new_callable=AsyncMock):
            resp = client.post(
                "/internal/audit",
                json=_AUDIT_PAYLOAD,
                headers={INTERNAL_SECRET_HEADER: _AGENT_SECRET},
            )
        assert resp.status_code == 200

    def test_sandbox_secret_accepted(self, client: TestClient) -> None:
        with patch("internal_endpoints.db.log_audit", new_callable=AsyncMock):
            resp = client.post(
                "/internal/audit",
                json=_AUDIT_PAYLOAD,
                headers={INTERNAL_SECRET_HEADER: _SANDBOX_SECRET},
            )
        assert resp.status_code == 200

    def test_wrong_secret_rejected(self, client: TestClient) -> None:
        resp = client.post(
            "/internal/audit",
            json=_AUDIT_PAYLOAD,
            headers={INTERNAL_SECRET_HEADER: _WRONG_SECRET},
        )
        assert resp.status_code == 401

    def test_empty_secret_rejected(self, client: TestClient) -> None:
        resp = client.post(
            "/internal/audit",
            json=_AUDIT_PAYLOAD,
            headers={INTERNAL_SECRET_HEADER: ""},
        )
        assert resp.status_code == 401

    def test_missing_header_rejected(self, client: TestClient) -> None:
        resp = client.post("/internal/audit", json=_AUDIT_PAYLOAD)
        assert resp.status_code == 401
