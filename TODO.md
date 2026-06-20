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

## Phase 1 — Persistence & run history ✅

Closed the two storage gaps in ARCHITECTURE.md §8/§10. Run state was in process memory only.

- [x] Added `langgraph-checkpoint-sqlite` + `aiosqlite` to [`pyproject.toml`](pyproject.toml).
- [x] Wired the async SQLite checkpointer into `graph.compile(checkpointer=…)`
      ([`graph_builder.py:83`](backend/app/engine/graph_builder.py#L83)); run with `thread_id == run_id`
      ([`runner.py:136-137`](backend/app/engine/runner.py#L136-L137)), DB from `settings.checkpoint_db`.
- [x] `AsyncSqliteSaver` lifecycle managed in the FastAPI lifespan ([`main.py:30`](backend/app/main.py#L30));
      attached to the runner via `runner.configure(...)`.
- [x] Durable `RunRecord`s via a dedicated `RunStore`
      ([`persistence/run_store.py`](backend/app/persistence/run_store.py)) in `runs.sqlite`; runner persists at
      start/running/end; `GET /runs/{id}` falls back to the store after restart.
- [x] Added `GET /runs` list endpoint (run history, newest first).
- [x] Tests: 4 new in [`tests/test_run_store.py`](tests/test_run_store.py) (roundtrip, upsert, restart,
      runner-after-restart). Suite 9/9 green.
- [x] Updated ARCHITECTURE.md §1/§2/§3/§5/§7/§8/§9/§10.
- 🎯 **Acceptance:** ✅ met — ran `soc_crew` over SSE, killed the server, restarted: `GET /runs/{id}` returned
      the full record (status `done`, all workers, answer) and `GET /runs` listed it.

---

## Phase 2 — Backend hardening ✅

Robustness items from ARCHITECTURE.md §10 and the spec's file-upload path. No UI yet.

- [x] **File upload** — `POST /runs/upload` (multipart) extracts text in the API
      ([`_extract_text`, `api/runs.py:109`](backend/app/api/runs.py#L109)) and feeds it as `uploaded_file`; the
      Manager + Worker prompts now include the capped upload (it was silently ignored before).
- [x] **SSE policy** — single-consumer documented on the endpoint; keep-alive comment every 15 s via the
      `KEEPALIVE` sentinel ([`events.py`](backend/app/engine/events.py)) so idle proxies don't drop the stream.
- [x] **Ollama failure UX** — clearer "cannot reach Ollama" message; worker failures become `error` results,
      Manager/Leader failures are caught by `_execute` → `error` + `done` (never a hang). Covered by a fake-client test.
- [x] **Run cancellation** — `POST /runs/{id}/cancel`; `_execute` catches `CancelledError`, marks `cancelled`,
      emits `error` + `done`. `Emitter.emit` uses `put_nowait` so cleanup emits are cancellation-safe.
- [x] **Context-window budget** — `max_upload_chars`, `manager_memory_k`, `leader_max_array_items`,
      `leader_max_str_len` now in [`settings.py`](backend/app/settings.py).
- [x] **Tests** — `tests/test_engine.py` (happy path, outage→error+done, JSON repair, cancel via fake Ollama),
      `tests/test_config_loader.py`, `tests/test_prompt_utils.py`. Suite **21/21** green.
- 🎯 **Acceptance:** ✅ met — killing the LLM mid-run yields `error`+`done` (fake-client test); an uploaded log's
      IOC (`198.51.100.77`, present only in the file) reached the triage worker and the final answer, live.

---

## Phase 3 — Frontend (build-order step 6) 🎯

The SSE contract in ARCHITECTURE.md §5 is the interface. **Look-and-feel goes through Impeccable** — do not design
UI ad hoc (see [`IMPECCABLE_SETUP.md`](IMPECCABLE_SETUP.md) and the `crewforge-frontend` skill).

- [x] One-time setup: Impeccable installed (plugin), `/impeccable init` run (register: **product**) → wrote
      [`PRODUCT.md`](PRODUCT.md) + seed [`DESIGN.md`](DESIGN.md). _(User to commit both.)_ Re-run
      `/impeccable document` once components exist to capture real tokens + sidecar.
- [x] Scaffold `frontend/` (React + Tailwind **v4** + TypeScript, **Vite**): `package.json`, `vite.config.ts`
      (dev proxy → :8000), `src/main.tsx`, pages, components, `api/` client. `tsc -b && vite build` green.
- [x] **Typed SSE client hook** `useRunStream` — mirrors the backend `RunEvent` union
      ([`models/run.py:41-90`](backend/app/models/run.py#L41-L90)) as a TS discriminated union with an
      **exhaustive** reducer; token bursts are rAF-batched and appended per-lane
      ([`frontend/src/hooks/useRunStream.ts`](frontend/src/hooks/useRunStream.ts)).
- [x] **Run view (hero)** — waves laid out from `plan`, top-to-bottom = execution; per-agent lanes with
      status pills + live mono token panels + validated JSON; Leader renders `final` as **prose** (sans, not
      mono). Handles live (stream) *and* historical (stored record) runs; cancel button while live.
- [x] **Crew composer** — beginner tier (pick workers, name crew) by default; **advanced step designer**
      (explicit `depends_on` → `execution_plan`) behind an opt-in toggle. Manager/Leader shown as fixed,
      non-removable roles, never in the worker picker.
- [x] **Input** — prompt + optional file upload (wires to the Phase 2 `/runs/upload` endpoint).
- [x] Wired list/read for `/agents` and `/crews` (Library) + crew create/update (Composer); client uses the
      Vite dev proxy (CORS already open in [`main.py`](backend/app/main.py)). _Agent create/edit UI deferred —
      agents are authored as YAML/prompts; documented as view-only in the Library for now._
- [x] Review passes: `/impeccable init` (PRODUCT.md + seed DESIGN.md) done; built to DESIGN.md as the contract
      (image-gen visual-direction step N/A in this harness). Design hook ran clean on every file. _Pending:
      `/impeccable critique` / `audit` / `polish` once the developer eyeballs it live._
- [x] Added the real frontend file tree to ARCHITECTURE.md §3 and a §10 resolution note.
- 🎯 **Acceptance:** _ready to verify_ — `uv run uvicorn backend.app.main:app` + `npm --prefix frontend run dev`,
      open `:5173`, pick `soc_crew`, run, watch waves + tokens stream to a final answer.

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
