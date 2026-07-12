from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from ..contracts.events import CanonicalRouteDeckEvent


_LOGGER = logging.getLogger(__name__)


@runtime_checkable
class RouteDeckNotifier(Protocol):
    async def notify(
        self,
        session_id: str,
        events: Sequence[CanonicalRouteDeckEvent],
    ) -> None: ...


async def notify_event_wakeup(
    notifier: RouteDeckNotifier,
    session_id: str,
    events: Sequence[CanonicalRouteDeckEvent],
) -> None:
    """Wake local followers without making delivery part of the durable commit."""

    try:
        await notifier.notify(session_id, events)
    except Exception as error:
        _LOGGER.error(
            "RouteDeck event wakeup failed; durable event replay remains authoritative",
            extra={
                "error_type": type(error).__name__,
                "event_count": len(events),
            },
        )


__all__ = ["RouteDeckNotifier", "notify_event_wakeup"]
