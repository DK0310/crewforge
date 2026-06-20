# Architecture

> **Status:** first end-to-end vertical slice landed (Manager → worker waves → Leader, streamed over SSE,
> with per-crew memory). This document describes the system **as it exists in code today**, with claims
> pointing at real files and line ranges.
>
> **Verification status:** ✅ **executed end-to-end against a live Ollama.** `uv sync` resolves on Python 3.13;
> `uv run pytest` is green (21/21); the `soc_crew` runs end to end both headless (`scripts/run_crew.py`) and over
> HTTP/SSE (`POST /runs` → `GET /runs/{id}/stream`), producing waves `[[triage], [threat_intel, forensics]]`,
> validated worker JSON, a streamed prose `final`, and a memory write.
> **Phase 1 (persistence)** verified: after a full server restart, `GET /runs/{id}` returns the run from
> `runs.sqlite`; graph state is checkpointed to `checkpoints.sqlite`. **Phase 2 (hardening)** verified: a file
> upload's IOC reached the triage worker live, run cancellation ends `cancelled`, and an Ollama outage ends a run
> `error` + `done` (tested with a fake client). See [Running it](#running-it).
>
> Companion docs: [`BUILD_SPEC.md`](BUILD_SPEC.md) is the pre-code blueprint (the *intended* design);
> [`PROJECT_VISION.md`](PROJECT_VISION.md) is the what/why. Where this file and `BUILD_SPEC.md` disagree on a
> **fact**, this file wins — it tracks the code; the spec tracks the intent.

---

## 1. System overview

CrewForge runs a hierarchical crew of agents against a local Ollama model and streams the run to the browser
live. One run is: **Manager** plans (reads crew memory, writes one task per worker) → **Workers** execute in
dependency-ordered parallel waves (each returns validated JSON) → **Leader** synthesizes a single prose answer
and writes a summary back to the crew's memory. The orchestration is a LangGraph built per crew
([`backend/app/engine/graph_builder.py`](backend/app/engine/graph_builder.py)); the web layer is a thin FastAPI
shell that starts a run and serializes the engine's event stream as Server-Sent Events
([`backend/app/api/runs.py`](backend/app/api/runs.py)). The engine is domain-agnostic — all domain knowledge
lives in agent YAML under [`config/`](config/), never in `engine/`.

State: build-order steps 1–5 from [`CLAUDE.md`](.claude/CLAUDE.md) are implemented (schemas + config loading,
Ollama client, engine, FastAPI + SSE, memory), plus **Phase 1 persistence** (LangGraph SQLite checkpointer +
durable run history) and **Phase 2 hardening** (file upload, run cancellation, Ollama-failure handling,
configurable context budget, SSE keep-alive). **Phase 3 (frontend)** is built: a React + Tailwind + TypeScript
app in [`frontend/`](frontend/) consumes the SSE contract live (see [§3](#3-project-structure) tree and
[§10](#10-known-issues--deferred)).

## 2. Tech stack

Floors are declared in [`pyproject.toml`](pyproject.toml); **resolved** versions are from `uv.lock` after the
first `uv sync` (Python provisioned: **3.13.0**).

| Concern | Choice | Resolved | Declared / used in |
|---|---|---|---|
| Language | Python ≥ 3.11 | 3.13.0 | [`pyproject.toml`](pyproject.toml) |
| Web framework | FastAPI (async) | 0.138.0 | [`backend/app/main.py`](backend/app/main.py) |
| ASGI server | uvicorn | 0.49.0 | dependency |
| HTTP client (→ Ollama) | httpx | 0.28.1 | [`backend/app/llm/ollama_client.py`](backend/app/llm/ollama_client.py) |
| Data / config models | pydantic / pydantic-settings | 2.13.4 / 2.14.2 | [`backend/app/models/`](backend/app/models/) |
| Orchestration | LangGraph | 1.2.6 | [`backend/app/engine/graph_builder.py`](backend/app/engine/graph_builder.py) |
| LLM + embeddings | Ollama (local HTTP API) | — | [`backend/app/llm/ollama_client.py`](backend/app/llm/ollama_client.py) |
| Vector memory | Chroma (persistent, per-crew collection) | 1.5.9 | [`backend/app/memory/crew_memory.py`](backend/app/memory/crew_memory.py) |
| Run persistence | LangGraph SQLite checkpointer + aiosqlite | 3.1.0 / 0.22.1 | [`main.py`](backend/app/main.py), [`persistence/run_store.py`](backend/app/persistence/run_store.py) |
| Config format | YAML (pyyaml) | 6.0.3 | [`backend/app/config_loader.py`](backend/app/config_loader.py) |
| Output validation | jsonschema | 4.26.0 | [`backend/app/engine/json_utils.py`](backend/app/engine/json_utils.py) |
| Package manager | `uv` | 0.11.14 | [`pyproject.toml`](pyproject.toml) |

> **Note — LangGraph resolved to 1.x** (the `>=0.2` floor allowed it). The core API used here
> (`StateGraph`, `add_node`/`add_edge`, `set_entry_point`, `compile`, `ainvoke`, `END`) works unchanged on 1.2.6;
> graph build + run are verified (§ verification status). Default model tags are `qwen2.5:7b` (workers + roles)
> and `nomic-embed-text` (memory), matching the locally installed models.

**Deviations from `BUILD_SPEC.md`:** none material at the backend level. The SQLite checkpointer (a spec item)
is now wired ([`graph_builder.py:83`](backend/app/engine/graph_builder.py#L83), opened in the
[`main.py`](backend/app/main.py) lifespan). The frontend (spec §) is not built yet.

## 3. Project structure

Real tree (excluding `__pycache__`, `data/`, and the not-yet-created `frontend/`):

```
crewforge/
├── pyproject.toml                     # uv-managed; deps + hatchling build (packages=["backend"])
├── .env.example                       # OLLAMA_BASE_URL, DEFAULT_MODEL, EMBED_MODEL, REQUEST_TIMEOUT, …
│
├── config/
│   ├── agents/                        # one YAML per worker
│   │   ├── triage.yaml                #   produces: extracted_iocs
│   │   ├── threat_intel.yaml          #   consumes: extracted_iocs ; produces: ioc_reputation
│   │   └── forensics.yaml             #   consumes: extracted_iocs ; produces: investigation
│   ├── crews/
│   │   └── soc_crew.yaml              # workers + explicit execution_plan (triage → {intel, forensics})
│   └── system_roles/
│       ├── manager.yaml               # built-in Manager prompt
│       └── leader.yaml                # built-in Leader prompt
│
├── backend/app/
│   ├── main.py                        # FastAPI app, router registration, CORS, lifespan
│   ├── settings.py                    # Settings (env/.env) + get_settings(); all paths derive here
│   ├── config_loader.py               # YAML → validated models, + write_*; cross-reference checks
│   │
│   ├── models/                        # Pydantic data shapes (config + run-time)
│   │   ├── agent.py                   # AgentConfig, AgentSummary, ToolSpec (reserved)
│   │   ├── crew.py                    # CrewConfig, CrewSummary, DependencySpec
│   │   ├── run.py                     # RunRequest, AgentResult, the RunEvent union, RunRecord
│   │   └── system_role.py             # SystemRoleConfig (manager | leader)
│   │
│   ├── llm/ollama_client.py           # async streaming generate() + embed(); the ONLY Ollama caller
│   ├── memory/crew_memory.py          # Chroma per-crew: read() (Manager) / write() (Leader)
│   ├── persistence/run_store.py       # aiosqlite RunRecord store (durable run history)
│   │
│   ├── engine/                        # the orchestration engine — domain-agnostic
│   │   ├── state.py                   # CrewState (TypedDict) + the `results` merge reducer
│   │   ├── planner.py                 # pure: dependencies → execution waves; cycle detection
│   │   ├── json_utils.py              # tolerant JSON extract + jsonschema validate
│   │   ├── prompt_utils.py            # shared prompt helpers (capped uploaded-file block)
│   │   ├── events.py                  # Emitter (queue) + KEEPALIVE; carries RunEvents to SSE
│   │   ├── graph_builder.py           # build(CrewConfig) → compiled LangGraph + plan
│   │   ├── runner.py                  # run lifecycle: start / run_events / get_record / list; persists records
│   │   └── nodes/
│   │       ├── manager.py             # plan + dispatch; the ONLY memory reader
│   │       ├── worker.py              # generic worker factory; stream + validate-and-repair; tool seam
│   │       └── leader.py              # synthesize prose; the ONLY memory writer
│   │
│   └── api/                           # thin FastAPI routers
│       ├── agents.py                  # GET/POST/PUT over config/agents
│       ├── crews.py                   # GET/POST/PUT over config/crews
│       └── runs.py                    # POST /runs(+/upload), /runs/{id}/stream, /cancel, GET /runs(/{id})
│
├── scripts/run_crew.py                # headless run (no FastAPI/SSE) — exercises the engine directly
├── tests/test_planner.py              # unit tests for the pure planner
│
└── frontend/                          # React + Tailwind v4 + TS (Vite); design per DESIGN.md
    ├── index.html                     # loads IBM Plex Sans/Mono; dark color-scheme
    ├── vite.config.ts                 # dev proxy: /agents /crews /runs /health → :8000
    └── src/
        ├── main.tsx                   # router (createBrowserRouter)
        ├── index.css                  # Tailwind v4 @theme tokens (OKLCH, AA-verified)
        ├── types.ts                   # TS mirror of models/run.py (RunEvent union, RunRecord, …)
        ├── api/client.ts              # fetch wrappers over the REST surface
        ├── hooks/
        │   ├── useRunStream.ts        # EventSource + exhaustive RunEvent reducer (rAF-batched)
        │   └── useAsync.ts            # load/loading/error/reload for REST reads
        ├── lib/status.tsx             # status → icon+label+color (state is never color-only)
        ├── components/                # AppShell, AgentLanePanel (signature), LeaderPanel,
        │   │                          #   StartRun, RunRow, PageHeader, icons, ui (primitives)
        └── pages/                     # Dashboard, RunView (hero), RunHistory, Composer, Library
```

## 4. Orchestration

**The graph (built per crew).** [`graph_builder.build()`](backend/app/engine/graph_builder.py#L33) loads each
worker's `AgentConfig`, the Manager/Leader role configs (applying any crew prompt override), computes the plan,
and wires the nodes:

- Entry point is the Manager node ([`graph_builder.py:76`](backend/app/engine/graph_builder.py#L76)).
- [`_wire_waves()`](backend/app/engine/graph_builder.py#L82) adds edges `Manager → wave₀ → wave₁ → … → Leader`.
  Each node in a wave gets an edge from **every** node in the previous barrier, so a wave waits for all of the
  previous wave; LangGraph runs same-wave nodes concurrently. A crew with no workers wires Manager → Leader
  directly.
- The node names `__manager__` / `__leader__` are the reserved sentinels from
  [`state.py:18-19`](backend/app/engine/state.py#L18-L19), reused as the `agent_id` on their SSE events.

**Shared state.** [`CrewState`](backend/app/engine/state.py#L22) is a `TypedDict`. The one detail that matters
for correctness: `results` carries a **merge reducer**
([`state.py:33`](backend/app/engine/state.py#L33), `Annotated[dict[str, AgentResult], or_]`) so parallel workers
in the same wave each return `{"results": {their_id: …}}` and get merged by key instead of clobbering each other.

**The planner is pure** ([`planner.py`](backend/app/engine/planner.py), no I/O, no LLM). Precedence
([`planner.py:27-66`](backend/app/engine/planner.py#L27-L66)): explicit `execution_plan` wins, else dependencies
are inferred from agents' `consumes`/`produces`, else a single all-parallel wave. `_waves()` is a Kahn-style
layered topological sort that raises `PlanError` naming the agents in a cycle
([`planner.py:92`](backend/app/engine/planner.py#L92)) rather than looping forever. It is unit-tested in
[`tests/test_planner.py`](tests/test_planner.py).

> **Design note — where the Manager's runtime ordering went.** `BUILD_SPEC.md` lists "Manager-provided order"
> as a precedence tier between the explicit plan and `consumes`/`produces` inference. In this slice the graph
> topology is fixed at **build** time (before the Manager runs), so the Manager writes task descriptions but does
> not reshape waves. This honors "user plan wins" exactly and keeps the engine simple; runtime Manager-decided
> reordering would require dynamic graph construction (e.g. LangGraph `Send`) and is deferred. Captured in
> [§9](#9-design-decisions) and the planner module docstring.

**Nodes.**
- **Manager** ([`nodes/manager.py`](backend/app/engine/nodes/manager.py)): emits `agent_status`, calls
  `crew_memory.read` (the only reader, top-`manager_memory_k`), asks the LLM for a `{worker_id: task}` map, and
  writes `tasks` + `plan` into state. Its prompt includes any uploaded file (capped). A malformed/missing task
  falls back to a generic per-worker task
  ([`manager.py:96-100`](backend/app/engine/nodes/manager.py#L96-L100)) so a Manager hiccup never kills the run.
- **Worker** ([`nodes/worker.py`](backend/app/engine/nodes/worker.py)): one generic factory
  ([`make_worker_node`, `worker.py:32`](backend/app/engine/nodes/worker.py#L32)), never a node per agent. It
  reads only the upstream outputs it depends on
  ([`worker.py:120-127`](backend/app/engine/nodes/worker.py#L120-L127)), assembles a prompt that includes the
  capped uploaded file ([`worker.py:130-154`](backend/app/engine/nodes/worker.py#L130-L154)), streams tokens out,
  then validates output against the agent's `output_schema` with **one repair retry**
  ([`worker.py:86-118`](backend/app/engine/nodes/worker.py#L86-L118)) before recording an `error` result. The
  reserved **tool seam** is a documented comment block at
  [`worker.py:52-57`](backend/app/engine/nodes/worker.py#L52-L57) — no tool execution in v1.
- **Leader** ([`nodes/leader.py`](backend/app/engine/nodes/leader.py)): streams a prose answer tagged
  `__leader__`, then calls `crew_memory.write` (the only writer). It passes **selected, summarized** structured
  fields to its prompt ([`leader.py:76-116`](backend/app/engine/nodes/leader.py#L76-L116)) — long arrays/strings
  are capped (`leader_max_array_items`, `leader_max_str_len` in [`settings.py`](backend/app/settings.py)) — as
  the defense against blowing the context window.

**Streaming out.** Nodes never format SSE. They push `RunEvent`s onto an
[`Emitter`](backend/app/engine/events.py#L22) (an `asyncio.Queue`; `emit` uses `put_nowait` so it is safe to call
from a cancelled task's cleanup). The runner drains it and the API serializes each event. Token events are
emitted chunk-by-chunk as Ollama streams
([`worker.py:156-166`](backend/app/engine/nodes/worker.py#L156-L166)). The worker prompt embeds the agent's
`output_schema` so the model emits the exact required field names
([`worker.py:145-152`](backend/app/engine/nodes/worker.py#L145-L152)).

## 5. API surface

All routes are unauthenticated (local-first, single user). Registered in
[`main.py:35-37`](backend/app/main.py#L35-L37).

| Method | Path | What it does | Source |
|---|---|---|---|
| GET | `/health` | Liveness probe | [`main.py:41`](backend/app/main.py#L41) |
| GET | `/agents` | List agent summaries | [`api/agents.py:19`](backend/app/api/agents.py#L19) |
| GET | `/agents/{id}` | One agent's full config | [`api/agents.py:24`](backend/app/api/agents.py#L24) |
| POST | `/agents` | Create an agent (writes `config/agents/{id}.yaml`) | [`api/agents.py:32`](backend/app/api/agents.py#L32) |
| PUT | `/agents/{id}` | Update an agent (path/body id must match) | [`api/agents.py:40`](backend/app/api/agents.py#L40) |
| GET | `/crews` | List crew summaries | [`api/crews.py:19`](backend/app/api/crews.py#L19) |
| GET | `/crews/{id}` | One crew (workers + optional plan) | [`api/crews.py:24`](backend/app/api/crews.py#L24) |
| POST | `/crews` | Create a crew (validates worker refs + plan) | [`api/crews.py:32`](backend/app/api/crews.py#L32) |
| PUT | `/crews/{id}` | Update a crew | [`api/crews.py:40`](backend/app/api/crews.py#L40) |
| POST | `/runs` | Start a run (JSON) → `{run_id}` | [`api/runs.py:33`](backend/app/api/runs.py#L33) |
| POST | `/runs/upload` | Start a run from a multipart file upload (text extracted in the API) | [`api/runs.py:43`](backend/app/api/runs.py#L43) |
| GET | `/runs` | List run history (durable; newest first) | [`api/runs.py:61`](backend/app/api/runs.py#L61) |
| GET | `/runs/{id}/stream` | SSE stream of run events (with keep-alive) | [`api/runs.py:66`](backend/app/api/runs.py#L66) |
| POST | `/runs/{id}/cancel` | Cancel an in-flight run → `cancelled` record | [`api/runs.py:92`](backend/app/api/runs.py#L92) |
| GET | `/runs/{id}` | Fetch a run's record (memory, else `runs.sqlite`) | [`api/runs.py:100`](backend/app/api/runs.py#L100) |

**SSE events** are defined once as a discriminated union in
[`models/run.py:41-90`](backend/app/models/run.py#L41-L90) and serialized verbatim by the stream endpoint
([`api/runs.py:76`](backend/app/api/runs.py#L76)). Emitted types and where they originate:

| `type` | Fields | Emitted by |
|---|---|---|
| `plan` | `waves: string[][]` | runner, before the graph runs ([`runner.py:87`](backend/app/engine/runner.py#L87)) |
| `agent_status` | `agent_id`, `status` | every node on start/finish |
| `token` | `agent_id`, `text` | worker + leader, per chunk |
| `agent_result` | `agent_id`, `output` | worker on success |
| `final` | `answer` | leader |
| `error` | `agent_id?`, `message` | worker (per-agent) / runner (whole run) |
| `done` | — | runner, always last ([`runner.py:110`](backend/app/engine/runner.py#L110)) |

The stream endpoint sets `Cache-Control: no-cache` and `X-Accel-Buffering: no`
([`api/runs.py:84-87`](backend/app/api/runs.py#L84-L87)) so tokens flush live instead of being held by a proxy,
and emits an SSE comment every 15 s while idle (the `KEEPALIVE` sentinel from the emitter) so the connection
survives idle proxies. **One SSE consumer per run** — the stream launches the graph on first connect and drains a
single queue; `GET /runs/{id}` is the way to inspect a run from elsewhere.

Uploaded files arrive via `POST /runs/upload` (multipart); text is extracted in the API
([`_extract_text`, `api/runs.py:109`](backend/app/api/runs.py#L109)) and handed to the engine as
`uploaded_file` — the engine never sees a raw upload.

## 6. Configuration

The Pydantic models in [`backend/app/models/`](backend/app/models/) are the schema of record;
[`config_loader.py`](backend/app/config_loader.py) loads and validates YAML into them, naming the offending file
and field on any error ([`ConfigError`, `config_loader.py:19`](backend/app/config_loader.py#L19)).

- **Agent** ([`models/agent.py:31`](backend/app/models/agent.py#L31)): `id, name, description, model?,
  system_prompt, consumes[], produces[], tools[] (reserved, empty in v1), output_schema`. The loader enforces
  `id == filename stem` ([`config_loader.py:61-64`](backend/app/config_loader.py#L61-L64)).
- **Crew** ([`models/crew.py:22`](backend/app/models/crew.py#L22)): `id, name, description?, workers[],
  execution_plan?, manager_prompt_override?, leader_prompt_override?`. The loader cross-checks that every worker
  resolves to an agent file and every plan entry (and its `depends_on`) is one of the crew's workers
  ([`config_loader.py:123-163`](backend/app/config_loader.py#L123-L163)).
- **System role** ([`models/system_role.py:10`](backend/app/models/system_role.py#L10)): `role (manager|leader),
  model?, system_prompt`.

**Validation on write is the same as on load** — `write_agent` / `write_crew` re-run model validation and
reference checks before persisting ([`config_loader.py:76-84`](backend/app/config_loader.py#L76-L84),
[`config_loader.py:113-121`](backend/app/config_loader.py#L113-L121)), so a UI-created file is as safe as a
hand-written one.

**Checked-in examples** live in [`config/`](config/): three agents (`triage`, `threat_intel`, `forensics`), one
crew (`soc_crew`) with an explicit plan, and the two system roles. With `soc_crew`'s plan, the planner resolves
the waves `[["triage"], ["threat_intel", "forensics"]]`.

## 7. Data flow (one run)

1. **Start.** `POST /runs` (or `/runs/upload`) → `Runner.start()` validates the crew and registers a `_Session`
   with a fresh `run_id` ([`runner.py:77-91`](backend/app/engine/runner.py#L77-L91)). No work runs yet.
2. **Stream opens.** `GET /runs/{id}/stream` → `Runner.run_events()` lazily launches the graph as a background
   task on first connect ([`runner.py:93-103`](backend/app/engine/runner.py#L93-L103)) and drains the emitter
   queue; the SSE endpoint serializes each event.
3. **Plan.** The runner emits the `plan` event from the build-time waves
   ([`runner.py:161`](backend/app/engine/runner.py#L161)).
4. **Manager.** Reads memory (`crew_memory.read`), writes one task per worker (its prompt includes any upload).
5. **Worker waves.** Each wave runs concurrently; workers stream tokens, validate JSON, and merge results into
   state.
6. **Leader.** Streams the prose `final` answer, then writes a summary via `crew_memory.write`.
7. **Finish.** The runner records the final `RunRecord` and always emits `done`
   ([`runner.py:181-194`](backend/app/engine/runner.py#L181-L194)) — including on error or cancellation, so the
   stream never hangs.

**Cancellation (Phase 2).** `POST /runs/{id}/cancel` → `Runner.cancel()` cancels the graph task; `_execute`
catches `CancelledError`, marks the record `cancelled`, and emits `error` + `done`
([`runner.py:181-186`](backend/app/engine/runner.py#L181-L186)). **Ollama outage:** a failed call raises
`OllamaError`, surfaced as a worker `error` result or (for Manager/Leader) caught by `_execute` → `error` +
`done`. Neither hangs the run.

**Persistence (Phase 1).** The runner writes the `RunRecord` to the `RunStore` (`runs.sqlite`) at **start**
(`pending`), at **running**, and at the **end** (`done`/`error`/`cancelled`) via `_persist`
([`runner.py:196`](backend/app/engine/runner.py#L196)), so `GET /runs/{id}` and `GET /runs` survive a restart.
Independently, the graph is compiled with a LangGraph `AsyncSqliteSaver`
([`runner.py:153`](backend/app/engine/runner.py#L153)) and run with `thread_id == run_id`
([`runner.py:175`](backend/app/engine/runner.py#L175)), checkpointing graph state per superstep to
`checkpoints.sqlite`. Both stores are opened in the [`main.py`](backend/app/main.py) lifespan and attached via
`runner.configure(...)`; the headless/test path runs with neither.

**Memory boundary** is enforced by import discipline: only [`nodes/manager.py:17`](backend/app/engine/nodes/manager.py#L17)
imports `crew_memory` (for `read`), and only [`nodes/leader.py:16`](backend/app/engine/nodes/leader.py#L16) imports
it (for `write`). Workers never import it.

## 8. Data stores

- **Chroma (per-crew memory).** A persistent client rooted at `data/chroma/`
  ([`crew_memory.py:33-38`](backend/app/memory/crew_memory.py#L33-L38)); one collection per crew named
  `crew_{crew_id}` ([`crew_memory.py:41-44`](backend/app/memory/crew_memory.py#L41-L44)), get-or-created on first
  use. Embeddings come from local Ollama (`EMBED_MODEL`). The Leader writes a compact summary keyed by `run_id`
  ([`crew_memory.py:65`](backend/app/memory/crew_memory.py#L65)); the Manager reads top-k (default 5)
  ([`crew_memory.py:47`](backend/app/memory/crew_memory.py#L47)). Crews never share a collection.
- **Run history (`data/runs.sqlite`).** A single `runs` table of `RunRecord`s (status, plan, results JSON,
  answer, error, timestamps), written by [`persistence/run_store.py`](backend/app/persistence/run_store.py)
  (`upsert`/`get`/`list`, one connection per op). The runner keeps live runs in memory
  ([`runner.py:64`](backend/app/engine/runner.py#L64)) and falls back to this store, so records survive a restart.
- **LangGraph checkpoints (`data/checkpoints.sqlite`).** `AsyncSqliteSaver` persists CrewState per superstep,
  keyed by `thread_id == run_id` — durable graph state for inspection/resume. Opened in the lifespan
  ([`main.py:30`](backend/app/main.py#L30)). Both DB paths come from [`settings.py`](backend/app/settings.py)
  (`runs_db`, `checkpoint_db`).

## 9. Design decisions

- **LangGraph for orchestration.** A crew is naturally a DAG (waves with barriers); LangGraph's superstep model
  gives same-wave parallelism and a shared reducer-merged state for free. The reducer on `results` is the
  load-bearing piece ([`state.py:33`](backend/app/engine/state.py#L33)).
- **SSE, not WebSocket.** Runs are one-way server→client token streams; `StreamingResponse` is enough and
  simpler. WebSocket is reserved for a future human-in-the-loop feature.
- **Manager reads / Leader writes memory.** A single read path and a single write path keep the boundary
  enforceable by import discipline, so memory access can't quietly leak into workers.
- **Build-time wave topology.** The graph is shaped from config before the run, which makes "user plan wins"
  exact and the engine simple, at the cost of deferring runtime Manager-decided reordering (see [§4](#4-orchestration)).
- **Generic worker node.** One factory parameterized by `AgentConfig` keeps "config is data" true — adding an
  agent is a new YAML file, never engine code.
- **Two persistence stores, by concern (Phase 1).** A LangGraph checkpointer (`checkpoints.sqlite`) holds
  low-level graph state for resume/inspection; a separate `RunStore` (`runs.sqlite`) holds the API-facing
  `RunRecord` (status/plan/results/answer). Keeping them apart avoids forcing run-status semantics onto the
  checkpoint schema, and lets `GET /runs` list history cheaply.

## 10. Known issues / deferred

No `KNOWN_ISSUES.md` yet; tracked inline until one is warranted.

- **~~Not executed end-to-end.~~ Resolved (Phase 0).** Verified headless + over SSE against live Ollama on
  `qwen2.5:7b` + `nomic-embed-text`. (Quality caveat: a 7B local model needs the schema shown in-prompt to emit
  correct field names — now done in [`worker.py:126-138`](backend/app/engine/nodes/worker.py#L126-L138).)
- **~~SQLite checkpointer / durable run history deferred.~~ Resolved (Phase 1).** `checkpoints.sqlite` (graph
  state) + `runs.sqlite` (`RunRecord`s) are wired; verified that `GET /runs/{id}` survives a full restart.
- **Runtime Manager reordering deferred.** See [§4](#4-orchestration) design note.
- **Single SSE consumer per run — by design (Phase 2).** The stream launches the graph on first connect and
  drains one queue; a second concurrent reader would compete for events. This is intentional for the
  single-user local model and is documented on the endpoint; `GET /runs/{id}` covers out-of-band inspection. A
  keep-alive comment is emitted every 15 s so idle proxies don't drop the stream.
- **Upload extraction is text-only (Phase 2).** `POST /runs/upload` decodes uploads as UTF-8; PDF/DOCX
  extraction is a future enhancement. Binary uploads decode leniently.
- **~~Frontend not built.~~ Resolved (Phase 3).** A React + Tailwind v4 + TypeScript app (Vite) lives in
  [`frontend/`](frontend/) and consumes the [§5](#5-api-surface) SSE contract. The run view is driven entirely by
  a typed `RunEvent` reducer ([`useRunStream.ts`](frontend/src/hooks/useRunStream.ts), mirroring
  [`models/run.py:41-90`](backend/app/models/run.py#L41-L90)); the visual system follows
  [`DESIGN.md`](DESIGN.md). Surfaces: Dashboard, Run view (hero), Composer (beginner + opt-in step designer),
  History, Library. `tsc -b && vite build` passes. Live verification against a running backend is pending the
  developer's check.

## Running it

```bash
uv sync                                              # resolve + install deps into .venv
cp .env.example .env                                 # adjust OLLAMA_BASE_URL / models if needed
ollama pull qwen2.5:7b && ollama pull nomic-embed-text

# Headless (no web layer) — exercises the engine directly:
uv run python scripts/run_crew.py soc_crew "Investigate failed SSH logins from 203.0.113.7 on web-01."

# Web layer:
uv run uvicorn backend.app.main:app --reload
#   POST /runs {"crew_id":"soc_crew","user_input":"…"} → {run_id}; then open GET /runs/{run_id}/stream

# Pure unit tests (no Ollama needed):
uv run pytest
```

## Staleness discipline

Keep this honest as code moves:
- **Every claim is checkable** — prefer `path/file.py:120-135` over prose.
- **Audit before significant updates** — re-verify routers, models, the graph builder, and (once it exists) the
  frontend route table against source; record mismatches with severity in `ARCHITECTURE_AUDIT.md`.
- **Doc vs. behavior** — "code doesn't match doc" (fix one) is different from "code matches doc but runtime
  differs" (a `KNOWN_ISSUES.md` entry).
- **Pin a commit** once this is a git repo, and update the [§2](#2-tech-stack) versions to the `uv.lock`-resolved
  ones after the first `uv sync`.
