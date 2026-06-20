---
name: crewforge-orchestration
description: Use when building or modifying the LangGraph engine — defining Manager/Worker/Leader nodes, wiring dependency edges, computing parallel waves, managing CrewState, or streaming tokens out of nodes
---

# CrewForge — Orchestration Skill

This skill holds the **reusable LangGraph patterns** that make a crew run: how nodes are defined, how the graph is built from a `CrewConfig`, how dependencies become parallel waves, how shared state is mutated safely, and how tokens stream out. The examples use this project's types so they drop in, but the patterns transfer to any LangGraph build.

> **Project facts live in [BUILD_SPEC.md](../../../BUILD_SPEC.md) / [ARCHITECTURE.md](../../../ARCHITECTURE.md)** — the real `CrewState` fields, the node file paths, and the SSE event shapes. This skill shows the *techniques*; consult those for the actual schema.

---

## The Graph Shape

Every crew compiles to the same topology:

```
        ┌─────────┐
        │ MANAGER │  reads input + memory, writes per-worker tasks + plan
        └────┬────┘
   ┌─────────┼─────────┐        each wave runs in parallel;
   ▼         ▼         ▼        later waves wait for earlier ones
┌──────┐ ┌──────┐ ┌──────┐
│worker│ │worker│ │worker│     (the planner decides the waves)
└──┬───┘ └──┬───┘ └──┬───┘
   └─────────┼─────────┘
        ┌────▼────┐
        │ LEADER  │  synthesizes prose, writes memory
        └─────────┘
```

The Manager and Leader are always present. The middle is whatever workers the crew lists, grouped into waves by the planner.

---

## CrewState — the shared object

The graph's state is a `TypedDict` every node reads and writes. The critical detail: **`results` must use a merge reducer** so workers in the same wave can write concurrently without clobbering each other.

```python
from typing import Annotated, TypedDict, Literal
from operator import or_  # dict merge for parallel writes

class CrewState(TypedDict):
    crew_id: str
    run_id: str
    user_input: str
    uploaded_file: str | None
    memory_context: str
    tasks: dict[str, str]                 # agent_id -> task (Manager writes)
    plan: list[list[str]]                 # waves (planner writes)
    results: Annotated[dict[str, AgentResult], or_]  # MERGE reducer — parallel-safe
    final_answer: str | None
```

Without the reducer on `results`, two workers finishing in the same wave race and one overwrites the other. The reducer merges by key. This is the single most common LangGraph bug in a fan-out graph — get it right first.

---

## Node patterns

### Manager node

```python
async def manager_node(state: CrewState) -> dict:
    # 1. read memory (ONLY the manager does this)
    context = await crew_memory.read(state["crew_id"], state["user_input"])

    # 2. ask the LLM to split the problem into per-worker tasks
    #    (+ an order, only if the crew gave no explicit plan)
    tasks, proposed_order = await _plan_with_llm(state, context)

    return {"memory_context": context, "tasks": tasks,
            "plan": planner.resolve(...)}   # see planner below
```

The Manager is the only memory reader and the only fallback planner. Keep both responsibilities here.

### Worker node — a factory, never hand-written per agent

```python
def make_worker_node(agent: AgentConfig):
    async def worker_node(state: CrewState) -> dict:
        task = state["tasks"][agent.id]
        upstream = {dep: state["results"][dep].output
                    for dep in _deps_of(agent, state)}      # only what it depends on
        prompt = assemble_prompt(agent, task, upstream)

        raw = await ollama_client.generate(prompt, model=agent.model, stream=...)
        output = validate_json(raw, agent.output_schema)    # repair once, then error
        return {"results": {agent.id: AgentResult(agent.id, "done", output, ...)}}
    return worker_node
```

One implementation, parameterized by `AgentConfig`. Adding an agent never adds a node function.

### Leader node

