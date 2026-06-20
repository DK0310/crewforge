"""Owns run lifecycle: start a run, stream its events, persist the result.

A run is *synchronous and streamed* (no job queue). `start()` validates the crew
and registers the run; `run_events()` lazily kicks off the graph as a background
task and drains the emitter queue, so tokens flush to the client live while the
graph executes.

Persistence (Phase 1): when a `RunStore` is configured, each run's `RunRecord` is
written at start and at every status transition, so `GET /runs/{id}` and
`GET /runs` survive a server restart. When a LangGraph `checkpointer` is configured,
graph state is checkpointed per superstep, keyed by `thread_id == run_id`. Both are
optional — the headless/test path runs with neither and behaves as before.
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
from backend.app.persistence import RunStore


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
    def __init__(
        self,
        store: RunStore | None = None,
        checkpointer: object | None = None,
        *,
        ollama: object | None = None,
        settings: object | None = None,
    ) -> None:
        self._sessions: dict[str, _Session] = {}
        self._store = store
        self._checkpointer = checkpointer
        self._ollama = ollama  # None -> graph_builder uses the default client
        self._settings = settings  # None -> default get_settings()

    def configure(
        self, *, store: RunStore | None = None, checkpointer: object | None = None
    ) -> None:
        """Attach persistence (called from the FastAPI lifespan)."""
        self._store = store
        self._checkpointer = checkpointer

    async def start(self, crew_id: str, user_input: str, file: str | None = None) -> str:
        # Validate the crew up front (resolves workers + plan) so a bad config
        # fails the POST, not the stream.
        crew = config_loader.load_crew(crew_id, self._settings)
        run_id = uuid4().hex
        record = RunRecord(run_id=run_id, crew_id=crew.id, status="pending")
        self._sessions[run_id] = _Session(
            run_id=run_id,
            crew=crew,
            user_input=user_input,
            uploaded_file=file,
            record=record,
        )
        await self._persist(record)
        return run_id

    async def run_events(
        self, run_id: str, keepalive: float | None = None
    ) -> AsyncIterator:
        session = self._sessions.get(run_id)
        if session is None:
            raise RunNotFoundError(run_id)
        if not session.started:
            session.started = True
            session.task = asyncio.create_task(self._execute(session))
        async for event in session.emitter.stream(keepalive):
            yield event

    async def cancel(self, run_id: str) -> RunRecord:
        """Cancel an in-flight run. The graph task is cancelled; its cleanup path
        marks the record `cancelled` and emits `error` + `done` to any stream.
        A run that hasn't started executing is marked `cancelled` directly.
        """
        session = self._sessions.get(run_id)
        if session is None:
            raise RunNotFoundError(run_id)
        if session.task is not None and not session.task.done():
            session.task.cancel()
            # _execute catches CancelledError, finalizes the record, and returns
            # normally — so awaiting it settles the status to "cancelled".
            try:
                await session.task
            except asyncio.CancelledError:
                pass
            return session.record  # now "cancelled"
        # Never started (or already finished): mark cancelled if still open.
        record = session.record
        if record is not None and record.status in ("pending", "running"):
            record.status = "cancelled"
            record.error = "run cancelled"
            await self._persist(record)
        return session.record  # type: ignore[return-value]

    async def get_record(self, run_id: str) -> RunRecord:
        session = self._sessions.get(run_id)
        if session is not None and session.record is not None:
            return session.record
        if self._store is not None:
            record = await self._store.get(run_id)
            if record is not None:
                return record
        raise RunNotFoundError(run_id)

    async def list_records(self, limit: int = 100) -> list[RunRecord]:
        if self._store is not None:
            return await self._store.list(limit)
        records = [s.record for s in self._sessions.values() if s.record is not None]
        return records[:limit]

    async def _execute(self, session: _Session) -> None:
        emitter = session.emitter
        record = session.record
        assert record is not None  # created in start()
        record.status = "running"
        await self._persist(record)
        try:
            built = graph_builder.build(
                session.crew,
                emitter=emitter,
                ollama=self._ollama,
                settings=self._settings,
                checkpointer=self._checkpointer,
            )
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
            # thread_id keys the checkpoint to this run (no-op without a checkpointer).
            config = {"configurable": {"thread_id": session.run_id}}
            final_state = await built.graph.ainvoke(initial, config=config)

            record.results = _coerce_results(final_state.get("results", {}))
            record.final_answer = final_state.get("final_answer")
            record.status = "done"
        except asyncio.CancelledError:
            # Cooperative cancel via cancel(). Emit is await-free (put_nowait), so
            # this is safe in the cancelled context; we own the cancellation and
            # finalize cleanly rather than re-raising.
            record.status = "cancelled"
            record.error = "run cancelled"
            await emitter.emit(ErrorEvent(message="run cancelled"))
        except Exception as exc:  # noqa: BLE001 — report failure as an SSE error event
            record.status = "error"
            record.error = str(exc)
            await emitter.emit(ErrorEvent(message=str(exc)))
        finally:
            await self._persist(record)
            await emitter.emit(DoneEvent())

    async def _persist(self, record: RunRecord) -> None:
        if self._store is not None:
            await self._store.upsert(record)


@lru_cache
def get_runner() -> Runner:
    """Process-wide run registry. One per app."""
    return Runner()


def _coerce_results(results: dict) -> dict[str, AgentResult]:
    coerced: dict[str, AgentResult] = {}
    for key, value in results.items():
        coerced[key] = value if isinstance(value, AgentResult) else AgentResult(**value)
    return coerced
