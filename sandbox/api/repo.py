"""Repo HTTP endpoints for the sandbox.

Thin HTTP layer — extracts request params, delegates to RepoService,
returns JSON responses. No git logic here.

Endpoints:
    POST /repo/bootstrap   clone + verify base + create working branch
    POST /repo/save        commit + push per-round changes
    POST /repo/teardown    commit leftovers + push + PR + diff stats
    POST /repo/diff        full unified diff
    POST /repo/diff/stats  per-file diff stats
"""

from aiohttp import web

from repo.service import RepoService


def _get_service(request: web.Request) -> RepoService:
    """Get the RepoService from the app."""
    return request.app["repo_service"]


async def handle_bootstrap(request: web.Request) -> web.Response:
    """Clone the repo, verify base branch, create working branch."""
    service = _get_service(request)
    body = await request.json()
    state = await service.bootstrap(body)
    return web.json_response({
        "ok": True,
        "working_branch": state.working_branch,
    })


async def handle_save(request: web.Request) -> web.Response:
    """Per-round commit + push. No-op if working tree is clean."""
    service = _get_service(request)
    body = await request.json()
    message: str = body["message"]
    result = await service.save(message)
    return web.json_response(result)


async def handle_teardown(request: web.Request) -> web.Response:
    """End-of-run: commit leftovers, push, create/update PR, capture diff."""
    service = _get_service(request)
    body = await request.json()
    result = await service.teardown(body)
    return web.json_response(result)


async def handle_diff(request: web.Request) -> web.Response:
    """Return the full unified diff of the working tree against base."""
    service = _get_service(request)
    diff_text = await service.diff()
    return web.json_response({"diff": diff_text})


async def handle_diff_stats(request: web.Request) -> web.Response:
    """Return per-file diff stats without the full diff body."""
    service = _get_service(request)
    files = await service.diff_stats()
    return web.json_response({"files": files})


def register(app: web.Application) -> None:
    """Attach /repo/* routes."""
    app.router.add_post("/repo/bootstrap", handle_bootstrap)
    app.router.add_post("/repo/save", handle_save)
    app.router.add_post("/repo/teardown", handle_teardown)
    app.router.add_post("/repo/diff", handle_diff)
    app.router.add_post("/repo/diff/stats", handle_diff_stats)
