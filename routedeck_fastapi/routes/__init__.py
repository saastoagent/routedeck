"""Internal route factories for the canonical RouteDeck FastAPI router."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request

from ..dependencies import RouteDeckDependencies


DependencyProvider = Callable[
    [Request],
    RouteDeckDependencies | Awaitable[RouteDeckDependencies],
]


__all__: list[str] = []
