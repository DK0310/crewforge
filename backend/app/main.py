"""FastAPI application: route registration and lifecycle.

The app is a thin shell. All orchestration lives in the engine; these routers just
move bytes and manage config files.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from backend.app.api import agents, crews, runs
from backend.app.engine.runner import get_runner
from backend.app.llm import get_ollama_client
from backend.app.persistence import RunStore
from backend.app.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    # Durable run history (API-facing) + LangGraph state checkpointer (graph-level).
    store = RunStore(settings.runs_db)
    await store.init()
    async with AsyncSqliteSaver.from_conn_string(str(settings.checkpoint_db)) as saver:
        get_runner().configure(store=store, checkpointer=saver)
        yield
    # Close the shared Ollama HTTP client on shutdown.
    await get_ollama_client().aclose()


app = FastAPI(title="CrewForge", version="0.1.0", lifespan=lifespan)

# The frontend dev server runs on a different origin; allow it during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agents.router)
app.include_router(crews.router)
app.include_router(runs.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
