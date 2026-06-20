---
name: crewforge-frontend
description: Use when building React + Tailwind UI for CrewForge — the SSE run client, the live wave/agent run view, the crew composer and advanced step designer, or anything that consumes the run stream
---

# CrewForge — Frontend Skill

This skill holds the **reusable React + Tailwind patterns** for the UI: consuming the SSE run stream, rendering waves of agents with live status and streaming tokens, and the crew-composition flow. For all visual/aesthetic decisions, defer to **Impeccable** (the project's design authority — see "Design authority" below). This skill is about the *data flow and structure* specific to CrewForge; Impeccable owns *how it looks*.

> **Design authority: Impeccable.** This project does not let the coding agent design UI ad hoc. All look-and-feel — typography, palette, spacing, motion, component shape — goes through Impeccable, installed at `.agents/skills/impeccable/`. Before building any UI, run `/impeccable shape` to plan it; build with `/impeccable craft`; review with `/impeccable critique`, `/impeccable audit`, and `/impeccable polish`. The project's design context lives in `PRODUCT.md` / `DESIGN.md` (written by `/impeccable init`). Never invent a visual language here — read Impeccable's and follow it. See [IMPECCABLE_SETUP.md](../../../IMPECCABLE_SETUP.md) for one-time setup.

> **The real component tree and route table live in [BUILD_SPEC.md](../../../BUILD_SPEC.md) / [ARCHITECTURE.md](../../../ARCHITECTURE.md).** This skill shows the *patterns*; consult those for actual file names.

---

## Principles

1. **The run view is driven entirely by SSE events.** The UI holds no orchestration logic; it reacts to `plan`, `agent_status`, `token`, `agent_result`, `final`. Lay out from `plan`, mutate from the rest.
2. **Composing a crew is choosing agents.** A beginner picks workers and names the crew — nothing about dependencies. The step designer (explicit order) is an *advanced, opt-in* surface, hidden by default.
3. **Stream, don't wait.** Tokens render as they arrive, per agent. Never collect a whole response and show it at the end — the live view is the product.
4. **TypeScript, typed events.** Mirror the backend's SSE event types as a discriminated union so the reducer is exhaustive and safe.

---

## The SSE client hook

Consume the run stream with `EventSource` (or a fetch-based reader). Reduce events into run state.

```ts
type RunEvent =
  | { type: "plan"; waves: string[][] }
  | { type: "agent_status"; agent_id: string; status: AgentStatus }
  | { type: "token"; agent_id: string; text: string }
  | { type: "agent_result"; agent_id: string; output: unknown }
  | { type: "final"; answer: string }
  | { type: "error"; agent_id?: string; message: string }
  | { type: "done" };

function useRunStream(runId: string) {
  const [state, dispatch] = useReducer(runReducer, initialRunState);
  useEffect(() => {
    const es = new EventSource(`/runs/${runId}/stream`);
    es.onmessage = (e) => dispatch(JSON.parse(e.data) as RunEvent);
    es.onerror = () => es.close();
    return () => es.close();
  }, [runId]);
  return state;
}
```

The reducer:
- `plan` → build the wave/agent layout, all agents `pending`.
- `agent_status` → flip one agent's status pill.
- `token` → append text to that agent's panel (`__leader__` → the Leader panel).
- `agent_result` → mark the agent done, stash its structured output.
- `final` → render the prose answer.
- `done` → close the stream, mark the run complete.

Keep token appends cheap (append to a per-agent string), since they arrive rapidly.

---

## The run view

Lay out the `plan` as ordered waves; within a wave, agents sit side by side (they run in parallel). Each agent card shows: name, a status pill (`pending → running → done/error`), and a streaming token panel. The Leader sits below the final wave; its tokens stream into a distinct panel, and the `final` answer renders as prose (the only place the user reads free text rather than structured output).

Reading the layout top to bottom should match how the run actually executes: Manager, then each wave, then Leader. The structure encodes the execution.

---

## The crew composer

Two tiers, beginner-first:

- **Beginner (default).** Pick workers from the agent list, name the crew, save. The Manager will decide execution order at run time. No dependency UI is shown.
- **Advanced (opt-in).** A step designer where the user explicitly wires `depends_on` between chosen workers, producing the crew's `execution_plan`. This plan wins over the Manager's ordering. Keep it behind a toggle so it never confronts a beginner.

Manager and Leader are shown as fixed, non-removable parts of the crew (their prompts are editable in an advanced panel), never as items in the worker picker.

---

## Review Checklist — Frontend Smells

| ❌ Smell | ✅ Correct | Why |
|---|---|---|
| Orchestration logic in the UI | UI reacts to SSE events only | Engine owns coordination |
| Waiting for the full response then rendering | Stream tokens per agent live | The live view is the product |
| Dependency wiring shown to all users | Step designer is advanced, opt-in | Don't burden beginners |
| Manager/Leader in the worker picker | Shown as fixed roles, not pickable | They're system roles |
| Untyped `any` SSE handling | Discriminated-union `RunEvent` + exhaustive reducer | Safety, fewer drift bugs |
| Re-rendering everything on each token | Append to a per-agent buffer | Tokens arrive fast; keep it cheap |
| Leader output shown as JSON | Render `final` as prose | Human-facing output is text |
| Aesthetic choices invented here | Defer to Impeccable (`/impeccable craft`/`critique`) | One source for visual language |

---

## Cross-References

- **Visual/aesthetic language (typography, palette, motion, components)** → **Impeccable** (design authority, `.agents/skills/impeccable/`; see IMPECCABLE_SETUP.md)
- **The SSE events this UI consumes** → `crewforge-api`
- **What the waves/plan mean in execution** → `crewforge-orchestration`
- **Real component tree, routes** → [BUILD_SPEC.md](../../../BUILD_SPEC.md) / [ARCHITECTURE.md](../../../ARCHITECTURE.md)
