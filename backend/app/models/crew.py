"""Crew configuration schema (which workers + optional explicit execution plan)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DependencySpec(BaseModel):
    """One entry of an explicit execution plan: an agent and what it waits on."""

    agent: str
    depends_on: list[str] = Field(default_factory=list)


class CrewSummary(BaseModel):
    id: str
    name: str
    description: str = ""
    workers: list[str] = Field(default_factory=list)


class CrewConfig(BaseModel):
    """A crew. Lists only the workers — Manager and Leader are injected by the
    engine for every crew and are never listed here.
    """

    id: str
    name: str
    description: str = ""

    workers: list[str]

    # OPTIONAL explicit execution plan (advanced mode). When present the engine
    # honors it exactly and the Manager does not decide order. When absent the
    # planner falls back to consumes/produces inference, then a single parallel
    # wave.
    execution_plan: list[DependencySpec] | None = None

    # Optional per-crew overrides for the built-in role prompts.
    manager_prompt_override: str | None = None
    leader_prompt_override: str | None = None

    def summary(self) -> CrewSummary:
        return CrewSummary(
            id=self.id, name=self.name, description=self.description, workers=self.workers
        )
