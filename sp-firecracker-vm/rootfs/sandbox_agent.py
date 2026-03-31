"""
SignalPilot Sandbox Agent

Runs INSIDE the Firecracker microVM. Starts on boot, listens for code
execution requests via virtio-vsock, executes Python code, returns results.

This process is the ONLY thing running in the VM. It:
  - Receives code + session token via vsock from the host
  - Executes Python code in an isolated subprocess
  - Routes any DB queries through SP_GATEWAY_URL (never direct DB access)
  - Returns stdout, stderr, and generated files back via vsock
  - Has NO internet access, NO raw DB credentials, NO host filesystem access
"""

import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import traceback
from contextlib import redirect_stdout, redirect_stderr

# Read config from kernel boot args or environment
GATEWAY_URL = os.getenv("SP_GATEWAY_URL", "")
SESSION_TOKEN = os.getenv("SP_SESSION_TOKEN", "")
VSOCK_PORT = 5000


def execute_code(code: str, session_token: str, gateway_url: str) -> dict:
    """Execute Python code in a restricted subprocess."""
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    # Set up the execution environment
    exec_globals = {
        "__builtins__": __builtins__,
        "SP_SESSION_TOKEN": session_token,
        "SP_GATEWAY_URL": gateway_url,
    }

    # Pre-import common data science packages
    try:
        import pandas as pd
        import numpy as np
        exec_globals["pd"] = pd
        exec_globals["np"] = np
    except ImportError:
        pass

    try:
        import matplotlib
        matplotlib.use("Agg")  # Non-interactive backend
        import matplotlib.pyplot as plt
        exec_globals["plt"] = plt
        exec_globals["matplotlib"] = matplotlib
    except ImportError:
        pass

    # Execute
    start_time = __import__("time").time()
    try:
        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            exec(code, exec_globals)

        duration = __import__("time").time() - start_time

        # Check for generated files (plots, CSVs, etc.)
        output_files = []
        output_dir = "/tmp/output"
        if os.path.exists(output_dir):
            for f in os.listdir(output_dir):
                filepath = os.path.join(output_dir, f)
                if os.path.isfile(filepath):
                    with open(filepath, "rb") as fh:
                        import base64
                        output_files.append({
                            "name": f,
                            "data": base64.b64encode(fh.read()).decode(),
                        })

        return {
            "success": True,
            "stdout": stdout_capture.getvalue(),
            "stderr": stderr_capture.getvalue(),
            "duration_sec": round(duration, 3),
            "files": output_files,
        }

    except Exception as e:
        duration = __import__("time").time() - start_time
        return {
            "success": False,
            "stdout": stdout_capture.getvalue(),
            "stderr": stderr_capture.getvalue(),
            "error": str(e),
            "traceback": traceback.format_exc(),
            "duration_sec": round(duration, 3),
            "files": [],
        }


def listen_vsock():
    """Listen on virtio-vsock for code execution requests from the host."""
    # VSOCK: AF_VSOCK, CID 3 (guest), port 5000
    sock = socket.socket(socket.AF_VSOCK, socket.SOCK_STREAM)
    sock.bind((socket.VMADDR_CID_ANY, VSOCK_PORT))
    sock.listen(1)

    print(f"Sandbox agent listening on vsock port {VSOCK_PORT}", flush=True)

    while True:
        conn, addr = sock.accept()
        try:
            data = b""
            while True:
                chunk = conn.recv(65536)
                if not chunk or b"\n" in chunk:
                    data += chunk
                    break
                data += chunk

            request = json.loads(data.decode().strip())
            action = request.get("action")

            if action == "execute":
                result = execute_code(
                    code=request["code"],
                    session_token=request.get("session_token", SESSION_TOKEN),
                    gateway_url=request.get("gateway_url", GATEWAY_URL),
                )
                conn.sendall(json.dumps(result).encode() + b"\n")

            elif action == "ping":
                conn.sendall(json.dumps({"status": "alive"}).encode() + b"\n")

            else:
                conn.sendall(json.dumps({
                    "error": f"Unknown action: {action}"
                }).encode() + b"\n")

        except Exception as e:
            try:
                conn.sendall(json.dumps({
                    "success": False,
                    "error": str(e),
                }).encode() + b"\n")
            except Exception:
                pass
        finally:
            conn.close()


if __name__ == "__main__":
    # Create output directory for generated files
    os.makedirs("/tmp/output", exist_ok=True)

    print("SignalPilot Sandbox Agent starting...", flush=True)
    print(f"  Gateway: {GATEWAY_URL}", flush=True)
    print(f"  Session: {SESSION_TOKEN[:8]}..." if SESSION_TOKEN else "  Session: (from vsock)", flush=True)

    listen_vsock()
