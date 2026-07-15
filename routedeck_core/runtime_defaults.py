from __future__ import annotations

import asyncio
import secrets
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .contracts.events import RouteDeckEvent


class UtcClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


@dataclass
class InProcessEventNotifier:
    """Cursor-aware local wakeups backed by durable event replay."""

    _condition: asyncio.Condition = field(default_factory=asyncio.Condition)
    _latest_cursor: dict[str, int] = field(default_factory=dict)

    async def notify(
        self,
        session_id: str,
        events: Sequence[RouteDeckEvent],
    ) -> None:
        if not events:
            return
        latest = max(event.cursor for event in events)
        async with self._condition:
            self._latest_cursor[session_id] = max(
                latest,
                self._latest_cursor.get(session_id, 0),
            )
            self._condition.notify_all()

    async def wait_for_events(
        self,
        session_id: str,
        after_cursor: int,
        timeout: timedelta,
    ) -> bool:
        async with self._condition:
            if self._latest_cursor.get(session_id, 0) > after_cursor:
                return True
            try:
                await asyncio.wait_for(
                    self._condition.wait_for(
                        lambda: self._latest_cursor.get(session_id, 0)
                        > after_cursor
                    ),
                    timeout=timeout.total_seconds(),
                )
            except TimeoutError:
                return False
            return True


def _new_runtime_id(kind: str) -> str:
    if not kind:
        raise ValueError("RouteDeck runtime ID kind must be non-empty")
    return f"{kind}_{secrets.token_urlsafe(18)}"


__all__ = ["InProcessEventNotifier", "UtcClock"]
