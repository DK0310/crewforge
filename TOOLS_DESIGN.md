# Tools Design

> **Status:** design proposal for the **Phase 5** milestone in [`TODO.md`](TODO.md). Pre-code — describes the
> *intended* design, not code that exists yet. The seam it builds on is real:
> [`worker.py:49-54`](backend/app/engine/nodes/worker.py#L49-L54) (`# --- TOOL SEAM ---`), the reserved
> `tools` field on [`AgentConfig`](backend/app/models/agent.py), and the `ToolSpec` stub. When this lands,
> fold the facts into [`ARCHITECTURE.md`](ARCHITECTURE.md) and tick the Phase 5 boxes.
>
> Decisions locked with the developer: **prompt-based ReAct loop** + **Python tool registry**.

---

## 1. What a tool is

A **tool** is a capability an agent calls when the task needs something the LLM can't do reliably on its own —
fetch live data, hit an API, do an exact lookup or computation. The agent *decides* to use it mid-task; the
engine just runs it and hands the result back. The LLM reasons; the tool supplies facts.

Worked example (SOC crew): `threat_intel` receives `extracted_iocs: ["203.0.113.7"]` from `triage`. Today it
*guesses* a reputation from training data. With a tool it calls `ioc_reputation(indicator="203.0.113.7")`, gets
real data, and writes a grounded verdict.

## 2. Design principles (tie-in to the non-negotiables)

| Rule | How tools honor it |
|---|---|
| **#2 Engine is domain-agnostic** | The engine only does *"look up a tool by name in the registry and run it."* It never knows what any tool *does*. All domain logic lives in `backend/app/tools/`. |
| **#6 Config is data** | *Enabling* a tool on an agent is editing YAML (`tools: [ioc_reputation]`). Authoring a *new* Python tool is a code file + one registration line — the accepted cost of the registry choice. |
| **#4 JSON between agents** | A worker's *final* output is still schema-validated JSON. Tool calls/results are an internal loop; they never change the agent-to-agent contract. |
| **#5 Memory boundary** | Unchanged. Tools are not memory. Manager still reads, Leader still writes; tools are a worker concern. |
| **#7 Reserved seam** | This replaces the documented seam with a real loop, gated so tool-less agents behave **exactly** as today. |

**Scope boundary:** only **workers** call tools in this increment. The Manager plans and the Leader synthesizes
prose — neither calls tools yet (revisit later if a real need appears).

## 3. The model: prompt-based ReAct + Python registry

### 3.1 A tool is a typed Python function

```python
# backend/app/tools/ioc_reputation.py
from pydantic import BaseModel
from backend.app.tools import tool   # the registry decorator

class IOCArgs(BaseModel):
    indicator: str                   # IP, domain, or file hash

@tool(
    name="ioc_reputation",
    description="Reputation/verdict for an IP, domain, or file hash.",
    args=IOCArgs,
)
async def ioc_reputation(args: IOCArgs) -> dict:
    # Domain logic lives here — call an API, query a local DB, etc.
    return {"indicator": args.indicator, "verdict": "suspicious", "sources": [...]}
```

- The `@tool` decorator registers the function under `name` and records a `ToolSpec` (name, description, and the
  JSON Schema derived from the `args` pydantic model). The registry is a process-wide `dict[str, ToolEntry]`.
- Tools are **async** (same as the request path) and **return a `dict`** (JSON-serializable, so it round-trips
  to the model and the SSE stream).

### 3.2 The registry

```python
# backend/app/tools/__init__.py
_REGISTRY: dict[str, ToolEntry] = {}

def tool(*, name, description, args): ...        # decorator -> registers ToolEntry(fn, ToolSpec)
def get_tool(name: str) -> ToolEntry: ...        # raises ToolNotFound
def specs_for(names: list[str]) -> list[ToolSpec]: ...   # builds the prompt block
```

Importing `backend.app.tools` imports each tool module so decorators run (explicit imports in `__init__`, no
magic auto-discovery in v1 — predictable and greppable).

### 3.3 Schema change to `AgentConfig`

`tools` moves from `list[ToolSpec]` (stub) to **`list[str]`** — a list of tool *names* resolved against the
registry. The registry is the source of truth for description/args; YAML just references by name.

```yaml
# config/agents/threat_intel.yaml
tools: [ioc_reputation]     # was: []
```

- Backward compatible: `tools: []` is a valid empty `list[str]`.
- **Validate on load** ([`config_loader.py`](backend/app/config_loader.py)): every name in `agent.tools` must
  exist in the registry — same fail-fast discipline as crew→worker reference checks. Unknown tool ⇒ `ConfigError`
  naming the file and the missing tool.

## 4. The worker ReAct loop

Replaces the single-shot generation at the seam. **If `agent.tools` is empty, the path is byte-for-byte today's
behavior** (one generation + validate-and-repair-once) — zero overhead, no regression to the Phase-0-verified flow.

**Turn protocol.** The worker prompt (in addition to task + upstream JSON + `output_schema`) lists the available
tools and instructs the model to reply with **exactly one** JSON envelope per turn:

```jsonc
// to call a tool:
{ "action": "tool",  "tool": "ioc_reputation", "args": { "indicator": "203.0.113.7" } }
// to finish:
{ "action": "final", "output": { /* object matching the agent's output_schema */ } }
```

The explicit `action` discriminator removes any ambiguity between "call a tool" and "final answer" (parsed with
the existing tolerant [`extract_json`](backend/app/engine/json_utils.py)).

**Loop (pseudocode):**

```
for step in range(MAX_TOOL_STEPS):           # cap — never loop forever
    raw = stream_generation(prompt)          # tokens still stream to SSE
    msg = extract_json(raw)
    if msg["action"] == "tool":
        emit TokenCall                        # tool_call SSE event
        try:
            spec  = get_tool(msg["tool"])     # must be in agent.tools
            valid = validate_args(msg["args"], spec)         # pydantic / jsonschema
            result = await asyncio.wait_for(spec.fn(valid), TOOL_TIMEOUT)
        except (ToolNotFound, ArgsInvalid, TimeoutError, ToolError) as e:
            result = {"error": str(e)}        # fed back so the model can adapt, not a crash
        emit ToolResult(result)               # tool_result SSE event
        prompt += observation(msg, result)    # append the call + result, continue
        continue
    if msg["action"] == "final":
        return validate_output(msg["output"], agent.output_schema)   # repair once, as today
# cap reached: force one final turn, then validate-and-repair-once, else error result
```

**Guardrails** (mirroring existing discipline):
- **`MAX_TOOL_STEPS`** cap (config, default ~5) — analogous to repair-once; prevents infinite loops on a local model.
- **`TOOL_TIMEOUT`** per call (`asyncio.wait_for`).
- A tool that is missing / not allowed / raises / times out becomes an `{"error": …}` **observation**, not an
  exception that kills the run — the model gets a chance to recover or finish without it.
- **Context budget:** truncate large tool results before feeding them back (reuse the Leader's array/string
  caps approach), so a chatty tool can't blow the window.

## 5. New SSE events

Defined **once** in the `RunEvent` union ([`models/run.py:41-90`](backend/app/models/run.py#L41-L90)), so the
frontend and backend never drift:

```jsonc
{ "type": "tool_call",   "agent_id": "threat_intel", "tool": "ioc_reputation", "args": { "indicator": "203.0.113.7" } }
{ "type": "tool_result", "agent_id": "threat_intel", "tool": "ioc_reputation", "output": { "verdict": "suspicious" } }
{ "type": "tool_result", "agent_id": "threat_intel", "tool": "ioc_reputation", "error": "timeout after 10s" }
```

- Emitted by the worker node via the existing [`Emitter`](backend/app/engine/events.py#L17); the API serializes
  them like any other event — no API changes beyond the union.
- Existing clients ignore unknown `type`s; the frontend reducer adds two cases (Phase 3 / `crewforge-frontend`):
  show a tool chip on the agent card with its args and result.

## 6. Example, end to end (the verifiable slice)

1. Add [`backend/app/tools/ioc_reputation.py`](backend/app/tools/ioc_reputation.py) — for the first slice it can
   be a **safe local stub** (deterministic verdicts from a small in-repo table) so verification needs no external
   network or API keys. A real HTTP-backed version is a drop-in later.
2. `config/agents/threat_intel.yaml`: `tools: [ioc_reputation]`.
3. Run `soc_crew`: `threat_intel` calls the tool on each IOC from `triage`, then returns its normal
   schema-valid JSON enriched with real `verdict`s.
4. Verify like Phase 0: headless + SSE; confirm `tool_call` / `tool_result` events appear and the final answer
   reflects the tool output.

## 7. Testing

- **Pure unit tests** (no live model, like the planner): the envelope parser (`tool` vs `final` discrimination,
  malformed JSON), args validation, the loop driven by a **mocked Ollama client** + **mock tools** (assert the
  cap, timeout→error-observation, and unknown-tool handling).
- **Config tests:** `agent.tools` referencing an unregistered tool raises `ConfigError` on load.
- **One live slice** with the real stub tool.

## 8. Explicitly out of scope (this increment)

- **Native Ollama function-calling** (`/api/chat` `tools`). The ReAct seam is designed so a native adapter can
  slot in later behind the same registry; not built now.
- **Untrusted / user-supplied tool code or remote tool loading.** Tools are trusted, in-repo Python only. No
  dynamic code execution from config. (Security: a tool runs real code — treat the registry like the rest of the
  codebase, reviewed.)
- **Parallel tool calls** in one turn (v1: one tool per turn, sequential). Manager/Leader tool use. Tool auth /
  secrets management beyond reading from `settings` / env.

## 9. Implementation checklist (expands TODO Phase 5)

- [ ] `backend/app/tools/__init__.py`: `tool` decorator, registry, `get_tool`, `specs_for`, `ToolEntry`.
- [ ] Refactor `ToolSpec` ([`models/agent.py`](backend/app/models/agent.py)) to the registry descriptor; change
      `AgentConfig.tools` to `list[str]`.
- [ ] Registry-reference validation in [`config_loader.py`](backend/app/config_loader.py).
- [ ] New SSE events in [`models/run.py`](backend/app/models/run.py).
- [ ] Worker ReAct loop in [`worker.py`](backend/app/engine/nodes/worker.py) (gated; no-tool path unchanged);
      `MAX_TOOL_STEPS` / `TOOL_TIMEOUT` in [`settings.py`](backend/app/settings.py).
- [ ] Example tool `ioc_reputation` (local stub) + enable on `threat_intel`.
- [ ] Tests (parser, loop with mocked Ollama, config validation) + one live slice.
- [ ] Update `ARCHITECTURE.md` (§4 nodes, §5 events, §6 schema) with real file:line claims.

## 10. Resolved decisions

Settled with the developer (2026-06-20) — apply these when the slice is built:

1. **First tool:** a **local deterministic `ioc_reputation` stub** — no API keys, no network, fully offline.
   Real integrations (VirusTotal / AbuseIPDB) are a later drop-in, not the first slice.
2. **`MAX_TOOL_STEPS` = 5** (balanced for a local 7B model). Lives in [`settings.py`](backend/app/settings.py).
3. **Tool results stay internal to the worker's JSON.** No special memory path — the Leader already summarizes
   worker output into memory.

Still open (raised, not yet decided): per-role model strategy (currently all `qwen2.5:7b`); whether *real* tools
may reach the network (the local stub sidesteps this for now); whether to port the old soar-crew VirusTotal /
AbuseIPDB integrations when real tools land.
