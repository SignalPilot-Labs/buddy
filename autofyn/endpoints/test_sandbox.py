"""Agent endpoint — test remote sandbox connectivity."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI, HTTPException

if TYPE_CHECKING:
    from server import AgentServer


def register_test_sandbox_routes(app: FastAPI, server: "AgentServer") -> None:
    """Register test-sandbox HTTP route."""

    @app.post("/test-sandbox/{sandbox_id}")
    async def test_sandbox(sandbox_id: str) -> dict:
        """Test SSH connection and image availability for a remote sandbox."""
        try:
            return await server.pool().test_connection(sandbox_id)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
