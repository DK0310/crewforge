"""Uploaded source material reaches the prompts (Phase 2 acceptance, unit level)."""

from __future__ import annotations

from backend.app.engine.nodes.worker import _assemble_prompt
from backend.app.engine.prompt_utils import source_material_block
from backend.app.models import AgentConfig


def test_source_block_empty_is_dropped():
    assert source_material_block(None, 100) == ""
    assert source_material_block("   ", 100) == ""


def test_source_block_caps_length():
    block = source_material_block("x" * 500, 100)
    assert "truncated" in block
    assert block.count("x") <= 100


def test_worker_prompt_includes_uploaded_text():
    agent = AgentConfig(
        id="a", name="A", description="d", system_prompt="p", output_schema={"type": "object"}
    )
    prompt = _assemble_prompt(agent, "the task", {}, "SECRET-LOG-LINE-42", 1000)
    assert "SECRET-LOG-LINE-42" in prompt
    assert "the task" in prompt
