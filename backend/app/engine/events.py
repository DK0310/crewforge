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

# Sentinel yielded by `stream(keepalive=…)` when the queue has been idle for the
# keep-alive interval. The API turns it into an SSE comment line so idle proxies
# don't drop the connection. It is not a `RunEvent`.
KEEPALIVE = object()


class Emitter:
    """A single-run async queue of `RunEvent`s."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue = asyncio.Queue()

    async def emit(self, event) -> None:
        # The queue is unbounded, so `put_nowait` never blocks. Keeping `emit`
        # await-free means it can be called safely from a task's cleanup path
        # (e.g. after CancelledError) without re-raising at a suspension point.
        self._queue.put_nowait(event)

    async def stream(self, keepalive: float | None = None) -> AsyncIterator:
        """Yield events until (and including) the terminal `DoneEvent`.

        If `keepalive` (seconds) is set, yield the `KEEPALIVE` sentinel whenever
        the queue stays idle that long. Racing `queue.get()` with a timeout is safe
        (cancelling a plain `get()` cleanly removes its waiter).
        """
        while True:
            if keepalive is None:
                event = await self._queue.get()
            else:
                try:
                    event = await asyncio.wait_for(self._queue.get(), keepalive)
                except asyncio.TimeoutError:
                    yield KEEPALIVE
                    continue
            yield event
            if isinstance(event, DoneEvent):
                break
