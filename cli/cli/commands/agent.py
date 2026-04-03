"""buddy agent — agent health and branch listing."""

from __future__ import annotations

import typer

from cli.client import get_client
from cli.output import console, print_detail, print_json, print_success, status_styled
from cli.config import state

app = typer.Typer(help="Agent container status")


@app.command()
def health() -> None:
    """Check if the agent container is reachable."""
    data = get_client().get("/api/agent/health")
    if state.json_mode:
        print_json(data)
        return

    status = data.get("status", "unknown")
    console.print(f"Agent: {status_styled(status)}")
    if data.get("current_run_id"):
        console.print(f"  Run:  {data['current_run_id']}")
    if data.get("elapsed_minutes") is not None:
        console.print(f"  Elapsed: {data['elapsed_minutes']:.1f}m")


@app.command()
def branches() -> None:
    """List git branches available on the agent."""
    data = get_client().get("/api/agent/branches")
    if state.json_mode:
        print_json(data)
        return

    if isinstance(data, list):
        for branch in data:
            console.print(f"  {branch}")
    else:
        console.print(str(data))
