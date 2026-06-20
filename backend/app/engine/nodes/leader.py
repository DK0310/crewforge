"""The Leader node — the only prose output and the only memory writer.

It synthesizes every worker's structured findings into a single human-facing
answer (streamed live), then writes a compact summary to the crew's memory.
"""

from __future__ import annotations

import json
import time
from collections.abc import Awaitable, Callable

from backend.app.engine.events import Emitter
from backend.app.engine.state import LEADER_ID, CrewState
from backend.app.llm import OllamaClient
from backend.app.memory import crew_memory  # ONLY the leader imports `write`
from backend.app.memory.crew_memory import MemoryEntry
from backend.app.models import (
    AgentResult,
    AgentStatusEvent,
    FinalEvent,
    SystemRoleConfig,
    TokenEvent,
)
from backend.app.settings import Settings

# Keep prompts within the context window: cap how much of each worker's output we
# forward, and how long a single string field may be. Configurable via settings.

LeaderNode = Callable[[CrewState], Awaitable[dict]]


def make_leader_node(
    role: SystemRoleConfig,
    *,
    emitter: Emitter,
    ollama: OllamaClient,
    settings: Settings,
) -> LeaderNode:
    model = role.model or settings.default_model

    async def leader_node(state: CrewState) -> dict:
        await emitter.emit(AgentStatusEvent(agent_id=LEADER_ID, status="running"))

        prompt = _assemble_prompt(
            state["user_input"],
            state["results"],
            settings.leader_max_array_items,
            settings.leader_max_str_len,
        )
        buf: list[str] = []
        async for chunk in ollama.generate(
            prompt, model=model, system=role.system_prompt, stream=True
        ):
            buf.append(chunk)
            await emitter.emit(TokenEvent(agent_id=LEADER_ID, text=chunk))
        answer = "".join(buf).strip()

        # Write a summary (not the transcript) to this crew's memory.
        await crew_memory.write(
            state["crew_id"],
            MemoryEntry(
                id=state["run_id"],
                text=_summary(state["user_input"], answer),
                meta={"run_id": state["run_id"], "ts": time.time()},
            ),
        )

        await emitter.emit(FinalEvent(answer=answer))
        await emitter.emit(AgentStatusEvent(agent_id=LEADER_ID, status="done"))
        return {"final_answer": answer}

    return leader_node


def _assemble_prompt(
    user_input: str,
    results: dict[str, AgentResult],
    max_array_items: int,
    max_str_len: int,
) -> str:
    """Pass selected, summarized structured fields — never raw concatenated text —
    so the Leader prompt stays within the model's context window.
    """
    findings = {
        agent_id: _compact(res.output, max_array_items, max_str_len)
        for agent_id, res in results.items()
        if res.status == "done" and res.output
    }
    errors = [agent_id for agent_id, res in results.items() if res.status == "error"]

    block = json.dumps(findings, ensure_ascii=False, indent=2) if findings else "(no findings)"
    error_note = (
        f"\n\nNote: these workers failed and produced no findings: {', '.join(errors)}."
        if errors
        else ""
    )
    return (
        f"User request:\n{user_input}\n\n"
        f"Worker findings (JSON):\n{block}{error_note}\n\n"
        f"Write a clear, complete answer to the user in prose."
    )


def _compact(output: dict, max_array_items: int, max_str_len: int) -> dict:
    """Truncate long arrays/strings so one verbose worker can't blow the budget."""
    compacted: dict = {}
    for key, value in output.items():
        if isinstance(value, list):
            compacted[key] = value[:max_array_items]
        elif isinstance(value, str) and len(value) > max_str_len:
            compacted[key] = value[:max_str_len] + "…"
        else:
            compacted[key] = value
    return compacted


def _summary(user_input: str, answer: str) -> str:
    """A compact memory entry: the request and the conclusion, capped."""
    request = user_input.strip().replace("\n", " ")[:200]
    conclusion = answer.replace("\n", " ")[:600]
    return f"Request: {request}\nConclusion: {conclusion}"
