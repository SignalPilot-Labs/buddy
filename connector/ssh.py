"""SSH connection and tunnel management for the connector."""

import asyncio
import logging
import os
import shlex
import signal
import socket

from connector.constants import (
    KILL_WAIT_TIMEOUT_SEC,
    SAFE_PATH_RE,
    SSH_CONNECT_TIMEOUT_SEC,
    SSH_KEEPALIVE_INTERVAL_SEC,
    SSH_KEEPALIVE_COUNT_MAX,
)

log = logging.getLogger("connector.ssh")


def _validate_safe_path(path: str, label: str) -> None:
    """Validate a path contains no shell metacharacters."""
    if not SAFE_PATH_RE.fullmatch(path):
        raise ValueError(f"{label} contains unsafe characters: {path!r}")


def _ssh_base_opts() -> list[str]:
    """Common SSH options for all connections."""
    return [
        "-o", f"ConnectTimeout={SSH_CONNECT_TIMEOUT_SEC}",
        "-o", "BatchMode=yes",
        "-o", f"ServerAliveInterval={SSH_KEEPALIVE_INTERVAL_SEC}",
        "-o", f"ServerAliveCountMax={SSH_KEEPALIVE_COUNT_MAX}",
    ]


def _preexec_fn() -> None:
    """Put SSH child processes into their own process group."""
    os.setsid()


async def open_ssh_tunnel(
    ssh_target: str,
    remote_host: str,
    remote_port: int,
    local_port: int,
) -> asyncio.subprocess.Process:
    """Open an SSH tunnel: local_port -> remote_host:remote_port."""
    cmd = [
        "ssh", "-N",
        "-L", f"127.0.0.1:{local_port}:{remote_host}:{remote_port}",
        *_ssh_base_opts(),
        ssh_target,
    ]
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
        preexec_fn=_preexec_fn,
    )
    log.info(
        "SSH tunnel %s -> %s:%d (pid %d)",
        ssh_target, remote_host, remote_port, process.pid,
    )
    return process


async def run_ssh_command(
    ssh_target: str,
    command: str,
    env: dict[str, str],
) -> asyncio.subprocess.Process:
    """Run a command over SSH with environment variables.

    All env values are shell-quoted to prevent injection.
    """
    env_exports = " ".join(
        f"{k}={shlex.quote(v)}" for k, v in env.items()
    )
    full_cmd = f"{env_exports} {command}" if env_exports else command
    cmd = [
        "ssh",
        *_ssh_base_opts(),
        ssh_target,
        full_cmd,
    ]
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        preexec_fn=_preexec_fn,
    )
    return process


async def write_remote_secret(
    ssh_target: str,
    secret_dir: str,
    run_key: str,
    secret: str,
) -> str:
    """Write a secret file on the remote host via stdin pipe. Returns the file path."""
    _validate_safe_path(secret_dir, "secret_dir")
    _validate_safe_path(run_key, "run_key")
    remote_path = f"{secret_dir}/{run_key}"
    shell_cmd = (
        f"mkdir -p {shlex.quote(secret_dir)} && "
        f"cat > {shlex.quote(remote_path)} && "
        f"chmod 600 {shlex.quote(remote_path)}"
    )
    proc = await asyncio.create_subprocess_exec(
        "ssh",
        *_ssh_base_opts(),
        ssh_target,
        shell_cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
        preexec_fn=_preexec_fn,
    )
    await proc.communicate(input=secret.encode())
    if proc.returncode != 0:
        raise RuntimeError(
            f"Failed to write secret file on {ssh_target}:{remote_path}"
        )
    return remote_path


async def delete_remote_secret(
    ssh_target: str,
    secret_file_path: str,
) -> None:
    """Delete a secret file on the remote host."""
    _validate_safe_path(secret_file_path, "secret_file_path")
    cmd = f"rm -f {shlex.quote(secret_file_path)}"
    proc = await run_ssh_command(ssh_target, cmd, {})
    await proc.wait()


async def kill_process_group(process: asyncio.subprocess.Process) -> None:
    """Kill a process and its process group."""
    if process.returncode is not None:
        return
    pid = process.pid
    try:
        pgid = os.getpgid(pid)
        if pgid == os.getpgrp():
            process.terminate()
        else:
            os.killpg(pgid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        await asyncio.wait_for(process.wait(), timeout=KILL_WAIT_TIMEOUT_SEC)
    except asyncio.TimeoutError:
        try:
            pgid = os.getpgid(pid)
            if pgid == os.getpgrp():
                process.kill()
            else:
                os.killpg(pgid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


async def find_free_port() -> int:
    """Find a free TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
