"""System-role configuration schema (the built-in Manager and Leader prompts)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class SystemRoleConfig(BaseModel):
    """A built-in role's prompt. Edited by advanced users; never composed away.

    Exactly one Manager and one Leader exist per crew, injected by the engine. A
    crew may override either prompt (see `CrewConfig.manager_prompt_override` /
    `leader_prompt_override`).
    """

    role: Literal["manager", "leader"]
    model: str | None = None  # Ollama tag; falls back to the default if omitted
    system_prompt: str
