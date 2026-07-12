from __future__ import annotations

from typing import NoReturn


class RouteDeckTopologyBuilderDeprecatedError(RuntimeError):
    """The legacy RouteDeck-to-LangGraph topology mirror is no longer supported."""


def build_route_deck_state_graph(*args: object, **kwargs: object) -> NoReturn:
    """Fail loudly for callers of the retired topology-generating adapter.

    The import remains available as a temporary migration signal. RouteDeck now
    integrates through ``RouteDeckMiddleware`` and ``RouteDeckToolWrapper``;
    callers keep ownership of their original LangGraph topology.
    """

    del args, kwargs
    raise RouteDeckTopologyBuilderDeprecatedError(
        "build_route_deck_state_graph() is deprecated and no longer builds or "
        "mutates LangGraph topology. Use RouteDeckMiddleware with create_agent(), "
        "or construct ToolNode(..., awrap_tool_call=RouteDeckToolWrapper(runtime)."
        "awrap_tool_call) for a raw StateGraph."
    )


__all__ = [
    "RouteDeckTopologyBuilderDeprecatedError",
    "build_route_deck_state_graph",
]
