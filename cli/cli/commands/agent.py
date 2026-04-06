"""autofyn agent — agent health and branch listing."""

from __future__ import annotations

import typer

from cli.client import get_client
from cli.config import state
from cli.output import console, print_json, status_styled

app = typer.Typer(
    help="Check agent container status and available branches.",
    rich_markup_mode=None,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@app.command()
def health() -> None:
    """Check if the agent container is reachable and show current status.

    \b
    Example:
      autofyn agent health
    """
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
    """List git branches available on the agent.

    \b
    Example:
      autofyn agent branches
    """
    data: list[str] = get_client().get("/api/agent/branches")
    if state.json_mode:
        print_json(data)
        return

    for branch in data:
        console.print(f"  {branch}")
