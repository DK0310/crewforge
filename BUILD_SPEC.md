# Build Spec

> **Status:** greenfield build specification — this describes the system *to be built*, not a system that exists yet.
> It is the blueprint Claude Code follows for the initial implementation. The file tree, schemas, endpoints, and
> event shapes below are the **target**; treat them as the intended design, and propose changes if implementation
> reveals a better path (flag deviations rather than silently diverging).
>
> Once the system is actually running, write `ARCHITECTURE.md` to describe *what the code actually is* — with
> claims pointing at real files and line numbers, kept honest by an audit pass. See `ARCHITECTURE.md` for that
> contract. This file (`BUILD_SPEC.md`) is the pre-code blueprint; `ARCHITECTURE.md` is the post-code ground truth.

Technical structure for the multi-agent crew platform. Read `PROJECT_VISION.md` and `CLAUDE.md` first.

## System overview

```
┌─────────────────────────────────────────────┐
│ Browser — React + Tailwind                    │
│  crew picker · run view · live token stream   │
└───────────────┬───────────────────────────────┘
                │ HTTP (REST) + SSE (run stream)
┌───────────────▼───────────────────────────────┐
│ FastAPI (Python, async)                        │
│  REST: agents / crews / runs                   │
│  SSE: /runs/{id}/stream                        │
│  ┌──────────────────────────────────────────┐ │
│  │ LangGraph orchestration                   │ │
│  │  Manager → Workers (DAG, parallel) → Leader│ │
│  └───────┬───────────────┬───────────────────┘ │
│          │               │                      │
│   ┌──────▼─────┐   ┌──────▼──────┐               │
│   │ Ollama     │   │ Chroma      │               │
│   │ (LLM +     │   │ per-crew    │               │
│   │  embed)    │   │ memory      │               │
│   └────────────┘   └─────────────┘               │
│   SQLite — LangGraph checkpoints / run history  │
└─────────────────────────────────────────────────┘
```

All inference and embeddings are local (Ollama). Memory is a per-crew Chroma collection. Run state is checkpointed to SQLite.

## Repository layout

```
crewforge/
├── PROJECT_VISION.md
├── CLAUDE.md
├── ARCHITECTURE.md
├── README.md
├── pyproject.toml                  # uv-managed
├── .env.example
│
├── config/
│   ├── agents/                     # one YAML per worker agent
│   │   ├── triage.yaml
│   │   ├── threat_intel.yaml
│   │   └── forensics.yaml
│   ├── crews/                      # one YAML per crew
│   │   └── soc_crew.yaml
│   └── system_roles/               # built-in Manager & Leader prompts
│       ├── manager.yaml
│       └── leader.yaml
│
├── backend/
│   └── app/
│       ├── main.py                 # FastAPI app, route registration
│       ├── settings.py             # env config (Ollama URL, model names, paths)
│       │
│       ├── models/                 # Pydantic schemas (data, not engine logic)
│       │   ├── agent.py            # AgentConfig
│       │   ├── crew.py             # CrewConfig, WorkerRef, DependencySpec
│       │   ├── run.py              # RunRequest, RunEvent, AgentResult
│       │   └── system_role.py      # SystemRoleConfig (manager/leader)
│       │
│       ├── config_loader.py        # load + validate YAML into models
│       │
│       ├── llm/
│       │   └── ollama_client.py    # async generate (stream) + embed
│       │
│       ├── memory/
│       │   └── crew_memory.py      # Chroma per-crew: read() and write()
│       │
│       ├── engine/
│       │   ├── state.py            # CrewState (LangGraph state schema)
│       │   ├── graph_builder.py    # build LangGraph from a CrewConfig
│       │   ├── nodes/
│       │   │   ├── manager.py      # plan + dispatch, reads memory
│       │   │   ├── worker.py       # generic worker node factory
│       │   │   └── leader.py       # synthesize, writes memory
│       │   └── planner.py          # dependency resolution → execution waves
│       │
│       └── api/
│           ├── agents.py           # CRUD-ish endpoints for agents
│           ├── crews.py            # CRUD-ish endpoints for crews
│           └── runs.py             # start run, SSE stream
│
├── data/
│   ├── checkpoints.sqlite          # LangGraph checkpointer
│   └── chroma/                     # per-crew vector collections
│
└── frontend/
    ├── package.json
    ├── tailwind.config.js
    └── src/
        ├── main.tsx
        ├── api/                    # fetch wrappers, SSE client
        ├── components/
        │   ├── CrewPicker.tsx
        │   ├── WorkerSelector.tsx
        │   ├── StepDesigner.tsx    # advanced: explicit dependency wiring
        │   ├── RunView.tsx         # waves + per-agent status
        │   ├── AgentStream.tsx     # live token output per agent
        │   └── FinalAnswer.tsx
        └── pages/
            ├── CrewsPage.tsx
            └── RunPage.tsx
```

