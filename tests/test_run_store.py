"""Persistence tests — durable run history survives a simulated restart.

No Ollama needed: these exercise the RunStore and the Runner's record bookkeeping
directly, never running the graph.
"""

from __future__ import annotations

from backend.app.engine.runner import Runner
from backend.app.models import AgentResult, RunRecord
from backend.app.persistence import RunStore


def _record() -> RunRecord:
    return RunRecord(
        run_id="run-abc",
        crew_id="soc_crew",
        status="done",
        plan=[["triage"], ["threat_intel", "forensics"]],
        results={
            "triage": AgentResult(
                agent_id="triage", status="done", output={"summary": "ok"}
            )
        },
        final_answer="All clear.",
    )


async def test_store_roundtrip_and_list(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite")
    await store.init()
    await store.upsert(_record())

    got = await store.get("run-abc")
    assert got is not None
    assert got.status == "done"
    assert got.plan == [["triage"], ["threat_intel", "forensics"]]
    assert got.results["triage"].output == {"summary": "ok"}
    assert got.final_answer == "All clear."

    listed = await store.list()
    assert [r.run_id for r in listed] == ["run-abc"]


async def test_upsert_updates_status(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite")
    await store.init()
    rec = _record()
    rec.status = "running"
    await store.upsert(rec)
    rec.status = "error"
    rec.error = "boom"
    await store.upsert(rec)

    got = await store.get("run-abc")
    assert got.status == "error"
    assert got.error == "boom"
    assert len(await store.list()) == 1  # upsert, not insert


async def test_store_survives_restart(tmp_path):
    db = tmp_path / "runs.sqlite"
    store1 = RunStore(db)
    await store1.init()
    await store1.upsert(_record())

    # Simulate a server restart: a brand-new store object on the same file.
    store2 = RunStore(db)
    got = await store2.get("run-abc")
    assert got is not None and got.crew_id == "soc_crew"


async def test_runner_reads_record_from_store_after_restart(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite")
    await store.init()

    runner1 = Runner(store=store)
    run_id = await runner1.start("soc_crew", "investigate something")  # no graph run

    # New runner (empty in-memory sessions), same store — as if the process restarted.
    runner2 = Runner(store=store)
    got = await runner2.get_record(run_id)
    assert got.run_id == run_id
    assert got.crew_id == "soc_crew"
    assert got.status == "pending"

    listed = await runner2.list_records()
    assert run_id in {r.run_id for r in listed}
