"""`CrewState` — the shared object every node reads from and writes to.

The critical detail is the reducer on `results`: parallel workers in the same
wave each return `{"results": {their_id: ...}}`, and the `or_` (dict merge)
reducer merges them by key. Without it, same-wave workers race and one clobbers
the other — the single most common fan-out bug in LangGraph.
"""

from __future__ import annotations

from operator import or_
from typing import Annotated, TypedDict

from backend.app.models import AgentResult

# Reserved stream ids for the built-in roles (used as both graph node names and
# the `agent_id` on their SSE token/status events).
MANAGER_ID = "__manager__"
LEADER_ID = "__leader__"


class CrewState(TypedDict):
    crew_id: str
    run_id: str
    user_input: str
    uploaded_file: str | None

    memory_context: str  # past-run context the Manager pulled in
    tasks: dict[str, str]  # agent_id -> task description (Manager writes)
    plan: list[list[str]]  # execution waves (planner writes)

    # Workers write here; the `or_` reducer merges parallel writes by key.
    results: Annotated[dict[str, AgentResult], or_]

    final_answer: str | None  # Leader's prose output
