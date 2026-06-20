"""Engine tests driven by a fake Ollama — full runs, failure, repair, cancellation,
all without a live model.
"""

from __future__ import annotations

import asyncio

import pytest

from backend.app.engine.runner import Runner
from tests._helpers import FakeOllama, happy_responder, repair_responder, write_tmp_config


@pytest.fixture(autouse=True)
def _no_memory(monkeypatch):
    """Stub the per-crew memory so tests need neither Chroma nor an embedder."""

    async def _read(*a, **k):
        return ""

    async def _write(*a, **k):
        return None

    monkeypatch.setattr("backend.app.memory.crew_memory.read", _read)
    monkeypatch.setattr("backend.app.memory.crew_memory.write", _write)


async def _drain(runner: Runner, run_id: str, timeout: float = 10.0) -> list:
    async def collect():
        return [e async for e in runner.run_events(run_id)]

    return await asyncio.wait_for(collect(), timeout)


def _types(events) -> list[str]:
    return [getattr(e, "type", "?") for e in events]


async def test_happy_path_runs_to_final(tmp_path):
    settings = write_tmp_config(tmp_path)
    runner = Runner(ollama=FakeOllama(happy_responder), settings=settings)
    run_id = await runner.start("t_crew", "do the thing")

    events = await _drain(runner, run_id)
    types = _types(events)

    assert types[0] == "plan"
    assert types[-1] == "done"
    assert "final" in types
    assert types.count("agent_result") == 2  # a and b

    rec = await runner.get_record(run_id)
    assert rec.status == "done"
    assert rec.final_answer == "Final synthesized answer."
    assert {k for k, v in rec.results.items() if v.status == "done"} == {"a", "b"}


async def test_ollama_outage_ends_error_then_done(tmp_path):
    settings = write_tmp_config(tmp_path)
    runner = Runner(ollama=FakeOllama(happy_responder, fail=True), settings=settings)
    run_id = await runner.start("t_crew", "do the thing")

    events = await _drain(runner, run_id)
    types = _types(events)

    assert "error" in types
    assert types[-1] == "done"  # never hangs
    rec = await runner.get_record(run_id)
    assert rec.status == "error"


async def test_worker_json_repair_recovers(tmp_path):
    settings = write_tmp_config(tmp_path)
    runner = Runner(ollama=FakeOllama(repair_responder), settings=settings)
    run_id = await runner.start("t_crew", "do the thing")

    events = await _drain(runner, run_id)
    rec = await runner.get_record(run_id)

    assert rec.status == "done"
    assert rec.results["a"].status == "done"
    assert rec.results["a"].output == {"summary": "repaired"}


async def test_cancel_marks_cancelled_and_emits_done(tmp_path):
    settings = write_tmp_config(tmp_path)
    runner = Runner(ollama=FakeOllama(happy_responder, delay=2.0), settings=settings)
    run_id = await runner.start("t_crew", "do the thing")

    collected: list = []

    async def consume():
        async for e in runner.run_events(run_id):
            collected.append(e)

    consumer = asyncio.create_task(consume())
    await asyncio.sleep(0.3)  # let the manager start and block in generate()
    await runner.cancel(run_id)
    await asyncio.wait_for(consumer, timeout=5)

    types = _types(collected)
    assert types[-1] == "done"
    assert any(
        getattr(e, "type", "") == "error" and "cancel" in getattr(e, "message", "")
        for e in collected
    )
    rec = await runner.get_record(run_id)
    assert rec.status == "cancelled"
