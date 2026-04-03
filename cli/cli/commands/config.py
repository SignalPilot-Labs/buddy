"""buddy config — manage CLI configuration (~/.buddy/cli.toml)."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from cli.config import CONFIG_PATH, DEFAULT_API_URL
from cli.output import print_detail, print_json, print_success
from cli.config import state

console = Console()

app = typer.Typer(
    help="Manage CLI configuration. Settings are saved to ~/.buddy/cli.toml.",
    rich_markup_mode=None,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _read_config() -> dict:
    """Read the current config file."""
    if CONFIG_PATH.is_file():
        return tomllib.loads(CONFIG_PATH.read_text())
    return {}


def _write_config(cfg: dict) -> None:
    """Write config dict as TOML to ~/.buddy/cli.toml."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for key, value in cfg.items():
        if isinstance(value, str):
            lines.append(f'{key} = "{value}"')
        elif isinstance(value, bool):
            lines.append(f"{key} = {'true' if value else 'false'}")
        elif isinstance(value, (int, float)):
            lines.append(f"{key} = {value}")
    CONFIG_PATH.write_text("\n".join(lines) + "\n")


@app.command("get")
def get_config() -> None:
    """Show current CLI configuration.

    \b
    Example:
      buddy config get
    """
    cfg = _read_config()
    if not cfg:
        console.print(f"[dim]No config file found at {CONFIG_PATH}[/dim]")
        console.print("[dim]Using defaults. Run 'buddy config set' to configure.[/dim]")
        cfg = {"api_url": DEFAULT_API_URL, "api_key": "(not set)", "project_dir": "(cwd)"}
    if state.json_mode:
        print_json(cfg)
        return
    print_detail(cfg, title=f"CLI Config ({CONFIG_PATH})")


@app.command("set")
def set_config(
    api_key: Optional[str] = typer.Option(None, "--api-key", metavar="<key>", help="Dashboard API key"),
    project_dir: Optional[str] = typer.Option(None, "--project-dir", metavar="<path>", help="Buddy project directory (where docker-compose.yml lives)"),
) -> None:
    """Set CLI configuration values. Saved to ~/.buddy/cli.toml.

    \b
    Examples:
      buddy config set --api-key my-secret-key
      buddy config set --project-dir /path/to/buddy
    """
    cfg = _read_config()
    updated: list[str] = []

    if api_key is not None:
        cfg["api_key"] = api_key
        updated.append("api_key")
    if project_dir is not None:
        cfg["project_dir"] = project_dir
        updated.append("project_dir")

    if not updated:
        console.print("[yellow]Nothing to update. Pass at least one --option.[/yellow]")
        raise typer.Exit(1)

    _write_config(cfg)
    print_success(f"Saved to {CONFIG_PATH}: {', '.join(updated)}")


@app.command("path")
def show_path() -> None:
    """Show the config file path.

    \b
    Example:
      buddy config path
    """
    console.print(str(CONFIG_PATH))
