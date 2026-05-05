"""autofyn start / stop / kill / update / logs — Docker Compose service management."""

from __future__ import annotations

import getpass
import os
import re
import signal
import socket
import subprocess
import sys
import time

import typer

from pathlib import Path
import secrets


from cli.client import get_client

from cli.constants import (
    AUTOFYN_HOME,
    BRANCH_TO_IMAGE_TAG,
    BUILD_SCRIPT,
    IMAGE_TAG_FILE,
    MASK_PREFIX_CLAUDE,
    MASK_PREFIX_GIT,
    SIGINT_EXIT_CODE,
    START_SCRIPT,
    UNINSTALL_SCRIPT,
)
from cli.git import detect_local_repo
from cli.output import console, mask_secret


def _compose(args: list[str]) -> None:
    """Run ``docker compose <args>`` in the AutoFyn home directory."""
    cmd = ["docker", "compose"] + args
    console.print(f"[dim]→ {' '.join(cmd)}[/dim]")
    os.environ.setdefault("AGENT_INTERNAL_SECRET", secrets.token_hex(32))
    os.environ.setdefault("SANDBOX_INTERNAL_SECRET", secrets.token_hex(32))
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


def _git_pull(branch: str, skip_fetch: bool) -> None:
    """Fetch latest and reset to origin/<branch>. Safe for install directory."""
    if not skip_fetch:
        console.print(f"[dim]→ git fetch origin {branch}[/dim]")
        fetch = subprocess.run(["git", "fetch", "origin", branch], cwd=AUTOFYN_HOME)
        if fetch.returncode != 0:
            console.print(f"[red]git fetch exited with code {fetch.returncode}[/red]")
            sys.exit(fetch.returncode)
    console.print(f"[dim]→ git reset --hard origin/{branch}[/dim]")
    reset = subprocess.run(["git", "reset", "--hard", f"origin/{branch}"], cwd=AUTOFYN_HOME)
    if reset.returncode != 0:
        console.print(f"[red]git reset exited with code {reset.returncode}[/red]")
        sys.exit(reset.returncode)


def build_services() -> None:
    """Run build.sh — docker compose build only."""
    tag = "local"
    os.environ["AF_IMAGE_TAG"] = tag
    _run_script(BUILD_SCRIPT)
    _save_image_tag(tag)
    console.print("[green]✓[/green] AutoFyn images built")


_DOCKER_WARNING = (
    "[bold yellow]⚠ WARNING:[/bold yellow] --allow-docker grants the agent "
    "[bold]full access to the host Docker daemon[/bold].\n"
    "  The agent can create, inspect, and remove any container on this machine.\n"
    "  Only use this if you understand the implications.\n"
)


def start_services(allow_docker: bool) -> None:
    """Run start.sh — docker compose up -d with whatever images are available."""
    if allow_docker:
        console.print(_DOCKER_WARNING)
        os.environ["AF_ALLOW_DOCKER"] = "1"
    # Generate connector secret and start connector BEFORE docker compose
    # so the agent container can reach it immediately on boot
    if not os.environ.get("CONNECTOR_SECRET"):
        os.environ["CONNECTOR_SECRET"] = secrets.token_hex(32)
    _start_connector()
    _run_script(START_SCRIPT)
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
                console.print(
                    "[yellow]Failed to save Claude token — add it in settings[/yellow]"
                )

    if not status["has_git_token"]:
        token = _detect_git_token()
        if token:
            try:
                client.put("/api/settings", json={"git_token": token})
                console.print("[green]✓[/green] Saved git token to settings")
            except SystemExit:
                console.print(
                    "[yellow]Failed to save git token — add it in settings[/yellow]"
                )

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
                    print(
                        f"✓ Token received ({mask_secret(token, MASK_PREFIX_CLAUDE)})"
                    )
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
        masked = mask_secret(token, MASK_PREFIX_GIT)
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


def _detect_branch() -> str:
    """Return the current git branch name in AUTOFYN_HOME."""
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        cwd=AUTOFYN_HOME,
    )
    if result.returncode != 0:
        console.print("[red]Failed to detect git branch[/red]")
        sys.exit(1)
    return result.stdout.strip()


def _switch_branch(branch: str) -> None:
    """Fetch and switch to the given branch in AUTOFYN_HOME, discarding local changes."""
    console.print(f"[dim]→ git fetch origin {branch}[/dim]")
    fetch = subprocess.run(["git", "fetch", "origin", branch], cwd=AUTOFYN_HOME)
    if fetch.returncode != 0:
        console.print(f"[red]Failed to fetch branch {branch}[/red]")
        sys.exit(fetch.returncode)
    console.print(f"[dim]→ git checkout -f {branch}[/dim]")
    checkout = subprocess.run(["git", "checkout", "-f", branch], cwd=AUTOFYN_HOME)
    if checkout.returncode != 0:
        console.print(f"[red]Failed to switch to branch {branch}[/red]")
        sys.exit(checkout.returncode)


def _resolve_image_tag(branch: str, image_tag_override: str | None) -> str | None:
    """Map branch to image tag, or use override. Returns None if no pre-built image."""
    if image_tag_override is not None:
        return image_tag_override
    return BRANCH_TO_IMAGE_TAG.get(branch)


def _save_image_tag(image_tag: str) -> None:
    """Persist the active image tag so start.sh can read it."""
    Path(IMAGE_TAG_FILE).write_text(image_tag + "\n")


