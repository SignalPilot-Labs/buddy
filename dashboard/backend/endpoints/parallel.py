"""Dashboard API endpoints — parallel runner proxy."""

from fastapi import APIRouter, Body, Depends, Query

from backend import auth
from backend.models import ControlSignalRequest, ParallelRunId, StartRunRequest
from backend.utils import agent_request, read_credentials

router = APIRouter(prefix="/api", dependencies=[Depends(auth.verify_api_key)])

PARALLEL_TIMEOUT = 15
PARALLEL_START_TIMEOUT = 180


@router.get("/parallel/runs")
async def parallel_list_runs() -> list:
    """List all parallel worker slots."""
    return await agent_request("GET", "/parallel/runs", PARALLEL_TIMEOUT, None, None, [])


@router.post("/parallel/start")
async def parallel_start(body: StartRunRequest) -> dict:
    """Start a new parallel worker container."""
    creds = await read_credentials()
    return await agent_request("POST", "/parallel/start", PARALLEL_START_TIMEOUT, {
        "prompt": body.prompt,
        "max_budget_usd": body.max_budget_usd,
        "duration_minutes": body.duration_minutes,
        "base_branch": body.base_branch,
        "extended_context": body.extended_context,
        **creds,
    }, None, None)


@router.get("/parallel/status")
async def parallel_status() -> dict:
    """Get parallel runner status summary."""
    return await agent_request("GET", "/parallel/status", PARALLEL_TIMEOUT, None, None, {
        "total_slots": 0, "active": 0, "max_concurrent": 10, "slots": [],
    })


@router.get("/parallel/runs/{run_id}")
async def parallel_get_run(run_id: str = ParallelRunId) -> dict:
    """Get a single parallel run by run_id."""
    return await agent_request("GET", f"/parallel/runs/{run_id}", PARALLEL_TIMEOUT, None, None, None)


@router.get("/parallel/runs/{run_id}/health")
async def parallel_run_health(run_id: str = ParallelRunId) -> dict:
    """Health check for a specific parallel worker."""
    return await agent_request("GET", f"/parallel/runs/{run_id}/health", PARALLEL_TIMEOUT, None, None, None)


@router.post("/parallel/runs/{run_id}/stop")
async def parallel_stop_run(run_id: str = ParallelRunId) -> dict:
    """Stop a parallel worker."""
    return await agent_request("POST", f"/parallel/runs/{run_id}/stop", PARALLEL_TIMEOUT, None, None, None)


@router.post("/parallel/runs/{run_id}/kill")
async def parallel_kill_run(run_id: str = ParallelRunId) -> dict:
    """Kill a parallel worker."""
    return await agent_request("POST", f"/parallel/runs/{run_id}/kill", PARALLEL_TIMEOUT, None, None, None)


@router.post("/parallel/runs/{run_id}/pause")
async def parallel_pause_run(run_id: str = ParallelRunId) -> dict:
    """Pause a parallel worker."""
    return await agent_request("POST", f"/parallel/runs/{run_id}/pause", PARALLEL_TIMEOUT, None, None, None)


@router.post("/parallel/runs/{run_id}/resume")
async def parallel_resume_run(run_id: str = ParallelRunId) -> dict:
    """Resume a parallel worker."""
    return await agent_request("POST", f"/parallel/runs/{run_id}/resume", PARALLEL_TIMEOUT, None, None, None)


@router.post("/parallel/runs/{run_id}/inject")
async def parallel_inject_run(run_id: str = ParallelRunId, body: ControlSignalRequest = Body()) -> dict:
    """Inject a prompt into a parallel worker."""
    return await agent_request("POST", f"/parallel/runs/{run_id}/inject", PARALLEL_TIMEOUT, {
        "payload": body.payload,
    }, None, None)


@router.post("/parallel/runs/{run_id}/unlock")
async def parallel_unlock_run(run_id: str = ParallelRunId) -> dict:
    """Unlock a parallel worker session."""
    return await agent_request("POST", f"/parallel/runs/{run_id}/unlock", PARALLEL_TIMEOUT, None, None, None)


@router.post("/parallel/cleanup")
async def parallel_cleanup() -> dict:
    """Clean up finished parallel containers."""
    return await agent_request("POST", "/parallel/cleanup", PARALLEL_TIMEOUT, None, None, {"ok": True, "cleaned": 0})


@router.get("/parallel/runs/{run_id}/logs")
async def parallel_run_logs(
    run_id: str = ParallelRunId,
    tail: int = Query(default=200, le=5000),
) -> dict:
    """Get container logs for a parallel worker."""
    return await agent_request("GET", f"/parallel/runs/{run_id}/logs", PARALLEL_TIMEOUT, None, {"tail": tail}, {"lines": []})
