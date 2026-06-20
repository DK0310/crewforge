"""Thin async wrapper over the local Ollama HTTP API.

The *only* module that speaks Ollama. Exposes a streaming `generate()` (an async
generator of token chunks, so nodes can forward them straight to SSE) and a
blocking `embed()` for memory. Local-first: no cloud provider, ever.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from functools import lru_cache

import httpx

from backend.app.settings import get_settings


class OllamaError(RuntimeError):
    """Raised when Ollama returns an error or is unreachable."""


class OllamaClient:
    def __init__(self, base_url: str, timeout: float) -> None:
        self._client = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout)

    async def generate(
        self,
        prompt: str,
        *,
        model: str,
        system: str | None = None,
        stream: bool = True,
    ) -> AsyncIterator[str]:
        """Yield response chunks from `/api/generate`.

        Works for both streaming and non-streaming calls — Ollama emits
        newline-delimited JSON objects, each carrying a `response` fragment and a
        `done` flag. Callers that want the whole string just join the chunks.
        """
        payload: dict = {"model": model, "prompt": prompt, "stream": stream}
        if system:
            payload["system"] = system

        try:
            async with self._client.stream("POST", "/api/generate", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    if data.get("error"):
                        raise OllamaError(data["error"])
                    chunk = data.get("response", "")
                    if chunk:
                        yield chunk
                    if data.get("done"):
                        break
        except httpx.HTTPError as exc:
            raise OllamaError(f"Ollama generate failed ({model}): {exc}") from exc

    async def embed(self, text: str, *, model: str) -> list[float]:
        """Return an embedding vector for `text` from `/api/embeddings`."""
        try:
            resp = await self._client.post(
                "/api/embeddings", json={"model": model, "prompt": text}
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise OllamaError(f"Ollama embed failed ({model}): {exc}") from exc
        data = resp.json()
        vec = data.get("embedding")
        if not vec:
            raise OllamaError(f"Ollama embed returned no vector ({model}): {data}")
        return vec

    async def aclose(self) -> None:
        await self._client.aclose()


@lru_cache
def get_ollama_client() -> OllamaClient:
    s = get_settings()
    return OllamaClient(s.ollama_base_url, s.request_timeout)
