"""buddy repos — repository management."""

from __future__ import annotations

import typer

from cli.client import get_client
from cli.output import print_json, print_success, print_table
from cli.config import state

app = typer.Typer(
    help="Manage configured repositories.",
    rich_markup_mode=None,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@app.command("list")
def list_repos() -> None:
    """List all configured repos and how many runs each has.

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
