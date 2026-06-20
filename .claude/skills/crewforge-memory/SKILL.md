---
name: crewforge-memory
description: Use when implementing or modifying per-crew memory — the Chroma vector store, Ollama embeddings, the Manager-reads/Leader-writes boundary, or context-window safety when assembling prompts
---

# CrewForge — Memory Skill

This skill holds the **reusable patterns for cross-run memory**: a per-crew Chroma collection, local Ollama embeddings, a strict read/write boundary, and how to keep retrieved context from blowing the model's context window.

> **Concrete facts (collection naming, embedding model, paths) live in [BUILD_SPEC.md](../../../BUILD_SPEC.md) / [ARCHITECTURE.md](../../../ARCHITECTURE.md).** This skill shows the *techniques and the boundary rules*.

---

## What "memory" means here

LLM calls are stateless — the model remembers nothing between runs. "Memory across runs" is something we build: we **save** a summary of each run, and on a new run we **retrieve** the relevant past summaries and feed them into the prompt. The model doesn't remember; we re-supply.

We use **semantic** memory (vector search), not just recent history, so a run can recall a *content-similar* past run ("this IP was flagged before") regardless of when it happened.

---

## The two hard rules

1. **One collection per crew.** Each crew's memory is an isolated Chroma collection keyed by `crew_id`. Crews never share memory — a SOC crew and a research crew must not see each other's history.
2. **Manager reads, Leader writes. Nobody else touches memory.**
   - `crew_memory.read(crew_id, query)` is called **only** by the Manager node, at the start of a run.
   - `crew_memory.write(crew_id, entry)` is called **only** by the Leader node, at the end of a run.
   - Workers never query memory. They receive any relevant past context *through the Manager's task descriptions*.

This boundary is enforced by import discipline: only `nodes/manager.py` imports `read`, only `nodes/leader.py` imports `write`. If anything else imports either, that's the smell.

---

## The module shape

```python
# memory/crew_memory.py
async def read(crew_id: str, query: str, k: int = 5) -> str:
    """Embed the query, fetch top-k similar past entries from this crew's
       collection, return them as a compact context string for the Manager."""
    col = _collection(crew_id)                 # get-or-create, named by crew_id
    vec = await ollama_client.embed(query)
    hits = col.query(query_embeddings=[vec], n_results=k)
    return _format_context(hits)               # compact, summarized — see below

async def write(crew_id: str, entry: MemoryEntry) -> None:
    """Embed the entry text, upsert it into this crew's collection."""
    col = _collection(crew_id)
    vec = await ollama_client.embed(entry.text)
    col.upsert(ids=[entry.id], embeddings=[vec],
               documents=[entry.text], metadatas=[entry.meta])
```

- **Embeddings are local** via Ollama (`ollama_client.embed`) — same local-first constraint as generation. No cloud embedding API.
- **Collection get-or-create by `crew_id`** — creating a crew doesn't need a migration; the collection appears on first write.

---

## What the Leader writes

After synthesis, the Leader records a **summary**, not the raw transcript:

- The final conclusion in a sentence or few.
- Key structured facts worth recalling (e.g. entities seen, verdicts), pulled from worker `results`.
- Light metadata (run id, timestamp) for filtering.

Writing summaries (not full dumps) keeps the collection retrievable and keeps later reads small.

---

## Context-window safety

The danger: worker outputs accumulate, and naively concatenating everything — past memory + every worker's full JSON — into the Manager or Leader prompt overflows the model's context window, causing silent truncation or errors.

Defenses:

- **Retrieve few, summarized.** `read()` returns top-k (small k) entries, each already a summary, formatted compactly — not every past run.
- **Pass fields, not blobs.** When assembling the Leader prompt, pass the structured fields from worker `results` (and summarize long arrays) rather than concatenating raw JSON strings. The JSON-between-agents contract exists partly to make this selective passing possible.
- **Budget-aware assembly.** Know the model's context length; if assembled context approaches it, summarize or drop the least-relevant pieces before calling, rather than letting the model truncate blindly.

---

## Review Checklist — Memory Smells

| ❌ Smell | ✅ Correct | Why |
|---|---|---|
| One shared collection for all crews | One collection per `crew_id` | Crew memory isolation |
| A worker calling `crew_memory.read` | Only the Manager reads | Single enforceable boundary |
| The Leader reading memory to "decide" | Leader only synthesizes + writes | Manager reads, Leader writes |
| Writing the full run transcript to memory | Write a summary + key facts | Keeps retrieval useful and small |
| Cloud embedding API | Ollama local `embed` | Local-first constraint |
| Concatenating all results into one prompt | Pass selected fields, summarize long arrays | Context-window safety |
| Retrieving all past runs | Top-k semantic, small k | Relevance + token budget |
| `read`/`write` imported outside manager/leader nodes | Restrict imports to those two nodes | Boundary stays enforceable |

---

## Cross-References

- **Why Manager-reads/Leader-writes; golden rules** → `crewforge-architecture`
- **Where `read`/`write` are called in the graph** → `crewforge-orchestration`
- **The structured worker output that feeds summaries** → `crewforge-agents`
- **Collection naming, embedding model, paths** → [BUILD_SPEC.md](../../../BUILD_SPEC.md) / [ARCHITECTURE.md](../../../ARCHITECTURE.md)
