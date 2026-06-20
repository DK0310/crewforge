"""SQLite-backed store of `RunRecord`s so run history survives a server restart.

This is deliberately separate from the LangGraph checkpointer:
  - the **checkpointer** persists low-level graph state (CrewState per superstep),
    keyed by `thread_id`, for resume/inspection;
  - the **RunStore** persists the API-facing summary (status, plan, results, answer,
    error) that `GET /runs/{id}` and `GET /runs` return.

One connection is opened per operation — simple and safe for a local single-user
app; no long-lived connection to manage.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import aiosqlite

from backend.app.models import AgentResult, RunRecord

_CREATE = """
CREATE TABLE IF NOT EXISTS runs (
    run_id       TEXT PRIMARY KEY,
    crew_id      TEXT NOT NULL,
    status       TEXT NOT NULL,
    plan         TEXT NOT NULL,
    results      TEXT NOT NULL,
    final_answer TEXT,
    error        TEXT,
    created_at   REAL NOT NULL,
    updated_at   REAL NOT NULL
)
"""

_UPSERT = """
INSERT INTO runs (run_id, crew_id, status, plan, results, final_answer, error, created_at, updated_at)
VALUES (:run_id, :crew_id, :status, :plan, :results, :final_answer, :error, :now, :now)
ON CONFLICT(run_id) DO UPDATE SET
    status       = excluded.status,
    plan         = excluded.plan,
    results      = excluded.results,
    final_answer = excluded.final_answer,
    error        = excluded.error,
    updated_at   = excluded.updated_at
"""


class RunStore:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)

    async def init(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(_CREATE)
            await db.commit()

    async def upsert(self, record: RunRecord) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                _UPSERT,
                {
                    "run_id": record.run_id,
                    "crew_id": record.crew_id,
                    "status": record.status,
                    "plan": json.dumps(record.plan),
                    "results": json.dumps(
                        {k: v.model_dump() for k, v in record.results.items()}
                    ),
                    "final_answer": record.final_answer,
                    "error": record.error,
                    "now": time.time(),
                },
            )
            await db.commit()

    async def get(self, run_id: str) -> RunRecord | None:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM runs WHERE run_id = ?", (run_id,)
            ) as cur:
                row = await cur.fetchone()
        return _row_to_record(row) if row else None

    async def list(self, limit: int = 100) -> list[RunRecord]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)
            ) as cur:
                rows = await cur.fetchall()
        return [_row_to_record(r) for r in rows]


def _row_to_record(row: aiosqlite.Row) -> RunRecord:
    results = {
        agent_id: AgentResult(**data)
        for agent_id, data in json.loads(row["results"]).items()
    }
    return RunRecord(
        run_id=row["run_id"],
        crew_id=row["crew_id"],
        status=row["status"],
        plan=json.loads(row["plan"]),
        results=results,
        final_answer=row["final_answer"],
        error=row["error"],
    )
