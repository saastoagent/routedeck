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
    EntryTurnDeclaration,
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
    entry_turn_request_id,
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
    release: asyncio.Event = field(default_factory=asyncio.Event)

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
                await self.release.wait()
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
    request: pytest.FixtureRequest,
    tmp_path: Path,
    graphs: _ConversationGraphs,
) -> AsyncIterator[RouteDeckRuntime]:
    entry_turn = getattr(request, "param", None)
    node = Node(
        id="test.home",
        title="Conversation transport test",
        kind=NodeKind.SECTION,
        route=Route(
            template="/",
            deep_link_policy=DeepLinkPolicy.SHAREABLE,
        ),
        surfaces=SurfaceSlots(active=None),
        entry_turn=entry_turn,
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
        "assistant_delta",
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
    assert_canonical_failure(response, code="request_id_reused", phase="session_store")
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
    assert_canonical_failure(response, code="request_id_reused", phase="session_store")
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
    assert_canonical_failure(response, code="version_conflict", phase="session_store")
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


@pytest.mark.asyncio
async def test_conversation_run_is_idempotent_and_replays_monotonic_progress(
    client: httpx.AsyncClient,
    runtime: RouteDeckRuntime,
    graphs: _ConversationGraphs,
) -> None:
    started = await client.post(
        "/api/routedeck/conversation/runs",
        json={
            "request_id": "run-1",
            "expected_session_version": 1,
            "trigger": "assistant_initiated",
        },
    )

    assert started.status_code == 202
    assert started.json()["run"]["stage"] == "awaiting_model"
    for _ in range(100):
        status = await client.get("/api/routedeck/conversation/runs/run-1")
        assert status.status_code == 200
        if status.json()["run"]["stage"] == "completed":
            break
        await asyncio.sleep(0.01)
    else:
        pytest.fail("conversation run did not complete")

    attached = await client.post(
        "/api/routedeck/conversation/runs",
        json={
            "request_id": "run-1",
            "expected_session_version": 999,
            "trigger": "assistant_initiated",
        },
    )
    events = await client.get(
        "/api/routedeck/conversation/runs/run-1/events?after=0"
    )

    assert attached.status_code == 200
    assert attached.json()["run"]["stage"] == "completed"
    assert len(graphs.assistant.calls) == 1
    frames = sse_events(events.text)
    assert [frame["stage"] for frame in frames] == ["completed"]
    assert frames[0]["cursor"] == 9_007_199_254_740_991
    assert frames[0]["assistant_content"] == (
        "Hello from the assistant-initiated graph."
    )
    assert (runtime_session_id(client), "run-1") not in (
        runtime.conversation_runs._runs
    )


@pytest.mark.asyncio
async def test_conversation_run_subscriber_disconnect_does_not_cancel_execution(
    client: httpx.AsyncClient,
    runtime: RouteDeckRuntime,
    graphs: _ConversationGraphs,
) -> None:
    graphs.assistant.wait_forever = True
    coordinator = runtime.conversation_runs
    run = await coordinator.start_or_attach(
        session_id=runtime_session_id(client),
        request_id="detached-run",
        expected_session_version=1,
        trigger=AssistantInitiatedTrigger(),
    )
    assert run.stage.value == "awaiting_model"
    await graphs.assistant.started.wait()

    subscriber = coordinator.events(
        runtime_session_id(client),
        "detached-run",
        0,
        0.01,
    )
    await anext(subscriber)
    await subscriber.aclose()

    graphs.assistant.release.set()
    for _ in range(100):
        terminal = await coordinator.get(runtime_session_id(client), "detached-run")
        if terminal.terminal:
            break
        await asyncio.sleep(0.01)
    else:
        pytest.fail("detached conversation run did not complete")

    assert terminal.stage.value == "completed"
    assert len(graphs.assistant.calls) == 1


@pytest.mark.asyncio
async def test_user_run_disconnect_reconnects_by_cursor_and_projects_request_id(
    client: httpx.AsyncClient,
    runtime: RouteDeckRuntime,
    graphs: _ConversationGraphs,
) -> None:
    graphs.user.wait_forever = True
    started = await client.post(
        "/api/routedeck/conversation/runs",
        json={
            "request_id": "user-run",
            "expected_session_version": 1,
            "trigger": "user_message",
            "message": "Hello RouteDeck.",
        },
    )
    assert started.status_code == 202
    await graphs.user.started.wait()

    projection = (await client.get("/api/routedeck/session")).json()["projection"]
    assert projection["interaction"] == {
        "phase": "active",
        "owner": "chat",
        "request_id": "user-run",
    }
    session_id = runtime_session_id(client)
    subscriber = runtime.conversation_runs.events(
        session_id,
        "user-run",
        started.json()["run"]["cursor"],
        0.01,
    )
    heartbeat = await anext(subscriber)
    assert heartbeat is None
    reconnect_cursor = started.json()["run"]["cursor"]
    await subscriber.aclose()

    graphs.user.release.set()
    resumed = runtime.conversation_runs.events(
        session_id,
        "user-run",
        reconnect_cursor,
        0.01,
    )
    observed = [event async for event in resumed if event is not None]

    terminal = await runtime.conversation_runs.get(session_id, "user-run")
    assert (observed[-1].stage.value, terminal.stage.value, terminal.failure) == (
        "completed",
        "completed",
        None,
    ), ([(event.cursor, event.stage.value) for event in observed], terminal)
    assert [event.cursor for event in observed] == sorted(
        event.cursor for event in observed
    )
    assert len(graphs.user.calls) == 1
    snapshot = await runtime.services.store.load(session_id)
    assert [turn.role for turn in snapshot.state.conversation] == [
        ConversationRole.USER,
        ConversationRole.ASSISTANT,
    ]


@pytest.mark.parametrize(
    "runtime",
    [EntryTurnDeclaration(id="welcome")],
    indirect=True,
)
@pytest.mark.asyncio
async def test_declared_entry_turn_starts_on_session_creation_only_once(
    client: httpx.AsyncClient,
    runtime: RouteDeckRuntime,
    graphs: _ConversationGraphs,
) -> None:
    declaration = EntryTurnDeclaration(id="welcome")
    request_id = entry_turn_request_id("test.home", declaration)
    session_id = runtime_session_id(client)
    for _ in range(100):
        mutation = await runtime.services.store.find_mutation(session_id, request_id)
        if mutation is not None:
            break
        await asyncio.sleep(0.01)
    else:
        pytest.fail("declared entry turn did not complete")

    snapshot = await runtime.services.store.load(session_id)
    attached = await runtime.ensure_declared_entry_run(snapshot)

    assert attached is not None
    assert attached.stage.value == "completed"
    assert len(graphs.assistant.calls) == 1


@pytest.mark.parametrize(
    "runtime",
    [EntryTurnDeclaration(id="welcome")],
    indirect=True,
)
@pytest.mark.asyncio
async def test_session_creation_projects_durably_claimed_entry_run(
    client: httpx.AsyncClient,
    graphs: _ConversationGraphs,
) -> None:
    graphs.assistant.wait_forever = True
    created = await client.post(
        "/api/routedeck/sessions",
        json={"request_id": "create-session-with-active-entry"},
    )

    assert created.status_code == 201
    assert created.json()["projection"]["interaction"] == {
        "phase": "active",
        "owner": "chat",
        "request_id": entry_turn_request_id(
            "test.home", EntryTurnDeclaration(id="welcome")
        ),
    }
    graphs.assistant.release.set()


@pytest.mark.asyncio
async def test_interrupt_persistence_failure_is_loud_and_not_cached_as_terminal(
    client: httpx.AsyncClient,
    runtime: RouteDeckRuntime,
    graphs: _ConversationGraphs,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graphs.assistant.failure_after_delta = RuntimeError("private graph failure")

    async def fail_interrupt(*_args, **_kwargs):
        raise RuntimeError("persistence unavailable")

    monkeypatch.setattr(runtime.services.runner, "interrupt_turn", fail_interrupt)
    started = await client.post(
        "/api/routedeck/conversation/runs",
        json={
            "request_id": "interrupt-persistence-failed",
            "expected_session_version": 1,
            "trigger": "assistant_initiated",
        },
    )
    assert started.status_code == 202

    for _ in range(100):
        status = await client.get(
            "/api/routedeck/conversation/runs/interrupt-persistence-failed"
        )
        if status.status_code == 503:
            break
        await asyncio.sleep(0.01)
    else:
        pytest.fail("conversation persistence failure was not surfaced")

    assert status.json()["failure"]["code"] == "persistence_failure"
    assert await runtime.services.store.find_mutation(
        runtime_session_id(client), "interrupt-persistence-failed"
    ) is None


@pytest.mark.asyncio
async def test_durable_interruption_reloads_after_post_commit_failure(
    client: httpx.AsyncClient,
    runtime: RouteDeckRuntime,
    graphs: _ConversationGraphs,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graphs.assistant.failure_after_delta = RuntimeError("private graph failure")
    interrupt = runtime.services.runner.interrupt_turn

    async def commit_then_fail(*args, **kwargs):
        await interrupt(*args, **kwargs)
        raise RuntimeError("response path failed after commit")

    monkeypatch.setattr(runtime.services.runner, "interrupt_turn", commit_then_fail)
    started = await client.post(
        "/api/routedeck/conversation/runs",
        json={
            "request_id": "interrupt-committed",
            "expected_session_version": 1,
            "trigger": "assistant_initiated",
        },
    )
    assert started.status_code == 202

    session_id = runtime_session_id(client)
    for _ in range(100):
        mutation = await runtime.services.store.find_mutation(
            session_id, "interrupt-committed"
        )
        if mutation is not None:
            break
        await asyncio.sleep(0.01)
    else:
        pytest.fail("durable interruption did not commit")

    loaded = await client.get(
        "/api/routedeck/conversation/runs/interrupt-committed"
    )
    assert loaded.status_code == 200
    assert loaded.json()["run"]["stage"] == "interrupted"
    assert (session_id, "interrupt-committed") not in (
        runtime.conversation_runs._runs
    )
