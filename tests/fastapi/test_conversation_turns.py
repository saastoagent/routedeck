from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from itertools import count
from pathlib import Path
from typing import Any

import httpx
import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from fastapi import FastAPI, Request
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage

from routedeck_core.app import (
    Application,
    FeatureBindings,
    Feature,
    bind_app,
    compile_app,
)
from routedeck_core.contracts.application import Node
from routedeck_core.contracts.conversation import (
    ConversationRole,
    ConversationTurnStatus,
)
from routedeck_core.contracts.mutations import MutationStatus
from routedeck_core.contracts.navigation import DeepLinkPolicy, NodeKind, Route
from routedeck_core.contracts.session import PrivateSessionState, SessionSnapshot
from routedeck_core.contracts.surfaces import SurfaceSlots
from routedeck_core.ports import AssistantInitiatedTrigger
from routedeck_core.runtime import RouteDeckRuntime
from routedeck_core.state import create_session
from routedeck_fastapi import (
    ConversationTurnRequest,
    GuestCookieSessionSelector,
    GuestCookieSettings,
    SseSettings,
    create_routedeck_router_from_runtime_provider,
    dependencies_from_runtime,
    stream_agent_turn,
)
from routedeck_langgraph import (
    RouteDeckLangGraphDriverFactory,
    RouteDeckLangGraphGraphs,
)
from routedeck_sqlalchemy import (
    SqlAlchemyRuntimeResources,
    open_sqlalchemy_routedeck_runtime,
)


def _guest_selector() -> GuestCookieSessionSelector:
    return GuestCookieSessionSelector(
        GuestCookieSettings(
            name="routedeck_guest",
            secure=False,
            path="/",
        )
    )


@dataclass
class _ScriptedGraph:
    content: str
    calls: list[Mapping[str, Any]] = field(default_factory=list)
    failure_after_delta: BaseException | None = None
    wait_forever: bool = False
    started: asyncio.Event = field(default_factory=asyncio.Event)
    closed: asyncio.Event = field(default_factory=asyncio.Event)

    async def astream_events(
        self,
        input: Mapping[str, Any],
        config: Mapping[str, Any] | None = None,
        *,
        version: str = "v2",
        **kwargs: Any,
    ) -> AsyncIterator[Mapping[str, Any]]:
        del config, kwargs
        assert version == "v2"
        self.calls.append(input)
        self.started.set()
        try:
            if self.wait_forever:
                await asyncio.Event().wait()
            incoming = input.get("messages")
            assert isinstance(incoming, list)
            assert all(isinstance(message, BaseMessage) for message in incoming)
            assistant = AIMessage(
                content=self.content,
                id=f"assistant-{len(self.calls)}",
            )
            yield {
                "event": "on_chat_model_stream",
                "run_id": f"model-{len(self.calls)}",
                "data": {"chunk": AIMessageChunk(content=self.content)},
            }
            if self.failure_after_delta is not None:
                raise self.failure_after_delta
            yield {
                "event": "on_chat_model_end",
                "run_id": f"model-{len(self.calls)}",
                "data": {"output": assistant},
            }
            yield {
                "event": "on_chain_end",
                "data": {"output": {"messages": [*incoming, assistant]}},
            }
        finally:
            self.closed.set()


@dataclass(frozen=True)
class _ConversationGraphs:
    user: _ScriptedGraph
    assistant: _ScriptedGraph


@pytest.fixture
def graphs() -> _ConversationGraphs:
    return _ConversationGraphs(
        user=_ScriptedGraph("Hello from the user-message graph."),
        assistant=_ScriptedGraph("Hello from the assistant-initiated graph."),
    )


