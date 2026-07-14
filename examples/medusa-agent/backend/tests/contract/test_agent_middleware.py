from __future__ import annotations

import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import MessagesState, StateGraph
from pydantic import SecretStr

from medusa_agent.agent import (
    BUYER_AGENT_PROMPT,
    _create_live_entry_model,
    create_medusa_agent,
)
from medusa_agent.config import Settings
from medusa_agent.features.checkout.feature import PROTECTED_CHECKOUT_INPUT_POLICY
from medusa_agent.medusa.client.models import CreateCartResult
from routedeck_core.contracts.operations import DeliveryPhase
from routedeck_core.context.framework_policies import RouteDeckAgentPolicyType
from routedeck_langgraph import (
    RouteDeckMiddleware,
    RouteDeckToolConfigurationError,
    RouteDeckToolWrapper,
    build_model_context,
    operation_tool_name,
)
from routedeck_testing import ScriptedTextModel, ScriptedToolModel, tool_call
from routedeck_testing.factories import session_factory
from support.medusa import RecordingMedusaStoreClient, buyer_market, cart
from support.runtime import build_test_medusa_runtime


def test_live_entry_model_omits_the_tool_only_parallel_call_option(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class RecordingChatOpenAI:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    monkeypatch.setattr("medusa_agent.agent.ChatOpenAI", RecordingChatOpenAI)

    _create_live_entry_model(
        settings=Settings(
            medusa_base_url="http://medusa.test",
            medusa_publishable_key=SecretStr("publishable-key"),
            medusa_region_id="region-1",
            medusa_country_code="gb",
            medusa_sales_channel_id="channel-1",
            medusa_payment_provider_id="pp_system_default",
            routedeck_database_url="sqlite+pysqlite:///routedeck.sqlite",
            routedeck_state_encryption_key=SecretStr("encryption-key"),
            openai_api_key=SecretStr("openai-key"),
            openai_buyer_model="buyer-model",
            openai_entry_model="entry-model",
            openai_turn_policy_model="policy-model",
        )
    )

    assert "model_kwargs" not in captured
    assert captured["model"] == "entry-model"


def test_buyer_prompt_keeps_product_identity_while_framework_rules_are_resolved() -> None:
    assert 'starts with "Hi"' in BUYER_AGENT_PROMPT
    assert "Use only the tools listed" not in BUYER_AGENT_PROMPT
    assert "An operation being legal" not in BUYER_AGENT_PROMPT
    assert "Direct the buyer to the rendered protected contact form" not in (
        BUYER_AGENT_PROMPT
    )

    bound_app = build_test_medusa_runtime(
        client=RecordingMedusaStoreClient(
            CreateCartResult(
                delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                cart=cart(),
            )
        ),
        market=buyer_market(),
    ).runner.app
    context = build_model_context(
        session_factory(app=bound_app.app, node_id="checkout.contact"),
        bound_app,
    )
    policy_ids = tuple(policy.policy_id for policy in context.policies)

    assert RouteDeckAgentPolicyType.EXECUTION_AUTHORITY in policy_ids
    assert PROTECTED_CHECKOUT_INPUT_POLICY.id in policy_ids
    assert "Direct the buyer to the rendered protected contact form" in (
        PROTECTED_CHECKOUT_INPUT_POLICY.instruction
    )


class _ConversationTurnPolicy:
    async def decide(self, _messages) -> str:
        return "conversation"


class _ActionTurnPolicy:
    async def decide(self, _messages) -> str:
        return "action"


@pytest.mark.asyncio
async def test_conversation_turn_policy_hides_all_commerce_tools() -> None:
    client = RecordingMedusaStoreClient(
        CreateCartResult(
            delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
            cart=cart(),
        )
    )
    runtime = build_test_medusa_runtime(client=client, market=buyer_market())
    model = ScriptedTextModel("Hello. How can I help?")
    agent = create_medusa_agent(
        model=model,
        runtime=runtime,
        turn_policy=_ConversationTurnPolicy(),
    )

    result = await agent.ainvoke(
        {"messages": [HumanMessage(content="Hello")]},
        context={
            "session_id": "session-1",
            "request_id_prefix": "conversation-policy",
        },
    )

    assert model.calls[0].tool_names == ()
    assert result["messages"][-1].content == "Hello. How can I help?"
    assert client.calls == []
    assert "Do not enumerate, request, restate, accept, or summarize" not in (
        BUYER_AGENT_PROMPT
    )


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
    agent = create_medusa_agent(
        model=model,
        runtime=runtime,
        turn_policy=_ActionTurnPolicy(),
    )

    result = await agent.ainvoke(
        {"messages": [HumanMessage(content="Start a cart for me.")]},
        context={
            "session_id": "session-1",
            "request_id_prefix": "agent-contract",
        },
    )

    assert agent.middleware_types[0] is RouteDeckMiddleware
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
    assert "RouteDeck resolved policies (trusted instructions):" in first_request
    assert RouteDeckAgentPolicyType.INTENT_AUTHORITY in first_request
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
        turn_policy=_ActionTurnPolicy(),
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
        turn_policy=_ActionTurnPolicy(),
    )

    with pytest.raises(RouteDeckToolConfigurationError, match="request_id_prefix"):
        await agent.ainvoke(
            {"messages": [HumanMessage(content="Start a cart for me.")]},
            context={"session_id": "session-1"},
        )

    assert client.calls == []
