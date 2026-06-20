"""The in-process event bus that carries node output to the SSE layer.

Nodes call `emitter.emit(event)`; the runner drains the same queue and the API
serializes each event as an SSE `data:` line. Nodes yield *chunks*; SSE
formatting happens at the edge, never inside a node.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from backend.app.models import DoneEvent
from backend.app.models.run import RunEvent


class Emitter:
    """A single-run async queue of `RunEvent`s."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue = asyncio.Queue()

    async def emit(self, event) -> None:
        await self._queue.put(event)

    async def stream(self) -> AsyncIterator[RunEvent]:
        """Yield events until (and including) the terminal `DoneEvent`."""
        while True:
            event = await self._queue.get()
            yield event
            if isinstance(event, DoneEvent):
                break
