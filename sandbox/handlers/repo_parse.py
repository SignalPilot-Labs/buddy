"""Pure parse helpers for git diff output.

Extracted from repo.py so they can be tested in isolation without
importing aiohttp or any handler machinery.
"""

import re

_RENAME_RE = re.compile(r"\{[^}]* => ([^}]*)\}")

_STATUS_CODE_MAP: dict[str, str] = {
    "A": "added",
    "M": "modified",
    "D": "deleted",
    "R": "renamed",
}


def _normalize_rename_path(path: str) -> str:
    """Resolve git's `{old => new}` rename syntax to the plain new path.

    Examples:
        ``src/{old.ts => new.ts}``  ->  ``src/new.ts``
        ``{old => new}/file.ts``    ->  ``new/file.ts``
        ``a/{b => c}/d.ts``         ->  ``a/c/d.ts``
        ``src/file.ts``             ->  ``src/file.ts``  (unchanged)
    """
    return _RENAME_RE.sub(r"\1", path)


def _parse_name_status(raw: str) -> dict[str, str]:
    """Parse ``git diff --name-status`` output into a path->status map."""
    result: dict[str, str] = {}
    for line in raw.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            code = parts[0][0]
            result[parts[-1]] = _STATUS_CODE_MAP.get(code, "modified")
    return result


def _parse_numstat(raw: str, status_map: dict[str, str]) -> list[dict]:
    """Parse ``git diff --numstat`` output into file-change dicts.

    Rename paths in numstat use ``{old => new}`` syntax while name-status
    stores only the plain new path.  ``_normalize_rename_path`` is applied
    before both the status-map lookup and the stored ``"path"`` value so
    the two parsers agree on rename entries.
    """
    results: list[dict] = []
    for line in raw.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        path = _normalize_rename_path(parts[2])
        results.append({
            "path": path,
            "added": int(parts[0]) if parts[0] != "-" else 0,
            "removed": int(parts[1]) if parts[1] != "-" else 0,
            "status": status_map.get(path, "modified"),
        })
    return results