@pytest_asyncio.fixture
async def runtime(
    tmp_path: Path,
    graphs: _ConversationGraphs,
) -> AsyncIterator[RouteDeckRuntime]:
    node = Node(
        id="test.home",
        title="Conversation transport test",
        kind=NodeKind.SECTION,
        route=Route(
            template="/",
            deep_link_policy=DeepLinkPolicy.SHAREABLE,
        ),
        surfaces=SurfaceSlots(active=None),
    )
    compiled = compile_app(
        Application(
            name="conversation-transport-test",
            entry_node=node.ref,
            features=(Feature(namespace="test", nodes=(node,)),),
        )
    )
    bindings = FeatureBindings(handlers={}, providers={}, guards={})
    ids = count(1)

    def application_factory(_resources: SqlAlchemyRuntimeResources):
        return bind_app(compiled, bindings)

    def graph_factory(_services):
        return RouteDeckLangGraphGraphs(
            user_message=graphs.user,
            assistant_initiated=graphs.assistant,
            ignored_event_tags=frozenset(),
        )

    async def keep_created_session(
        _services,
        snapshot: SessionSnapshot,
    ) -> SessionSnapshot:
        return snapshot

    opened = await open_sqlalchemy_routedeck_runtime(
        compiled_app=compiled,
        application_factory=application_factory,
        session_factory=lambda app, session_id: create_session(
            app=app,
            session_id=session_id,
            private_state=PrivateSessionState(),
        ),
        session_initializer=keep_created_session,
        public_key_validator_factory=lambda _session: None,
        agent_driver_factory=RouteDeckLangGraphDriverFactory(
            graph_factory=graph_factory
        ),
        database_url=(
            "sqlite+pysqlite:///"
            f"{(tmp_path / 'conversation.sqlite').as_posix()}"
        ),
        encryption_key=Fernet.generate_key(),
        instance_id="conversation-fastapi-test",
        id_factory=lambda kind: f"{kind}-{next(ids)}",
        review_ttl=timedelta(minutes=5),
        resume_capability_ttl=timedelta(hours=1),
    )
    try:
        yield opened
    finally:
        await opened.close()


@pytest_asyncio.fixture
async def client(runtime: RouteDeckRuntime) -> AsyncIterator[httpx.AsyncClient]:
    application = FastAPI()

    async def runtime_provider(_request: Request) -> RouteDeckRuntime:
        return runtime

    application.include_router(
        create_routedeck_router_from_runtime_provider(
            runtime_provider,
            session_selector=_guest_selector(),
            sse=SseSettings(follow=False),
        )
    )
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://routedeck.test",
    ) as http_client:
        created = await http_client.post(
            "/api/routedeck/sessions",
            json={"request_id": "create-conversation-session"},
        )
        assert created.status_code == 201
        yield http_client


