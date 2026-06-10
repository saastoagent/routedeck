from __future__ import annotations

from typing import Any

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from core.config import Settings
from services.agent_tools import MEDUSA_AGENT_TOOLS


COMMERCE_SYSTEM_PROMPT = """\
You are the Medusa demo shopping assistant.

Respond like a normal commerce assistant helping a shopper browse demo products,
choose sizes, compare colors, and clarify what they want. Keep replies concise
and friendly. Keep replies to two or three short sentences unless the shopper
asks for deeper detail.

This slice is read-only: you can explain products, compare options, and help the
shopper decide what to do next, but you cannot change cart state or claim that
cart contents changed. If the shopper asks for a cart change, say this preview
does not render cart controls yet, then offer comparison, sizing, or color help.
Do not offer cart steps, cart instructions, or button names in this slice.
Do not offer cart actions or adding items as a next step in this slice.
If the shopper has not explicitly asked about cart, do not mention cart at all.

Do not expose framework internals, debug details, private product ids,
credentials, or developer terminology.

When the shopper asks to see the current catalog, products, or product list,
call `open_medusa_surface` with `surface_id="browse.product_list"` before
answering. Use the tool result's `product_facts` as the source of product
facts. Do not say the surface has no products when `product_facts` lists
products. Do not call a surface tool for product-detail or cart requests in this
slice.
"""


def build_agent_graph(settings: Settings):
    llm = ChatOpenAI(
        model=settings.medusa_agent_model,
        api_key=settings.openai_api_key,
        streaming=True,
        timeout=settings.model_timeout_seconds,
        temperature=0.3,
    ).bind_tools(MEDUSA_AGENT_TOOLS)

    async def agent_node(state: MessagesState) -> dict[str, Any]:
        messages = [SystemMessage(content=COMMERCE_SYSTEM_PROMPT), *state["messages"]]
        return {"messages": [await llm.ainvoke(messages)]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(MEDUSA_AGENT_TOOLS))
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")
    return graph.compile(checkpointer=InMemorySaver())
