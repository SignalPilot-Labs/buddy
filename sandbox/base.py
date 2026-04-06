"""Base class for sandbox executors.

Shared logic for VM/sandbox lifecycle: capacity checks, ID generation,
active tracking, result building, cleanup. Subclasses implement _run()
for backend-specific execution.
"""

import abc
import asyncio
import json
import logging
import time
import uuid

log = logging.getLogger("executor")


class ExecutorBase(abc.ABC):
    """Base executor with shared lifecycle management.

    Subclasses must implement:
        start()  — one-time initialization
        _run()   — execute code in the backend, return raw result dict
        health() — return backend-specific health info
        _kill_process() — kill a backend-specific process
        _cleanup_resources() — clean up backend-specific files/dirs
    """

    def __init__(self, max_vms: int, timeout_sec: int):
        self._max_vms = max_vms
        self._timeout_sec = timeout_sec
        self._active: dict[str, dict] = {}

    # ── Public interface ─────────────────────────────────────────────────

    async def execute(self, code: str, timeout: int) -> dict:
        """Run untrusted code. Always returns a consistent result dict.

        Never raises — all errors are captured in the result so the
        calling agent always gets a structured response it can learn from.
        """
        vm_id = self._generate_id()
        start_time = time.monotonic()

        try:
            self._check_capacity()
            result = await self._run(code, timeout, vm_id)
            result["vm_id"] = vm_id
            result["execution_ms"] = (time.monotonic() - start_time) * 1000
            return result
        except asyncio.TimeoutError:
            return self._error_result(vm_id, start_time, "Execution timed out")
        except RuntimeError as e:
            log.error("Sandbox runtime error: %s", e)
            return self._error_result(vm_id, start_time, "Execution failed")
        except Exception:
            log.exception("Unexpected error in execute()")
            return self._error_result(vm_id, start_time, "Internal sandbox error")
        finally:
            self._remove(vm_id)

    def cleanup_vm(self, vm_id: str) -> None:
        """Force-kill and clean up a specific execution."""
        entry = self._active.pop(vm_id, None)
        if entry is None:
            return
        self._kill_process(entry)
        self._cleanup_resources(entry)
        log.info("VM %s cleaned up", vm_id)

    def list_vms(self) -> list[dict]:
        """Return list of currently active executions."""
        now = time.time()
        return [
            {"vm_id": k, "uptime_sec": now - v["started_at"]}
            for k, v in self._active.items()
        ]

    # ── Subclass interface ───────────────────────────────────────────────

    @abc.abstractmethod
    async def start(self) -> None:
        """One-time initialization (snapshot creation, binary check, etc.)."""
        raise NotImplementedError

    @abc.abstractmethod
    async def _run(self, code: str, timeout: int, vm_id: str) -> dict:
        """Execute code in the backend. Return dict with success/output/error/exit_code."""
        raise NotImplementedError

    @abc.abstractmethod
    def health(self) -> dict:
        """Return backend-specific health status dict."""
        raise NotImplementedError

    @abc.abstractmethod
    def _kill_process(self, entry: dict) -> None:
        """Kill the process associated with an active entry."""
        raise NotImplementedError

    @abc.abstractmethod
    def _cleanup_resources(self, entry: dict) -> None:
        """Clean up files/dirs associated with an active entry."""
        raise NotImplementedError

    # ── Shared helpers ───────────────────────────────────────────────────

    def _check_capacity(self) -> None:
        """Raise if at max concurrent executions."""
        if len(self._active) >= self._max_vms:
            raise RuntimeError(f"Max concurrent executions ({self._max_vms}) reached")

    def _generate_id(self) -> str:
        """Generate a short unique execution ID."""
        return str(uuid.uuid4())[:8]

    def _register(self, vm_id: str, **kwargs) -> None:
        """Register an active execution for tracking."""
        self._active[vm_id] = {"started_at": time.time(), **kwargs}

    def _remove(self, vm_id: str) -> None:
        """Remove an execution from tracking (without killing)."""
        self._active.pop(vm_id, None)

    def _error_result(self, vm_id: str, start_time: float, error: str) -> dict:
        """Build a consistent error result dict."""
        return {
            "success": False,
            "output": "",
            "error": error,
            "exit_code": -1,
            "vm_id": vm_id,
            "execution_ms": (time.monotonic() - start_time) * 1000,
        }

    def _parse_json_result(self, stdout: str, stderr: str) -> dict:
        """Parse JSON result from stdout. Falls back to error dict."""
        try:
            return json.loads(stdout.strip())
        except (json.JSONDecodeError, ValueError):
            return {
                "success": False,
                "output": stdout,
                "error": stderr or "Failed to parse result",
                "exit_code": -1,
            }
