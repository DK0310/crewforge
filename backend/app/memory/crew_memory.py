"""Per-crew semantic memory backed by Chroma + local Ollama embeddings.

LLM calls are stateless; "memory across runs" is something we build: the Leader
**writes** a compact summary of each run, and on a new run the Manager **reads**
the most relevant past summaries back in. The model doesn't remember — we
re-supply.

Two hard rules:
  1. One collection per crew (`crew_{crew_id}`). Crews never share memory.
  2. `read` is called only by the Manager node; `write` only by the Leader node.
"""

from __future__ import annotations

import time
from functools import lru_cache

import chromadb
from chromadb.config import Settings as ChromaSettings
from pydantic import BaseModel, Field

from backend.app.llm import get_ollama_client
from backend.app.settings import get_settings


class MemoryEntry(BaseModel):
    id: str
    text: str
    meta: dict = Field(default_factory=dict)


@lru_cache
def _client():
    s = get_settings()
    s.chroma_dir.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=str(s.chroma_dir), settings=ChromaSettings(anonymized_telemetry=False)
    )


def _collection(crew_id: str):
    # get-or-create: a new crew needs no migration; the collection appears on
    # first write.
    return _client().get_or_create_collection(f"crew_{crew_id}")


async def read(crew_id: str, query: str, k: int = 5) -> str:
    """Embed the query, fetch top-k similar past entries from THIS crew's
    collection, and return them as a compact context string for the Manager.

    Called only by the Manager node. Returns "" when the crew has no memory yet.
    """
    col = _collection(crew_id)
    count = col.count()
    if count == 0:
        return ""
    vec = await get_ollama_client().embed(query, model=get_settings().embed_model)
    hits = col.query(query_embeddings=[vec], n_results=min(k, count))
    docs = (hits.get("documents") or [[]])[0]
    if not docs:
        return ""
    return "\n".join(f"- {doc}" for doc in docs)


async def write(crew_id: str, entry: MemoryEntry) -> None:
    """Embed the entry text and upsert it into THIS crew's collection.

    Called only by the Leader node. The entry should be a *summary* (conclusion +
    key facts), not a raw transcript, so recall stays small and cheap.
    """
    col = _collection(crew_id)
    vec = await get_ollama_client().embed(entry.text, model=get_settings().embed_model)
    meta = {"ts": time.time(), **entry.meta}
    col.upsert(ids=[entry.id], embeddings=[vec], documents=[entry.text], metadatas=[meta])
