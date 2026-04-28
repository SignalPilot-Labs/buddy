"""AutoFyn CLI — manage AutoFyn services, runs, and resources from the terminal."""

from __future__ import annotations

from typing import Optional

import typer

from cli.commands import agent, config, repos, run, services, settings
from cli.config import state
from cli.constants import DEFAULT_LOG_TAIL_LINES

_HELP = """\
AutoFyn CLI — manage services, runs, settings, and repos.

\b
Getting started:
  autofyn start                                  Start all services
  autofyn settings set --claude-token <token>   Configure credentials
  autofyn run new -p "Fix auth bugs" -d 30      Start a 30-minute run
  autofyn run                                   Select and manage a run
  autofyn repos list                             See configured repos (auto-detects local repo)"""

app = typer.Typer(
    name="autofyn",
    help=_HELP,
    no_args_is_help=True,
    rich_markup_mode=None,
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
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
def start(
    allow_docker: bool = typer.Option(False, "--allow-docker", help="Mount Docker socket into sandbox containers"),
) -> None:
    """Start all AutoFyn services (docker compose up -d).

    \b
    Example:
      autofyn start
      autofyn start --allow-docker    # Give agent Docker access (unsafe)
    """
    services.start_services(allow_docker)


@app.command("stop")
def stop() -> None:
    """Stop all running AutoFyn containers.

    \b
    Example:
      autofyn stop
    """
    services.stop_services()



@app.command("update")
def update(
    branch: Optional[str] = typer.Option(None, "--branch", metavar="<branch>", help="Switch to branch before updating (e.g. main, production)"),
    image_tag: Optional[str] = typer.Option(None, "--image-tag", metavar="<tag>", help="Override image tag (e.g. stable, nightly, abc1234)"),
    build: bool = typer.Option(False, "--build", help="Force local image build, skip pulling pre-built images"),
) -> None:
    """Pull latest code and Docker images. Builds locally if no pre-built image exists.

    \b
    Detects branch from git and maps to image tag:
      production → stable
      main       → nightly
      other      → builds locally

    \b
    Examples:
      autofyn update                        # Update current branch
      autofyn update --branch main          # Switch to main, pull nightly images
      autofyn update --image-tag abc1234    # Pin to specific image version
      autofyn update --build                # Force local build
    """
    if build and image_tag is not None:
        typer.echo("Error: --build and --image-tag are mutually exclusive", err=True)
        raise typer.Exit(code=1)
    services.update_services(branch, image_tag, build)


@app.command("logs")
def logs(
    lines: int = typer.Argument(DEFAULT_LOG_TAIL_LINES, metavar="<lines>", help="Number of lines to tail"),
) -> None:
    """Stream Docker Compose logs. Pass a number to tail that many lines.

    \b
    Examples:
      autofyn logs            # tail last 100 lines + follow
      autofyn logs 50         # tail last 50 lines + follow
    """
    services.show_logs(lines)


@app.command("kill")
def kill() -> None:
    """Remove all AutoFyn containers (docker compose down). Asks for confirmation.

    \b
    Example:
      autofyn kill
    """
    services.kill_services()


@app.command("uninstall")
def uninstall() -> None:
    """Remove all AutoFyn containers, images, and ~/.autofyn. Asks for confirmation.

    \b
    Example:
      autofyn uninstall
    """
    services.uninstall_services()


# ── Subcommand groups ───────────────────────────────────────────────────────

app.add_typer(run.app, name="run")
app.add_typer(settings.app, name="settings")
app.add_typer(repos.app, name="repos")
app.add_typer(agent.app, name="agent")
app.add_typer(config.app, name="config")


if __name__ == "__main__":
    app()
