"""gVisor executor — user-space kernel sandbox via runsc.

Used on hosts without /dev/kvm (macOS Docker Desktop, CI, etc.).
Runs untrusted code inside a gVisor sandbox using `runsc do`, which
intercepts all syscalls through a user-space kernel (Sentry).
"""

import asyncio
import glob
import json
import logging
import os
import tempfile

from base import ExecutorBase

log = logging.getLogger("executor.gvisor")

RUNSC_PATH = "/usr/local/bin/runsc"
PYTHON_PATH = os.getenv("SP_PYTHON_PATH", "/usr/local/bin/python3")

# Wrapper script injected into the sandbox. Captures stdout/stderr as JSON.
_WRAPPER_TEMPLATE = '''
import io, json, sys, traceback

code = {code_json}

stdout_buf = io.StringIO()
stderr_buf = io.StringIO()
old_out, old_err = sys.stdout, sys.stderr
exit_code = 0

try:
    sys.stdout = stdout_buf
    sys.stderr = stderr_buf
    # Restricted builtins: open(), __import__(), exec(), eval(), compile() excluded
    # to prevent file access and arbitrary code loading inside the sandbox.
    _safe = {{k: __builtins__[k] if isinstance(__builtins__, dict) else getattr(__builtins__, k) for k in [
        "print", "len", "range", "enumerate", "zip", "map", "filter", "sorted", "reversed",
        "min", "max", "sum", "abs", "round", "pow", "divmod",
        "int", "float", "str", "bool", "list", "dict", "tuple", "set", "frozenset",
        "bytes", "bytearray", "memoryview", "complex",
        "type", "isinstance", "issubclass", "hasattr", "getattr", "setattr", "delattr",
        "iter", "next", "slice", "repr", "format", "hash", "id", "callable",
        "all", "any", "chr", "ord", "hex", "oct", "bin",
        "input", "Exception", "ValueError", "TypeError", "KeyError", "IndexError",
        "RuntimeError", "StopIteration", "AttributeError", "NameError", "ZeroDivisionError",
        "True", "False", "None",
    ] if (isinstance(__builtins__, dict) and k in __builtins__) or (not isinstance(__builtins__, dict) and hasattr(__builtins__, k))}}
    exec(compile(code, "<sandbox>", "exec"), {{"__builtins__": _safe}})
except SystemExit as e:
    exit_code = e.code if isinstance(e.code, int) else 1
except Exception:
    exit_code = 1
    traceback.print_exc(file=stderr_buf)
finally:
    sys.stdout = old_out
    sys.stderr = old_err

result = json.dumps({{
    "success": exit_code == 0,
    "output": stdout_buf.getvalue().rstrip("\\n"),
    "error": stderr_buf.getvalue().rstrip("\\n") or None,
    "exit_code": exit_code,
}})
print(result)
'''


class GVisorExecutor(ExecutorBase):
    """gVisor sandbox executor using runsc standalone mode."""

    async def start(self) -> None:
        """Verify runsc binary is available and clean orphan temp dirs."""
        if not os.path.exists(RUNSC_PATH):
            raise RuntimeError(f"gVisor binary not found at {RUNSC_PATH}")
        for path in glob.glob("/tmp/sp_gvisor_*"):
            self._remove_tmp_dir(path)
        log.info("gVisor executor ready (runsc at %s)", RUNSC_PATH)

    def health(self) -> dict:
        """Return gVisor-specific health info."""
        return {
            "backend": "gvisor",
            "runsc_available": os.path.exists(RUNSC_PATH),
            "active_sandboxes": len(self._active),
            "max_sandboxes": self._max_vms,
        }

    def _kill_process(self, entry: dict) -> None:
        """Kill the runsc subprocess."""
        proc = entry.get("process")
        if proc and proc.returncode is None:
            proc.kill()

    def _cleanup_resources(self, entry: dict) -> None:
        """Remove the temporary script directory."""
        tmp_dir = entry.get("tmp_dir")
        if tmp_dir:
            self._remove_tmp_dir(tmp_dir)

    async def _run(self, code: str, timeout: int, vm_id: str) -> dict:
        """Run code inside a gVisor sandbox via `runsc do`."""
        wrapper_code = _WRAPPER_TEMPLATE.format(code_json=json.dumps(code))

        tmp_dir = tempfile.mkdtemp(prefix=f"sp_gvisor_{vm_id}_")
        script_path = os.path.join(tmp_dir, "run.py")
        with open(script_path, "w") as f:
            f.write(wrapper_code)

        proc = await asyncio.create_subprocess_exec(
            RUNSC_PATH, "-ignore-cgroups", "do", "-quiet", "--",
            PYTHON_PATH, script_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._register(vm_id, process=proc, tmp_dir=tmp_dir)

        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=timeout,
        )

        stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
        stderr = stderr_bytes.decode("utf-8", errors="replace").strip()
        return self._parse_json_result(stdout, stderr)

    def _remove_tmp_dir(self, path: str) -> None:
        """Remove a temporary directory and its contents."""
        try:
            for f in os.listdir(path):
                os.remove(os.path.join(path, f))
            os.rmdir(path)
        except OSError:
            pass
