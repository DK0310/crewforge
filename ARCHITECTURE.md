# Architecture

> **Status:** first end-to-end vertical slice landed (Manager → worker waves → Leader, streamed over SSE,
> with per-crew memory). This document describes the system **as it exists in code today**, with claims
> pointing at real files and line ranges.
>
> **Verification status:** ✅ **executed end-to-end against a live Ollama** (Phase 0). `uv sync` resolves on
> Python 3.13; `uv run pytest` is green (5/5); the `soc_crew` runs end to end both headless
> (`scripts/run_crew.py`) and over HTTP/SSE (`POST /runs` → `GET /runs/{id}/stream`), producing waves
> `[[triage], [threat_intel, forensics]]`, validated worker JSON, a streamed prose `final`, and a memory write.
> Verified at commit `93acd7d` on the `main` branch. See [Running it](#running-it).
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

State of the slice: build-order steps 1–5 from [`CLAUDE.md`](.claude/CLAUDE.md) are implemented (schemas + config
loading, Ollama client, engine, FastAPI + SSE, memory). Step 6 (frontend) and the SQLite checkpointer are **not
yet built** — see [§10](#10-known-issues--deferred).

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
| Config format | YAML (pyyaml) | 6.0.3 | [`backend/app/config_loader.py`](backend/app/config_loader.py) |
| Output validation | jsonschema | 4.26.0 | [`backend/app/engine/json_utils.py`](backend/app/engine/json_utils.py) |
| Package manager | `uv` | 0.11.14 | [`pyproject.toml`](pyproject.toml) |

> **Note — LangGraph resolved to 1.x** (the `>=0.2` floor allowed it). The core API used here
> (`StateGraph`, `add_node`/`add_edge`, `set_entry_point`, `compile`, `ainvoke`, `END`) works unchanged on 1.2.6;
> graph build + run are verified (§ verification status). Default model tags are `qwen2.5:7b` (workers + roles)
> and `nomic-embed-text` (memory), matching the locally installed models.

**Deviations from `BUILD_SPEC.md`:**
- **No SQLite checkpointer yet.** The spec lists a LangGraph SQLite checkpointer; the graph currently compiles
  with no checkpointer ([`graph_builder.py:79`](backend/app/engine/graph_builder.py#L79)), and run results are
  kept in memory by the runner instead. The seam is clean (pass a `checkpointer=` to `.compile()`). See
  [§10](#10-known-issues--deferred).
- **`langgraph-checkpoint-sqlite` is not yet a dependency** — add it when the checkpointer lands.

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
│   │
│   ├── engine/                        # the orchestration engine — domain-agnostic
│   │   ├── state.py                   # CrewState (TypedDict) + the `results` merge reducer
│   │   ├── planner.py                 # pure: dependencies → execution waves; cycle detection
│   │   ├── json_utils.py              # tolerant JSON extract + jsonschema validate
│   │   ├── events.py                  # Emitter (asyncio.Queue) carrying RunEvents to the SSE layer
│   │   ├── graph_builder.py           # build(CrewConfig) → compiled LangGraph + plan
│   │   ├── runner.py                  # run lifecycle: start / run_events / get_record; Runner singleton
│   │   └── nodes/
│   │       ├── manager.py             # plan + dispatch; the ONLY memory reader
│   │       ├── worker.py              # generic worker factory; stream + validate-and-repair; tool seam
│   │       └── leader.py              # synthesize prose; the ONLY memory writer
│   │
│   └── api/                           # thin FastAPI routers
│       ├── agents.py                  # GET/POST/PUT over config/agents
│       ├── crews.py                   # GET/POST/PUT over config/crews
│       └── runs.py                    # POST /runs, GET /runs/{id}/stream (SSE), GET /runs/{id}
│
├── scripts/run_crew.py                # headless run (no FastAPI/SSE) — exercises the engine directly
└── tests/test_planner.py              # unit tests for the pure planner
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
  `crew_memory.read` (the only reader), asks the LLM for a `{worker_id: task}` map, and writes `tasks` + `plan`
  into state. A malformed/missing task falls back to a generic per-worker task
  ([`manager.py:77-81`](backend/app/engine/nodes/manager.py#L77-L81)) so a Manager hiccup never kills the run.
- **Worker** ([`nodes/worker.py`](backend/app/engine/nodes/worker.py)): one generic factory
  ([`make_worker_node`, `worker.py:31`](backend/app/engine/nodes/worker.py#L31)), never a node per agent. It
  reads only the upstream outputs it depends on
  ([`worker.py:117-124`](backend/app/engine/nodes/worker.py#L117-L124)), streams tokens out, then validates output
  against the agent's `output_schema` with **one repair retry**
  ([`worker.py:83-114`](backend/app/engine/nodes/worker.py#L83-L114)) before recording an `error` result. The
  reserved **tool seam** is a documented comment block at
  [`worker.py:49-54`](backend/app/engine/nodes/worker.py#L49-L54) — no tool execution in v1.
- **Leader** ([`nodes/leader.py`](backend/app/engine/nodes/leader.py)): streams a prose answer tagged
  `__leader__`, then calls `crew_memory.write` (the only writer). It passes **selected, summarized** structured
  fields to its prompt ([`leader.py:73-108`](backend/app/engine/nodes/leader.py#L73-L108)) — long arrays/strings
  are capped (`_MAX_ARRAY_ITEMS`, `_MAX_STR_LEN`) — as the defense against blowing the context window.

**Streaming out.** Nodes never format SSE. They push `RunEvent`s onto an
[`Emitter`](backend/app/engine/events.py#L17) (an `asyncio.Queue`). The runner drains it and the API serializes
each event. Token events are emitted chunk-by-chunk as Ollama streams
([`worker.py:144-154`](backend/app/engine/nodes/worker.py#L144-L154)). The worker prompt embeds the agent's
`output_schema` so the model emits the exact required field names
([`worker.py:126-138`](backend/app/engine/nodes/worker.py#L126-L138)).

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
| POST | `/runs` | Start a run → `{run_id}` | [`api/runs.py:20`](backend/app/api/runs.py#L20) |
| GET | `/runs/{id}/stream` | SSE stream of run events | [`api/runs.py:30`](backend/app/api/runs.py#L30) |
| GET | `/runs/{id}` | Fetch a run's record (from in-memory store) | [`api/runs.py:53`](backend/app/api/runs.py#L53) |

**SSE events** are defined once as a discriminated union in
[`models/run.py:41-90`](backend/app/models/run.py#L41-L90) and serialized verbatim by the stream endpoint
([`api/runs.py:37`](backend/app/api/runs.py#L37)). Emitted types and where they originate:

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
([`api/runs.py:46-49`](backend/app/api/runs.py#L46-L49)) so tokens flush live instead of being held by a proxy.

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

1. **Start.** `POST /runs` → `Runner.start()` validates the crew and registers a `_Session` with a fresh
   `run_id` ([`runner.py:52-60`](backend/app/engine/runner.py#L52-L60)). No work runs yet.
2. **Stream opens.** `GET /runs/{id}/stream` → `Runner.run_events()` lazily launches the graph as a background
   task on first connect ([`runner.py:62-71`](backend/app/engine/runner.py#L62-L71)) and drains the emitter
   queue; the SSE endpoint serializes each event.
3. **Plan.** The runner emits the `plan` event from the build-time waves
   ([`runner.py:87`](backend/app/engine/runner.py#L87)).
4. **Manager.** Reads memory (`crew_memory.read`), writes one task per worker.
5. **Worker waves.** Each wave runs concurrently; workers stream tokens, validate JSON, and merge results into
   state.
6. **Leader.** Streams the prose `final` answer, then writes a summary via `crew_memory.write`.
7. **Finish.** The runner stores the final `RunRecord` (results + answer) for `GET /runs/{id}` and always emits
   `done` ([`runner.py:101-110`](backend/app/engine/runner.py#L101-L110)).

**Memory boundary** is enforced by import discipline: only [`nodes/manager.py:16`](backend/app/engine/nodes/manager.py#L16)
imports `crew_memory` (for `read`), and only [`nodes/leader.py:16`](backend/app/engine/nodes/leader.py#L16) imports
it (for `write`). Workers never import it.

## 8. Data stores

- **Chroma (per-crew memory).** A persistent client rooted at `data/chroma/`
  ([`crew_memory.py:33-38`](backend/app/memory/crew_memory.py#L33-L38)); one collection per crew named
  `crew_{crew_id}` ([`crew_memory.py:41-44`](backend/app/memory/crew_memory.py#L41-L44)), get-or-created on first
  use. Embeddings come from local Ollama (`EMBED_MODEL`). The Leader writes a compact summary keyed by `run_id`
  ([`crew_memory.py:65`](backend/app/memory/crew_memory.py#L65)); the Manager reads top-k (default 5)
  ([`crew_memory.py:47`](backend/app/memory/crew_memory.py#L47)). Crews never share a collection.
- **Run records.** Held **in memory** by the `Runner` for the process lifetime
  ([`runner.py:50`](backend/app/engine/runner.py#L50)) — there is no persistent run history yet (the SQLite
  checkpointer is deferred; see [§10](#10-known-issues--deferred)). `data/checkpoints.sqlite` is reserved by
  [`settings.py`](backend/app/settings.py) but not yet written.

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
- **In-memory run registry for v1.** Avoids wiring the async SQLite checkpointer before the slice is proven;
  the seam to add it is a one-line `.compile(checkpointer=…)`.

## 10. Known issues / deferred

No `KNOWN_ISSUES.md` yet; tracked inline until one is warranted.

- **~~Not executed end-to-end.~~ Resolved (Phase 0).** Verified headless + over SSE against live Ollama on
  `qwen2.5:7b` + `nomic-embed-text`. (Quality caveat: a 7B local model needs the schema shown in-prompt to emit
  correct field names — now done in [`worker.py:126-138`](backend/app/engine/nodes/worker.py#L126-L138).)
- **SQLite checkpointer deferred.** Run state lives in process memory; restarting the server loses history.
  Build-order step 5's checkpointer is the next backend task.
- **Runtime Manager reordering deferred.** See [§4](#4-orchestration) design note.
- **Single SSE consumer per run.** `run_events` launches the graph on first connect and drains one queue; a
  second concurrent reader of the same run would compete for events. Fine for the single-user local model.
- **Frontend not built.** Build-order step 6. The SSE event contract in [§5](#5-api-surface) is what it will
  consume.

## Running it

```bash
uv sync                                              # resolve + install deps into .venv
cp .env.example .env                                 # adjust OLLAMA_BASE_URL / models if needed
ollama pull llama3.1:8b && ollama pull nomic-embed-text

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
