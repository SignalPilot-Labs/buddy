"""MetadataStore — read/write `/tmp/rounds.json` via the sandbox.

The RoundEntry and RoundsMetadata dataclasses live in `utils.models`.
This module is just the I/O layer that loads and persists them.
"""

import json
import logging
import time

from sandbox_client.client import SandboxClient
from utils.constants import METADATA_PATH
from utils.models import RoundEntry, RoundsMetadata

log = logging.getLogger("memory.metadata")


class MetadataStore:
    """Read/write `/tmp/rounds.json` via the sandbox file_system handler.

    Public API:
        load()                                  -> RoundsMetadata
        save(metadata)                          -> None
        record_round(n, summary, pr_title?,     -> RoundsMetadata
                     pr_description?)
    """

    def __init__(self, sandbox: SandboxClient) -> None:
        self._sandbox = sandbox

    async def load(self) -> RoundsMetadata:
        """Read rounds.json. Returns an empty RoundsMetadata if absent."""
        raw = await self._sandbox.file_system.read(METADATA_PATH)
        if raw is None or not raw.strip():
            return RoundsMetadata.empty()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            log.warning("rounds.json is malformed: %s — starting empty", exc)
            return RoundsMetadata.empty()
        return RoundsMetadata(
            pr_title=str(data.get("pr_title", "")),
            pr_description=str(data.get("pr_description", "")),
            rounds=[
                RoundEntry(
                    n=int(r.get("n", 0)),
                    summary=str(r.get("summary", "")),
                    ended_at=str(r.get("ended_at", "")),
                )
                for r in data.get("rounds", [])
            ],
        )

    async def save(self, metadata: RoundsMetadata) -> None:
        """Write metadata back to rounds.json. Overwrites the file."""
        await self._sandbox.file_system.write(
            METADATA_PATH, metadata.to_json(), append=False,
        )

    async def record_round(
        self,
        n: int,
        summary: str,
        pr_title: str | None,
        pr_description: str | None,
    ) -> RoundsMetadata:
        """Append a round entry (or overwrite one with the same n).

        Updates PR title/description if non-None is provided. Returns the
        resulting metadata so callers can persist or log it.
        """
        metadata = await self.load()
        if pr_title is not None:
            metadata.pr_title = pr_title
        if pr_description is not None:
            metadata.pr_description = pr_description

        entry = RoundEntry(
            n=n,
            summary=summary,
            ended_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
        metadata.rounds = [r for r in metadata.rounds if r.n != n] + [entry]
        metadata.rounds.sort(key=lambda r: r.n)
        await self.save(metadata)
        return metadata
