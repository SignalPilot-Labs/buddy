"""Reverse proxy handler — forwards agent HTTP to remote sandbox over SSH tunnel."""

import logging

import httpx
from aiohttp import web

from connector.constants import PROXY_TIMEOUT_SEC, SANDBOX_SECRET_HEADER
from connector.forward_state import ForwardState

log = logging.getLogger("connector.proxy")


async def handle_proxy(
    request: web.Request,
    states: dict[str, ForwardState],
) -> web.StreamResponse:
    """Reverse-proxy a request to the sandbox via SSH tunnel."""
    run_key = request.match_info["run_key"]
    state = states.get(run_key)
    if not state:
        return web.json_response(
            {"error": f"No active tunnel for run {run_key}"}, status=404,
        )

    target_url = _build_target_url(request, state.local_port)
    headers = _build_proxy_headers(request, state.sandbox_secret)
    body = await request.read() if request.can_read_body else None

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(PROXY_TIMEOUT_SEC),
    ) as client:
        resp = await client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body,
        )

    response = web.Response(
        status=resp.status_code,
        body=resp.content,
        content_type=resp.headers.get("content-type", "application/json"),
    )
    return response


def _build_target_url(request: web.Request, local_port: int) -> str:
    """Build the target URL for proxying."""
    sub_path = request.match_info.get("path", "")
    url = f"http://127.0.0.1:{local_port}/{sub_path}"
    if request.query_string:
        url += f"?{request.query_string}"
    return url


def _build_proxy_headers(
    request: web.Request,
    sandbox_secret: str,
) -> dict[str, str]:
    """Build headers for the proxied request."""
    headers = dict(request.headers)
    headers[SANDBOX_SECRET_HEADER] = sandbox_secret
    headers.pop("Host", None)
    return headers
