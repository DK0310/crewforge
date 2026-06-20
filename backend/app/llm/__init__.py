"""LLM access. The only module that knows the Ollama HTTP API."""

from backend.app.llm.ollama_client import OllamaClient, get_ollama_client

__all__ = ["OllamaClient", "get_ollama_client"]
