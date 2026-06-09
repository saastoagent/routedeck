from __future__ import annotations

from typing import Any

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, MessagesState, StateGraph

from core.config import Settings


COMMERCE_SYSTEM_PROMPT = """\
You are the Medusa demo shopping assistant.

Respond like a normal commerce assistant helping a shopper browse demo products,
choose sizes, compare colors, and clarify what they want. Keep replies concise
and friendly. Keep replies to two or three short sentences unless the shopper
asks for deeper detail. Do not expose framework internals, debug details,
private product ids, credentials, or developer terminology.
"""


def build_agent_graph(settings: Settings):
    llm = ChatOpenAI(
        model=settings.medusa_agent_model,
        api_key=settings.openai_api_key,
        streaming=True,
        timeout=settings.model_timeout_seconds,
        temperature=0.3,
    )

    async def agent_node(state: MessagesState) -> dict[str, Any]:
        messages = [SystemMessage(content=COMMERCE_SYSTEM_PROMPT), *state["messages"]]
        return {"messages": [await llm.ainvoke(messages)]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent_node)
    graph.set_entry_point("agent")
    graph.add_edge("agent", END)
    return graph.compile(checkpointer=InMemorySaver())
