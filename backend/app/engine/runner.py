"""Owns run lifecycle: start a run, stream its events, remember the result.

A run is *synchronous and streamed* (no job queue). `start()` validates the crew
and registers the run; `run_events()` lazily kicks off the graph as a background
task and drains the emitter queue, so tokens flush to the client live while the
graph executes. The final state is kept in memory for `GET /runs/{id}`.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from functools import lru_cache
from uuid import uuid4

from backend.app import config_loader
from backend.app.engine import graph_builder
from backend.app.engine.events import Emitter
from backend.app.engine.state import CrewState
from backend.app.models import (
    AgentResult,
    CrewConfig,
    DoneEvent,
    ErrorEvent,
    PlanEvent,
    RunRecord,
)
from backend.app.models.run import RunEvent


class RunNotFoundError(KeyError):
    pass


@dataclass
class _Session:
    run_id: str
    crew: CrewConfig
    user_input: str
    uploaded_file: str | None
    emitter: Emitter = field(default_factory=Emitter)
    record: RunRecord | None = None
    task: asyncio.Task | None = None
    started: bool = False


class Runner:
    def __init__(self) -> None:
        self._sessions: dict[str, _Session] = {}

    async def start(self, crew_id: str, user_input: str, file: str | None = None) -> str:
        # Validate the crew up front (resolves workers + plan) so a bad config
        # fails the POST, not the stream.
        crew = config_loader.load_crew(crew_id)
        run_id = uuid4().hex
        self._sessions[run_id] = _Session(
            run_id=run_id, crew=crew, user_input=user_input, uploaded_file=file
        )
        return run_id

    async def run_events(self, run_id: str) -> AsyncIterator[RunEvent]:
        session = self._sessions.get(run_id)
        if session is None:
            raise RunNotFoundError(run_id)
        if not session.started:
            session.started = True
            session.task = asyncio.create_task(self._execute(session))
        async for event in session.emitter.stream():
            yield event

    def get_record(self, run_id: str) -> RunRecord:
        session = self._sessions.get(run_id)
        if session is None:
            raise RunNotFoundError(run_id)
        if session.record is not None:
            return session.record
        return RunRecord(run_id=run_id, crew_id=session.crew.id, status="running")

    async def _execute(self, session: _Session) -> None:
        emitter = session.emitter
        record = RunRecord(run_id=session.run_id, crew_id=session.crew.id, status="running")
        session.record = record
        try:
            built = graph_builder.build(session.crew, emitter=emitter)
            record.plan = built.plan
            await emitter.emit(PlanEvent(waves=built.plan))

            initial: CrewState = {
                "crew_id": session.crew.id,
                "run_id": session.run_id,
                "user_input": session.user_input,
                "uploaded_file": session.uploaded_file,
                "memory_context": "",
                "tasks": {},
                "plan": built.plan,
                "results": {},
                "final_answer": None,
            }
            final_state = await built.graph.ainvoke(initial)

            record.results = _coerce_results(final_state.get("results", {}))
            record.final_answer = final_state.get("final_answer")
            record.status = "done"
        except Exception as exc:  # noqa: BLE001 — report failure as an SSE error event
            record.status = "error"
            record.error = str(exc)
            await emitter.emit(ErrorEvent(message=str(exc)))
        finally:
            await emitter.emit(DoneEvent())


@lru_cache
def get_runner() -> Runner:
    """Process-wide run registry. One per app."""
    return Runner()


def _coerce_results(results: dict) -> dict[str, AgentResult]:
    coerced: dict[str, AgentResult] = {}
    for key, value in results.items():
        coerced[key] = value if isinstance(value, AgentResult) else AgentResult(**value)
    return coerced
