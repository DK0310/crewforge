"""The Manager node — the only memory reader and the only fallback planner.

It reads relevant crew memory, asks the LLM to split the request into one task per
worker, and writes those tasks (plus the precomputed plan) into state. It does not
solve the task and does not reshape the wave topology.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from backend.app.engine.events import Emitter
from backend.app.engine.json_utils import extract_json
from backend.app.engine.prompt_utils import source_material_block
from backend.app.engine.state import MANAGER_ID, CrewState
from backend.app.llm import OllamaClient
from backend.app.memory import crew_memory  # ONLY the manager imports `read`
from backend.app.models import AgentConfig, AgentStatusEvent, SystemRoleConfig
from backend.app.settings import Settings

ManagerNode = Callable[[CrewState], Awaitable[dict]]


def make_manager_node(
    role: SystemRoleConfig,
    workers: list[AgentConfig],
    plan: list[list[str]],
    *,
    emitter: Emitter,
    ollama: OllamaClient,
    settings: Settings,
) -> ManagerNode:
    worker_ids = [w.id for w in workers]
    model = role.model or settings.default_model

    async def manager_node(state: CrewState) -> dict:
        await emitter.emit(AgentStatusEvent(agent_id=MANAGER_ID, status="running"))

        # 1. Read relevant memory (the manager is the ONLY reader).
        context = await crew_memory.read(
            state["crew_id"], state["user_input"], k=settings.manager_memory_k
        )

        # 2. Ask the LLM to write one task per worker.
        prompt = _assemble_prompt(
            workers,
            state["user_input"],
            context,
            state.get("uploaded_file"),
            settings.max_upload_chars,
        )
        raw = await _collect(ollama.generate(prompt, model=model, system=role.system_prompt))
        tasks = _parse_tasks(raw, worker_ids, state["user_input"])

        await emitter.emit(AgentStatusEvent(agent_id=MANAGER_ID, status="done"))
        return {"memory_context": context, "tasks": tasks, "plan": plan}

    return manager_node


def _assemble_prompt(
    workers: list[AgentConfig],
    user_input: str,
    context: str,
    uploaded_file: str | None,
    max_upload_chars: int,
) -> str:
    roster = "\n".join(f"- {w.id}: {w.description}" for w in workers)
    memory_block = context.strip() or "(no relevant past runs)"
    ids = ", ".join(w.id for w in workers)
    parts = [f"User request:\n{user_input}"]
    source = source_material_block(uploaded_file, max_upload_chars)
    if source:
        parts.append(source)
    parts.append(f"Relevant memory of past runs:\n{memory_block}")
    parts.append(f"Available workers:\n{roster}")
    parts.append(
        f"Return ONLY a JSON object whose keys are exactly these worker ids "
        f"[{ids}] and whose values are the task instruction for each worker."
    )
    return "\n\n".join(parts)


def _parse_tasks(raw: str, worker_ids: list[str], user_input: str) -> dict[str, str]:
    """Best-effort parse of the manager's task map. Missing/invalid entries fall
    back to a generic task so a manager hiccup never nukes the whole run.
    """
    parsed: dict = {}
    try:
        data = extract_json(raw)
        if isinstance(data, dict):
            parsed = data
    except ValueError:
        parsed = {}

    fallback = f"Address the following request within your specialty:\n{user_input}"
    tasks: dict[str, str] = {}
    for wid in worker_ids:
        value = parsed.get(wid)
        tasks[wid] = value.strip() if isinstance(value, str) and value.strip() else fallback
    return tasks


async def _collect(chunks) -> str:
    return "".join([chunk async for chunk in chunks])
