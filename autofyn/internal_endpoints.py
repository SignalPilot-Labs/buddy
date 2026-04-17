"""Internal HTTP endpoints for sandbox-to-agent communication.

These endpoints accept audit and tool-call data from sandbox containers,
allowing sandboxes to write to the database without a direct DB connection.

Auth is handled by the server's middleware (accepts SANDBOX_INTERNAL_SECRET).
Endpoints return 200 regardless of DB outcome — the underlying DB functions
use @swallow_errors, so failures are logged but never propagated. The sandbox
treats audit logging as non-fatal (log warning and continue).
"""

import logging

from fastapi import FastAPI

from utils import db
from utils.models import InternalAuditRequest, InternalToolCallRequest

log = logging.getLogger("internal_endpoints")


def register_internal_routes(app: FastAPI) -> None:
    """Register /internal/* routes on the FastAPI app."""

    @app.post("/internal/audit")
    async def internal_audit(body: InternalAuditRequest) -> dict:
        """Receive an audit event from a sandbox and write it to the DB.

        Returns 200 regardless of DB outcome — @swallow_errors handles failures.
        """
        await db.log_audit(body.run_id, body.event_type, body.details)
        return {"ok": True}

    @app.post("/internal/tool-call")
    async def internal_tool_call(body: InternalToolCallRequest) -> dict:
        """Receive a tool-call event from a sandbox and write it to the DB.

        Returns 200 regardless of DB outcome — @swallow_errors handles failures.
        """
        await db.log_tool_call(
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
        return {"ok": True}
