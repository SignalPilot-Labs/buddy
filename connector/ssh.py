"""SSH connection and tunnel management for the connector."""

import asyncio
import logging
import os
import signal
import socket
import sys

from connector.constants import SSH_CONNECT_TIMEOUT_SEC, SSH_KEEPALIVE_INTERVAL_SEC

log = logging.getLogger("connector.ssh")

_SSH_KEEPALIVE_COUNT_MAX: int = 3
_KILL_WAIT_TIMEOUT_SEC: int = 5


async def open_ssh_tunnel(
    ssh_target: str,
    remote_host: str,
    remote_port: int,
    local_port: int,
) -> asyncio.subprocess.Process:
    """Open an SSH tunnel: local_port -> remote_host:remote_port."""
    cmd = [
        "ssh",
        "-N",
        "-L", f"127.0.0.1:{local_port}:{remote_host}:{remote_port}",
        "-o", f"ConnectTimeout={SSH_CONNECT_TIMEOUT_SEC}",
        "-o", f"ServerAliveInterval={SSH_KEEPALIVE_INTERVAL_SEC}",
        "-o", f"ServerAliveCountMax={_SSH_KEEPALIVE_COUNT_MAX}",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "BatchMode=yes",
        ssh_target,
    ]
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
        preexec_fn=os.setsid if sys.platform != "darwin" else None,
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
    """Run a command over SSH with environment variables."""
    env_exports = " ".join(f"{k}={v}" for k, v in env.items())
    full_cmd = f"{env_exports} {command}" if env_exports else command
    cmd = [
        "ssh",
        "-o", f"ConnectTimeout={SSH_CONNECT_TIMEOUT_SEC}",
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=accept-new",
        ssh_target,
        full_cmd,
    ]
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        preexec_fn=os.setsid if sys.platform != "darwin" else None,
    )
    return process


async def write_remote_secret(
    ssh_target: str,
    secret_dir: str,
    run_key: str,
    secret: str,
) -> str:
    """Write a secret file on the remote host. Returns the file path."""
    remote_path = f"{secret_dir}/{run_key}"
    cmd = (
        f"mkdir -p {secret_dir} && "
        f"printf '%s' '{secret}' > {remote_path} && "
        f"chmod 600 {remote_path}"
    )
    proc = await run_ssh_command(ssh_target, cmd, {})
    await proc.wait()
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
    cmd = f"rm -f {secret_file_path}"
    proc = await run_ssh_command(ssh_target, cmd, {})
    await proc.wait()


async def kill_process_group(process: asyncio.subprocess.Process) -> None:
    """Kill a process and its process group."""
    if process.returncode is not None:
        return
    pid = process.pid
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        await asyncio.wait_for(process.wait(), timeout=_KILL_WAIT_TIMEOUT_SEC)
    except asyncio.TimeoutError:
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


async def find_free_port() -> int:
    """Find a free TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
