"""Entry point that composes all route modules into one register_routes call."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI

from endpoints.control import register_control_routes
from endpoints.diff import register_diff_routes
from endpoints.logs import register_log_routes
from endpoints.run import register_run_routes

if TYPE_CHECKING:
    from server import AgentServer


def register_routes(app: FastAPI, server: "AgentServer") -> None:
    """Register all HTTP route handlers on the FastAPI app."""
    register_run_routes(app, server)
    register_control_routes(app, server)
    register_diff_routes(app, server)
    register_log_routes(app, server)
