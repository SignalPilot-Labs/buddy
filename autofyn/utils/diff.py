"""Diff parsing utilities for the agent."""


def extract_file_patch(full_diff: str, target_path: str) -> str | None:
    """Extract the unified diff patch for a single file from a full diff.

    Returns the patch body (everything after the header line) or None
    if the target file is not found in the diff.
    """
    sections = full_diff.split("\ndiff --git ")
    for i, section in enumerate(sections):
        if i == 0:
            if section.startswith("diff --git "):
                section = section[len("diff --git "):]
            else:
                continue
        first_newline = section.find("\n")
        if first_newline == -1:
            continue
        header = section[:first_newline]
        if f"b/{target_path}" in header:
            return section[first_newline + 1:]
    return None
