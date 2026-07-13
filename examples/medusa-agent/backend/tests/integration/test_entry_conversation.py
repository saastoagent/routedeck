from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

from medusa_agent.agent import BUYER_AGENT_PROMPT, create_medusa_entry_agent
from medusa_agent.entry_conversation import start_home_conversation
from medusa_agent.medusa.client.models import CreateCartResult
from routedeck_core.contracts.operations import DeliveryPhase
from routedeck_core.contracts.session import Location
from routedeck_testing import ScriptedTextModel
from support.medusa import RecordingMedusaStoreClient, buyer_market, cart
from support.runtime import build_test_medusa_runtime


@pytest.mark.asyncio
async def test_home_entry_persists_a_model_greeting_without_a_synthetic_user_message() -> None:
    runtime = build_test_medusa_runtime(
        client=RecordingMedusaStoreClient(
            CreateCartResult(
                delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                cart=cart(),
            )
        ),
        market=buyer_market(),
        initial_location=Location(node_id="buyer.home"),
    )
    model = ScriptedTextModel("Hi — what would you like to explore?")
    agent = create_medusa_entry_agent(model=model)

    completed = await start_home_conversation(
        runner=runtime.runner,
        store=runtime.store,
        agent=agent,
        session_id="session-1",
        request_id="entry-1",
        expected_session_version=runtime.store.session.session_version,
    )

    assert [turn.role.value for turn in completed.state.conversation] == [
        "assistant"
    ]
    assert completed.state.conversation[0].content == "Hi — what would you like to explore?"
    assert not any(
        isinstance(message, HumanMessage) for message in model.calls[0].messages
    )
    assert BUYER_AGENT_PROMPT in str(model.calls[0].messages[0].content)
