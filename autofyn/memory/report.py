"""Per-round report I/O for subagents and the orchestrator.

All reports for a round live in one directory: `/tmp/round-<N>/`. Subagents
write free-form markdown there (e.g. `architect.md`, `backend-dev.md`, etc.)
and the orchestrator writes its own summary to
`/tmp/round-<N>/orchestrator.md`. This module is the one place that
knows those paths.

Report files are authored inside the sandbox by the LLM itself — this
module only creates the per-round directory and lists its contents for
prompt context.
"""

import logging

from sandbox_client.client import SandboxClient
from utils.constants import ROUND_DIR_PREFIX

log = logging.getLogger("memory.report")


class ReportStore:
    """Manage per-round report directories and list their contents.

    Public API:
        ensure_round_directory(n)   -> None
        list_round(n)               -> list[str]
    """

    def __init__(self, sandbox: SandboxClient) -> None:
        self._sandbox = sandbox

    async def ensure_round_directory(self, round_number: int) -> None:
        """Create `/tmp/round-<n>/` if it does not exist yet."""
        await self._sandbox.file_system.mkdir(self._round_dir(round_number))

    async def list_round(self, round_number: int) -> list[str]:
        """List report filenames under `/tmp/round-<n>/`. Empty if missing."""
        entries = await self._sandbox.file_system.ls(self._round_dir(round_number))
        return sorted(entries)

    @staticmethod
    def _round_dir(round_number: int) -> str:
        """Return the `/tmp/round-<n>` directory for a round."""
        return f"{ROUND_DIR_PREFIX}{round_number}"
