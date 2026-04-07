"""Diff parsing helpers for RepoOps."""

import logging

log = logging.getLogger("sandbox_manager.repo_diff")


def parse_name_status(raw: str) -> dict[str, str]:
    """Parse git diff --name-status into a path->status map."""
    result: dict[str, str] = {}
    for line in raw.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            code = parts[0][0]
            result[parts[-1]] = {
                "A": "added", "M": "modified", "D": "deleted", "R": "renamed",
            }.get(code, "modified")
    return result


def parse_numstat(raw: str, status_map: dict[str, str]) -> list[dict]:
    """Parse git diff --numstat into file change dicts."""
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


def aggregate_live_diff(all_lines: str) -> list[dict]:
    """Aggregate numstat lines by path."""
    stats: dict[str, dict] = {}
    for line in all_lines.split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        added = int(parts[0]) if parts[0] != "-" else 0
        removed = int(parts[1]) if parts[1] != "-" else 0
        path = parts[2]
        if path in stats:
            stats[path]["added"] += added
            stats[path]["removed"] += removed
        else:
            stats[path] = {"path": path, "added": added, "removed": removed, "status": "modified"}
    return list(stats.values())
