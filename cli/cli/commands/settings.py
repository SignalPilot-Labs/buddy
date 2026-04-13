"""autofyn settings — credential and config management."""

from __future__ import annotations

from typing import Optional

import typer

from cli.client import get_client
from cli.output import console, print_detail, print_json, print_success
from cli.config import state

app = typer.Typer(
    help="Manage AutoFyn server settings and credentials (API tokens, repo, budget).",
    rich_markup_mode=None,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@app.command()
def status() -> None:
    """Check which credentials are configured.

    \b
    Example:
      autofyn settings status
    """
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
    """Show all settings (secrets are masked).

    \b
    Example:
      autofyn settings get
    """
    data = get_client().get("/api/settings")
    if state.json_mode:
        print_json(data)
        return
    print_detail(data, title="Settings")


@app.command("set")
def set_settings(
    claude_token: Optional[str] = typer.Option(None, metavar="<token>", help="Claude OAuth token (added to token pool)"),
    git_token: Optional[str] = typer.Option(None, metavar="<token>", help="GitHub personal access token"),
    github_repo: Optional[str] = typer.Option(None, metavar="<owner/repo>", help="GitHub repo (owner/name)"),
    budget: Optional[str] = typer.Option(None, "--budget", metavar="<amount>", help="Max budget in USD"),
    api_key: Optional[str] = typer.Option(None, "--api-key", metavar="<key>", help="Dashboard API key"),
) -> None:
    """Update one or more settings.

    \b
    Examples:
      autofyn settings set --claude-token sk-ant-... --git-token ghp_...
      autofyn settings set --github-repo owner/repo
      autofyn settings set --budget 10.00
      autofyn settings set --api-key my-secret-key
    """
    # Claude token goes to the pool, not generic settings.
    if claude_token is not None:
        get_client().post("/api/tokens", json={"token": claude_token})
        print_success("Added Claude OAuth token to pool")

    body: dict = {}
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
