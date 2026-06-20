"""Shared test helpers: a throwaway config tree and a fake Ollama client so the
engine can run fully without a live model.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from backend.app.llm.ollama_client import OllamaError
from backend.app.settings import Settings

_AGENT_A = """\
id: a
name: A
description: agent a
system_prompt: You are agent A.
consumes: []
produces: [x]
tools: []
output_schema:
  type: object
  required: [summary]
  properties:
    summary: { type: string }
"""

_AGENT_B = """\
id: b
name: B
description: agent b
system_prompt: You are agent B.
consumes: [x]
produces: []
tools: []
output_schema:
  type: object
  required: [summary]
  properties:
    summary: { type: string }
"""

_CREW = """\
id: t_crew
name: Test Crew
description: a crew for tests
workers: [a, b]
execution_plan:
  - agent: a
    depends_on: []
  - agent: b
    depends_on: [a]
"""

_MANAGER = "role: manager\nsystem_prompt: You are the manager.\n"
_LEADER = "role: leader\nsystem_prompt: You are the leader.\n"


def write_tmp_config(tmp_path: Path) -> Settings:
    """Write a minimal config tree under tmp_path and return Settings pointed at it."""
    cfg = tmp_path / "config"
    (cfg / "agents").mkdir(parents=True)
    (cfg / "crews").mkdir(parents=True)
    (cfg / "system_roles").mkdir(parents=True)
    (cfg / "agents" / "a.yaml").write_text(_AGENT_A, encoding="utf-8")
    (cfg / "agents" / "b.yaml").write_text(_AGENT_B, encoding="utf-8")
    (cfg / "crews" / "t_crew.yaml").write_text(_CREW, encoding="utf-8")
    (cfg / "system_roles" / "manager.yaml").write_text(_MANAGER, encoding="utf-8")
    (cfg / "system_roles" / "leader.yaml").write_text(_LEADER, encoding="utf-8")
    return Settings(config_dir=cfg, data_dir=tmp_path / "data")


class FakeOllama:
    """Stands in for OllamaClient. `responder(prompt, system, stream) -> str` decides
    the text; set `fail=True` to simulate an outage (raises on first iteration).
    """

    def __init__(
        self,
        responder: Callable[[str, str | None, bool], str],
        *,
        fail: bool = False,
        delay: float = 0.0,
    ) -> None:
        self._responder = responder
        self._fail = fail
        self._delay = delay
        self.calls: list[tuple[str | None, str]] = []

    async def generate(self, prompt, *, model, system=None, stream=True):
        import asyncio

        self.calls.append((system, prompt))
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._fail:
            raise OllamaError("simulated Ollama outage")
        text = self._responder(prompt, system, stream)
        # Yield in a few chunks to mimic streaming.
        for i in range(0, len(text), 16):
            yield text[i : i + 16]

    async def embed(self, text, *, model):
        return [0.0] * 8

    async def aclose(self):
        return None


# --- Common responders -------------------------------------------------------
def happy_responder(prompt: str, system: str | None, stream: bool) -> str:
    import json

    if "keys are exactly these worker ids" in prompt:  # manager
        return json.dumps({"a": "do a", "b": "do b"})
    if "conforms to this JSON Schema" in prompt:  # worker
        return json.dumps({"summary": "ok"})
    return "Final synthesized answer."  # leader


def repair_responder(prompt: str, system: str | None, stream: bool) -> str:
    """Worker emits invalid JSON while streaming, valid JSON on the repair retry."""
    import json

    if "keys are exactly these worker ids" in prompt:
        return json.dumps({"a": "do a", "b": "do b"})
    if "conforms to this JSON Schema" in prompt:
        return "not json at all" if stream else json.dumps({"summary": "repaired"})
    return "Final answer."
