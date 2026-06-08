from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from routedeck_core import RouteDeckEvent

from core.config import Settings
from services.agent_tools import build_agent_tools
from services.routedeck_provider import get_routedeck_runtime
from services.routedeck_runtime import MedusaRouteDeckRuntime


COMMERCE_SYSTEM_PROMPT = """\
You are the Medusa demo shopping assistant.

Respond like a normal commerce assistant helping a shopper browse demo products,
choose sizes, compare colors, and clarify what they want. Keep replies concise
and friendly. Do not expose framework internals, debug details, private product
ids, credentials, or developer terminology.
"""


def build_agent_graph(
    settings: Settings,
    session_id: str = "default",
    runtime: MedusaRouteDeckRuntime | None = None,
    route_event_sink: Callable[[RouteDeckEvent], None] | None = None,
):
    llm = ChatOpenAI(
        model=settings.medusa_agent_model,
        api_key=settings.openai_api_key,
        streaming=True,
        temperature=0.3,
    )
    route_runtime = runtime or get_routedeck_runtime(settings=settings)
    tools = build_agent_tools(runtime=route_runtime, session_id=session_id, event_sink=route_event_sink)
    llm_with_tools = llm.bind_tools(tools)

    def agent_node(state: MessagesState) -> dict[str, Any]:
        messages = [SystemMessage(content=COMMERCE_SYSTEM_PROMPT), *state["messages"]]
        return {"messages": [llm_with_tools.invoke(messages)]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(tools))
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")
    return graph.compile(checkpointer=InMemorySaver())
