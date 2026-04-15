"""Git output parsing helpers for the repo handler.

All functions are module-private (underscore prefix) because they are only
called from sandbox.handlers.repo and have no other consumers.
"""


def _parse_name_status(raw: str) -> dict[str, str]:
    """Parse `git diff --name-status` output into a path->status map."""
    result: dict[str, str] = {}
    for line in raw.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            code = parts[0][0]
            result[parts[-1]] = {
                "A": "added", "M": "modified",
                "D": "deleted", "R": "renamed",
            }.get(code, "modified")
    return result


def _parse_numstat(raw: str, status_map: dict[str, str]) -> list[dict]:
    """Parse `git diff --numstat` output into file change dicts."""
    results: list[dict] = []
    for line in raw.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        results.append({
            "path": parts[2],
            "added": int(parts[0]) if parts[0] != "-" else 0,
            "removed": int(parts[1]) if parts[1] != "-" else 0,
            "status": status_map.get(parts[2], "modified"),
        })
    return results
