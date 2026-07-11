from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from ..contracts.events import CanonicalRouteDeckEvent


@runtime_checkable
class RouteDeckNotifier(Protocol):
    async def notify(
        self,
        session_id: str,
        events: Sequence[CanonicalRouteDeckEvent],
    ) -> None: ...


__all__ = ["RouteDeckNotifier"]
