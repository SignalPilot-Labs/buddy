"""buddy settings — credential and config management."""

from __future__ import annotations

import re
from typing import Optional

import typer

from cli.client import get_client
from cli.constants import CLAUDE_TOKEN_PREFIX, GITHUB_REPO_PATTERN, GITHUB_TOKEN_PREFIXES
from cli.output import console, print_detail, print_json, print_success
from cli.config import state

app = typer.Typer(
    help="Manage Buddy server settings and credentials (API tokens, repo, budget).",
    rich_markup_mode=None,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _validate_settings_input(
    claude_token: str | None,
    git_token: str | None,
    github_repo: str | None,
) -> None:
    """Validate credential format before sending to the server."""
    if claude_token is not None and not claude_token.startswith(CLAUDE_TOKEN_PREFIX):
        console.print(f"[red]Invalid claude_token: {claude_token[:8]}… — must start with '{CLAUDE_TOKEN_PREFIX}'[/red]")
        raise typer.Exit(1)
    if git_token is not None and not any(git_token.startswith(p) for p in GITHUB_TOKEN_PREFIXES):
        prefixes = ", ".join(f"'{p}'" for p in GITHUB_TOKEN_PREFIXES)
        console.print(f"[red]Invalid git_token: {git_token[:8]}… — must start with one of {prefixes}[/red]")
        raise typer.Exit(1)
    if github_repo is not None and not re.match(GITHUB_REPO_PATTERN, github_repo):
        console.print(f"[red]Invalid github_repo: {github_repo} — must match owner/repo (e.g. acme/my-project)[/red]")
        raise typer.Exit(1)


@app.command()
def status() -> None:
    """Check which credentials are configured.

    \b
    Example:
      buddy settings status
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
        console.print("[dim]Run: buddy settings set --claude-token <token> --git-token <token> --github-repo <owner/repo>[/dim]")


@app.command("get")
def get_settings() -> None:
    """Show all settings (secrets are masked).

    \b
    Example:
      buddy settings get
    """
    data = get_client().get("/api/settings")
    if state.json_mode:
        print_json(data)
        return
    print_detail(data, title="Settings")


@app.command("set")
def set_settings(
    claude_token: Optional[str] = typer.Option(None, metavar="<token>", help="Anthropic API key"),
    git_token: Optional[str] = typer.Option(None, metavar="<token>", help="GitHub personal access token"),
    github_repo: Optional[str] = typer.Option(None, metavar="<owner/repo>", help="GitHub repo (owner/name)"),
    budget: Optional[str] = typer.Option(None, "--budget", metavar="<amount>", help="Max budget in USD"),
    api_key: Optional[str] = typer.Option(None, "--api-key", metavar="<key>", help="Dashboard API key"),
) -> None:
    """Update one or more settings.

    \b
    Examples:
      buddy settings set --claude-token sk-ant-... --git-token ghp_...
      buddy settings set --github-repo owner/repo
      buddy settings set --budget 10.00
      buddy settings set --api-key my-secret-key
    """
    _validate_settings_input(claude_token, git_token, github_repo)
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
