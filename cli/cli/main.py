"""Buddy CLI — manage Buddy services, runs, and resources from the terminal."""

from __future__ import annotations

from typing import Optional

import typer

from cli.config import state
from cli.commands import agent, config, repos, run, services, settings

_HELP = """\
Buddy CLI — manage services, runs, settings, and repos.

\b
Getting started:
  buddy start                                 Start all services
  buddy settings set --claude-token <token>   Configure credentials
  buddy run new -p "Fix auth bugs" -d 30      Start a 30-minute run
  buddy run                                   Select and manage a run"""

app = typer.Typer(
    name="buddy",
    help=_HELP,
    no_args_is_help=True,
    rich_markup_mode=None,
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
)

# ── Global options ──────────────────────────────────────────────────────────


@app.callback()
def main(
    json_mode: bool = typer.Option(False, "--json", help="Output raw JSON instead of formatted tables"),
) -> None:
    """Global options."""
    state.json_mode = json_mode


# ── Top-level service commands ──────────────────────────────────────────────


@app.command("start")
def start() -> None:
    """Start all Buddy services (docker compose up --build -d).

    \b
    Example:
      buddy start
    """
    services.start_services()


@app.command("stop")
def stop() -> None:
    """Stop all running Buddy containers.

    \b
    Example:
      buddy stop
    """
    services.stop_services()


@app.command("kill")
def kill() -> None:
    """Remove all Buddy containers (docker compose down). Asks for confirmation.

    \b
    Example:
      buddy kill
    """
    services.kill_services()


# ── Subcommand groups ───────────────────────────────────────────────────────

app.add_typer(run.app, name="run")
app.add_typer(settings.app, name="settings")
app.add_typer(repos.app, name="repos")
app.add_typer(agent.app, name="agent")
app.add_typer(config.app, name="config")


if __name__ == "__main__":
    app()
