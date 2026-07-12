from .conversation import (
    ExtractedConversation,
    extract_conversation_turns,
    messages_from_agent_state,
)
from .middleware import RouteDeckMiddleware
from .model_context import (
    ModelContextEntity,
    ModelContextObservation,
    ModelContextStatus,
    ModelContextSurface,
    ModelContextTool,
    ModelContextValue,
    RouteDeckModelContext,
    build_model_context,
    reconstruct_messages,
)
from .tool_wrapper import (
    RouteDeckInvocationContext,
    RouteDeckRunnerRuntime,
    RouteDeckToolConfigurationError,
    RouteDeckToolWrapper,
    awrap_tool_call,
    operation_tool_name,
)


_COMPATIBILITY_EXPORTS = {
    "RouteDeckTopologyBuilderDeprecatedError": (
        ".graph",
        "RouteDeckTopologyBuilderDeprecatedError",
    ),
    "TransitionDiagnostics": (".transition", "TransitionDiagnostics"),
    "assert_route_transition": (".transition", "assert_route_transition"),
    "build_route_deck_state_graph": (".graph", "build_route_deck_state_graph"),
    "matching_route_deck_edge": (".transition", "matching_route_deck_edge"),
    "validate_langgraph_contract": (".validation", "validate_langgraph_contract"),
}


def __getattr__(name: str) -> object:
    """Resolve retired topology/parity APIs for explicit compatibility imports.

    These names are intentionally absent from ``__all__``. Corpus still imports
    some of them directly while it migrates, so resolution stays lazy and
    compatibility-only instead of advertising the retired topology model.
    """

    target = _COMPATIBILITY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = target
    from importlib import import_module

    value = getattr(import_module(module_name, __name__), attribute_name)
    globals()[name] = value
    return value


__all__ = [
    "ExtractedConversation",
    "ModelContextEntity",
    "ModelContextObservation",
    "ModelContextStatus",
    "ModelContextSurface",
    "ModelContextTool",
    "ModelContextValue",
    "RouteDeckInvocationContext",
    "RouteDeckMiddleware",
    "RouteDeckModelContext",
    "RouteDeckRunnerRuntime",
    "RouteDeckToolConfigurationError",
    "RouteDeckToolWrapper",
    "awrap_tool_call",
    "build_model_context",
    "extract_conversation_turns",
    "messages_from_agent_state",
    "operation_tool_name",
    "reconstruct_messages",
]
