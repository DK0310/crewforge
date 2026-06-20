---
name: crewforge-api
description: Use when implementing FastAPI endpoints, streaming runs over SSE, forwarding engine token events to the browser, or building the CRUD endpoints that read/write agent and crew YAML
---

# CrewForge — API Skill

This skill holds the **reusable FastAPI + SSE patterns** for the web layer: how runs stream to the browser, how engine token events become SSE events, and how the thin CRUD endpoints over config work. The web layer is a *wrapper* around the engine — it formats events and moves bytes; it holds no orchestration logic.

> **The real endpoint list and event shapes live in [BUILD_SPEC.md](../../../BUILD_SPEC.md) / [ARCHITECTURE.md](../../../ARCHITECTURE.md).** This skill shows the *techniques*; consult those for the actual routes.

---

## Principles

1. **The API is thin.** It parses requests, calls the engine, and formats responses/events. No planning, no agent logic, no memory access in the API layer.
2. **Async all the way.** Request → engine → Ollama is async end to end. Never block the event loop with a sync call inside a request.
3. **Streaming is SSE, not WebSocket.** Runs are one-way server→client streams. Use `StreamingResponse` with the SSE content type. (WebSocket is reserved for a future human-in-the-loop feature; don't reach for it now.)
4. **One place defines event types.** SSE event shapes are defined once (a Pydantic/enum module) and reused, so the frontend and backend never drift on event names.

---

## The run stream — SSE pattern

A run is started, then its events are streamed. The engine yields events (plan, status, tokens, results, final); the endpoint serializes each as an SSE `data:` line.

```python
from fastapi.responses import StreamingResponse

@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: str):
    async def event_gen():
        async for event in engine.run_events(run_id):   # async generator from the engine
            yield f"data: {event.model_dump_json()}\n\n"
        yield 'data: {"type":"done"}\n\n'
    return StreamingResponse(event_gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})  # disable proxy buffering
```

Key details:
- **`media_type="text/event-stream"`** and each message ends with a blank line (`\n\n`).
- **Disable buffering** (`X-Accel-Buffering: no`, `Cache-Control: no-cache`) so tokens flush immediately instead of being held by a proxy.
- **The engine, not the API, decides event content.** The endpoint just serializes whatever the engine yields.

### Event types (serialize whatever the engine emits)

The engine emits a small, fixed set — plan, `agent_status`, `token` (tagged with `agent_id`, `__leader__` for the Leader), `agent_result`, `final`, `error`, `done`. Define them once and serialize uniformly. The frontend lays out waves from `plan`, flips status pills on `agent_status`, appends `token` text to the matching agent panel, and renders `final` as the answer.

---

## Starting a run

```python
@router.post("/runs")
async def start_run(req: RunRequest) -> dict:
    run_id = await engine.start(req.crew_id, req.user_input, req.file)
    return {"run_id": run_id}
```

Synchronous-and-streamed model: the client POSTs to start, gets a `run_id`, then opens the SSE stream. No background queue.

### File upload

Uploads (a log, a report) arrive as multipart; the handler extracts text (or stores a path) and passes it into the run as `uploaded_file`. Keep extraction out of the engine — hand the engine text or a path, not a raw upload.

---

## Config CRUD — thin endpoints over YAML

Agents and crews are YAML files; the CRUD endpoints read and write those files through the config loader/validator, never a database.

```python
@router.get("/agents")
async def list_agents() -> list[AgentSummary]:
    return [a.summary() for a in config_loader.all_agents()]

@router.post("/agents")
async def create_agent(cfg: AgentConfig) -> AgentConfig:
    config_loader.validate(cfg)         # same validation as load-time
    config_loader.write_agent(cfg)      # writes config/agents/{id}.yaml
    return cfg
```

Rules:
- **Validate on write with the same rules as load** — a UI-created agent must pass the exact checks a hand-written file does (id matches, schema present, references resolve).
- **Writing a crew validates its worker references and plan** before persisting.
- **No engine logic here** — these endpoints just manage config files.

---

## Review Checklist — API Smells

| ❌ Smell | ✅ Correct | Why |
|---|---|---|
| Orchestration/planning logic in a router | Delegate to the engine | API stays thin |
| A sync/blocking call inside a request | Async all the way | Don't stall the event loop |
| WebSocket for run streaming | SSE `StreamingResponse` | One-way stream; WS reserved for later |
| Proxy buffering tokens | `X-Accel-Buffering: no`, `no-cache` | Tokens must flush live |
| Event names duplicated/ad-hoc | Define event types once, reuse | Frontend/backend never drift |
| Memory or Ollama called from the API | Only the engine touches those | Separation of concerns |
| File extraction inside the engine | Extract in the API, pass text/path | Engine stays domain/IO-agnostic |
| Config written without validation | Validate on write == validate on load | UI files must be as safe as hand-written |
| Returning raw entities/YAML text | Return typed models | Clean API boundary |

---

## Cross-References

- **What the engine yields (events, tokens)** → `crewforge-orchestration`
- **AgentConfig/CrewConfig validation reused on write** → `crewforge-agents`
- **The frontend SSE client that consumes this stream** → `crewforge-frontend`
- **Exact routes and event shapes** → [BUILD_SPEC.md](../../../BUILD_SPEC.md) / [ARCHITECTURE.md](../../../ARCHITECTURE.md)
