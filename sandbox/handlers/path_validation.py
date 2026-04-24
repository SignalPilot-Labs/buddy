"""Path confinement validation for sandbox filesystem handlers.

All filesystem API handlers must call validate_fs_path before operating on
any caller-supplied path. This prevents path traversal attacks by resolving
symlinks and .. components and checking against the allowed directory list.
"""

import json
from pathlib import Path

from aiohttp import web

from constants import FS_ALLOWED_PREFIXES, FS_PATH_DENIED_MSG, FS_PATH_EMPTY_MSG


def validate_fs_path(raw_path: str) -> Path:
    """Resolve raw_path and verify it falls within an allowed directory.

    Raises HTTPBadRequest for empty input.
    Raises HTTPForbidden if the resolved path is outside all allowed prefixes.
    Returns the resolved Path on success.
    """
    if not raw_path:
        raise web.HTTPBadRequest(
            text=json.dumps({"error": FS_PATH_EMPTY_MSG}),
            content_type="application/json",
        )
    resolved = Path(raw_path).resolve()
    resolved_str = str(resolved)
    for prefix in FS_ALLOWED_PREFIXES:
        if resolved_str == prefix or resolved_str.startswith(prefix + "/"):
            return resolved
    raise web.HTTPForbidden(
        text=json.dumps({"error": FS_PATH_DENIED_MSG, "path": raw_path}),
        content_type="application/json",
    )
