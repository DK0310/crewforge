# CrewForge — TODO

Phased plan derived from [`ARCHITECTURE.md`](ARCHITECTURE.md) (§10 deferrals + verification status) and the
build order in [`CLAUDE.md`](.claude/CLAUDE.md). Phases are ordered so each one rests on a proven layer below it.
Check items off as they land; when a phase changes the code, update `ARCHITECTURE.md` (file:line claims) and tick
the matching §10 entry.

**Legend:** `[ ]` todo · `[~]` in progress · `[x]` done · 🔒 blocks later phases · 🎯 acceptance check

---

## Phase 0 — Prove the slice runs (highest priority) 🔒

The whole backend byte-compiles but has **never run against a live Ollama** (ARCHITECTURE.md verification status).
Nothing else is trustworthy until this passes. No new features here — just make it real.

- [x] `git init` on `main`, add a `.gitignore` (`.venv/`, `data/`, `__pycache__/`, `.env`).
- [x] `uv sync` resolves cleanly (Python 3.13); `uv.lock` committed.
- [x] Update ARCHITECTURE.md §2 version table from the resolved `uv.lock` (LangGraph resolved to **1.x**).
- [x] `uv run pytest` green 5/5 ([`tests/test_planner.py`](tests/test_planner.py)) — no Ollama needed.
- [x] Models present (`qwen2.5:7b` workers+roles, `nomic-embed-text` memory); `OLLAMA_BASE_URL` reachable.
- [x] Headless run works end to end (`scripts/run_crew.py soc_crew "…"`).
- [x] Web run works: `POST /runs` → `GET /runs/{id}/stream` → `plan · agent_status×10 · token×828 ·
      agent_result×3 · final · done`; `GET /runs/{id}` returns status `done` with answer.
- [x] Non-negotiables hold at runtime: JSON between workers, prose `final`, memory write by Leader, waves =
      `[[triage],[threat_intel,forensics]]` (wave 1 runs in parallel).
