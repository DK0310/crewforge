---
name: crewforge-architecture
description: Use when designing a new feature, understanding the system structure, or deciding where code belongs in the CrewForge multi-agent orchestration platform
---

# CrewForge — Architecture Skill

This skill holds the **reusable** architectural thinking for this project: principles, decision trees, naming conventions, and review checklists. It tells you *how to think* about where code belongs and why.

> **Project facts live in [BUILD_SPEC.md](../../../BUILD_SPEC.md)** (the greenfield blueprint) and, once code exists, [ARCHITECTURE.md](../../../ARCHITECTURE.md) (the authoritative ground truth: real file tree, schemas, endpoints, SSE event shapes, data stores). This skill does not repeat them — consult those whenever you need a concrete name, path, field, or event type.

---

## Core Principles

1. **The engine is domain-agnostic.** The orchestration engine knows nothing about cybersecurity, polls, research, or any domain. Domain knowledge lives entirely in agent definitions (prompts, and later, tools). If you find yourself writing `if alert_type == ...` or any domain branch inside `engine/`, stop — that belongs in an agent's prompt, not the engine.
2. **Config is data, not code.** Agents and crews are YAML the user (or UI) can create and edit. Adding or changing an agent/crew must never require touching engine code. A new agent is a new YAML file, full stop.
3. **Manager and Leader are fixed system roles.** Every crew has exactly one Manager and one Leader, injected by the engine. The user composes only the workers in between. Users may edit the system-role prompts; they cannot add, remove, or duplicate these roles.
4. **User plan wins over Manager plan.** If a crew/run specifies an execution order, the engine honors it exactly and the Manager only writes task descriptions. Only when no order is given does the Manager decide order (optionally from agents' `consumes`/`produces`).
5. **Structured between agents, prose to the user.** Worker-to-worker communication is validated JSON. The Leader's answer to the user is free-form text. Never leak raw JSON to the user; never pass unstructured prose between workers.
6. **Memory is per-crew, read by Manager, written by Leader.** Each crew owns an isolated vector collection. The Manager is the only role that reads memory; the Leader is the only role that writes it. Crews never share memory. Keep this boundary so it stays enforceable.
7. **Local-first.** All inference and embeddings run on local Ollama. No cloud LLM dependency. Treat any cloud-provider assumption as a smell.

---

## Decision Tree — Which MODULE owns this code?

Map the responsibility to its owning module. (For the concrete module map and file paths, see BUILD_SPEC.md.)

```
WHAT IS THIS ABOUT?

├─ Deciding the order agents run, dispatching them, merging their state?
│  └─ ENGINE (graph_builder / planner / nodes). Domain-free.

├─ A single agent's behavior, role, or I/O contract?
│  └─ AGENT CONFIG (YAML) + the generic worker node. Never a bespoke node per agent.

├─ Talking to the LLM (generate, stream tokens, embed)?
│  └─ LLM CLIENT. The only module that knows the Ollama HTTP API.

├─ Remembering or recalling past runs?
│  └─ MEMORY module (Chroma per-crew). Called only by Manager (read) / Leader (write).

├─ Loading, validating, or shaping agent/crew/role definitions?
│  └─ MODELS (Pydantic) + CONFIG LOADER.

├─ Accepting an HTTP request, streaming SSE, choosing a status code?
│  └─ API layer (FastAPI routers). Thin — no orchestration logic here.

└─ Rendering UI or calling the backend?
   └─ FRONTEND. Every call targets the FastAPI base URL.
```

**Heuristic:** if a change touches how agents coordinate, it's the engine. If it changes what one agent *does*, it's that agent's YAML. These two must never bleed into each other.

---

## Decision Tree — Which LAYER within the backend?

```
IS THE CODE...

├─ Parsing an HTTP request or formatting an SSE event?
│  └─ API ROUTER (thin)

├─ Orchestrating the run (plan → waves → synthesize)?
│  └─ ENGINE (graph + nodes)

├─ A single node's logic (manager / worker / leader)?
│  └─ engine/nodes/* — workers share ONE generic factory

├─ Computing execution order from dependencies?
│  └─ engine/planner.py (pure function, unit-testable)

├─ Calling Ollama (generate/embed)?
│  └─ llm/ollama_client.py (the only caller)

├─ Reading/writing crew memory?
│  └─ memory/crew_memory.py (read = Manager, write = Leader)

├─ Defining the shape of config or run data?
│  └─ models/* (Pydantic)

└─ Turning YAML files into validated models?
   └─ config_loader.py
```

---

## Naming Conventions

| What | Pattern | Example |
|---|---|---|
| Agent config file | `{agent_id}.yaml` (snake_case) | `threat_intel.yaml` |
| Agent id | snake_case noun phrase | `threat_intel` |
| Crew config file | `{crew_id}.yaml` | `soc_crew.yaml` |
| System role file | `{role}.yaml` | `manager.yaml`, `leader.yaml` |
| Pydantic config model | `{Thing}Config` | `AgentConfig`, `CrewConfig` |
| Run-data model | `{Thing}` / `{Thing}Request`/`Event` | `AgentResult`, `RunRequest`, `RunEvent` |
| Engine node module | `engine/nodes/{role}.py` | `manager.py`, `worker.py`, `leader.py` |
| LangGraph state | `CrewState` | `CrewState` |
| API router module | `api/{resources}.py` (plural) | `agents.py`, `crews.py`, `runs.py` |
| API route | lowercase plural | `/agents`, `/crews`, `/runs` |
| SSE event `type` | snake_case | `agent_status`, `token`, `final` |
| Special leader stream id | reserved sentinel | `__leader__` |
| React page | `{Purpose}Page` | `RunPage`, `CrewsPage` |
| React component | PascalCase noun | `RunView`, `WorkerSelector` |
| React hook | `use{What}` | `useRunStream` |
| Chroma collection | `crew_{crew_id}` | `crew_soc_crew` |

---

## Design Heuristics (patterns to reach for)

These are *why and when*. For concrete code, see `crewforge-orchestration`, `crewforge-agents`, `crewforge-memory`, `crewforge-api`, `crewforge-frontend`.

- **One generic worker node, parameterized by `AgentConfig`.** Never hand-write a node per agent. The node assembles the prompt (task + upstream JSON), streams tokens, and validates output against the agent's schema.
- **Planner is a pure function.** Dependency resolution (explicit plan > Manager order > `consumes`/`produces` > single parallel wave) returns `list[list[str]]` waves and detects cycles. No I/O, fully unit-testable.
- **Stream from the node, format at the edge.** Nodes yield token chunks; the API layer wraps them as SSE. Keep SSE formatting out of the engine.
- **Validate-and-repair JSON once.** A worker that returns malformed JSON gets exactly one repair retry before its result is marked `error`. Don't loop indefinitely against a local model.
- **Summarize before you store.** The Leader's full prose isn't what goes into memory — a compact summary of the conclusion + key structured findings is. Keep memory entries small so recall stays cheap and within context limits.
- **Filter fields, don't concatenate text, when building the Leader prompt.** Pass the structured fields that matter; summarize long arrays. This is the main defense against blowing the model's context window.

---

## Heuristic — Adding a New Feature

1. **Is this a new agent capability?** → Write a new agent YAML (prompt + I/O contract + reserved `tools: []`). No engine change. Add it to a crew's worker list.
2. **Is this a new way agents coordinate?** (a new dependency mode, a new wave strategy) → It's an engine change in `planner`/`graph_builder`. Keep it domain-free and unit-test the planner.
3. **Is this a new piece of data crossing the API?** → Add/extend a Pydantic model + a router endpoint + (if needed) an SSE event type. Update the frontend client.
4. **Does it need to recall the past?** → It goes through the Manager (read) / Leader (write) memory boundary. Don't let workers touch memory directly.
5. **Update the docs.** While code doesn't exist yet, refine BUILD_SPEC.md. Once it does, update ARCHITECTURE.md (real files/lines) and keep it audited.

> The domain-agnostic engine is only cheap to keep *if you never let a domain assumption leak into it*. Honor that from day one and the same engine runs a SOC crew, a research crew, or anything else without modification.

---

## Review Checklist — Architectural Smells

| ❌ Smell | ✅ Correct | Why |
|---|---|---|
| `if domain/alert/poll ...` inside `engine/` | Put the behavior in an agent prompt | Engine must stay domain-agnostic |
| A bespoke node class per agent | One generic worker node + `AgentConfig` | Config is data, not code |
| Worker querying Chroma directly | Manager reads, passes context via task | Keeps the memory boundary enforceable |
| Leader reading memory to "remember" | Leader only writes; Manager supplies past context | Single read path |
| Manager overriding a user-supplied plan | User plan wins; Manager only writes tasks | Predictable advanced mode |
| Raw JSON shown to the user | Leader returns prose | Human-friendly output contract |
| Unstructured prose passed between workers | Validated JSON between agents | Reliable downstream parsing |
| Adding/removing Manager or Leader per crew | Fixed roles injected by the engine | They are system roles |
| SSE formatting inside engine nodes | Nodes yield chunks; API formats SSE | Separation of concerns |
| New agent requires editing the engine | New agent = new YAML | Config is data |
| Cloud LLM fallback "just in case" | Local Ollama only | Local-first |
| Crews sharing one Chroma collection | One collection per crew | Memory isolation |
| Planner doing I/O or LLM calls | Planner is pure; nodes do I/O | Testability |

---

## Cross-References

- **Authoritative structure, schema, flows, events** → BUILD_SPEC.md (pre-code) → ARCHITECTURE.md (post-code)
- **Building the LangGraph: nodes, edges, waves, streaming** → `crewforge-orchestration`
- **Agent/crew YAML, schemas, JSON contracts** → `crewforge-agents`
- **Per-crew Chroma memory, read/write boundary** → `crewforge-memory`
- **FastAPI async + SSE, endpoints** → `crewforge-api`
- **React + Tailwind, SSE client, run view** → `crewforge-frontend`
- **Debugging, TDD, verification** → generic skills (`systematic-debugging`, `test-driven-development`, `verification-before-completion`). **UI aesthetics** → Impeccable (design authority, `.agents/skills/impeccable/`)
