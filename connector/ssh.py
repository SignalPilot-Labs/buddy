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
    SSH_KEEPALIVE_COUNT_MAX,
    SSH_KEEPALIVE_INTERVAL_SEC,
    SSH_TUNNEL_READY_TIMEOUT_SEC,
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
    """Open an SSH tunnel: local_port -> remote_host:remote_port.

    Waits until the local port accepts connections before returning.
    """
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
    await _wait_for_port_ready(local_port, SSH_TUNNEL_READY_TIMEOUT_SEC)
    return process


async def _wait_for_port_ready(port: int, timeout: float) -> None:
    """Wait until a TCP port accepts connections."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection("127.0.0.1", port),
                timeout=0.5,
            )
            writer.close()
            await writer.wait_closed()
            return
        except (ConnectionRefusedError, asyncio.TimeoutError, OSError):
            await asyncio.sleep(0.1)
    raise RuntimeError(f"SSH tunnel port {port} not ready after {timeout}s")


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
    try:
        await asyncio.wait_for(proc.wait(), timeout=SSH_CONNECT_TIMEOUT_SEC)
    except asyncio.TimeoutError:
        log.warning(
            "delete_remote_secret timed out for %s, killing process",
            secret_file_path,
        )
        await kill_process_group(proc)


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
    """Find a free TCP port on localhost. Uses SO_REUSEADDR to reduce TOCTOU window."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def run_derived_stop(
    ssh_target: str,
    sandbox_type: str,
    backend_id: str,
) -> None:
    """Run the derived stop command for a remote sandbox over SSH.

    For Slurm sandboxes, runs scancel. For Docker, runs docker rm -f.
    """
    if sandbox_type == "slurm":
        cmd = f"scancel {shlex.quote(backend_id)}"
    elif sandbox_type == "docker":
        cmd = f"docker rm -f {shlex.quote(backend_id)}"
    else:
        raise ValueError(f"Unknown sandbox_type: {sandbox_type!r}")
    proc = await run_ssh_command(ssh_target, cmd, {})
    try:
        await asyncio.wait_for(proc.wait(), timeout=SSH_CONNECT_TIMEOUT_SEC)
    except asyncio.TimeoutError:
        log.warning(
            "Derived stop timed out for %s:%s, killing process",
            sandbox_type,
            backend_id,
        )
        await kill_process_group(proc)
    if proc.returncode is not None and proc.returncode != 0:
        log.warning(
            "Derived stop failed for %s:%s (exit %d)",
            sandbox_type,
            backend_id,
            proc.returncode,
        )
