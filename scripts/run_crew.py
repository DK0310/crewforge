"""Run a crew headless — no FastAPI, no SSE — to exercise the engine directly.

    uv run python scripts/run_crew.py soc_crew "Investigate: failed SSH logins
    from 203.0.113.7 against host web-01, then a successful login as root."

Requires a local Ollama serving the models referenced by the crew's agents. This
is the script the engine's `build()` is designed to support: the graph runs with a
plain `Emitter`, and events print to stdout as they stream.
"""

from __future__ import annotations

import asyncio
import sys

from backend.app import config_loader
from backend.app.engine import graph_builder
from backend.app.engine.events import Emitter
from backend.app.engine.state import CrewState
from backend.app.models import (
    AgentResultEvent,
    AgentStatusEvent,
    DoneEvent,
    ErrorEvent,
    FinalEvent,
    PlanEvent,
    TokenEvent,
)


async def main(crew_id: str, user_input: str) -> None:
    crew = config_loader.load_crew(crew_id)
    emitter = Emitter()
    built = graph_builder.build(crew, emitter=emitter)

    initial: CrewState = {
        "crew_id": crew.id,
        "run_id": "headless",
        "user_input": user_input,
        "uploaded_file": None,
        "memory_context": "",
        "tasks": {},
        "plan": built.plan,
        "results": {},
        "final_answer": None,
    }

    await emitter.emit(PlanEvent(waves=built.plan))

    async def drive() -> None:
        try:
            await built.graph.ainvoke(initial)
        except Exception as exc:  # noqa: BLE001
            await emitter.emit(ErrorEvent(message=str(exc)))
        finally:
            await emitter.emit(DoneEvent())

    task = asyncio.create_task(drive())
    async for event in emitter.stream():
        _print_event(event)
    await task


def _print_event(event) -> None:
    if isinstance(event, PlanEvent):
        print(f"\n[plan] waves={event.waves}\n")
    elif isinstance(event, AgentStatusEvent):
        print(f"\n[{event.agent_id}] -> {event.status}")
    elif isinstance(event, TokenEvent):
        print(event.text, end="", flush=True)
    elif isinstance(event, AgentResultEvent):
        print(f"\n[{event.agent_id}] result keys: {list(event.output)}")
    elif isinstance(event, FinalEvent):
        print(f"\n\n=== FINAL ANSWER ===\n{event.answer}\n")
    elif isinstance(event, ErrorEvent):
        print(f"\n[error] {event.agent_id or ''} {event.message}")
    elif isinstance(event, DoneEvent):
        print("\n[done]")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print('usage: python scripts/run_crew.py <crew_id> "<user input>"', file=sys.stderr)
        raise SystemExit(2)
    asyncio.run(main(sys.argv[1], sys.argv[2]))
