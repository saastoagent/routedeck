from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import replace
from typing import Any

import httpx
import pytest
from langchain_core.callbacks import AsyncCallbackManagerForLLMRun
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from langchain_core.outputs import ChatGenerationChunk

from main import create_medusa_app
from medusa_agent.agent import BUYER_AGENT_PROMPT, create_medusa_entry_agent
from medusa_agent.medusa.client.models import CreateCartResult
from routedeck_core.contracts.operations import DeliveryPhase
from routedeck_core.contracts.session import Location
from routedeck_langgraph import (
    RouteDeckLangGraphAgentDriver,
    RouteDeckLangGraphGraphs,
)
from routedeck_fastapi import GuestCookieSessionSelector, GuestCookieSettings
from routedeck_testing import ScriptedTextModel
from support.medusa import RecordingMedusaStoreClient, buyer_market, cart
from support.runtime import build_test_runtime


class _StreamingScriptedTextModel(ScriptedTextModel):
    async def _astream(
        self,
        messages,
        stop=None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        del stop, run_manager, kwargs
        message = self._result(messages).generations[0].message
        assert isinstance(message, AIMessage)
        yield ChatGenerationChunk(
            message=AIMessageChunk(content=message.content)
        )


@pytest.mark.asyncio
async def test_home_entry_persists_a_model_greeting_without_a_synthetic_user_message() -> None:
    runtime = build_test_runtime(
        client=RecordingMedusaStoreClient(
            CreateCartResult(
                delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                cart=cart(),
            )
        ),
        market=buyer_market(),
        initial_location=Location(node_id="buyer.home"),
    )
    model = _StreamingScriptedTextModel("Hi — what would you like to explore?")
    graph = create_medusa_entry_agent(model=model)
    driver = RouteDeckLangGraphAgentDriver(
        graphs=RouteDeckLangGraphGraphs(
            user_message=graph,
            assistant_initiated=graph,
            ignored_event_tags=frozenset(),
        ),
        id_factory=runtime.services.id_factory,
    )
    runtime = replace(runtime, agent_driver=driver)
    before_entry = await runtime.services.store.load("session-1")
    application = create_medusa_app(
        runtime=runtime,
        browser_origins=("http://testserver",),
        session_selector=GuestCookieSessionSelector(
            GuestCookieSettings(
                name="routedeck_guest",
                secure=False,
                path="/",
            )
        ),
    )

    try:
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            client.cookies.set("routedeck_guest", "session-1")
            response = await client.post(
                "/api/routedeck/conversation/assistant-turn",
                json={
                    "request_id": "entry-1",
                    "expected_session_version": before_entry.session_version,
                },
            )

        assert response.status_code == 200
        assert _sse_event_names(response.text) == [
            "stream_start",
            "conversation_snapshot",
            "assistant_delta",
            "assistant_end",
            "stream_end",
        ]
        completed = await runtime.services.store.load("session-1")
        assert [turn.role.value for turn in completed.state.conversation] == [
            "assistant"
        ]
        assert completed.state.conversation[0].content == (
            "Hi — what would you like to explore?"
        )
        assert not any(
            isinstance(message, HumanMessage) for message in model.calls[0].messages
        )
        assert BUYER_AGENT_PROMPT in str(model.calls[0].messages[0].content)
    finally:
        await runtime.close()


def _sse_event_names(body: str) -> list[str]:
    names: list[str] = []
    for frame in body.split("\n\n"):
        lines = frame.splitlines()
        event_lines = [line for line in lines if line.startswith("event: ")]
        data_lines = [line for line in lines if line.startswith("data: ")]
        if not event_lines and not data_lines:
            continue
        assert len(event_lines) == 1
        assert len(data_lines) == 1
        assert isinstance(json.loads(data_lines[0].removeprefix("data: ")), dict)
        names.append(event_lines[0].removeprefix("event: "))
    return names
