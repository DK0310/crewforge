"""Turn YAML files into validated Pydantic models, and back.

Validation happens once, at load (and identically on write, so a UI-created file
is as safe as a hand-written one). Errors name the offending file and field so a
YAML typo never surfaces as a confusing runtime crash three layers deep.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from backend.app.models import AgentConfig, CrewConfig, SystemRoleConfig
from backend.app.settings import Settings, get_settings


class ConfigError(Exception):
    """Raised when a config file is missing, malformed, or internally inconsistent."""


# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
def _agent_path(agent_id: str, s: Settings) -> Path:
    return s.agents_dir / f"{agent_id}.yaml"


def _crew_path(crew_id: str, s: Settings) -> Path:
    return s.crews_dir / f"{crew_id}.yaml"


def _role_path(role: str, s: Settings) -> Path:
    return s.system_roles_dir / f"{role}.yaml"


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"Config file {path.name} must contain a YAML mapping at the top level")
    return data


# --------------------------------------------------------------------------- #
# Agents
# --------------------------------------------------------------------------- #
def load_agent(agent_id: str, s: Settings | None = None) -> AgentConfig:
    s = s or get_settings()
    path = _agent_path(agent_id, s)
    data = _read_yaml(path)
    try:
        cfg = AgentConfig(**data)
    except ValidationError as exc:
        raise ConfigError(f"Invalid agent config {path.name}: {exc}") from exc
    if cfg.id != agent_id:
        raise ConfigError(
            f"Agent id '{cfg.id}' does not match filename '{path.name}' (expected id '{agent_id}')"
        )
    return cfg


def all_agents(s: Settings | None = None) -> list[AgentConfig]:
    s = s or get_settings()
    if not s.agents_dir.exists():
        return []
    agents = [load_agent(p.stem, s) for p in sorted(s.agents_dir.glob("*.yaml"))]
    return agents


def write_agent(cfg: AgentConfig, s: Settings | None = None) -> AgentConfig:
    """Validate then persist `config/agents/{id}.yaml`."""
    s = s or get_settings()
    # Re-run model validation (catches programmatic construction bugs too).
    cfg = AgentConfig.model_validate(cfg.model_dump())
    s.agents_dir.mkdir(parents=True, exist_ok=True)
    path = _agent_path(cfg.id, s)
    path.write_text(_dump_yaml(cfg.model_dump()), encoding="utf-8")
    return cfg


# --------------------------------------------------------------------------- #
# Crews
# --------------------------------------------------------------------------- #
def load_crew(crew_id: str, s: Settings | None = None) -> CrewConfig:
    s = s or get_settings()
    path = _crew_path(crew_id, s)
    data = _read_yaml(path)
    try:
        cfg = CrewConfig(**data)
    except ValidationError as exc:
        raise ConfigError(f"Invalid crew config {path.name}: {exc}") from exc
    if cfg.id != crew_id:
        raise ConfigError(
            f"Crew id '{cfg.id}' does not match filename '{path.name}' (expected id '{crew_id}')"
        )
    _validate_crew_references(cfg, s)
    return cfg


def all_crews(s: Settings | None = None) -> list[CrewConfig]:
    s = s or get_settings()
    if not s.crews_dir.exists():
        return []
    return [load_crew(p.stem, s) for p in sorted(s.crews_dir.glob("*.yaml"))]


def write_crew(cfg: CrewConfig, s: Settings | None = None) -> CrewConfig:
    s = s or get_settings()
    cfg = CrewConfig.model_validate(cfg.model_dump())
    _validate_crew_references(cfg, s)
    s.crews_dir.mkdir(parents=True, exist_ok=True)
    path = _crew_path(cfg.id, s)
    path.write_text(_dump_yaml(cfg.model_dump(exclude_none=True)), encoding="utf-8")
    return cfg


def _validate_crew_references(cfg: CrewConfig, s: Settings) -> None:
    """Every worker must resolve to an agent file; every plan entry must be a worker."""
    workers = set(cfg.workers)
    for wid in cfg.workers:
        if not _agent_path(wid, s).exists():
            raise ConfigError(
                f"Crew '{cfg.id}' references unknown worker '{wid}' "
                f"(no config/agents/{wid}.yaml)"
            )
    if cfg.execution_plan:
        for spec in cfg.execution_plan:
            if spec.agent not in workers:
                raise ConfigError(
                    f"Crew '{cfg.id}' execution_plan references '{spec.agent}', "
                    f"which is not in its workers {sorted(workers)}"
                )
            for dep in spec.depends_on:
                if dep not in workers:
                    raise ConfigError(
                        f"Crew '{cfg.id}' execution_plan: '{spec.agent}' depends_on "
                        f"'{dep}', which is not in its workers {sorted(workers)}"
                    )


# --------------------------------------------------------------------------- #
# System roles
# --------------------------------------------------------------------------- #
def load_system_role(role: str, s: Settings | None = None) -> SystemRoleConfig:
    s = s or get_settings()
    path = _role_path(role, s)
    data = _read_yaml(path)
    try:
        cfg = SystemRoleConfig(**data)
    except ValidationError as exc:
        raise ConfigError(f"Invalid system role config {path.name}: {exc}") from exc
    if cfg.role != role:
        raise ConfigError(f"System role '{cfg.role}' does not match filename '{path.name}'")
    return cfg


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _dump_yaml(data: dict) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False)
