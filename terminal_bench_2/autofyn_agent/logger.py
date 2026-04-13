"""JSONL event logger — writes structured events to /logs/agent/events.jsonl.

Harbor persists /logs/agent/ as a trial artifact, so every event written here
survives the container and can be queried after the eval completes.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any

log = logging.getLogger("terminal_bench.logger")


class EventLogger:
    """Appends structured JSONL events to the agent log file."""

    def __init__(self, log_path: str) -> None:
        path = Path(log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._file = path.open("a", encoding="utf-8")

    def log(self, event: str, **kwargs: Any) -> None:
        """Write one JSONL line: {ts, event, ...kwargs}."""
        entry: dict[str, Any] = {"ts": round(time.time(), 3), "event": event}
        entry.update(kwargs)
        self._file.write(json.dumps(entry) + "\n")
        self._file.flush()

    def close(self) -> None:
        """Flush and close the log file."""
        self._file.flush()
        self._file.close()
