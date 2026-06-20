"""Run endpoints: start a run (JSON or file upload), stream it over SSE, fetch or
cancel it.

Synchronous-and-streamed model: POST to start (get a `run_id`), then open the SSE
stream. No background queue. The endpoint serializes whatever the engine emits; it
decides no event content itself.

**One SSE consumer per run.** The stream launches the graph on first connect and
drains a single queue, so a run is meant to be watched by one client. The durable
`GET /runs/{id}` is the way to inspect a run from elsewhere or after the fact.
"""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from backend.app.config_loader import ConfigError
from backend.app.engine.events import KEEPALIVE
from backend.app.engine.runner import RunNotFoundError, get_runner
from backend.app.models import RunRecord, RunRequest

router = APIRouter(tags=["runs"])

# Emit an SSE comment this often while a run is idle, so proxies don't drop it.
_KEEPALIVE_SECONDS = 15.0

# Cap on stored uploaded text (the per-prompt cap is separate, in settings). Guards
# the checkpoint/DB against a pathologically large upload.
_MAX_UPLOAD_STORE_CHARS = 200_000


@router.post("/runs")
async def start_run(req: RunRequest) -> dict:
    runner = get_runner()
    try:
        run_id = await runner.start(req.crew_id, req.user_input, req.file)
    except ConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"run_id": run_id}


@router.post("/runs/upload")
async def start_run_with_upload(
    crew_id: str = Form(...),
    user_input: str = Form(...),
    file: UploadFile = File(...),
) -> dict:
    """Start a run with an uploaded file. Text is extracted **here** (the API layer);
    the engine only ever receives text, never a raw upload.
    """
    text = await _extract_text(file)
    runner = get_runner()
    try:
        run_id = await runner.start(crew_id, user_input, text)
    except ConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"run_id": run_id}


@router.get("/runs")
async def list_runs(limit: int = 100) -> list[RunRecord]:
    return await get_runner().list_records(limit)


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: str) -> StreamingResponse:
    runner = get_runner()

    async def event_gen():
        try:
            async for event in runner.run_events(run_id, keepalive=_KEEPALIVE_SECONDS):
                if event is KEEPALIVE:
                    yield ": keep-alive\n\n"
                else:
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


@router.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: str) -> RunRecord:
    try:
        return await get_runner().cancel(run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc


@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> RunRecord:
    runner = get_runner()
    try:
        return await runner.get_record(run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc


async def _extract_text(file: UploadFile) -> str:
    """Decode an uploaded file to text. v1 supports text-like files (logs, reports,
    JSON, CSV); binary formats (PDF/DOCX) are decoded leniently and are a future
    enhancement. Capped to keep the run state bounded.
    """
    raw = await file.read()
    text = raw.decode("utf-8", errors="replace")
    if len(text) > _MAX_UPLOAD_STORE_CHARS:
        text = text[:_MAX_UPLOAD_STORE_CHARS] + "\n…[truncated]"
    return text
