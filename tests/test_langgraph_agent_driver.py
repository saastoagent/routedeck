from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from pydantic import SecretStr

from routedeck_core.contracts.conversation import (
    ConversationRole,
    FinalizedConversationTurn,
)
from routedeck_core.ports import (
    AgentTurnCompleted,
    AssistantInitiatedTrigger,
    AssistantTextDelta,
    RouteDeckAgentTurn,
    UserMessageTrigger,
)
from routedeck_core.state.leases import TurnLease
from routedeck_langgraph import (
    RouteDeckLangGraphAgentDriver,
    RouteDeckLangGraphGraphs,
)


EventFactory = Callable[
    [Mapping[str, Any]],
    AsyncIterator[Mapping[str, Any]],
]


@dataclass
class RecordingGraph:
    event_factory: EventFactory
    inputs: list[Mapping[str, Any]] = field(default_factory=list)

    def astream_events(
        self,
        input: Mapping[str, Any],
        config: Mapping[str, Any] | None = None,
        *,
        version: str = "v2",
        **kwargs: Any,
    ) -> AsyncIterator[Mapping[str, Any]]:
        del config
        assert version == "v2"
        self.inputs.append(input)
        return self.event_factory({"input": input, "kwargs": kwargs})


def _user_events(call: Mapping[str, Any]) -> AsyncIterator[Mapping[str, Any]]:
    async def events() -> AsyncIterator[Mapping[str, Any]]:
        user = call["input"]["messages"][0]
        assert isinstance(user, HumanMessage)
        assistant = AIMessage(content="Hello there.", id="assistant-user-1")
        yield {
            "event": "on_chat_model_stream",
            "run_id": "user-model",
            "data": {"chunk": AIMessageChunk(content="Hello there.")},
        }
        yield {
            "event": "on_chat_model_end",
            "run_id": "user-model",
            "data": {"output": assistant},
        }
        yield {
            "event": "on_chain_end",
            "data": {"output": {"messages": [user, assistant]}},
        }

    return events()


def _assistant_events(call: Mapping[str, Any]) -> AsyncIterator[Mapping[str, Any]]:
    async def events() -> AsyncIterator[Mapping[str, Any]]:
        assert call["input"] == {"messages": []}
        assistant = AIMessage(content="Hi — how can I help?", id="assistant-entry-1")
        yield {
            "event": "on_chat_model_stream",
            "run_id": "entry-model",
            "data": {"chunk": AIMessageChunk(content="Hi — how can I help?")},
        }
        yield {
            "event": "on_chat_model_end",
            "run_id": "entry-model",
            "data": {"output": assistant},
        }
        yield {
            "event": "on_chain_end",
            "data": {"output": {"messages": [assistant]}},
        }

    return events()


def _tagged_user_events(call: Mapping[str, Any]) -> AsyncIterator[Mapping[str, Any]]:
    async def events() -> AsyncIterator[Mapping[str, Any]]:
        user = call["input"]["messages"][0]
        policy = AIMessage(content="policy sentinel")
        yield {
            "event": "on_chat_model_stream",
            "run_id": "policy-model",
            "tags": ["product.policy"],
            "data": {"chunk": AIMessageChunk(content="policy sentinel")},
        }
        yield {
            "event": "on_chat_model_end",
            "run_id": "policy-model",
            "tags": ["product.policy"],
            "data": {"output": policy},
        }
        assistant = AIMessage(content="Visible answer.", id="assistant-visible")
        yield {
            "event": "on_chat_model_stream",
            "run_id": "visible-model",
            "data": {"chunk": AIMessageChunk(content="Visible answer.")},
        }
        yield {
            "event": "on_chat_model_end",
            "run_id": "visible-model",
            "data": {"output": assistant},
        }
        yield {
            "event": "on_chain_end",
            "data": {"output": {"messages": [user, assistant]}},
        }

    return events()


def _turn(trigger) -> RouteDeckAgentTurn:
    return RouteDeckAgentTurn(
        session_id="session-1",
        request_id="request-1",
        lease=TurnLease(
            capability=SecretStr("lease-capability"),
            fencing_token=1,
            session_id="session-1",
            request_id="request-1",
        ),
        trigger=trigger,
    )


def _user_trigger() -> UserMessageTrigger:
    return UserMessageTrigger(
        message="Hello",
        user_turn=FinalizedConversationTurn(
            turn_id="user-turn-1",
            role=ConversationRole.USER,
            content="Hello",
            request_id="request-1",
        ),
    )


@pytest.mark.asyncio
async def test_user_graph_streams_and_extracts_one_durable_suffix() -> None:
    trigger = _user_trigger()
    driver = RouteDeckLangGraphAgentDriver(
        graphs=RouteDeckLangGraphGraphs(
            user_message=RecordingGraph(_user_events),
            assistant_initiated=RecordingGraph(_assistant_events),
            ignored_event_tags=frozenset(),
        ),
        id_factory=lambda kind: f"{kind}-generated",
    )

    events = [event async for event in driver.stream(_turn(trigger))]

    assert [type(event) for event in events] == [
        AssistantTextDelta,
        AgentTurnCompleted,
    ]
    completed = events[-1]
    assert isinstance(completed, AgentTurnCompleted)
    assert [turn.role for turn in completed.turns] == [
        ConversationRole.USER,
        ConversationRole.ASSISTANT,
    ]
    assert len(completed.turns) == 2
    assert completed.turns[0] == trigger.user_turn


@pytest.mark.asyncio
async def test_assistant_graph_sends_no_user_marker_and_persists_only_assistant() -> None:
    assistant_graph = RecordingGraph(_assistant_events)
    driver = RouteDeckLangGraphAgentDriver(
        graphs=RouteDeckLangGraphGraphs(
            user_message=RecordingGraph(_user_events),
            assistant_initiated=assistant_graph,
            ignored_event_tags=frozenset(),
        ),
        id_factory=lambda kind: f"{kind}-generated",
    )

    events = [
        event
        async for event in driver.stream(_turn(AssistantInitiatedTrigger()))
    ]

    completed = events[-1]
    assert isinstance(completed, AgentTurnCompleted)
    assert [turn.role for turn in completed.turns] == [ConversationRole.ASSISTANT]
    assert assistant_graph.inputs == [{"messages": []}]
    assert all(
        not isinstance(message, HumanMessage)
        for graph_input in assistant_graph.inputs
        for message in graph_input["messages"]
    )


@pytest.mark.asyncio
async def test_ignored_product_event_tags_never_leak_model_text() -> None:
    driver = RouteDeckLangGraphAgentDriver(
        graphs=RouteDeckLangGraphGraphs(
            user_message=RecordingGraph(_tagged_user_events),
            assistant_initiated=RecordingGraph(_assistant_events),
            ignored_event_tags=frozenset({"product.policy"}),
        ),
        id_factory=lambda kind: f"{kind}-generated",
    )

    events = [event async for event in driver.stream(_turn(_user_trigger()))]

    assert all(
        not isinstance(event, AssistantTextDelta)
        or "policy sentinel" not in event.content
        for event in events
    )
