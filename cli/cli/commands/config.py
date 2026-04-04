"""buddy config — manage CLI configuration (~/.buddy/config.json)."""

from __future__ import annotations

from typing import Optional

import typer

from cli.config import CONFIG_PATH, _load_config, _save_config, resolve_api_key, state
from cli.constants import DEFAULT_API_URL
from cli.output import console, print_detail, print_error, print_json, print_success

app = typer.Typer(
    help="Manage CLI configuration. Settings are saved to ~/.buddy/config.json.",
    rich_markup_mode=None,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@app.command("get")
def get_config() -> None:
    """Show current CLI configuration.

    \b
    Example:
      buddy config get
    """
    cfg = _load_config()
    if not cfg:
        console.print(f"[dim]No config file found at {CONFIG_PATH}[/dim]")
        console.print("[dim]Using defaults. Run 'buddy config set' to configure.[/dim]")
        cfg = {"api_url": DEFAULT_API_URL, "api_key": "(auto from container)"}
    if state.json_mode:
        print_json(cfg)
        return
    print_detail(cfg, title=f"CLI Config ({CONFIG_PATH})")


@app.command("set")
def set_config(
    api_key: Optional[str] = typer.Option(None, "--api-key", metavar="<key>", help="Dashboard API key"),
) -> None:
    """Set CLI configuration values. Saved to ~/.buddy/config.json.

    \b
    Examples:
      buddy config set --api-key my-secret-key
    """
    cfg = _load_config()
    updated: list[str] = []

    if api_key is not None:
        cfg["api_key"] = api_key
        updated.append("api_key")

    if not updated:
        console.print("[yellow]Nothing to update. Pass at least one --option.[/yellow]")
        raise typer.Exit(1)

    _save_config(cfg)
    print_success(f"Saved to {CONFIG_PATH}: {', '.join(updated)}")


@app.command("show-key")
def show_key() -> None:
    """Print the dashboard API key. Reads from config, env, or the running container.

    \b
    Example:
      buddy config show-key
    """
    key = resolve_api_key()
    if key is None:
        print_error("Could not resolve API key. Is Buddy running? Try: buddy start")
        raise typer.Exit(1)
    console.print(key)


@app.command("path")
def show_path() -> None:
    """Show the config file path.

    \b
    Example:
      buddy config path
    """
    console.print(str(CONFIG_PATH))
