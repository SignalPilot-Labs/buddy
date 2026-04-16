"""Parse a unified git diff into per-file stats.

Used by `/runs/{run_id}/diff` when `run.diff_stats` is null (i.e. the
run is still live and teardown hasn't written the final stats). We
derive the same shape on-demand from the agent's `/diff/repo` output so
the Changes panel can show real file counts + additions/removals while
the run is in progress instead of falling through to an "unavailable"
empty state.
"""

FILE_ADDED = "added"
FILE_DELETED = "deleted"
FILE_MODIFIED = "modified"
FILE_RENAMED = "renamed"


def parse_diff_stats(diff_text: str) -> list[dict]:
    """Parse a unified diff into a list of {path, added, removed, status}.

    One entry per file. Skips empty input. Paths are the `b/` side
    (post-image), which is what the frontend expects.
    """
    if not diff_text:
        return []
    sections = diff_text.split("\ndiff --git ")
    entries: list[dict] = []
    for i, raw in enumerate(sections):
        if i == 0:
            if raw.startswith("diff --git "):
                section = raw[len("diff --git "):]
            else:
                continue
        else:
            section = raw
        entry = _parse_section(section)
        if entry is not None:
            entries.append(entry)
    return entries


def _parse_section(section: str) -> dict | None:
    """Parse a single `a/<x> b/<y>\\n<body>` block into a stats entry."""
    nl = section.find("\n")
    if nl == -1:
        return None
    header = section[:nl]
    body = section[nl + 1:]
    path = _extract_path(header, body)
    if path is None:
        return None
    status = _extract_status(body)
    added, removed = _count_changed_lines(body)
    return {
        "path": path,
        "added": added,
        "removed": removed,
        "status": status,
    }


def _extract_path(header: str, body: str) -> str | None:
    """Pull the b/-side path from the header; fall back to rename marker."""
    b_idx = header.rfind(" b/")
    if b_idx != -1:
        return header[b_idx + 3:]
    # Pure rename with no content change: header may only list rename lines.
    for line in body.splitlines():
        if line.startswith("rename to "):
            return line[len("rename to "):]
    return None


def _extract_status(body: str) -> str:
    """Classify by looking at the diff body's mode/rename markers."""
    for line in body.splitlines():
        if line.startswith("new file mode"):
            return FILE_ADDED
        if line.startswith("deleted file mode"):
            return FILE_DELETED
        if line.startswith("rename from ") or line.startswith("rename to "):
            return FILE_RENAMED
        # Stop scanning header lines once we hit a hunk — status markers
        # always appear before the first `@@`.
        if line.startswith("@@ "):
            break
    return FILE_MODIFIED


def _count_changed_lines(body: str) -> tuple[int, int]:
    """Count `+` and `-` body lines, skipping the `+++`/`---` file headers."""
    added = 0
    removed = 0
    for line in body.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1
    return added, removed


def build_stats_response(files: list[dict], source: str) -> dict:
    """Shape a list of parsed entries into the API response dict."""
    return {
        "files": files,
        "total_files": len(files),
        "total_added": sum(f.get("added", 0) for f in files),
        "total_removed": sum(f.get("removed", 0) for f in files),
        "source": source,
    }
