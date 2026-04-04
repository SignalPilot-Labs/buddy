"""Buddy CLI — manage Buddy services, runs, and resources from the terminal."""

from __future__ import annotations

from typing import Optional

import typer

from cli.commands import agent, config, doctor, repos, run, services, settings
from cli.config import state
from cli.constants import DEFAULT_LOG_TAIL_LINES

_HELP = """\
Buddy CLI — manage services, runs, settings, and repos.

\b
Getting started:
  buddy start                                  Start all services
  buddy settings set --claude-token <token>   Configure credentials
  buddy doctor                                 Verify setup is healthy
  buddy run new -p "Fix auth bugs" -d 30      Start a 30-minute run
  buddy open                                   Open the dashboard"""

app = typer.Typer(
    name="buddy",
    help=_HELP,
    no_args_is_help=True,
    rich_markup_mode=None,
    context_settings={"help_option_names": ["-h", "--help"]},
)

# ── Global options ──────────────────────────────────────────────────────────


@app.callback()
def main(
    api_url: Optional[str] = typer.Option(None, "--api-url", metavar="<url>", help="Dashboard API base URL"),
    api_key: Optional[str] = typer.Option(None, "--api-key", metavar="<key>", help="Dashboard API key"),
    json_mode: bool = typer.Option(False, "--json", help="Output raw JSON instead of formatted tables"),
) -> None:
    """Global options."""
    state.json_mode = json_mode
    if api_url is not None:
        state.api_url = api_url
    if api_key is not None:
        state.api_key = api_key


# ── Top-level service commands ──────────────────────────────────────────────


@app.command("start")
def start() -> None:
    """Start all Buddy services (docker compose up -d).

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


@app.command("update")
def update() -> None:
    """Pull latest code and rebuild Docker images (git pull + docker compose build).

    \b
    Example:
      buddy update
    """
    services.update_services()


@app.command("logs")
def logs(
    lines: int = typer.Argument(DEFAULT_LOG_TAIL_LINES, metavar="<lines>", help="Number of lines to tail"),
) -> None:
    """Stream Docker Compose logs. Pass a number to tail that many lines.

    \b
    Examples:
      buddy logs            # tail last 100 lines + follow
      buddy logs 50         # tail last 50 lines + follow
    """
    services.show_logs(lines)


@app.command("doctor")
def doctor_cmd() -> None:
    """Run health checks against your Buddy setup and print actionable guidance.

    \b
    Example:
      buddy doctor
    """
    doctor.run_doctor()


@app.command("open")
def open_cmd() -> None:
    """Open the Buddy dashboard in your default browser.

    \b
    Example:
      buddy open
    """
    services.open_dashboard()


@app.command("kill")
def kill() -> None:
    """Remove all Buddy containers — data volumes are preserved (docker compose down). Asks for confirmation.

    \b
    Example:
      buddy kill
    """
    services.kill_services()


@app.command("uninstall")
def uninstall() -> None:
    """Remove all Buddy containers, images, volumes, ~/.buddy/, and the buddy shim. Asks for confirmation.

    \b
    Example:
      buddy uninstall
    """
    services.uninstall_buddy()


# ── Subcommand groups ───────────────────────────────────────────────────────

app.add_typer(run.app, name="run")
app.add_typer(settings.app, name="settings")
app.add_typer(repos.app, name="repos")
app.add_typer(agent.app, name="agent")
app.add_typer(config.app, name="config")


if __name__ == "__main__":
    app()
