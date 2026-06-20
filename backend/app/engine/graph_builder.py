"""Build a runnable LangGraph from a `CrewConfig`.

Topology is the same for every crew: Manager -> worker waves (fan-out within a
wave, barrier between waves) -> Leader. The wave structure comes from the planner
at build time. `build()` returns a headless runnable graph — no FastAPI required —
so the engine is testable and scriptable on its own.
"""

from __future__ import annotations

from dataclasses import dataclass

from langgraph.graph import END, StateGraph

from backend.app import config_loader
from backend.app.engine import planner
from backend.app.engine.events import Emitter
from backend.app.engine.nodes.leader import make_leader_node
from backend.app.engine.nodes.manager import make_manager_node
from backend.app.engine.nodes.worker import make_worker_node
from backend.app.engine.state import LEADER_ID, MANAGER_ID, CrewState
from backend.app.llm import OllamaClient, get_ollama_client
from backend.app.models import AgentConfig, CrewConfig, SystemRoleConfig
from backend.app.settings import Settings, get_settings


@dataclass
class BuiltGraph:
    graph: object  # langgraph CompiledStateGraph
    plan: list[list[str]]  # execution waves, also emitted as the `plan` SSE event


def build(
    crew: CrewConfig,
    *,
    emitter: Emitter,
    ollama: OllamaClient | None = None,
    settings: Settings | None = None,
    checkpointer: object | None = None,
) -> BuiltGraph:
    settings = settings or get_settings()
    ollama = ollama or get_ollama_client()

    agents: dict[str, AgentConfig] = {
        wid: config_loader.load_agent(wid, settings) for wid in crew.workers
    }
    manager_role = _role("manager", crew.manager_prompt_override, settings)
    leader_role = _role("leader", crew.leader_prompt_override, settings)

    plan = planner.resolve(crew.workers, crew.execution_plan, agents)
    deps = planner.dependency_map(crew.workers, crew.execution_plan, agents)

    g: StateGraph = StateGraph(CrewState)
    g.add_node(
        MANAGER_ID,
        make_manager_node(
            manager_role,
            list(agents.values()),
            plan,
            emitter=emitter,
            ollama=ollama,
            settings=settings,
        ),
    )
    for wid, agent in agents.items():
        g.add_node(
            wid,
            make_worker_node(
                agent, deps[wid], emitter=emitter, ollama=ollama, settings=settings
            ),
        )
    g.add_node(
        LEADER_ID,
        make_leader_node(leader_role, emitter=emitter, ollama=ollama, settings=settings),
    )

    g.set_entry_point(MANAGER_ID)
    _wire_waves(g, plan)

    # `checkpointer` (a LangGraph saver, e.g. AsyncSqliteSaver) persists graph state
    # per superstep, keyed by the `thread_id` passed at run time. None -> no
    # persistence (headless/test path behaves exactly as before).
    return BuiltGraph(graph=g.compile(checkpointer=checkpointer), plan=plan)


def _wire_waves(g: StateGraph, plan: list[list[str]]) -> None:
    """Manager -> wave_0 -> wave_1 -> ... -> Leader.

    Each node in a wave gets an edge from every node in the previous barrier, so a
    wave waits for all of the previous wave; LangGraph runs same-wave nodes
    concurrently. If a crew has no workers, the Manager goes straight to the Leader.
    """
    previous: list[str] = [MANAGER_ID]
    for wave in plan:
        for node in wave:
            for src in previous:
                g.add_edge(src, node)
        previous = wave
    for src in previous:
        g.add_edge(src, LEADER_ID)
    g.add_edge(LEADER_ID, END)


def _role(role: str, override: str | None, settings: Settings) -> SystemRoleConfig:
    cfg = config_loader.load_system_role(role, settings)
    if override:
        cfg = cfg.model_copy(update={"system_prompt": override})
    return cfg
