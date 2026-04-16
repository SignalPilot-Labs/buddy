"""autofyn config — manage CLI configuration (~/.autofyn/config.json)."""

from __future__ import annotations

from typing import Optional

import typer

from cli.config import CONFIG_PATH, _load_config, _save_config, state
from cli.constants import CLI_SECRET_KEYS, DEFAULT_API_URL
from cli.output import console, print_detail, print_json, print_success

app = typer.Typer(
    help="Manage CLI configuration. Settings are saved to ~/.autofyn/config.json.",
    rich_markup_mode=None,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@app.command("get")
def get_config() -> None:
    """Show current CLI configuration.

    \b
    Example:
      autofyn config get
    """
    cfg = _load_config()
    if not cfg:
        console.print(f"[dim]No config file found at {CONFIG_PATH}[/dim]")
        console.print("[dim]Using defaults. Run 'autofyn config set' to configure.[/dim]")
        cfg = {"api_url": DEFAULT_API_URL, "api_key": "(auto from container)"}
    if state.json_mode:
        print_json(cfg, secret_keys=CLI_SECRET_KEYS)
        return
    print_detail(cfg, title=f"CLI Config ({CONFIG_PATH})", secret_keys=CLI_SECRET_KEYS)


@app.command("set")
def set_config(
    api_key: Optional[str] = typer.Option(None, "--api-key", metavar="<key>", help="Dashboard API key"),
) -> None:
    """Set CLI configuration values. Saved to ~/.autofyn/config.json.

    \b
    Examples:
      autofyn config set --api-key my-secret-key
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


@app.command("path")
def show_path() -> None:
    """Show the config file path.

    \b
    Example:
      autofyn config path
    """
    console.print(str(CONFIG_PATH))
