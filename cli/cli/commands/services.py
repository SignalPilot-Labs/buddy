"""buddy start / stop / kill / update / logs — Docker Compose service management."""

from __future__ import annotations

import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path

import typer

from cli.constants import (
    BUDDY_BIN,
    BUDDY_HOME,
    BUDDY_VENV_PIP,
    BUILD_SCRIPT,
    DASHBOARD_URL,
    SIGINT_EXIT_CODE,
    UP_SCRIPT,
)
from cli.git_utils import is_git_repo
from cli.output import console


def _compose(args: list[str]) -> None:
    """Run ``docker compose <args>`` in the Buddy home directory."""
    cmd = ["docker", "compose"] + args
    console.print(f"[dim]→ {' '.join(cmd)}[/dim]")
    result = subprocess.run(cmd, cwd=BUDDY_HOME)
    if result.returncode != 0:
        console.print(f"[red]Command exited with code {result.returncode}[/red]")
        sys.exit(result.returncode)


def _run_script(script_path: str) -> None:
    """Execute a shell script and exit on failure."""
    console.print(f"[dim]→ bash {script_path}[/dim]")
    result = subprocess.run(["bash", script_path])
    if result.returncode != 0:
        console.print(f"[red]Command exited with code {result.returncode}[/red]")
        console.print("[dim]Run 'buddy logs' to see what went wrong, or 'buddy doctor' to check prerequisites.[/dim]")
        sys.exit(result.returncode)


def _git_pull() -> None:
    """Run git pull in BUDDY_HOME to update the installation."""
    if not is_git_repo(BUDDY_HOME):
        console.print(
            "[red]~/.buddy is not a git repository (likely an old cp-based install).[/red]\n"
            "[red]Re-run the installer to fix this: curl -fsSL https://get.buddy.sh | sh[/red]"
        )
        sys.exit(1)
    console.print(f"[dim]→ git pull in {BUDDY_HOME}[/dim]")
    result = subprocess.run(["git", "pull"], cwd=BUDDY_HOME)
    if result.returncode != 0:
        console.print(f"[red]git pull exited with code {result.returncode}[/red]")
        sys.exit(result.returncode)


def build_services() -> None:
    """Run build.sh — docker compose build only."""
    _run_script(BUILD_SCRIPT)
    console.print("[green]✓[/green] Buddy images built")


def start_services() -> None:
    """Run up.sh — docker compose up -d only. No build."""
    _run_script(UP_SCRIPT)
    console.print("[green]✓[/green] Buddy services started")
    console.print(f"[dim]Dashboard: {DASHBOARD_URL}[/dim]")


def _reinstall_cli() -> None:
    """Reinstall the CLI package into the venv after a git pull."""
    cmd = [BUDDY_VENV_PIP, "install", "-e", str(Path(BUDDY_HOME) / "cli")]
    console.print(f"[dim]→ {' '.join(cmd)}[/dim]")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        console.print(f"[red]Command exited with code {result.returncode}[/red]")
        sys.exit(result.returncode)


def update_services() -> None:
    """Update: git pull in BUDDY_HOME, reinstall CLI, rebuild images, and restart."""
    _git_pull()
    _reinstall_cli()
    build_services()
    start_services()


def show_logs(tail_lines: int) -> None:
    """Stream Docker Compose logs with optional tail.

    Ctrl+C (SIGINT) is a normal exit for log streaming, so exit code 130
    is silently swallowed instead of printing an error.
    """
    cmd = ["docker", "compose", "logs", "--tail", str(tail_lines), "-f"]
    console.print(f"[dim]→ {' '.join(cmd)}[/dim]")
    result = subprocess.run(cmd, cwd=BUDDY_HOME)
    if result.returncode != 0 and result.returncode != SIGINT_EXIT_CODE:
        console.print(f"[red]Command exited with code {result.returncode}[/red]")
        sys.exit(result.returncode)


def stop_services() -> None:
    """Stop all Buddy services."""
    _compose(["stop"])
    console.print("[green]✓[/green] Buddy services stopped")


def open_dashboard() -> None:
    """Open the Buddy dashboard in the default browser."""
    console.print(f"[dim]Opening {DASHBOARD_URL}...[/dim]")
    webbrowser.open(DASHBOARD_URL)


def kill_services() -> None:
    """Force-remove all Buddy containers and volumes."""
    typer.confirm(
        "This will remove all Buddy containers (data volumes are preserved). Continue?",
        abort=True,
    )
    _compose(["down"])
    console.print("[green]✓[/green] Buddy containers removed (volumes preserved — run 'buddy start' to restart)")


def uninstall_buddy() -> None:
    """Remove all Buddy containers, images, volumes, ~/.buddy/, and the buddy shim."""
    typer.confirm(
        "This will remove all Buddy containers, images, volumes, and the ~/.buddy/ directory. Continue?",
        abort=True,
    )
    _compose(["down", "--volumes", "--rmi", "all"])
    shutil.rmtree(BUDDY_HOME, ignore_errors=True)
    Path(BUDDY_BIN).unlink(missing_ok=True)
    console.print("[green]✓[/green] Buddy has been uninstalled")
