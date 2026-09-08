"""In-memory per-incident event stream store.

The engine pushes DiagnosticEvent objects here as it runs, and the SSE
endpoint streams them to the client in real time.

NOTE: Events are held in memory (per-process). This is fine for a single
node PoC. If you later run multiple uvicorn workers or processes, this
would need to be replaced with Redis pub/sub or similar.
"""
import asyncio
from collections import defaultdict


class EventStreamStore:
    def __init__(self):
        # incident_id -> asyncio.Queue of event dicts
        self._queues: dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
        # incident_id -> final result dict once diagnosis finishes
        self._results: dict[str, dict] = {}

    def push(self, incident_id: str, event: dict):
        """Add a single event to the incident's stream (non-blocking)."""
        queue = self._queues[incident_id]
        try:
            queue.put_nowait(event)
        except Exception:
            pass

    async def subscribe(self, incident_id: str):
        """Yield events for an incident as they are produced.

        Yields None when the stream has ended (final result available),
        so the caller can attach the final status.
        """
        queue = self._queues[incident_id]
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                # No new event within the timeout: check whether the
                # incident finished while we were waiting.
                if incident_id in self._results:
                    yield None
                    return
                continue

            yield event

            if incident_id in self._results and queue.empty():
                yield None
                return

    def set_result(self, incident_id: str, result: dict):
        """Mark an incident as finished and store its final result."""
        self._results[incident_id] = result

    def get_result(self, incident_id: str):
        return self._results.get(incident_id)

    def clear(self, incident_id: str):
        self._results.pop(incident_id, None)
        self._queues.pop(incident_id, None)


store = EventStreamStore()
