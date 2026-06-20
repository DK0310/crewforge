# CrewForge Skills

Skills for working on CrewForge. Two groups: **project-specific** (`crewforge-*`, written for this codebase) and **generic** (reusable across projects, copied in from prior work).

The project-specific skills follow one rule: **a skill holds reusable thinking (principles, decision trees, patterns, checklists); concrete facts live in [`BUILD_SPEC.md`](../../BUILD_SPEC.md) (pre-code) and [`ARCHITECTURE.md`](../../ARCHITECTURE.md) (post-code).** A skill never duplicates the file tree, schemas, or endpoint list — it points at those docs.

## Project skills (`crewforge-*`)

| Skill | Use when… |
|---|---|
| **crewforge-architecture** | Deciding where code belongs; the golden rules (engine domain-agnostic, config-as-data, Manager/Leader fixed, user-plan-wins, Manager-reads/Leader-writes, local-first). Start here. |
| **crewforge-orchestration** | Building the LangGraph engine: Manager/Worker/Leader nodes, dependency edges, parallel waves, `CrewState` + reducers, token streaming, the pure planner. |
| **crewforge-agents** | Writing/validating agent & crew YAML, Pydantic config models, the JSON contract between workers, reserving the tools seam. |
| **crewforge-memory** | Per-crew Chroma memory, Ollama embeddings, the read(Manager)/write(Leader) boundary, context-window safety. |
| **crewforge-api** | FastAPI async endpoints, SSE run streaming, forwarding token events, thin CRUD over config YAML. |
| **crewforge-frontend** | React + Tailwind: the SSE run client, the live wave/agent view, the crew composer + advanced step designer. |

## Design authority (`Impeccable`)

Frontend look-and-feel is governed by **Impeccable**, installed separately at `.agents/skills/impeccable/` (not `.claude/skills/`). It replaces Anthropic's `frontend-design` skill (which it is built on and supersedes). The coding agent does **not** design UI ad hoc — all typography, palette, spacing, motion, and component decisions go through Impeccable's commands (`/impeccable shape`, `craft`, `critique`, `audit`, `polish`, …) and its `PRODUCT.md` / `DESIGN.md` context. `crewforge-frontend` owns the *data flow*; Impeccable owns *how it looks*. Setup: see [`IMPECCABLE_SETUP.md`](../../IMPECCABLE_SETUP.md).

## Generic skills (reusable, not CrewForge-specific)

These are general engineering skills carried over from prior projects. Already present in this repo:

| Skill | Use when… |
|---|---|
| **systematic-debugging** | Chasing a bug methodically (root-cause tracing, find-the-polluter, condition-based waiting). |
| **test-driven-development** | Writing tests first; avoiding testing anti-patterns. |
| **verification-before-completion** | The pre-"done" checklist — verify before claiming a task complete. |
| **webapp-testing** | Driving the running web app for end-to-end checks. |
| **claude-api** | Reference for calling the Anthropic API (useful if any agent or tooling talks to it). |

## Maintenance

- When a `crewforge-*` skill and `BUILD_SPEC.md`/`ARCHITECTURE.md` disagree on a **fact**, the doc wins — fix the skill (or, better, the skill shouldn't have stated the fact at all; it should point at the doc).
- When the **way we think** about something changes (a new principle, a new smell), update the skill.
- After the first end-to-end slice, swap every "see BUILD_SPEC.md" emphasis toward ARCHITECTURE.md as the post-code ground truth.