def sse_events(body: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for frame in body.replace("\r\n", "\n").split("\n\n"):
        lines = [line for line in frame.splitlines() if line]
        if not lines:
            continue
        event_lines = [line for line in lines if line.startswith("event: ")]
        data_lines = [line for line in lines if line.startswith("data: ")]
        assert len(event_lines) == 1
        assert len(data_lines) == 1
        payload = json.loads(data_lines[0].removeprefix("data: "))
        assert isinstance(payload, dict)
        events.append(
            {
                "event": event_lines[0].removeprefix("event: "),
                **payload,
            }
        )
    return events


def runtime_session_id(client: httpx.AsyncClient) -> str:
    session_id = client.cookies.get("routedeck_guest")
    assert isinstance(session_id, str) and session_id
    return session_id


def assert_canonical_failure(
    response: httpx.Response,
    *,
    code: str,
    kind: str = "state_conflict",
    phase: str = "conversation_turn",
) -> None:
    failure = response.json()["failure"]
    assert failure["kind"] == kind
    assert failure["code"] == code
    assert failure["phase"] == phase
    assert isinstance(failure["correlation_id"], str)
    assert failure["correlation_id"]
    assert isinstance(failure["public_message"], str)
    assert "message" not in failure


async def post_completed_chat(
    client: httpx.AsyncClient,
    *,
    request_id: str,
    expected_session_version: int = 1,
) -> httpx.Response:
    response = await client.post(
        "/api/routedeck/chat",
        json={
            "request_id": request_id,
            "expected_session_version": expected_session_version,
            "message": "Hello RouteDeck.",
        },
    )
    assert response.status_code == 200
    assert sse_events(response.text)[-1] == {
        "event": "stream_end",
        "request_id": request_id,
        "status": "completed",
    }
    return response


async def post_assistant_turn(
    client: httpx.AsyncClient,
    *,
    request_id: str,
    expected_session_version: int = 1,
) -> httpx.Response:
    return await client.post(
        "/api/routedeck/conversation/assistant-turn",
        json={
            "request_id": request_id,
            "expected_session_version": expected_session_version,
        },
    )


@pytest.mark.asyncio
async def test_assistant_turn_persists_without_a_user_message(
    client: httpx.AsyncClient,
    runtime: RouteDeckRuntime,
) -> None:
    response = await post_assistant_turn(client, request_id="entry-1")

    assert response.status_code == 200
    assert [event["event"] for event in sse_events(response.text)] == [
        "stream_start",
        "conversation_snapshot",
        "assistant_delta",
        "assistant_end",
        "stream_end",
    ]
    snapshot = await runtime.services.store.load(runtime_session_id(client))
    assert [turn.role for turn in snapshot.state.conversation] == [
        ConversationRole.ASSISTANT
    ]
    assert all(turn.content for turn in snapshot.state.conversation)


@pytest.mark.asyncio
async def test_assistant_turn_exact_replay_does_not_invoke_graph(
    client: httpx.AsyncClient,
    graphs: _ConversationGraphs,
) -> None:
    first = await post_assistant_turn(client, request_id="entry-replay")
    assert first.status_code == 200
    assert len(graphs.assistant.calls) == 1

    replay = await post_assistant_turn(
        client,
        request_id="entry-replay",
        expected_session_version=999,
    )

    assert replay.status_code == 200
    assert len(graphs.assistant.calls) == 1
    assert [event["event"] for event in sse_events(replay.text)] == [
        "stream_start",
        "conversation_snapshot",
        "assistant_end",
        "stream_end",
    ]


@pytest.mark.asyncio
async def test_chat_request_id_cannot_be_reused_for_assistant_turn(
    client: httpx.AsyncClient,
    graphs: _ConversationGraphs,
) -> None:
    await post_completed_chat(client, request_id="shared-id")

    response = await post_assistant_turn(client, request_id="shared-id")

    assert response.status_code == 409
    assert_canonical_failure(response, code="request_id_reused")
    assert graphs.assistant.calls == []


@pytest.mark.asyncio
async def test_assistant_request_id_cannot_be_reused_for_chat(
    client: httpx.AsyncClient,
    graphs: _ConversationGraphs,
) -> None:
    first = await post_assistant_turn(client, request_id="shared-id")
    assert first.status_code == 200

    response = await client.post(
        "/api/routedeck/chat",
        json={
            "request_id": "shared-id",
            "expected_session_version": 1,
            "message": "Hello RouteDeck.",
        },
    )

    assert response.status_code == 409
    assert_canonical_failure(response, code="request_id_reused")
    assert graphs.user.calls == []


@pytest.mark.asyncio
async def test_stale_assistant_turn_version_is_rejected_before_graph(
    client: httpx.AsyncClient,
    runtime: RouteDeckRuntime,
    graphs: _ConversationGraphs,
) -> None:
    response = await post_assistant_turn(
        client,
        request_id="entry-stale",
        expected_session_version=0,
    )

    assert response.status_code == 409
    assert_canonical_failure(response, code="version_conflict")
    assert graphs.assistant.calls == []
    snapshot = await runtime.services.store.load(runtime_session_id(client))
    assert snapshot.state.conversation == ()


@pytest.mark.asyncio
async def test_missing_conversation_session_uses_canonical_failure_envelope(
    client: httpx.AsyncClient,
) -> None:
    client.cookies.clear()

    response = await client.get("/api/routedeck/conversation")

    assert response.status_code == 404
    assert_canonical_failure(
        response,
        code="session_not_found",
        kind="contract",
        phase="http_transport",
    )


@pytest.mark.asyncio
async def test_assistant_stream_failure_is_interrupted_and_replayable(
    client: httpx.AsyncClient,
    runtime: RouteDeckRuntime,
    graphs: _ConversationGraphs,
) -> None:
    graphs.assistant.failure_after_delta = RuntimeError("private graph failure")

    failed = await post_assistant_turn(client, request_id="entry-failure")

    assert failed.status_code == 200
    failed_events = sse_events(failed.text)
    assert [event["event"] for event in failed_events] == [
        "stream_start",
        "conversation_snapshot",
        "assistant_delta",
        "chat_error",
        "stream_end",
    ]
    assert failed_events[-1]["status"] == "turn_interrupted"
    session_id = runtime_session_id(client)
    snapshot = await runtime.services.store.load(session_id)
    assert len(snapshot.state.conversation) == 1
    interrupted = snapshot.state.conversation[0]
    assert interrupted.role is ConversationRole.ASSISTANT
    assert interrupted.status is ConversationTurnStatus.INTERRUPTED
    assert interrupted.content == ""
    mutation = await runtime.services.store.find_mutation(
        session_id,
        "entry-failure",
    )
    assert mutation is not None
    assert mutation.status is MutationStatus.TURN_INTERRUPTED

    replay = await post_assistant_turn(
        client,
        request_id="entry-failure",
        expected_session_version=999,
    )

    assert replay.status_code == 200
    assert len(graphs.assistant.calls) == 1
    assert [event["event"] for event in sse_events(replay.text)] == [
        "stream_start",
        "conversation_snapshot",
        "chat_error",
        "stream_end",
    ]


@pytest.mark.asyncio
async def test_cancellation_closes_graph_and_shields_interruption_persistence(
    client: httpx.AsyncClient,
    runtime: RouteDeckRuntime,
    graphs: _ConversationGraphs,
) -> None:
    graphs.assistant.wait_forever = True
    session_id = runtime_session_id(client)
    dependencies = dependencies_from_runtime(
        runtime,
        session_selector=_guest_selector(),
        sse=SseSettings(follow=False),
    )
    initial = await runtime.services.store.load(session_id)
    stream = stream_agent_turn(
        dependencies=dependencies,
        session_id=session_id,
        request=ConversationTurnRequest(
            request_id="entry-cancelled",
            expected_session_version=initial.session_version,
            trigger=AssistantInitiatedTrigger(),
        ),
        initial_snapshot=initial,
    )
    assert "event: stream_start" in await anext(stream)
    assert "event: conversation_snapshot" in await anext(stream)
    pending = asyncio.create_task(anext(stream))
    await graphs.assistant.started.wait()

    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending

    assert graphs.assistant.closed.is_set()
    mutation = await runtime.services.store.find_mutation(
        session_id,
        "entry-cancelled",
    )
    assert mutation is not None
    assert mutation.status is MutationStatus.TURN_INTERRUPTED
    snapshot = await runtime.services.store.load(session_id)
    assert snapshot.state.conversation[-1].status is (
        ConversationTurnStatus.INTERRUPTED
    )


@pytest.mark.asyncio
async def test_concurrent_assistant_turn_preserves_typed_store_conflict(
    client: httpx.AsyncClient,
    runtime: RouteDeckRuntime,
    graphs: _ConversationGraphs,
) -> None:
    graphs.assistant.wait_forever = True
    session_id = runtime_session_id(client)
    dependencies = dependencies_from_runtime(
        runtime,
        session_selector=_guest_selector(),
        sse=SseSettings(follow=False),
    )
    initial = await runtime.services.store.load(session_id)
    first = stream_agent_turn(
        dependencies=dependencies,
        session_id=session_id,
        request=ConversationTurnRequest(
            request_id="medusa.initial-greeting.v1",
            expected_session_version=initial.session_version,
            trigger=AssistantInitiatedTrigger(),
        ),
        initial_snapshot=initial,
    )
    assert "event: stream_start" in await anext(first)
    assert "event: conversation_snapshot" in await anext(first)
    first_pending = asyncio.create_task(anext(first))
    await graphs.assistant.started.wait()

    current = await runtime.services.store.load(session_id)
    second = stream_agent_turn(
        dependencies=dependencies,
        session_id=session_id,
        request=ConversationTurnRequest(
            request_id="medusa.initial-greeting.v1",
            expected_session_version=current.session_version,
            trigger=AssistantInitiatedTrigger(),
        ),
        initial_snapshot=current,
    )
    second_events: list[dict[str, object]] = []
    async for frame in second:
        second_events.extend(sse_events(frame))

    assert second_events == [
        {
            "event": "chat_error",
            "code": "operation_in_progress",
            "message": "The RouteDeck session request could not be completed.",
        },
        {
            "event": "stream_end",
            "request_id": "medusa.initial-greeting.v1",
            "status": "rejected",
        },
    ]
    assert len(graphs.assistant.calls) == 1

    first_pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first_pending
