# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Read first

Before writing any code, read `PROJECT_VISION.md` (what we're building and why) and `BUILD_SPEC.md` (the technical blueprint for the initial build). This file covers *how to work in the repo*; those cover *what to build*.

Note the difference between two technical docs:
- **`BUILD_SPEC.md`** — the greenfield blueprint. Describes the system *to be built*. This is your primary reference while implementing.
- **`ARCHITECTURE.md`** — currently a placeholder. It is written *after* code exists, to describe what the code *actually is*, with claims pointing at real files. Do not treat it as a source of build instructions; fill it in once the first end-to-end slice runs.

## What this project is, in one paragraph

A local-first multi-agent orchestration platform. A Python backend (FastAPI) wraps a LangGraph orchestration that runs a hierarchical crew of agents — a built-in Manager that plans, user-chosen Workers that execute in a dependency graph, and a built-in Leader that synthesizes — against a local Ollama model. A React + Tailwind frontend lets users compose crews and watch runs stream live over SSE. Each crew has its own persistent memory in a Chroma vector store.

## Tech stack (do not substitute without asking)

- **Backend language:** Python 3.11+
- **Web framework:** FastAPI (async). Streaming to the client is **SSE** via `StreamingResponse`, not WebSocket.
- **Orchestration:** LangGraph. Each agent is a node; dependencies are edges; independent workers fan out in parallel.
- **LLM:** Ollama, local, via its HTTP API. No cloud providers.
- **Embeddings:** Ollama local embedding model (e.g. `nomic-embed-text` or `mxbai-embed-large`).
- **Vector store / memory:** Chroma, one collection per crew.
- **Run state / checkpointing:** LangGraph checkpointer backed by SQLite.
- **Config:** YAML files for agents and crews.
- **Frontend:** React + Tailwind CSS. TypeScript preferred.
- **Package management:** use `uv` for Python (the developer prefers it over pip).

## Non-negotiable design rules

These come straight from the design discussion. Treat them as constraints, not suggestions.

1. **Manager and Leader are built-in system roles.** Every crew has exactly one of each. The user cannot add or remove them. The user *can* edit their prompts (via separate system-role config). Workers are the only members the user composes.

2. **The orchestration engine is domain-agnostic.** No security-specific logic in the engine. Anything domain-specific lives in agent YAML (prompts, and later, tools). If you find yourself writing "if alert type == ..." in the engine, stop — that belongs in an agent.

3. **Execution order: user plan wins.** If the crew/run specifies dependencies, honor them exactly; the Manager only writes task descriptions, it does not override order. If no order is specified, the Manager decides the order (and may use agents' declared `consumes`/`produces` to infer it).

4. **Agent-to-agent output is JSON; the final user-facing answer is free text.** Workers must return structured JSON with named fields. The Leader returns prose.

5. **Memory is per-crew and persists across runs.** The Manager *reads* relevant past context from the crew's Chroma collection at the start of a run. The Leader's conclusion is summarized and *written* to that collection at the end. Workers and the Leader do not query memory directly — they receive context through the Manager's task descriptions. Crews never share memory.

6. **Config is data.** Adding or editing an agent/crew is editing YAML (by hand or via the UI), never editing engine code.

7. **Tools are reserved, not implemented in v1.** Keep a `tools: []` field in the agent schema and a clean seam in the agent-execution node, but do not build tool-calling yet.

8. **Runs are synchronous and streamed.** No background job queue. The user triggers a run and watches tokens stream until completion.

## Build order (suggested)

Work in vertical slices so something runs end-to-end early.

1. **Schemas + config loading.** Define the YAML schema for agents and crews (Pydantic models). Load and validate them. Ship a couple of example agents and one example crew.
2. **Ollama client.** Thin async wrapper over the Ollama HTTP API: a `generate`/`chat` call that can stream tokens, and an `embed` call.
3. **Engine — happy path, no memory.** Build the LangGraph: Manager node → worker nodes (parallel waves from a dependency graph) → Leader node. JSON between workers, prose out of Leader. Make it runnable from a script before any web layer.
4. **FastAPI + SSE.** Wrap the engine: an endpoint to run a crew that streams agent status + tokens as SSE events. Endpoints to list/get/create agents and crews.
5. **Memory.** Add the Chroma per-crew collection: Manager reads at start, Leader summary writes at end. Add the SQLite checkpointer.
6. **Frontend.** Crew picker → worker selection (+ optional advanced step designer) → input (prompt + file upload) → live run view (waves, per-agent status, streaming tokens) → final answer.

Confirm the schema (step 1) with the developer before building far on top of it.

Once step 4 runs end to end (Manager → worker → Leader over SSE), start `ARCHITECTURE.md` describing the real code, and keep it current as later slices land. Follow the staleness discipline documented in that file.

## Coding conventions

- Prefer clear, complete, production-quality code over placeholders or TODO stubs. The developer dislikes half-finished output. If something must be deferred (e.g. tools), say so explicitly and leave a documented seam, don't fake it.
- Async all the way through the request path (FastAPI → engine → Ollama). Don't block the event loop.
- Type everything: Pydantic for data models and config, type hints on functions.
- Keep the engine importable and runnable without the web server (for testing and for the developer's own scripts).
- One concern per module. Engine, LLM client, memory, config, and web layer stay separate.
- Validate YAML config on load with clear error messages naming the offending file and field.

## Skills

This repo carries skills in `.claude/skills/`. Consult the relevant one before working in its area — they encode the project's conventions and the non-negotiable rules above.

- **crewforge-architecture** — where code belongs, the golden rules. Start here for any structural decision.
- **crewforge-orchestration** — the LangGraph engine (nodes, waves, state, streaming).
- **crewforge-agents** — agent/crew YAML, schemas, JSON-between-agents, tools seam.
- **crewforge-memory** — per-crew Chroma, embeddings, read/write boundary.
- **crewforge-api** — FastAPI async + SSE.
- **crewforge-frontend** — React + Tailwind run view and SSE client.

Generic skills are also present (systematic-debugging, test-driven-development, verification-before-completion, webapp-testing, claude-api). See `.claude/skills/README.md` for the full index.

**Frontend design is governed by Impeccable**, installed at `.agents/skills/impeccable/` (it replaces and supersedes Anthropic's `frontend-design`). Do not design UI ad hoc: run `/impeccable init` once to write `PRODUCT.md`/`DESIGN.md`, then use `/impeccable shape` before building UI, `/impeccable craft` to build, and `/impeccable critique` / `audit` / `polish` to review. `crewforge-frontend` owns the data flow; Impeccable owns the look. See `IMPECCABLE_SETUP.md`.

The skills hold *reusable thinking*; concrete facts (file tree, schemas, endpoints) live in `BUILD_SPEC.md` / `ARCHITECTURE.md`. When a skill and a doc disagree on a fact, the doc wins.

## Communication style with the developer

- The developer is Vietnamese; technical discussion may be in Vietnamese or English. Code, comments, and docs stay in English.
- Be concise and concrete. Show file paths and real code, not vague descriptions.
- When a decision is genuinely ambiguous, ask rather than guess — but address what you can first.
- Don't reverse settled design decisions (the ones in "Non-negotiable design rules") without flagging it clearly and explaining why.