- [x] Fixed a real bug found during verification: worker prompt now embeds `output_schema` so the model emits
      the exact required field names ([`worker.py:126-138`](backend/app/engine/nodes/worker.py#L126-L138)).
- [x] Flipped ARCHITECTURE.md status to **verified** (commit hash pinned in the status block).
- 🎯 **Acceptance:** ✅ met — fresh `uv sync` + SOC crew runs end to end with a streamed final answer.

---

## Phase 1 — Persistence & run history

Closes the two storage gaps in ARCHITECTURE.md §8/§10. Run state currently lives only in process memory.

- [ ] Add `langgraph-checkpoint-sqlite` to [`pyproject.toml`](pyproject.toml) deps (ARCHITECTURE.md §2 lists this
      as the missing dependency).
- [ ] Wire the async SQLite checkpointer into `graph.compile(checkpointer=…)`
      ([`graph_builder.py:79`](backend/app/engine/graph_builder.py#L79)); key by `run_id` (thread_id), DB path
      from `settings.checkpoint_db` (already reserved in [`settings.py`](backend/app/settings.py)).
- [ ] Manage the checkpointer's async lifecycle in the FastAPI lifespan
      ([`main.py`](backend/app/main.py)) and pass it through the runner.
- [ ] Persist `RunRecord`s beyond process memory (currently in-memory at
      [`runner.py:50`](backend/app/engine/runner.py#L50)) so `GET /runs/{id}` survives a restart; back
      `GET /runs/{id}` from the checkpoint/history store.
- [ ] Add a `GET /runs` list endpoint (run history) if the UI will need it.
- [ ] Tests: a run can be fetched after a simulated restart.
- [ ] Update ARCHITECTURE.md §2/§8/§10 (remove the "deferred" notes, fix line refs).
- 🎯 **Acceptance:** restart the server mid/after a run and `GET /runs/{id}` still returns its record.

---

## Phase 2 — Backend hardening

Robustness items implied by ARCHITECTURE.md §10 and the spec's file-upload path. No UI yet.

- [ ] **File upload** ([`BUILD_SPEC.md` API surface], spec's `uploaded_file`): multipart endpoint that extracts
      text (or stores a path) and feeds it into the run as `uploaded_file`. Keep extraction in the API layer, not
      the engine.
- [ ] **SSE reconnection / multi-consumer** (ARCHITECTURE.md §10 "single SSE consumer"): decide policy — either
      document single-consumer as intended, or buffer/replay events so a reconnecting client resumes. Add SSE
      heartbeat/keep-alive comments to survive idle proxies.
- [ ] **Ollama failure UX**: surface a clear `error` event when Ollama is unreachable or the model is missing
      ([`ollama_client.py`](backend/app/llm/ollama_client.py) raises `OllamaError`); make sure it ends the run
      with `error` + `done`, not a hang.
- [ ] **Run cancellation**: endpoint to cancel an in-flight run (cancel the runner's asyncio task; emit `error`/`done`).
- [ ] **Context-window budget**: revisit Leader prompt assembly caps (`_MAX_ARRAY_ITEMS`/`_MAX_STR_LEN`,
      [`leader.py:73-108`](backend/app/engine/nodes/leader.py#L73-L108)) and Manager memory `k`; make them
      configurable in [`settings.py`](backend/app/settings.py).
- [ ] **Tests**: config-loader validation errors (bad id, missing worker, plan ⊄ workers), JSON
      validate-and-repair path ([`worker.py:83-114`](backend/app/engine/nodes/worker.py#L83-L114)), and an
      end-to-end engine test with a mocked Ollama client (no live model).
- 🎯 **Acceptance:** killing Ollama mid-run yields a clean `error`+`done`; uploaded text reaches a worker.

---

## Phase 3 — Frontend (build-order step 6) 🎯

The SSE contract in ARCHITECTURE.md §5 is the interface. **Look-and-feel goes through Impeccable** — do not design
UI ad hoc (see [`IMPECCABLE_SETUP.md`](IMPECCABLE_SETUP.md) and the `crewforge-frontend` skill).

- [ ] One-time setup: `npx impeccable install --providers=claude --scope=project`, reload, then
      `/impeccable init` (pick **product**) → commit `PRODUCT.md` / `DESIGN.md`.
- [ ] Scaffold `frontend/` (React + Tailwind + TypeScript, per BUILD_SPEC tree): `package.json`,
      `tailwind.config.js`, `src/main.tsx`, pages, components, `api/` client.
- [ ] **Typed SSE client hook** `useRunStream` — mirror the backend `RunEvent` union
      ([`models/run.py:41-90`](backend/app/models/run.py#L41-L90)) as a TS discriminated union; reduce
      `plan/agent_status/token/agent_result/final/error/done` into run state (cheap per-agent token append).
- [ ] **Run view** — lay out waves from `plan`; per-agent cards with status pills + live token panels; Leader
      panel renders `final` as prose. Top-to-bottom layout mirrors execution.
- [ ] **Crew composer** — beginner tier (pick workers, name crew) by default; **advanced step designer**
      (explicit `depends_on` → `execution_plan`) behind an opt-in toggle. Manager/Leader shown as fixed,
      non-removable roles, never in the worker picker.
- [ ] **Input** — prompt + optional file upload (wires to Phase 2 upload endpoint).
- [ ] Wire CRUD pages to `/agents` and `/crews`; point the client at the FastAPI base URL (CORS already open in
      [`main.py`](backend/app/main.py)).
- [ ] Review passes: `/impeccable shape` before building, `craft` to build, then `critique` / `audit` / `polish`.
- [ ] Add the real frontend file tree + route table to ARCHITECTURE.md §3/§5 (the section the staleness note says
      drifts fastest).
- 🎯 **Acceptance:** compose `soc_crew` in the UI, run it, and watch waves + tokens stream to a final answer.

---

## Phase 4 — Runtime Manager-decided ordering

Restores the precedence tier deferred in ARCHITECTURE.md §4/§9 ("Manager-provided order"). Only worthwhile once
crews exist without an explicit plan and without `consumes`/`produces`.

- [ ] Design dynamic dispatch (e.g. LangGraph `Send`) so the Manager's runtime ordering can shape waves *after*
      it runs — without breaking "user plan wins" (explicit `execution_plan` must still take precedence).
- [ ] Extend [`planner.py`](backend/app/engine/planner.py) precedence to slot Manager order between explicit plan
      and `consumes`/`produces`; keep it pure + unit-tested (cycle detection still applies).
- [ ] Keep the build-time path as the default; gate the dynamic path so the simple case stays simple.
- [ ] Update ARCHITECTURE.md §4 design note + §9.
- 🎯 **Acceptance:** a planless crew whose agents have no I/O contract still runs in a sensible Manager-chosen order.

---

## Phase 5 — Tools (reserved seam → real feature)

The `tools: []` field and the worker seam exist but execute nothing
([`worker.py:49-54`](backend/app/engine/nodes/worker.py#L49-L54)). This is a **new milestone**, not a v1 task — do
it only when explicitly scoped.

- [ ] Flesh out `ToolSpec` ([`models/agent.py`](backend/app/models/agent.py)) and a small tool registry (still
      domain-agnostic — tools are data/config, not engine branches).
- [ ] Implement tool-calling in the worker seam: model requests a tool → execute → feed result back → continue.
- [ ] Ship one real example tool (e.g. an enrichment lookup for the SOC agents) to validate the loop.
- [ ] Stream tool-call events to the UI (new SSE event type, defined once in `models/run.py`).
- 🎯 **Acceptance:** a worker invokes a tool and incorporates its result into validated JSON output.

---

## Phase 6 — Quality & docs maintenance (continuous)

- [ ] Create [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md) and move ARCHITECTURE.md §10's inline items there (referenced by id).
- [ ] Create `DEPLOYMENT.md` (local Ollama setup, `uv` commands, frontend dev server) — companion file the
      placeholder anticipated.
- [ ] Add CI: `uv run pytest` + `py_compile`/lint on push.
- [ ] Set up `ruff` (lint/format) + type checking (`mypy`/`pyright`) consistent with the codebase's type-everything rule.
- [ ] Periodic ARCHITECTURE.md **audit pass** (re-verify file:line claims; log mismatches in
      `ARCHITECTURE_AUDIT.md` with HIGH/MEDIUM/LOW severity) per the staleness discipline.
- [ ] Expand test coverage: graph wiring/waves, memory boundary (import-discipline assertion), API error codes.

---

### Dependency order

```
Phase 0  (prove it runs)         🔒 blocks everything
   ├─ Phase 1  (persistence)
   ├─ Phase 2  (hardening)  ──┐
   │                          ├─ Phase 3  (frontend)   ← needs Phase 2 upload + stable SSE
   ├─ Phase 4  (runtime ordering, independent)
   └─ Phase 5  (tools, independent milestone)
Phase 6  (quality/docs) runs continuously alongside all of the above
```
