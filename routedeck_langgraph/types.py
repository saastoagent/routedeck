from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Protocol

from routedeck_core import RouteDeckEdgeSpec


class RouteDeckState(Protocol):
    def get(self, key: str, default: Any = None) -> Any: ...


ConditionResolver = Callable[[RouteDeckEdgeSpec, Mapping[str, Any]], bool]
ConditionResolvers = Mapping[str, ConditionResolver]
HandlerMap = Mapping[str, Callable[..., Any]]
GroupMap = Mapping[str, set[str] | list[str] | tuple[str, ...]]
