"""autofyn start / stop / kill / update / logs — Docker Compose service management."""

from __future__ import annotations

import getpass
import os
import re
import subprocess
import sys

import typer

from pathlib import Path

from cli.client import get_client
from cli.constants import AUTOFYN_HOME, BUILD_SCRIPT, SIGINT_EXIT_CODE, UP_SCRIPT
from cli.git import detect_local_repo
from cli.output import console


def _compose(args: list[str]) -> None:
    """Run ``docker compose <args>`` in the AutoFyn home directory.

    Docker Compose auto-loads ~/.autofyn/.env (cwd=AUTOFYN_HOME), so
    AGENT_INTERNAL_SECRET is substituted from there. Do not re-parse
    .env here — compose owns that contract.

    Note: the CLI talks directly to FastAPI at http://localhost:3401 via
    loopback, not through the Next.js proxy on :3400. This is intentional:
    the CLI is a trusted local process and routing through :3400 would
    require Next.js to be running. Do not redirect the CLI to :3400.
    """
    cmd = ["docker", "compose"] + args
    console.print(f"[dim]→ {' '.join(cmd)}[/dim]")
    result = subprocess.run(cmd, cwd=AUTOFYN_HOME)
    if result.returncode != 0:
        console.print(f"[red]Command exited with code {result.returncode}[/red]")
        sys.exit(result.returncode)


def _run_script(script_path: str) -> None:
    """Execute a shell script and exit on failure."""
    console.print(f"[dim]→ bash {script_path}[/dim]")
    result = subprocess.run(["bash", script_path])
    if result.returncode != 0:
        console.print(f"[red]Command exited with code {result.returncode}[/red]")
        sys.exit(result.returncode)


def _git_pull() -> None:
    """Fetch latest and reset to origin/main. Safe for install directory."""
    console.print(f"[dim]→ git fetch + reset in {AUTOFYN_HOME}[/dim]")
    fetch = subprocess.run(["git", "fetch", "origin", "main"], cwd=AUTOFYN_HOME)
    if fetch.returncode != 0:
        console.print(f"[red]git fetch exited with code {fetch.returncode}[/red]")
        sys.exit(fetch.returncode)
    reset = subprocess.run(["git", "reset", "--hard", "origin/main"], cwd=AUTOFYN_HOME)
    if reset.returncode != 0:
        console.print(f"[red]git reset exited with code {reset.returncode}[/red]")
        sys.exit(reset.returncode)


def build_services() -> None:
    """Run build.sh — docker compose build only."""
    _run_script(BUILD_SCRIPT)
    console.print("[green]✓[/green] AutoFyn images built")


_DOCKER_WARNING = (
    "[bold yellow]⚠ WARNING:[/bold yellow] --allow-docker grants the agent "
    "[bold]full access to the host Docker daemon[/bold].\n"
    "  The agent can create, inspect, and remove any container on this machine.\n"
    "  Only use this if you trust the prompts you send.\n"
)


def start_services(allow_docker: bool) -> None:
    """Run up.sh — tears down stale containers then docker compose up -d."""
    if allow_docker:
        console.print(_DOCKER_WARNING)
        os.environ["AF_ALLOW_DOCKER"] = "1"
    _run_script(UP_SCRIPT)
    console.print("[green]✓[/green] AutoFyn services started")
    try:
        _ensure_tokens()
    except (KeyboardInterrupt, EOFError):
        console.print("\n[dim]Skipped token setup. Run: autofyn settings set[/dim]")


def _ensure_tokens() -> None:
    """Check for missing tokens and offer to auto-detect from CLI tools."""
    client = get_client()
    try:
        status = client.get("/api/settings/status")
    except SystemExit:
        console.print(
            "[yellow]Dashboard not reachable yet — set tokens manually via: autofyn settings set[/yellow]"
        )
        return

    if status["configured"]:
        return

    if not status["has_claude_token"]:
        token = _detect_claude_token()
        if token:
            try:
                client.post("/api/tokens", json={"token": token})
                console.print("[green]✓[/green] Saved Claude OAuth token to pool")
            except SystemExit:
                console.print("[yellow]Failed to save Claude token — add it in settings[/yellow]")

    if not status["has_git_token"]:
        token = _detect_git_token()
        if token:
            try:
                client.put("/api/settings", json={"git_token": token})
                console.print("[green]✓[/green] Saved git token to settings")
            except SystemExit:
                console.print("[yellow]Failed to save git token — add it in settings[/yellow]")

    if not status["has_github_repo"]:
        _detect_repo(client)

    console.print(
        "[green]✓[/green] Setup complete. Open [bold]http://localhost:3400[/bold] or run [bold]autofyn run new[/bold]"
    )


