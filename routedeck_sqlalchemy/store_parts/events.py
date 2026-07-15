from __future__ import annotations

from routedeck_core.contracts.events import EventPage

from ..sessions import SessionRepository
from .lifecycle import _StoreLifecycle


class _EventTransactions:
    def __init__(
        self,
        *,
        lifecycle: _StoreLifecycle,
        sessions: SessionRepository,
    ) -> None:
        self._lifecycle = lifecycle
        self._sessions = sessions

    async def events_after(
        self,
        session_id: str,
        cursor: int,
        limit: int,
    ) -> EventPage:
        if cursor < 0:
            raise ValueError("event cursor must be non-negative")
        if limit <= 0 or limit > 1_000:
            raise ValueError("event page limit must be between 1 and 1000")
        return await self._lifecycle.read(
            lambda database, now: self._sessions.events_after(
                database,
                session_id=session_id,
                cursor=cursor,
                limit=limit,
                now=now,
            )
        )
