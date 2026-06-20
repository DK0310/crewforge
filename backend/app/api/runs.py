"""Run endpoints: start a run, stream it over SSE, fetch the result.

Synchronous-and-streamed model: POST to start (get a `run_id`), then open the SSE
stream. No background queue. The endpoint serializes whatever the engine emits; it
decides no event content itself.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.app.config_loader import ConfigError
from backend.app.engine.runner import RunNotFoundError, get_runner
from backend.app.models import RunRecord, RunRequest

router = APIRouter(tags=["runs"])


@router.post("/runs")
async def start_run(req: RunRequest) -> dict:
    runner = get_runner()
    try:
        run_id = await runner.start(req.crew_id, req.user_input, req.file)
    except ConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"run_id": run_id}


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: str) -> StreamingResponse:
    runner = get_runner()

    async def event_gen():
        try:
            async for event in runner.run_events(run_id):
                yield f"data: {event.model_dump_json()}\n\n"
        except RunNotFoundError:
            yield 'data: {"type":"error","message":"run not found"}\n\n'
            yield 'data: {"type":"done"}\n\n'

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable proxy buffering so tokens flush live
        },
    )


@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> RunRecord:
    runner = get_runner()
    try:
        return runner.get_record(run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc
