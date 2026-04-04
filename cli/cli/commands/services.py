"""buddy start / stop / kill — Docker Compose service management."""

from __future__ import annotations

import subprocess
import sys

import typer
from rich.console import Console

from cli.config import resolve_project_dir

console = Console()


def _run(cmd: list[str], *, project_dir: str | None = None) -> None:
    """Run a command in the project directory, streaming output."""
    cwd = project_dir or resolve_project_dir()
    console.print(f"[dim]→ {' '.join(cmd)}  (in {cwd})[/dim]")
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        console.print(f"[red]Command exited with code {result.returncode}[/red]")
        sys.exit(result.returncode)


def _compose(args: list[str], *, project_dir: str | None = None) -> None:
    """Run ``docker compose <args>`` in the project directory."""
    _run(["docker", "compose"] + args, project_dir=project_dir)


def start_services() -> None:
    """Start all Buddy services via start.sh."""
    _run(["bash", "start.sh", "-d"])
    console.print("[green]✓[/green] Buddy services started")


def stop_services() -> None:
    """Stop all Buddy services."""
    _compose(["stop"])
    console.print("[green]✓[/green] Buddy services stopped")


def kill_services() -> None:
    """Force-remove all Buddy containers and volumes."""
    typer.confirm(
        "This will remove all Buddy containers. Continue?",
        abort=True,
    )
    _compose(["down"])
    console.print("[green]✓[/green] Buddy containers removed")
