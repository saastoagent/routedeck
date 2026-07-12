from __future__ import annotations

from langchain_core.messages import AIMessage

from medusa_agent.agent import create_medusa_agent
from medusa_agent.composition import MedusaRuntime
from routedeck_langgraph import operation_tool_name
from routedeck_testing import ScriptedToolModel, tool_call


def create_scripted_test_agent(*, runtime: MedusaRuntime) -> object:
    """Build the bounded script used only by the local browser release gate."""

    model = ScriptedToolModel(
        (
            tool_call(
                operation_tool_name("catalog.list"),
                {},
                call_id="release-scripted-catalog-list",
            ),
            AIMessage(content="The available products are open."),
        )
    )
    return create_medusa_agent(model=model, runtime=runtime)


__all__ = ["create_scripted_test_agent"]
