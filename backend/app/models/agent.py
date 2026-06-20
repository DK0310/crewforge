"""Agent configuration schema (one worker = one YAML file)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ToolSpec(BaseModel):
    """A tool an agent may invoke.

    RESERVED FOR A FUTURE FEATURE. The field is typed so agent YAML can declare
    tools and the schema stays stable, but tool-calling is **not** implemented in
    v1. The worker node carries a documented seam where execution would slot in.
    """

    name: str
    description: str = ""
    params: dict = Field(default_factory=dict)


class AgentSummary(BaseModel):
    """Lightweight view returned by list endpoints / shown in the UI picker."""

    id: str
    name: str
    description: str
    consumes: list[str] = Field(default_factory=list)
    produces: list[str] = Field(default_factory=list)


class AgentConfig(BaseModel):
    """A worker agent. Pure data — the engine reads it, never embeds it."""

    id: str  # unique; must match the YAML filename stem
    name: str  # display name
    description: str  # shown in the UI worker picker
    model: str | None = None  # Ollama tag; falls back to the default if omitted
    system_prompt: str  # role / goal / backstory

    # I/O contract. Used by the planner to infer order when no explicit plan is
    # given. Both optional.
    consumes: list[str] = Field(default_factory=list)
    produces: list[str] = Field(default_factory=list)

    # Reserved seam — always present, empty in v1.
    tools: list[ToolSpec] = Field(default_factory=list)

    # JSON Schema the worker's output must satisfy (validated after generation).
    output_schema: dict

    def summary(self) -> AgentSummary:
        return AgentSummary(
            id=self.id,
            name=self.name,
            description=self.description,
            consumes=self.consumes,
            produces=self.produces,
        )
