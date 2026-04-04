"""HTTP client for the Buddy dashboard API."""

from __future__ import annotations

import json as _json
import sys
from typing import Any, Iterator

import httpx
from httpx_sse import connect_sse
from rich.console import Console

from cli.config import resolve_api_key, resolve_api_url
from cli.constants import HTTP_TIMEOUT_SECONDS

err = Console(stderr=True)

_client: BuddyClient | None = None


class BuddyClient:
    """Thin wrapper around httpx that handles auth and error formatting."""

    def __init__(self, base_url: str, api_key: str | None = None) -> None:
        headers: dict[str, str] = {}
        if api_key:
            headers["X-API-Key"] = api_key
        self._http = httpx.Client(base_url=base_url, headers=headers, timeout=HTTP_TIMEOUT_SECONDS)
        self.base_url = base_url

    # -- convenience verbs ---------------------------------------------------

    def get(self, path: str, params: dict | None = None) -> Any:
        return self._request("GET", path, params=params)

    def post(self, path: str, json: dict | None = None) -> Any:
        return self._request("POST", path, json=json)

    def put(self, path: str, json: dict | None = None) -> Any:
        return self._request("PUT", path, json=json)

    def delete(self, path: str) -> Any:
        return self._request("DELETE", path)

    # -- SSE streaming -------------------------------------------------------

    def stream_sse(self, path: str) -> Iterator[dict]:
        """Yield parsed SSE events from *path*.

        Each yielded dict has ``event`` (str) and ``data`` (parsed JSON).
        """
        with connect_sse(
            self._http, "GET", path, timeout=httpx.Timeout(None)
        ) as source:
            for event in source.iter_sse():
                try:
                    data = _json.loads(event.data) if event.data else {}
                except _json.JSONDecodeError:
                    data = {"raw": event.data}
                yield {"event": event.event, "data": data}

    # -- internals -----------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            resp = self._http.request(method, path, **kwargs)
        except (httpx.ConnectError, httpx.TimeoutException):
            err.print(
                f"[red]Cannot connect to Buddy at {self.base_url}[/red]\n"
                "Is Buddy running? Try: buddy start"
            )
            sys.exit(1)

        if resp.status_code == 401:
            err.print(
                "[red]Authentication failed[/red] — check your API key.\n"
                "Set it with: buddy settings set --api-key YOUR_KEY"
            )
            sys.exit(1)

        if resp.status_code >= 400:
            detail = _extract_error_detail(resp)
            err.print(f"[red]Error {resp.status_code}:[/red] {detail}")
            sys.exit(1)

        if resp.status_code == 204 or not resp.text:
            return {}
        return resp.json()


def _extract_error_detail(resp: httpx.Response) -> str:
    """Pull the error detail from a failed HTTP response."""
    content_type = resp.headers.get("content-type", "")
    if content_type.startswith("application/json"):
        return resp.json().get("detail", resp.text)
    return resp.text


def get_client() -> BuddyClient:
    """Return (or create) the module-level client singleton."""
    global _client
    if _client is None:
        _client = BuddyClient(resolve_api_url(), resolve_api_key())
    return _client
