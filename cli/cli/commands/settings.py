"""buddy settings — credential and config management."""

from __future__ import annotations

from typing import Optional

import typer

from cli.client import get_client
from cli.output import console, print_detail, print_json, print_success
from cli.config import state

app = typer.Typer(help="Manage Buddy settings and credentials")


@app.command()
def status() -> None:
    """Show which credentials are configured."""
    data = get_client().get("/api/settings/status")
    if state.json_mode:
        print_json(data)
        return

    checks = {
        "has_claude_token": "Claude API token",
        "has_git_token": "Git token",
        "has_github_repo": "GitHub repo",
    }
    for key, label in checks.items():
        icon = "[green]✓[/green]" if data.get(key) else "[red]✗[/red]"
        console.print(f"  {icon} {label}")

    if data.get("configured"):
        console.print("\n[green]All credentials configured.[/green]")
    else:
        console.print("\n[yellow]Some credentials are missing.[/yellow]")


@app.command("get")
def get_settings() -> None:
    """Show all settings (secrets are masked)."""
    data = get_client().get("/api/settings")
    if state.json_mode:
        print_json(data)
        return
    print_detail(data, title="Settings")


@app.command("set")
def set_settings(
    claude_token: Optional[str] = typer.Option(None, help="Anthropic API key"),
    git_token: Optional[str] = typer.Option(None, help="GitHub personal access token"),
    github_repo: Optional[str] = typer.Option(None, help="GitHub repo (owner/name)"),
    budget: Optional[str] = typer.Option(None, "--budget", help="Max budget in USD"),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="Dashboard API key"),
) -> None:
    """Update one or more settings."""
    body: dict = {}
    if claude_token is not None:
        body["claude_token"] = claude_token
    if git_token is not None:
        body["git_token"] = git_token
    if github_repo is not None:
        body["github_repo"] = github_repo
    if budget is not None:
        body["max_budget_usd"] = budget
    if api_key is not None:
        body["dashboard_api_key"] = api_key

    if not body:
        console.print("[yellow]Nothing to update. Pass at least one --option.[/yellow]")
        raise typer.Exit(1)

    data = get_client().put("/api/settings", json=body)
    print_success(f"Updated: {', '.join(data.get('updated', []))}")
