"""Internal HTTP endpoints for sandbox-to-agent communication.

These endpoints accept audit and tool-call data from sandbox containers,
allowing sandboxes to write to the database without a direct DB connection.

Auth is handled by the server's middleware (accepts SANDBOX_INTERNAL_SECRET).
Endpoints return 500 on DB failure so the sandbox can retry. The sandbox
retries up to 3 times with exponential backoff before giving up.
"""

import logging

from fastapi import FastAPI, HTTPException

from utils.db_logging import log_audit_raw, log_tool_call_raw
from utils.models_http import InternalAuditRequest, InternalToolCallRequest

log = logging.getLogger("internal_endpoints")


def register_internal_routes(app: FastAPI) -> None:
    """Register /internal/* routes on the FastAPI app."""

    @app.post("/internal/audit")
    async def internal_audit(body: InternalAuditRequest) -> dict:
        """Receive an audit event from a sandbox and write it to the DB."""
        try:
            await log_audit_raw(body.run_id, body.event_type, body.details)
        except Exception:
            log.error("DB write failed for /internal/audit", exc_info=True)
            raise HTTPException(status_code=500, detail="DB write failed")
        return {"ok": True}

    @app.post("/internal/tool-call")
    async def internal_tool_call(body: InternalToolCallRequest) -> dict:
        """Receive a tool-call event from a sandbox and write it to the DB."""
        try:
            await log_tool_call_raw(
                body.run_id,
                body.phase,
                body.tool_name,
                body.input_data,
                body.output_data,
                body.duration_ms,
                body.permitted,
                body.deny_reason,
                body.agent_role,
                body.tool_use_id,
                body.session_id,
                body.agent_id,
            )
        except Exception:
            log.error("DB write failed for /internal/tool-call", exc_info=True)
            raise HTTPException(status_code=500, detail="DB write failed")
        return {"ok": True}
