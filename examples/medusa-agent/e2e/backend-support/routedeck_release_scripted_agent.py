from __future__ import annotations

from langchain_core.messages import AIMessage

from medusa_agent.agent import create_medusa_agent, create_medusa_entry_agent
from routedeck_core import RouteDeckRuntimeServices
from routedeck_langgraph import RouteDeckInvocationTraceRecorder, RouteDeckLangGraphGraphs, operation_tool_name
from routedeck_testing import ScriptedTextModel, ScriptedToolModel, tool_call


def create_scripted_test_graphs(
    *,
    runtime: RouteDeckRuntimeServices,
    invocation_traces: RouteDeckInvocationTraceRecorder,
) -> RouteDeckLangGraphGraphs:
    """Build the complete graph set used only by the local browser release gate."""

    user_message = create_medusa_agent(
        model=ScriptedToolModel(
            (
                tool_call(
                    operation_tool_name("catalog.list"),
                    {},
                    call_id="release-scripted-catalog-list",
                ),
                AIMessage(content="The available products are open."),
            )
        ),
        runtime=runtime,
        invocation_traces=invocation_traces,
    )
    assistant_initiated = create_medusa_entry_agent(
        model=ScriptedTextModel("Hi \N{EM DASH} how can I help you shop today?"),
        runtime=runtime,
        invocation_traces=invocation_traces,
    )
    return RouteDeckLangGraphGraphs(
        user_message=user_message,
        assistant_initiated=assistant_initiated,
        ignored_event_tags=frozenset(),
    )


__all__ = ["create_scripted_test_graphs"]
