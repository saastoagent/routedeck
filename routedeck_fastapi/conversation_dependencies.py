from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import Request

from routedeck_core.ports import RouteDeckAgentDriver

from .dependencies import RouteDeckDependencies, RouteDeckDependencyUnavailable


@dataclass(frozen=True)
class RouteDeckConversationDependencies:
    routedeck: RouteDeckDependencies
    agent: RouteDeckAgentDriver | None = None

    def __post_init__(self) -> None:
        if self.agent is not None and not isinstance(self.agent, RouteDeckAgentDriver):
            raise TypeError("RouteDeck conversation requires an agent driver")


ConversationDependencyProvider = Callable[
    [Request],
    RouteDeckConversationDependencies
    | Awaitable[RouteDeckConversationDependencies],
]


async def resolve_conversation_dependencies(
    provider: ConversationDependencyProvider,
    request: Request,
) -> RouteDeckConversationDependencies:
    value = provider(request)
    if inspect.isawaitable(value):
        value = await value
    if not isinstance(value, RouteDeckConversationDependencies):
        raise RouteDeckDependencyUnavailable(
            "RouteDeck conversation runtime is not configured"
        )
    return value


__all__ = [
    "ConversationDependencyProvider",
    "RouteDeckConversationDependencies",
    "resolve_conversation_dependencies",
]
