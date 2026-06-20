"""Unit tests for the pure planner — no I/O, no LLM, fully deterministic."""

from __future__ import annotations

import pytest

from backend.app.engine import planner
from backend.app.engine.planner import PlanError
from backend.app.models import AgentConfig, DependencySpec


def _agent(agent_id: str, consumes=None, produces=None) -> AgentConfig:
    return AgentConfig(
        id=agent_id,
        name=agent_id,
        description="",
        system_prompt="x",
        consumes=consumes or [],
        produces=produces or [],
        output_schema={"type": "object"},
    )


def test_no_plan_no_io_is_single_parallel_wave():
    workers = ["a", "b", "c"]
    agents = {w: _agent(w) for w in workers}
    assert planner.resolve(workers, None, agents) == [["a", "b", "c"]]


def test_explicit_plan_wins_and_orders_into_waves():
    workers = ["triage", "threat_intel", "forensics"]
    agents = {w: _agent(w) for w in workers}
    plan = [
        DependencySpec(agent="triage", depends_on=[]),
        DependencySpec(agent="threat_intel", depends_on=["triage"]),
        DependencySpec(agent="forensics", depends_on=["triage"]),
    ]
    waves = planner.resolve(workers, plan, agents)
    assert waves == [["triage"], ["threat_intel", "forensics"]]


def test_consumes_produces_inference():
    workers = ["triage", "threat_intel"]
    agents = {
        "triage": _agent("triage", produces=["iocs"]),
        "threat_intel": _agent("threat_intel", consumes=["iocs"]),
    }
    assert planner.resolve(workers, None, agents) == [["triage"], ["threat_intel"]]


def test_cycle_detection_raises_with_names():
    workers = ["a", "b"]
    agents = {w: _agent(w) for w in workers}
    plan = [
        DependencySpec(agent="a", depends_on=["b"]),
        DependencySpec(agent="b", depends_on=["a"]),
    ]
    with pytest.raises(PlanError) as exc:
        planner.resolve(workers, plan, agents)
    assert "a" in str(exc.value) and "b" in str(exc.value)


def test_explicit_plan_unknown_dependency_raises():
    workers = ["a"]
    agents = {"a": _agent("a")}
    plan = [DependencySpec(agent="a", depends_on=["ghost"])]
    with pytest.raises(PlanError):
        planner.resolve(workers, plan, agents)
