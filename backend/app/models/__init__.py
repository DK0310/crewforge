"""Pydantic data models: config schemas and run-time data shapes.

These are *data*, not engine logic. The engine, API, and config loader all share
these types so the contract stays in one place.
"""

from backend.app.models.agent import AgentConfig, AgentSummary, ToolSpec
from backend.app.models.crew import CrewConfig, CrewSummary, DependencySpec
from backend.app.models.run import (
    AgentResult,
    AgentResultEvent,
    AgentStatusEvent,
    DoneEvent,
    ErrorEvent,
    FinalEvent,
    PlanEvent,
    RunEvent,
    RunRecord,
    RunRequest,
    TokenEvent,
)
from backend.app.models.system_role import SystemRoleConfig

__all__ = [
    "AgentConfig",
    "AgentSummary",
    "ToolSpec",
    "CrewConfig",
    "CrewSummary",
    "DependencySpec",
    "SystemRoleConfig",
    "RunRequest",
    "RunRecord",
    "AgentResult",
    "RunEvent",
    "PlanEvent",
    "AgentStatusEvent",
    "TokenEvent",
    "AgentResultEvent",
    "FinalEvent",
    "ErrorEvent",
    "DoneEvent",
]
