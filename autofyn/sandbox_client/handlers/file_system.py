"""FileSystem handler — typed wrapper around `/file_system/*`.

Bound to the shared httpx client owned by SandboxClient. Exposed as
`sandbox.file_system`.
"""

import httpx


class FileSystem:
    """Handler for sandbox filesystem HTTP endpoints.

    Public API:
        write(path, content, append) -> None
        read(path)                     -> str | None
        mkdir(path)                    -> None
        exists(path)                   -> bool
        ls(path)                       -> list[str]
        read_dir(path)                 -> dict[str, str] | None
        write_dir(path, files)         -> None
    """

    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def write(
        self, path: str, content: str, append: bool,
    ) -> None:
        """Write (or append) text to a file. Creates parent dirs."""
        resp = await self._http.post(
            "/file_system/write",
            json={"path": path, "content": content, "append": append},
        )
        resp.raise_for_status()

    async def read(self, path: str) -> str | None:
        """Read a text file. Returns None if the path does not exist."""
        resp = await self._http.post(
            "/file_system/read", json={"path": path},
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("exists"):
            return None
        return data["content"]

    async def mkdir(self, path: str) -> None:
        """Create a directory (with parents)."""
        resp = await self._http.post(
            "/file_system/mkdir", json={"path": path},
        )
        resp.raise_for_status()

    async def exists(self, path: str) -> bool:
        """Return True if the path exists in the sandbox."""
        resp = await self._http.post(
            "/file_system/exists", json={"path": path},
        )
        resp.raise_for_status()
        return bool(resp.json().get("exists"))

    async def ls(self, path: str) -> list[str]:
        """List sorted directory entries. Empty list if the path is missing."""
        resp = await self._http.post(
            "/file_system/ls", json={"path": path},
        )
        resp.raise_for_status()
        return list(resp.json().get("entries", []))

    async def read_dir(self, path: str) -> dict[str, str] | None:
        """Read every file under a dir as a {name: content} map. None if missing."""
        resp = await self._http.post(
            "/file_system/read_dir", json={"path": path},
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("exists"):
            return None
        return dict(data.get("files", {}))

    async def write_dir(self, path: str, files: dict[str, str]) -> None:
        """Create a dir and write every entry in `files` into it."""
        resp = await self._http.post(
            "/file_system/write_dir",
            json={"path": path, "files": files},
        )
        resp.raise_for_status()