```python
async def leader_node(state: CrewState) -> dict:
    answer = await _synthesize(state["results"])   # prose, streamed out
    await crew_memory.write(state["crew_id"], summarize(answer, state["results"]))
    return {"final_answer": answer}
```

The only prose output and the only memory writer.

---

## Building the graph from a CrewConfig

```python
def build(crew: CrewConfig) -> CompiledGraph:
    g = StateGraph(CrewState)
    g.add_node("manager", manager_node)
    for wid in crew.workers:
        g.add_node(wid, make_worker_node(load_agent(wid)))
    g.add_node("leader", leader_node)

    g.set_entry_point("manager")
    # edges are added from the resolved plan: manager → wave1 → wave2 → … → leader
    _wire_waves(g, crew)        # fan-out within a wave, barrier between waves
    g.add_edge(<last wave>, "leader")
    return g.compile(checkpointer=sqlite_checkpointer)
```

Workers in the same wave each get an edge from the previous barrier; the next wave waits on all of them. LangGraph runs same-wave nodes concurrently automatically.

---

## The planner — a pure function

Ordering logic lives in **one pure function** with no I/O, so it's trivially testable:

```python
def resolve(workers: list[str],
            explicit_plan: list[DependencySpec] | None,
            manager_order: ... | None,
            agent_io: dict[str, AgentIO]) -> list[list[str]]:
    """Return execution waves. Precedence:
       1. explicit_plan (user, advanced mode)  — wins
       2. manager_order (Manager decided)
       3. consumes/produces inference
       4. single all-parallel wave (fallback)
    Topological sort; raise on cycle with a clear message."""
```

Rules:
- **Precedence is fixed** (above). User plan always wins.
- **Detect cycles** and raise a readable error naming the agents in the cycle — never loop forever.
- **Pure**: no LLM, no DB, no clock. Same inputs → same waves. Unit-test it hard.

---

## Streaming tokens out

Nodes call Ollama in streaming mode and surface chunks via an async generator. The API layer turns each chunk into an SSE `token` event tagged with the agent id (`__leader__` for the Leader). Don't buffer a full response before emitting — the live token view is the product's whole point.

```python
async for chunk in ollama_client.generate(prompt, stream=True):
    emit({"type": "token", "agent_id": agent.id, "text": chunk})
```

Status transitions (`pending → running → done`) are emitted as `agent_status` events as each node starts and finishes, so the UI can flip the wave's pills.

---

## Review Checklist — Orchestration Smells

| ❌ Smell | ✅ Correct | Why |
|---|---|---|
| `results` field without a merge reducer | `Annotated[dict, or_]` | Parallel workers race and clobber otherwise |
| A node function per agent | One `make_worker_node(agent)` factory | Adding agents = YAML only |
| Ordering logic scattered in nodes | One pure `planner.resolve()` | Testable, single source of order truth |
| Manager order overriding a user's explicit plan | User plan wins; Manager only writes tasks then | Settled design rule |
| No cycle detection in the planner | Raise a clear error on cycles | Avoid infinite loops / hangs |
| Worker reading the whole `results` map | Read only its declared dependencies | Keeps prompts small, deps honest |
| Buffering the full LLM reply | Stream chunks → SSE token events | Live UX |
| Memory read/write in a worker | Manager reads, Leader writes only | Enforceable boundary |
| Graph that needs FastAPI to run | `build()` returns a headless runnable graph | Testability |

---

## Cross-References

- **Where engine code lives, the golden rules** → `crewforge-architecture`
- **AgentConfig, output_schema, JSON validation/repair** → `crewforge-agents`
- **`crew_memory.read`/`.write`, context-window safety** → `crewforge-memory`
- **Turning node events into SSE** → `crewforge-api`
- **Real `CrewState` fields & event shapes** → [BUILD_SPEC.md](../../../BUILD_SPEC.md) / [ARCHITECTURE.md](../../../ARCHITECTURE.md)
