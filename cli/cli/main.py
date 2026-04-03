"""Buddy CLI — manage Buddy services, runs, and resources from the terminal."""

from __future__ import annotations

from typing import Optional

import typer

from cli.config import state
from cli.commands import agent, repos, run, services, settings

app = typer.Typer(
    name="buddy",
    help="Buddy CLI — manage services, runs, settings, and repos.",
    no_args_is_help=True,
)

# ── Global options ──────────────────────────────────────────────────────────


@app.callback()
def main(
    api_url: Optional[str] = typer.Option(None, "--api-url", envvar="BUDDY_API_URL", help="Dashboard API URL"),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="BUDDY_API_KEY", help="Dashboard API key"),
    json_mode: bool = typer.Option(False, "--json", help="Output raw JSON"),
    project_dir: Optional[str] = typer.Option(None, "--project-dir", envvar="BUDDY_PROJECT_DIR", help="Buddy project directory"),
) -> None:
    """Buddy CLI — manage services, runs, settings, and repos."""
    state.api_url = api_url
    state.api_key = api_key
    state.json_mode = json_mode
    state.project_dir = project_dir


# ── Top-level service commands ──────────────────────────────────────────────


@app.command("start")
def start() -> None:
    """Start all Buddy services (docker compose up)."""
    services.start_services()


@app.command("stop")
def stop() -> None:
    """Stop all Buddy services (docker compose stop)."""
    services.stop_services()


@app.command("kill")
def kill() -> None:
    """Force-remove all Buddy containers (docker compose down)."""
    services.kill_services()


# ── Subcommand groups ───────────────────────────────────────────────────────

app.add_typer(run.app, name="run")
app.add_typer(settings.app, name="settings")
app.add_typer(repos.app, name="repos")
app.add_typer(agent.app, name="agent")


if __name__ == "__main__":
    app()
