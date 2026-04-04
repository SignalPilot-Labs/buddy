"""buddy repos — repository management."""

from __future__ import annotations

from pathlib import Path

import typer

from cli.client import get_client
from cli.git import detect_local_repo
from cli.output import console, print_json, print_success, print_table
from cli.config import state

app = typer.Typer(
    help="Manage configured repositories.",
    rich_markup_mode=None,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _check_local_repo(repo_list: list[str]) -> str | None:
    """Check if local git repo is in the repo list."""
    slug = detect_local_repo(Path.cwd())
    if slug is not None and slug not in repo_list:
        console.print(f"[yellow]Detected local repo: {slug} (not configured)[/yellow]")
    return slug


@app.command("list")
def list_repos() -> None:
    """List all configured repos and how many runs each has (auto-detects local repo).

    \b
    Example:
      buddy repos list
    """
    data = get_client().get("/api/repos")
    if state.json_mode:
        print_json(data)
        return
    print_table(
        data,
        [("repo", "Repository"), ("run_count", "Runs")],
        title="Repositories",
    )
    repo_names = [r.get("repo", "") for r in data]
    slug = _check_local_repo(repo_names)
    if slug is not None and slug not in repo_names:
        if typer.confirm(f"Add {slug} and set as active?", default=False):
            get_client().put("/api/repos/active", json={"repo": slug})
            print_success(f"Active repo set to {slug}")


@app.command("detect")
def detect() -> None:
    """Detect the git repo in the current directory.

    \b
    Example:
      buddy repos detect
    """
    slug = detect_local_repo(Path.cwd())
    if slug is None:
        console.print("[yellow]No git repo detected in current directory.[/yellow]")
        raise typer.Exit(0)
    console.print(f"Detected repo: [bold]{slug}[/bold]")


@app.command("set-active")
def set_active(
    repo: str = typer.Argument(metavar="<owner/repo>", help="Repo slug (owner/name)"),
) -> None:
    """Set which repo the agent works on.

    \b
    Example:
      buddy repos set-active myorg/my-app
    """
    get_client().put("/api/repos/active", json={"repo": repo})
    print_success(f"Active repo set to {repo}")


@app.command("remove")
def remove(
    repo: str = typer.Argument(metavar="<owner/repo>", help="Repo slug (owner/name)"),
) -> None:
    """Remove a repo from the list. Does not delete any runs.

    \b
    Example:
      buddy repos remove myorg/old-repo
    """
    typer.confirm(f"Remove {repo} from the repo list?", abort=True)
    get_client().delete(f"/api/repos/{repo}")
    print_success(f"Removed {repo}")
