"""Agent CRUD — thin endpoints over `config/agents/*.yaml`.

Validation on write is identical to validation on load, so a UI-created agent is
as safe as a hand-written one. No database; the YAML files are the store.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app import config_loader
from backend.app.config_loader import ConfigError
from backend.app.models import AgentConfig, AgentSummary

router = APIRouter(tags=["agents"])


@router.get("/agents")
async def list_agents() -> list[AgentSummary]:
    return [a.summary() for a in config_loader.all_agents()]


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str) -> AgentConfig:
    try:
        return config_loader.load_agent(agent_id)
    except ConfigError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/agents")
async def create_agent(cfg: AgentConfig) -> AgentConfig:
    try:
        return config_loader.write_agent(cfg)
    except ConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/agents/{agent_id}")
async def update_agent(agent_id: str, cfg: AgentConfig) -> AgentConfig:
    if cfg.id != agent_id:
        raise HTTPException(
            status_code=400, detail=f"Body id '{cfg.id}' does not match path '{agent_id}'"
        )
    try:
        return config_loader.write_agent(cfg)
    except ConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
