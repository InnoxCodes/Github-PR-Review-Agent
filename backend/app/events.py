"""In-process pub/sub that fans review events out to connected SSE clients.

Events are always written to the review_events table *before* they're published, so the
database is the source of truth and a client that connects late (or reconnects with
Last-Event-ID) replays from the table, then switches to the live queue.

Single-process by design: a multi-instance deployment would swap this for Redis pub/sub
or Postgres LISTEN/NOTIFY behind the same subscribe/publish interface.
"""

import asyncio
import json
from collections import defaultdict
from typing import Any

TERMINAL_EVENTS = frozenset({"review.completed", "review.failed"})

Event = dict[str, Any]


class EventBroker:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[Event]]] = defaultdict(set)

    def subscribe(self, review_id: str) -> asyncio.Queue[Event]:
        queue: asyncio.Queue[Event] = asyncio.Queue()
        self._subscribers[review_id].add(queue)
        return queue

    def unsubscribe(self, review_id: str, queue: asyncio.Queue[Event]) -> None:
        subscribers = self._subscribers.get(review_id)
        if subscribers is None:
            return
        subscribers.discard(queue)
        if not subscribers:
            del self._subscribers[review_id]

    def publish(self, review_id: str, event: Event) -> None:
        for queue in list(self._subscribers.get(review_id, ())):
            queue.put_nowait(event)

    def subscriber_count(self, review_id: str) -> int:
        return len(self._subscribers.get(review_id, ()))


def format_sse(event_id: int, event_type: str, data: dict[str, Any]) -> str:
    return f"id: {event_id}\nevent: {event_type}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"