> **Frontend design authority: Impeccable.** The UI's visual language is not invented during the build.
> Impeccable (installed at `.agents/skills/impeccable/`, replacing Anthropic's `frontend-design`) governs
> all typography, palette, spacing, motion, and component shape. Before building UI, run `/impeccable shape`;
> build with `/impeccable craft`; review with `/impeccable critique` / `audit` / `polish`. Design context
> lives in `PRODUCT.md` / `DESIGN.md` (from `/impeccable init`). The components above define *structure and
> data flow*; their *appearance* must conform to Impeccable. See `IMPECCABLE_SETUP.md`.

## Configuration schemas

### Agent (`config/agents/*.yaml`)

```yaml
id: threat_intel                    # unique, matches filename stem
name: Threat Intel                  # display name
description: >                      # shown in the UI worker picker
  Enriches indicators of compromise with reputation and context.
model: qwen2.5:7b                 # Ollama model tag; falls back to default if omitted
system_prompt: >                    # the agent's role / goal / backstory
  You are a threat intelligence analyst. Given indicators extracted from an
  alert, assess their reputation and known associations. ...

# Declares this agent's I/O contract. Used by the Manager to infer order
# when the user hasn't designed steps explicitly. Both optional.
consumes: [extracted_iocs]          # field names this agent needs upstream
produces: [ioc_reputation]          # field names this agent outputs

# Reserved for a future feature. Always present, empty in v1.
tools: []

# JSON shape this worker must return. Enforced/validated after generation.
output_schema:
  type: object
  required: [summary, findings]
  properties:
    summary:   { type: string }
    findings:  { type: array, items: { type: string } }
    ioc_reputation: { type: object }
```

### Crew (`config/crews/*.yaml`)

```yaml
id: soc_crew
name: SOC Analysis Crew
description: Investigates a security alert end to end.

# Workers chosen for this crew. Manager and Leader are NOT listed here —
# they are injected by the engine for every crew.
workers:
  - triage
  - threat_intel
  - forensics

# OPTIONAL explicit execution plan (advanced mode). When present, the engine
# honors it exactly and the Manager does not decide order. When absent, the
# Manager plans the order (optionally using agents' consumes/produces).
# Each entry: an agent id and the worker ids whose output it depends on.
execution_plan:
  - agent: triage
    depends_on: []
  - agent: threat_intel
    depends_on: [triage]
  - agent: forensics
    depends_on: [triage]

# Optional per-crew overrides for the built-in roles. Omit to use defaults
# from config/system_roles/.
manager_prompt_override: null
leader_prompt_override: null
```

### System roles (`config/system_roles/manager.yaml`, `leader.yaml`)

```yaml
role: manager                       # or: leader
model: qwen2.5:7b 
system_prompt: >
  You are the manager of a team of specialist agents. Read the user's input
  and any relevant memory of past runs. Break the problem into a specific task
  for each available worker. If an execution order is provided, respect it;
  otherwise decide a sensible order and which workers may run in parallel. ...
```

## LangGraph state schema

`CrewState` is the shared object every node reads from and writes to. Workers write into a keyed map so parallel writes don't collide.

```python
class AgentResult(BaseModel):
    agent_id: str
    status: Literal["pending", "running", "done", "error"]
    output: dict | None          # the worker's validated JSON
    error: str | None
    started_at: float | None
    finished_at: float | None

class CrewState(TypedDict):
    crew_id: str
    run_id: str
    user_input: str
    uploaded_file: str | None    # path or extracted text of the upload

    memory_context: str          # past-run context the Manager pulled in
    tasks: dict[str, str]        # agent_id -> task description (from Manager)
    plan: list[list[str]]        # execution waves; e.g. [["triage"], ["threat_intel","forensics"]]

    results: dict[str, AgentResult]   # agent_id -> result (workers write here)
    final_answer: str | None          # Leader's prose output
```

Notes:
- `results` uses a reducer that merges per-key, so workers in the same wave can write concurrently without clobbering each other.
- `plan` is a list of waves; each wave is a list of agent ids that run in parallel. The planner produces it; the worker-dispatch logic iterates waves in order.

## Execution flow (one run)

1. **Start.** `POST /runs` with `{crew_id, user_input, file?}`. Server creates a `run_id`, builds the graph for that crew, opens an SSE stream.
2. **Manager node.**
   - Reads relevant memory: `crew_memory.read(crew_id, user_input)` → top-k past entries → `memory_context`.
   - Calls Ollama with the manager system prompt + input + memory context.
   - Produces `tasks` (one description per worker) and, if no `execution_plan` in the crew config, an ordering.
   - The **planner** turns ordering (user's `execution_plan` if present, else Manager's, else `consumes`/`produces` inference, else all-parallel) into `plan` (waves) via topological sort.
3. **Worker waves.** For each wave in `plan`, dispatch its workers concurrently (LangGraph fan-out / `asyncio`). Each worker:
   - Receives its task description + the JSON outputs of the workers it depends on.
   - Calls Ollama, streaming tokens out as SSE events tagged with its `agent_id`.
   - Parses + validates its output against `output_schema`; stores `AgentResult` in `results`.
4. **Leader node.** Receives all `results`. Calls Ollama with the leader system prompt to synthesize a single prose answer → `final_answer`, streamed to the client.
5. **Memory write.** `crew_memory.write(crew_id, summary_of(final_answer + key results))` — embed via Ollama, upsert into the crew's Chroma collection.
6. **Checkpoint.** LangGraph checkpointer persists state to SQLite throughout, keyed by `run_id`.

## API surface

REST (JSON):

```
GET    /agents                 list available agents (from config/agents)
GET    /agents/{id}            one agent
POST   /agents                 create a new agent (writes a YAML file)
PUT    /agents/{id}            update an agent

GET    /crews                  list crews
GET    /crews/{id}             one crew (workers + optional plan)
POST   /crews                  create a crew (writes a YAML file)
PUT    /crews/{id}             update a crew

POST   /runs                   start a run -> { run_id }
GET    /runs/{id}/stream       SSE: agent status + token events + final
GET    /runs/{id}              fetch a completed run (from checkpoint/history)
```

SSE event types on `/runs/{id}/stream` (one JSON object per `data:` line):

```
{ "type": "plan",          "waves": [["triage"], ["threat_intel","forensics"]] }
{ "type": "agent_status",  "agent_id": "triage", "status": "running" }
{ "type": "token",         "agent_id": "triage", "text": "..." }
{ "type": "agent_result",  "agent_id": "triage", "output": { ... } }
{ "type": "token",         "agent_id": "__leader__", "text": "..." }
{ "type": "final",         "answer": "..." }
{ "type": "error",         "agent_id": "...", "message": "..." }
{ "type": "done" }
```

The frontend uses `plan` to lay out the waves, flips per-agent status pills on `agent_status`, appends `token` events to the matching agent's panel, and renders `final` as the user-facing answer.

## Key implementation notes

- **Planner (`engine/planner.py`).** Pure function: given workers, an optional explicit plan, and agents' `consumes`/`produces`, return `list[list[str]]` waves. Detect cycles and surface a clear error. Precedence: explicit `execution_plan` > Manager-provided order > `consumes`/`produces` inference > single all-parallel wave.
- **Worker node factory (`engine/nodes/worker.py`).** One generic implementation parameterized by `AgentConfig`; do not hand-write a node per agent. Handles prompt assembly (task + upstream JSON), streaming, and JSON validation/repair (one retry on malformed JSON before erroring).
- **Ollama client.** Async, streaming. Surface token chunks via an async generator so nodes can forward them to SSE. Separate `embed()` for memory.
- **Memory boundary.** Only the Manager node imports/calls `crew_memory.read`; only the Leader node calls `crew_memory.write`. Keep this boundary so the rule stays enforceable.
- **Context-window safety.** Worker outputs are JSON; when assembling the Leader prompt, pass structured fields (and summarize long arrays) rather than raw concatenated text, to stay within the model's context window.
- **Engine runnable headless.** `graph_builder.build(crew_config)` returns a compiled graph runnable from a plain script with no FastAPI, for testing and for the developer's own use.
