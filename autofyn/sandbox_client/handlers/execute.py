"""Execute handler — typed wrapper around `/execute`.

Not a separate client — a namespace bound to the shared httpx client
owned by SandboxClient. Exposed as `sandbox.execute`.
"""

from dataclasses import asdict

import httpx

from utils.models import ExecRequest, ExecResult


class Execute:
    """Handler for the sandbox `/execute` HTTP endpoint.

    Public API:
        run(request) -> ExecResult
    """

    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def run(self, request: ExecRequest) -> ExecResult:
        """Execute a command in the sandbox. Returns structured result.

        Raises RuntimeError if the sandbox response has no exit_code
        (transport error, auth failure, 5xx). Exit code 0 or non-zero
        is returned as a normal ExecResult — the caller decides.
        """
        resp = await self._http.post(
            "/execute",
            json=asdict(request),
            timeout=request.timeout + 10,
        )
        resp.raise_for_status()
        data = resp.json()
        if "exit_code" in data:
            return ExecResult(
                stdout=data["stdout"],
                stderr=data["stderr"],
                exit_code=data["exit_code"],
            )
        raise RuntimeError(f"Sandbox error: {data}")
