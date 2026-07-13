from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ..contracts.session import Location


IdFactory = Callable[[str], str]


@dataclass(frozen=True)
class RouteEntryInvocation:
    """Structurally matched route entry passed to the supervised operation path."""

    location: Location


__all__ = ["IdFactory", "RouteEntryInvocation"]
