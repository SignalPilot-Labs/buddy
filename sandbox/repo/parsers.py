"""Pure parse helpers for git diff output.

No aiohttp, no subprocess — pure string parsing. Testable in isolation.
"""

import re

_RENAME_RE = re.compile(r"\{[^}]* => ([^}]*)\}")

_STATUS_CODE_MAP: dict[str, str] = {
    "A": "added",
    "M": "modified",
    "D": "deleted",
    "R": "renamed",
}


def normalize_rename_path(path: str) -> str:
    """Resolve git's `{old => new}` rename syntax to the plain new path."""
    return _RENAME_RE.sub(r"\1", path)


def parse_name_status(raw: str) -> dict[str, str]:
    """Parse ``git diff --name-status`` output into a path->status map."""
    result: dict[str, str] = {}
    for line in raw.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0]:
            code = parts[0][0]
            result[parts[-1]] = _STATUS_CODE_MAP.get(code, "modified")
    return result


def parse_numstat(raw: str, status_map: dict[str, str]) -> list[dict]:
    """Parse ``git diff --numstat`` output into file-change dicts."""
    results: list[dict] = []
    for line in raw.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        path = normalize_rename_path(parts[2])
        results.append({
            "path": path,
            "added": int(parts[0]) if parts[0].isdigit() else 0,
            "removed": int(parts[1]) if parts[1].isdigit() else 0,
            "status": status_map.get(path, "modified"),
        })
    return results
