"""The generic worker node — ONE factory parameterized by `AgentConfig`.

Adding an agent never adds a node function. A worker assembles its prompt (task +
only the upstream JSON it depends on), streams tokens out, then validates its
output against the agent's schema (repairing once before erroring).
"""

from __future__ import annotations

import json
import time
from collections.abc import Awaitable, Callable

from backend.app.engine.events import Emitter
from backend.app.engine.json_utils import JsonValidationError, validate_output
from backend.app.engine.state import CrewState
from backend.app.llm import OllamaClient
from backend.app.models import (
    AgentConfig,
    AgentResult,
    AgentResultEvent,
    AgentStatusEvent,
    ErrorEvent,
    TokenEvent,
)
from backend.app.settings import Settings

WorkerNode = Callable[[CrewState], Awaitable[dict]]


def make_worker_node(
    agent: AgentConfig,
    deps: set[str],
    *,
    emitter: Emitter,
    ollama: OllamaClient,
    settings: Settings,
) -> WorkerNode:
    model = agent.model or settings.default_model

    async def worker_node(state: CrewState) -> dict:
        await emitter.emit(AgentStatusEvent(agent_id=agent.id, status="running"))
        started = time.time()

        task = state["tasks"].get(agent.id, state["user_input"])
        upstream = _upstream_outputs(state, deps)
        prompt = _assemble_prompt(agent, task, upstream)

        # --- TOOL SEAM (reserved, not implemented in v1) ---------------------
        # Tool-calling would slot in here: inspect `agent.tools`, let the model
        # request a tool, execute it, feed the result back, then continue. v1
        # ships `tools: []` and no execution. Do not fake it.
        # ---------------------------------------------------------------------

        try:
            output = await _generate_and_validate(agent, prompt, model, emitter, ollama)
        except Exception as exc:  # noqa: BLE001 — surface as an error result, don't kill the run
            await emitter.emit(ErrorEvent(agent_id=agent.id, message=str(exc)))
            await emitter.emit(AgentStatusEvent(agent_id=agent.id, status="error"))
            result = AgentResult(
                agent_id=agent.id,
                status="error",
                error=str(exc),
                started_at=started,
                finished_at=time.time(),
            )
            return {"results": {agent.id: result}}

        result = AgentResult(
            agent_id=agent.id,
            status="done",
            output=output,
            started_at=started,
            finished_at=time.time(),
        )
        await emitter.emit(AgentResultEvent(agent_id=agent.id, output=output))
        await emitter.emit(AgentStatusEvent(agent_id=agent.id, status="done"))
        return {"results": {agent.id: result}}

    return worker_node


async def _generate_and_validate(
    agent: AgentConfig,
    prompt: str,
    model: str,
    emitter: Emitter,
    ollama: OllamaClient,
) -> dict:
    """Stream a generation and validate it. On invalid JSON, regenerate exactly
    once (non-streamed, stricter) and re-validate, then give up with an error.
    """
    raw = await _stream(agent.id, prompt, model, agent.system_prompt, emitter, ollama)
    try:
        return validate_output(raw, agent.output_schema)
    except JsonValidationError:
        pass  # fall through to a single repair attempt

    repair_prompt = (
        prompt
        + "\n\nYour previous reply was not valid JSON for the required schema. "
        "Reply again with ONLY the corrected JSON object — no prose, no code fences."
    )
    repaired = "".join(
        [
            chunk
            async for chunk in ollama.generate(
                repair_prompt, model=model, system=agent.system_prompt, stream=False
            )
        ]
    )
    # Re-validate; a second failure raises JsonValidationError up to the caller,
    # which records an error result for this worker.
    return validate_output(repaired, agent.output_schema)


def _upstream_outputs(state: CrewState, deps: set[str]) -> dict[str, dict]:
    """Only the validated outputs of the workers this agent depends on."""
    out: dict[str, dict] = {}
    for dep in deps:
        res = state["results"].get(dep)
        if res and res.output:
            out[dep] = res.output
    return out


def _assemble_prompt(agent: AgentConfig, task: str, upstream: dict[str, dict]) -> str:
    parts = [f"Your task:\n{task}"]
    if upstream:
        parts.append(
            "Upstream findings you may rely on (JSON):\n"
            + json.dumps(upstream, ensure_ascii=False, indent=2)
        )
    # Show the actual schema so the model emits the exact field names it requires.
    # Without this, models invent plausible-but-wrong keys and fail validation.
    parts.append(
        "Return ONLY a JSON object that conforms to this JSON Schema — use exactly "
        "these field names and include every required field:\n"
        + json.dumps(agent.output_schema, ensure_ascii=False, indent=2)
    )
    return "\n\n".join(parts)


async def _stream(
    agent_id: str,
    prompt: str,
    model: str,
    system: str,
    emitter: Emitter,
    ollama: OllamaClient,
) -> str:
    buf: list[str] = []
    async for chunk in ollama.generate(prompt, model=model, system=system, stream=True):
        buf.append(chunk)
        await emitter.emit(TokenEvent(agent_id=agent_id, text=chunk))
    return "".join(buf)