def _pull_images(image_tag: str) -> bool:
    """Try to pull pre-built images for the given tag. Returns True on success."""
    os.environ["AF_IMAGE_TAG"] = image_tag
    # docker-compose.yml references these secrets in service definitions, so
    # docker compose warns when they're unset — even for pull, which never
    # uses them. Placeholders silence the warning; start.sh generates real
    # secrets before any container runs.
    os.environ.setdefault("AGENT_INTERNAL_SECRET", "pull-placeholder")
    os.environ.setdefault("SANDBOX_INTERNAL_SECRET", "pull-placeholder")
    console.print(f"[dim]→ docker compose pull (tag: {image_tag})[/dim]")
    result = subprocess.run(
        ["docker", "compose", "pull"],
        cwd=AUTOFYN_HOME,
    )
    if result.returncode == 0:
        _save_image_tag(image_tag)
    return result.returncode == 0


def update_services(
    branch_override: str | None,
    image_tag_override: str | None,
    force_build: bool,
) -> None:
    """Update code and images: git pull, then pull pre-built images or build locally."""
    already_fetched = branch_override is not None
    if already_fetched:
        _switch_branch(branch_override)

    branch = _detect_branch()
    _git_pull(branch, skip_fetch=already_fetched)

    if force_build:
        console.print("[dim]Building images locally (--build)...[/dim]")
        build_services()
        console.print("[green]✓[/green] Images built locally")
        return

    image_tag = _resolve_image_tag(branch, image_tag_override)

    if image_tag is not None and _pull_images(image_tag):
        console.print(f"[green]✓[/green] Images updated (tag: {image_tag})")
    else:
        if image_tag is not None:
            console.print(f"[yellow]Pre-built images not available for tag: {image_tag}[/yellow]")
        console.print("[dim]Building images locally...[/dim]")
        build_services()
        console.print("[green]✓[/green] Images built locally")


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
    _stop_connector()
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


def uninstall_services() -> None:
    """Remove all AutoFyn containers, images, CLI, and ~/.autofyn."""
    typer.confirm(
        "This will remove all AutoFyn containers, images, run history, and ~/.autofyn. Continue?",
        abort=True,
    )
    _run_script(UNINSTALL_SCRIPT)


def _connector_pid_file() -> Path:
    """Path to the connector wrapper PID file."""
    return Path(AUTOFYN_HOME) / ".connector.pid"


def _kill_port_pids(port: str) -> None:
    """Kill every process listening on the given port."""
    result = subprocess.run(
        ["lsof", "-ti", f"tcp:{port}"],
        capture_output=True, text=True,
    )
    for pid_str in result.stdout.strip().split():
        if pid_str:
            try:
                os.kill(int(pid_str), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass


def _wait_port_free(port: str, timeout: float) -> bool:
    """Block until nothing is listening on the port."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = subprocess.run(
            ["lsof", "-ti", f"tcp:{port}"],
            capture_output=True, text=True,
        )
        if not result.stdout.strip():
            return True
        time.sleep(0.2)
    return False


def _wait_port_ready(port: str, timeout: float) -> bool:
    """Block until the port is accepting connections."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", int(port)), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def _start_connector() -> None:
    """Spawn the connector, guaranteeing the port is clean first."""
    connector_secret = os.environ.get("CONNECTOR_SECRET", "")
    if not connector_secret:
        connector_secret = secrets.token_hex(32)
        os.environ["CONNECTOR_SECRET"] = connector_secret

    connector_port = os.environ.get("CONNECTOR_PORT", "9400")
    pid_file = _connector_pid_file()
    log_file = Path(AUTOFYN_HOME) / ".connector.log"

    # 1. Kill old wrapper from PID file (kills entire process group)
    if pid_file.exists():
        try:
            old_pid = int(pid_file.read_text().strip())
            os.killpg(os.getpgid(old_pid), signal.SIGKILL)
        except (ProcessLookupError, ValueError, PermissionError, OSError):
            pass
        pid_file.unlink(missing_ok=True)

    # 2. Kill anything still on the port (stale connector, manual runs, etc.)
    _kill_port_pids(connector_port)

    # 3. Wait until port is actually free — fail if something won't die
    if not _wait_port_free(connector_port, timeout=3.0):
        console.print(f"[red]✗[/red] Port {connector_port} still in use — cannot start connector")
        sys.exit(1)

    # 4. Spawn connector with logs (not DEVNULL)
    log_handle = open(log_file, "a")
    proc = subprocess.Popen(
        ["autofyn-connector", "--port", connector_port],
        stdout=log_handle,
        stderr=log_handle,
        start_new_session=True,
    )
    pid_file.write_text(str(proc.pid))

    # 5. Wait until connector is actually listening
    if not _wait_port_ready(connector_port, timeout=5.0):
        console.print(f"[red]✗[/red] Connector failed to start — see {log_file}")
        sys.exit(1)
    console.print(f"[green]✓[/green] Connector started (pid {proc.pid}, port {connector_port})")


def _stop_connector() -> None:
    """Stop the connector — kill process and free port."""
    connector_port = os.environ.get("CONNECTOR_PORT", "9400")

    pid_file = _connector_pid_file()
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except (ProcessLookupError, ValueError, PermissionError, OSError):
            pass
        pid_file.unlink(missing_ok=True)

    _kill_port_pids(connector_port)
    console.print("[green]✓[/green] Connector stopped")