def _run_token_cmd(cmd: list[str]) -> str | None:
    """Run a command and return stdout, or None if it fails or isn't installed."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return None


def _ask_yes_no(prompt: str) -> bool:
    """Ask a yes/no question. Returns True for yes (default)."""
    sys.stdout.flush()
    sys.stderr.flush()
    answer = input(f"{prompt} [Y/n]: ").strip().lower()
    return answer in ("", "y", "yes")


def _ask_token(prompt: str) -> str | None:
    """Ask user to paste a token. Enter to skip."""
    sys.stdout.flush()
    sys.stderr.flush()
    token = getpass.getpass(f"{prompt} (enter to skip): ").strip()
    return token if token else None


def _extract_token(raw: str) -> str | None:
    """Extract OAuth token from claude setup-token output.

    The CLI line-wraps at 80 columns when stdout is piped, splitting the
    token across multiple lines. We find the line starting with 'sk-ant-'
    and join consecutive lines that contain only valid token characters.
    """
    parts: list[str] = []
    collecting = False
    for line in raw.splitlines():
        stripped = line.strip()
        if not collecting and stripped.startswith("sk-ant-"):
            collecting = True
        if collecting:
            if stripped and re.fullmatch(r"[A-Za-z0-9_\-]+", stripped):
                parts.append(stripped)
            else:
                break
    return "".join(parts) if parts else None


def _detect_claude_token() -> str | None:
    """Get Claude OAuth token via `claude setup-token` (interactive OAuth flow)."""
    console.print("\n[bold]Claude OAuth Token[/bold]")
    if _ask_yes_no("Run `claude setup-token` to authenticate via browser?"):
        try:
            result = subprocess.run(
                ["claude", "setup-token"],
                stdout=subprocess.PIPE,
                text=True,
            )
            if result.returncode == 0 and result.stdout:
                token = _extract_token(result.stdout)
                if token:
                    print(f"✓ Token received ({token[:12]}****)")
                    return token
        except FileNotFoundError:
            console.print(
                "[yellow]claude CLI not installed. Install it: npm install -g @anthropic-ai/claude-code[/yellow]"
            )
    console.print("[dim]Paste your token below, or press enter to skip.[/dim]")
    return _ask_token("Claude OAuth token")


def _detect_git_token() -> str | None:
    """Try to get GitHub token via `gh auth token`."""
    console.print("\n[bold]GitHub Personal Access Token[/bold]")
    console.print("[dim]Checking gh CLI for an existing token...[/dim]")
    token = _run_token_cmd(["gh", "auth", "token"])
    if token:
        masked = token[:7] + "****"
        if _ask_yes_no(f"Found token from gh CLI ({masked}). Use it?"):
            return token
    console.print(
        "[dim]No token found. Run `gh auth login` to authenticate, or paste one below.[/dim]"
    )
    return _ask_token("GitHub token")


def _detect_repo(client) -> None:
    """Auto-detect local git repo and save as active repo."""
    console.print("\n[bold]GitHub Repository[/bold]")
    slug = detect_local_repo(Path.cwd())
    if slug:
        if _ask_yes_no(f"Detected repo: {slug}. Use it?"):
            client.put("/api/settings", json={"github_repo": slug})
            client.put("/api/repos/active", json={"repo": slug})
            console.print(f"[green]✓[/green] Active repo set to {slug}")
            console.print(
                "[dim]Add more repos with: autofyn repos set-active owner/repo[/dim]"
            )
            return
    repo = input("GitHub repo (owner/repo, enter to skip): ").strip()
    if repo:
        client.put("/api/settings", json={"github_repo": repo})
        client.put("/api/repos/active", json={"repo": repo})
        console.print(f"[green]✓[/green] Active repo set to {repo}")
        console.print(
            "[dim]Add more repos with: autofyn repos set-active owner/repo[/dim]"
        )


def update_services() -> None:
    """Update: git pull in AUTOFYN_HOME then rebuild."""
    _git_pull()
    build_services()


def show_logs(tail_lines: int) -> None:
    """Stream Docker Compose logs with optional tail.

    Ctrl+C (SIGINT) is a normal exit for log streaming, so exit code 130
    is silently swallowed instead of printing an error.
    """
    cmd = ["docker", "compose", "logs", "--tail", str(tail_lines), "-f"]
    console.print(f"[dim]→ {' '.join(cmd)}[/dim]")
    result = subprocess.run(cmd, cwd=AUTOFYN_HOME)
    if result.returncode != 0 and result.returncode != SIGINT_EXIT_CODE:
        console.print(f"[red]Command exited with code {result.returncode}[/red]")
        sys.exit(result.returncode)


def stop_services() -> None:
    """Stop all AutoFyn services."""
    _compose(["down"])
    console.print("[green]✓[/green] AutoFyn services stopped")


def kill_services() -> None:
    """Force-remove all AutoFyn containers and volumes."""
    typer.confirm(
        "This will remove all AutoFyn containers. Continue?",
        abort=True,
    )
    _compose(["down"])
    console.print("[green]✓[/green] AutoFyn containers removed")
