from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from collections.abc import AsyncGenerator
from typing import Any


class RouteDeckEventBus:
    def __init__(self, history_limit: int = 25) -> None:
        self._history_limit = history_limit
        self._history: dict[str, deque[dict[str, Any]]] = defaultdict(
            lambda: deque(maxlen=self._history_limit)
        )
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)

    def publish(self, conversation_id: str, event: dict[str, Any]) -> None:
        self._history[conversation_id].append(event)
        for queue in list(self._subscribers.get(conversation_id, set())):
            queue.put_nowait(event)

    def recent(self, conversation_id: str) -> list[dict[str, Any]]:
        return list(self._history.get(conversation_id, ()))

    def clear(self) -> None:
        self._history.clear()
        self._subscribers.clear()

    async def stream(self, conversation_id: str) -> AsyncGenerator[dict[str, Any], None]:
        replay_events = self.recent(conversation_id)
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers[conversation_id].add(queue)
        try:
            for event in replay_events:
                yield event

            while True:
                yield await queue.get()
        finally:
            self._subscribers[conversation_id].discard(queue)


route_event_bus = RouteDeckEventBus()
