"""Process configuration, read from environment / `.env` (see `.env.example`).

This is the single source of truth for paths, the Ollama URL, and default model
tags. Nothing else in the codebase should hard-code these values.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/settings.py -> parents[2] is the repository root.
_REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Ollama (local LLM + embeddings) ---
    ollama_base_url: str = "http://localhost:11434"
    default_model: str = "qwen2.5:7b"
    embed_model: str = "nomic-embed-text"
    request_timeout: float = 300.0

    # --- Context-window budget (keep prompts within the model's limit) ---
    max_upload_chars: int = 12000  # cap on uploaded-file text injected into a prompt
    manager_memory_k: int = 5  # top-k past entries the Manager pulls from memory
    leader_max_array_items: int = 10  # truncate worker arrays before the Leader prompt
    leader_max_str_len: int = 800  # truncate long worker strings before the Leader prompt

    # --- Filesystem locations ---
    config_dir: Path = _REPO_ROOT / "config"
    data_dir: Path = _REPO_ROOT / "data"

    @property
    def agents_dir(self) -> Path:
        return self.config_dir / "agents"

    @property
    def crews_dir(self) -> Path:
        return self.config_dir / "crews"

    @property
    def system_roles_dir(self) -> Path:
        return self.config_dir / "system_roles"

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def checkpoint_db(self) -> Path:
        return self.data_dir / "checkpoints.sqlite"

    @property
    def runs_db(self) -> Path:
        return self.data_dir / "runs.sqlite"


@lru_cache
def get_settings() -> Settings:
    return Settings()
