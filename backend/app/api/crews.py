"""Crew CRUD — thin endpoints over `config/crews/*.yaml`.

Writing a crew validates its worker references and execution plan before
persisting, so a crew can never point at a non-existent worker.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app import config_loader
from backend.app.config_loader import ConfigError
from backend.app.models import CrewConfig, CrewSummary

router = APIRouter(tags=["crews"])


@router.get("/crews")
async def list_crews() -> list[CrewSummary]:
    return [c.summary() for c in config_loader.all_crews()]


@router.get("/crews/{crew_id}")
async def get_crew(crew_id: str) -> CrewConfig:
    try:
        return config_loader.load_crew(crew_id)
    except ConfigError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/crews")
async def create_crew(cfg: CrewConfig) -> CrewConfig:
    try:
        return config_loader.write_crew(cfg)
    except ConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/crews/{crew_id}")
async def update_crew(crew_id: str, cfg: CrewConfig) -> CrewConfig:
    if cfg.id != crew_id:
        raise HTTPException(
            status_code=400, detail=f"Body id '{cfg.id}' does not match path '{crew_id}'"
        )
    try:
        return config_loader.write_crew(cfg)
    except ConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
