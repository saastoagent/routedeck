"""Reusable async action dispatch mechanics for RouteDeck runtimes."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar


StateT = TypeVar("StateT")
MessageT = TypeVar("MessageT")
ContextT = TypeVar("ContextT")


@dataclass(slots=True)
class RouteDeckActionResult(Generic[StateT, MessageT]):
    state: StateT
    messages: list[MessageT] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)


RouteDeckActionHandler = Callable[
    [StateT, Mapping[str, Any], ContextT],
    Awaitable[RouteDeckActionResult[StateT, MessageT]],
]
RouteDeckDefaultActionHandler = Callable[
    [str, StateT, Mapping[str, Any], ContextT],
    Awaitable[RouteDeckActionResult[StateT, MessageT]],
]


class RouteDeckActionDispatcher(Generic[StateT, MessageT, ContextT]):
    """Dispatches operation ids to explicit handlers with optional fallback."""

    def __init__(
        self,
        handlers: Mapping[str, RouteDeckActionHandler[StateT, MessageT, ContextT]] | None = None,
        *,
        default_handler: RouteDeckDefaultActionHandler[StateT, MessageT, ContextT] | None = None,
    ) -> None:
        self._handlers = dict(handlers or {})
        self._default_handler = default_handler

    def has_handler(self, action_id: str) -> bool:
        return action_id in self._handlers

    async def dispatch(
        self,
        action_id: str,
        *,
        state: StateT,
        payload: Mapping[str, Any],
        context: ContextT,
    ) -> RouteDeckActionResult[StateT, MessageT]:
        handler = self._handlers.get(action_id)
        if handler is not None:
            return await handler(state, payload, context)
        if self._default_handler is None:
            raise KeyError(action_id)
        return await self._default_handler(action_id, state, payload, context)
