"""Per-round report I/O for subagents and the orchestrator.

Subagents write free-form markdown reports to `/tmp/<phase>/round-N-<agent>.md`.
The orchestrator writes its own round report to
`/tmp/orchestrator/round-N-<label>.md`. This module is the one place that
knows those paths.

Report files are authored inside the sandbox by the LLM itself — this
module only reads them (for prompt context) and creates the directories
at bootstrap time.
"""

import logging

from sandbox_client.client import SandboxClient
from utils.constants import ORCHESTRATOR_DIR_NAME, PHASE_BASE, PHASE_DIRS

log = logging.getLogger("memory.report")


class ReportStore:
    """Read phase/orchestrator reports and manage their directories.

    Public API:
        ensure_directories()                     -> None
        list_phase(phase)                        -> list[str]
        read_phase(phase, filename)              -> str | None
        list_orchestrator()                      -> list[str]
        read_orchestrator(filename)              -> str | None
        collect_round(n)                         -> dict[str, list[str]]
    """

    def __init__(self, sandbox: SandboxClient) -> None:
        self._sandbox = sandbox

    # ── Setup ──────────────────────────────────────────────────────────

    async def ensure_directories(self) -> None:
        """Create /tmp/<phase>/ and /tmp/orchestrator/ if missing."""
        for phase in PHASE_DIRS:
            await self._sandbox.file_system.mkdir(self._phase_dir(phase))
        await self._sandbox.file_system.mkdir(
            f"{PHASE_BASE}/{ORCHESTRATOR_DIR_NAME}",
        )

    # ── Phase reports ──────────────────────────────────────────────────

    async def list_phase(self, phase: str) -> list[str]:
        """List report filenames under /tmp/<phase>/. Empty if missing."""
        return await self._sandbox.file_system.ls(self._phase_dir(phase))

    async def read_phase(self, phase: str, filename: str) -> str | None:
        """Read a single report under /tmp/<phase>/. None if missing."""
        return await self._sandbox.file_system.read(
            f"{self._phase_dir(phase)}/{filename}",
        )

    # ── Orchestrator reports ──────────────────────────────────────────

    async def list_orchestrator(self) -> list[str]:
        """List report filenames under /tmp/orchestrator/."""
        return await self._sandbox.file_system.ls(
            f"{PHASE_BASE}/{ORCHESTRATOR_DIR_NAME}",
        )

    async def read_orchestrator(self, filename: str) -> str | None:
        """Read a single orchestrator report. None if missing."""
        return await self._sandbox.file_system.read(
            f"{PHASE_BASE}/{ORCHESTRATOR_DIR_NAME}/{filename}",
        )

    # ── Aggregations ───────────────────────────────────────────────────

    async def collect_round(self, n: int) -> dict[str, list[str]]:
        """Return filenames grouped by phase that match `round-N-*`.

        Used by the round loop to feed the next round's orchestrator prompt
        with a compact index of what was produced previously.
        """
        prefix = f"round-{n}-"
        result: dict[str, list[str]] = {}
        for phase in PHASE_DIRS:
            entries = await self.list_phase(phase)
            matches = sorted(e for e in entries if e.startswith(prefix))
            if matches:
                result[phase] = matches
        orch = await self.list_orchestrator()
        orch_matches = sorted(e for e in orch if e.startswith(prefix))
        if orch_matches:
            result[ORCHESTRATOR_DIR_NAME] = orch_matches
        return result

    # ── Private ────────────────────────────────────────────────────────

    @staticmethod
    def _phase_dir(phase: str) -> str:
        """Return the `/tmp/<phase>` directory for a known phase."""
        if phase not in PHASE_DIRS and phase != ORCHESTRATOR_DIR_NAME:
            raise ValueError(f"unknown phase: {phase}")
        return f"{PHASE_BASE}/{phase}"
