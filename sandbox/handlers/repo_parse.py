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


def _parse_full_diff(raw: str) -> dict[str, str]:
    """Parse full unified diff output into a path->patch map.

    Splits on ``diff --git`` boundaries and extracts the destination path
    from the ``diff --git a/... b/...`` header line. Rename lines
    (``rename from``/``rename to``) are included verbatim in the patch text.
    """
    patches: dict[str, str] = {}
    if not raw.strip():
        return patches

    sections = raw.split("\ndiff --git ")
    for i, section in enumerate(sections):
        # The very first section either starts with "diff --git " (if raw
        # begins with that prefix) or is empty/pre-header text we skip.
        if i == 0:
            if section.startswith("diff --git "):
                section = section[len("diff --git "):]
            else:
                continue

        first_newline = section.find("\n")
        if first_newline == -1:
            continue

        header_line = section[:first_newline]
        # Header format: "a/<path> b/<path>"
        b_marker = header_line.rfind(" b/")
        if b_marker == -1:
            continue
        file_path = header_line[b_marker + 3:]
        if not file_path:
            continue

        patch_body = section[first_newline + 1:]
        patches[file_path] = patch_body

    return patches
