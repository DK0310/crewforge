"""Run-time data shapes: the run request, per-agent results, and the SSE event
union that the engine emits and the API serializes.

Defining the event types **once** here is what keeps the frontend and backend
from drifting on event names (the API just serializes whatever the engine emits).
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

AgentStatus = Literal["pending", "running", "done", "error"]


class RunRequest(BaseModel):
    crew_id: str
    user_input: str
    file: str | None = None  # path or extracted text of an upload


class AgentResult(BaseModel):
    """One worker's outcome, stored in `CrewState.results` under its agent id."""

    agent_id: str
    status: AgentStatus
    output: dict | None = None  # the worker's validated JSON
    error: str | None = None
    started_at: float | None = None
    finished_at: float | None = None


# --- SSE event union -------------------------------------------------------
#
# One JSON object per `data:` line. The `type` field discriminates. Token events
# are tagged with an `agent_id`; the Manager and Leader use the reserved sentinels
# `__manager__` and `__leader__`.


class PlanEvent(BaseModel):
    type: Literal["plan"] = "plan"
    waves: list[list[str]]


class AgentStatusEvent(BaseModel):
    type: Literal["agent_status"] = "agent_status"
    agent_id: str
    status: AgentStatus


class TokenEvent(BaseModel):
    type: Literal["token"] = "token"
    agent_id: str
    text: str


class AgentResultEvent(BaseModel):
    type: Literal["agent_result"] = "agent_result"
    agent_id: str
    output: dict


class FinalEvent(BaseModel):
    type: Literal["final"] = "final"
    answer: str


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    agent_id: str | None = None
    message: str


class DoneEvent(BaseModel):
    type: Literal["done"] = "done"


RunEvent = Annotated[
    Union[
        PlanEvent,
        AgentStatusEvent,
        TokenEvent,
        AgentResultEvent,
        FinalEvent,
        ErrorEvent,
        DoneEvent,
    ],
    Field(discriminator="type"),
]


class RunRecord(BaseModel):
    """A completed (or in-flight) run, returned by `GET /runs/{id}` and `GET /runs`."""

    run_id: str
    crew_id: str
    status: Literal["pending", "running", "done", "error", "cancelled"]
    plan: list[list[str]] = Field(default_factory=list)
    results: dict[str, AgentResult] = Field(default_factory=dict)
    final_answer: str | None = None
    error: str | None = None
