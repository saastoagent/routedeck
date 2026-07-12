from __future__ import annotations

import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import MessagesState, StateGraph

from medusa_agent.agent import create_medusa_agent
from medusa_agent.medusa.client.models import CreateCartResult
from routedeck_core.contracts.operations import DeliveryPhase
from routedeck_langgraph import (
    RouteDeckMiddleware,
    RouteDeckToolConfigurationError,
    RouteDeckToolWrapper,
    operation_tool_name,
)
from routedeck_testing import ScriptedToolModel, tool_call
from support.medusa import RecordingMedusaStoreClient, buyer_market, cart
from support.runtime import build_test_medusa_runtime


def test_runner_tools_use_provider_safe_names_and_preserve_operation_ids() -> None:
    runtime = build_test_medusa_runtime(
        client=RecordingMedusaStoreClient(
            CreateCartResult(
                delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                cart=cart(),
            )
        ),
        market=buyer_market(),
    )
    wrapper = RouteDeckToolWrapper(runtime.runner)

    tool_names = tuple(tool.name for tool in wrapper.tools)
    assert len(tool_names) == len(set(tool_names))
    for tool in wrapper.tools:
        assert len(tool.name) <= 64
        assert all(
            character.isascii() and (character.isalnum() or character in {"_", "-"})
            for character in tool.name
        )
        operation_id = tool.metadata["routedeck_operation_id"]
        assert wrapper.operation_id_for_tool_name(tool.name) == operation_id


@pytest.mark.asyncio
async def test_model_context_allowed_tool_runner_result_and_raw_topology() -> None:
    client = RecordingMedusaStoreClient(
        CreateCartResult(
            delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
            cart=cart(),
        )
    )
    runtime = build_test_medusa_runtime(client=client, market=buyer_market())
    wrapper = RouteDeckToolWrapper(runtime.runner)

    raw_graph = StateGraph(MessagesState)
    raw_graph.add_node("agent", lambda state: state)
    raw_graph.set_entry_point("agent")
    topology_before = frozenset(raw_graph.edges)
    wrapper.tool_node()
    assert frozenset(raw_graph.edges) == topology_before

    model = ScriptedToolModel(
        [
            tool_call(
                operation_tool_name("cart.create"),
                {},
                call_id="cart-create-1",
            ),
            AIMessage(content="Cart ready."),
        ]
    )
    agent = create_medusa_agent(model=model, runtime=runtime)

    result = await agent.ainvoke(
        {"messages": [HumanMessage(content="Start a cart for me.")]},
        context={
            "session_id": "session-1",
            "request_id_prefix": "agent-contract",
        },
    )

    assert agent.middleware_types == (RouteDeckMiddleware,)
    assert len(model.calls) == 2
    assert set(model.calls[0].tool_names) == {
        operation_tool_name("catalog.open_product_by_route"),
        operation_tool_name("catalog.select_variant"),
        operation_tool_name("cart.create"),
        operation_tool_name("cart.add_item"),
        operation_tool_name("cart.open"),
    }
    assert operation_tool_name("catalog.list") not in model.calls[0].tool_names
    first_request = "\n".join(
        str(message.content) for message in model.calls[0].messages
    )
    assert '"current_node":"catalog.product"' in first_request
    assert "private-region-sentinel" not in first_request
    assert "private-channel-sentinel" not in first_request
    assert "private-cart-sentinel" not in first_request

    tool_messages = [
        message for message in result["messages"] if isinstance(message, ToolMessage)
    ]
    assert len(tool_messages) == 1
    tool_payload = json.loads(str(tool_messages[0].content))
    assert tool_payload["disposition"] == "completed"
    assert tool_payload["operation_id"] == "cart.create"
    assert tool_payload["outcome"] == "created"
    assert client.calls == ["create_cart"]


@pytest.mark.asyncio
async def test_agent_tool_execution_requires_explicit_session_context() -> None:
    client = RecordingMedusaStoreClient(
        CreateCartResult(
            delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
            cart=cart(),
        )
    )
    runtime = build_test_medusa_runtime(client=client, market=buyer_market())
    agent = create_medusa_agent(
        model=ScriptedToolModel(
            [
                tool_call(
                    operation_tool_name("cart.create"),
                    {},
                    call_id="cart-create-miswired",
                )
            ]
        ),
        runtime=runtime,
    )

    with pytest.raises(RouteDeckToolConfigurationError, match="session_id"):
        await agent.ainvoke(
            {"messages": [HumanMessage(content="Start a cart for me.")]}
        )

    assert client.calls == []


@pytest.mark.asyncio
async def test_agent_tool_execution_requires_explicit_parent_request_prefix() -> None:
    client = RecordingMedusaStoreClient(
        CreateCartResult(
            delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
            cart=cart(),
        )
    )
    runtime = build_test_medusa_runtime(client=client, market=buyer_market())
    agent = create_medusa_agent(
        model=ScriptedToolModel(
            [
                tool_call(
                    operation_tool_name("cart.create"),
                    {},
                    call_id="cart-create-miswired",
                )
            ]
        ),
        runtime=runtime,
    )

    with pytest.raises(RouteDeckToolConfigurationError, match="request_id_prefix"):
        await agent.ainvoke(
            {"messages": [HumanMessage(content="Start a cart for me.")]},
            context={"session_id": "session-1"},
        )

    assert client.calls == []
