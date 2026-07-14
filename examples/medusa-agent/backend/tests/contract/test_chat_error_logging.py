from __future__ import annotations

import logging
from itertools import count
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk
from pydantic import SecretStr

from medusa_agent.agent_driver import MedusaLangGraphAgentDriver
from routedeck_fastapi import (
    ChatStreamRequest,
    RouteDeckConversationDependencies,
    stream_agent_chat,
)
from routedeck_fastapi.conversation_stream import _log_failure
from medusa_agent.session import BuyerMarket, create_medusa_session
from routedeck_core.contracts.session import SessionSnapshot
from routedeck_core.state.leases import TurnLease


class _FailingInterruptStore:
    def __init__(self, snapshot: SessionSnapshot) -> None:
        self.snapshot = snapshot

    async def load(self, session_id: str) -> SessionSnapshot:
        assert session_id == self.snapshot.session_id
        return self.snapshot


class _FailingInterruptRunner:
    def __init__(self, store: _FailingInterruptStore) -> None:
        self.store = store

    def id_factory(self, kind: str) -> str:
        return f"{kind}-chat-failure"

    async def begin_turn(self, claim) -> TurnLease:
        return TurnLease(
            capability=SecretStr("turn-capability"),
            fencing_token=1,
            session_id=claim.session_id,
            request_id=claim.request_id,
        )

    async def interrupt_turn(self, *args, **kwargs):
        del args, kwargs
        raise RuntimeError("interruption persistence unavailable")


class _FailingAgent:
    def astream_events(self, *args, **kwargs):
        del args, kwargs

        async def events():
            raise RuntimeError("model stream unavailable")
            yield {}

        return events()


class _StreamingStore:
    def __init__(self, snapshot: SessionSnapshot) -> None:
        self.snapshot = snapshot

    async def load(self, session_id: str) -> SessionSnapshot:
        assert session_id == self.snapshot.session_id
        return self.snapshot


class _StreamingRunner:
    def __init__(self, store: _StreamingStore) -> None:
        self.store = store
        self.complete_calls = 0
        self._ids = count(1)

    def id_factory(self, kind: str) -> str:
        return f"{kind}-stream-{next(self._ids)}"

    async def begin_turn(self, claim) -> TurnLease:
        return TurnLease(
            capability=SecretStr("turn-capability"),
            fencing_token=1,
            session_id=claim.session_id,
            request_id=claim.request_id,
        )

    async def complete_turn(self, *args, **kwargs) -> SessionSnapshot:
        del args, kwargs
        self.complete_calls += 1
        return self.store.snapshot

    async def interrupt_turn(self, *args, **kwargs) -> SessionSnapshot:
        del args, kwargs
        return self.store.snapshot


class _StreamingAgent:
    def astream_events(self, input, *args, **kwargs):
        del args, kwargs
        user_message = input["messages"][0]

        async def events():
            policy_run_id = "turn-policy-model-run"
            policy_output = AIMessage(content='{"mode":"conversation"}')
            yield {
                "event": "on_chat_model_stream",
                "run_id": policy_run_id,
                "tags": ["medusa.turn_policy"],
                "data": {
                    "chunk": AIMessageChunk(content='{"mode":"conversation"}')
                },
            }
            yield {
                "event": "on_chat_model_end",
                "run_id": policy_run_id,
                "tags": ["medusa.turn_policy"],
                "data": {"output": policy_output},
            }
            run_id = "direct-response-model-run"
            yield {
                "event": "on_chat_model_stream",
                "run_id": run_id,
                "data": {"chunk": AIMessageChunk(content="Hello ")},
            }
            yield {
                "event": "on_chat_model_stream",
                "run_id": run_id,
                "data": {"chunk": AIMessageChunk(content="there.")},
            }
            assistant = AIMessage(content="Hello there.", id="assistant-stream")
            yield {
                "event": "on_chat_model_end",
                "run_id": run_id,
                "data": {"output": assistant},
            }
            yield {
                "event": "on_chain_end",
                "data": {"output": {"messages": [user_message, assistant]}},
            }

        return events()


def test_chat_failure_logging_excludes_exception_message_and_traceback(caplog) -> None:
    secret = "private-cart-id-must-not-enter-logs"

    with caplog.at_level(logging.ERROR, logger="routedeck_fastapi.conversation"):
        _log_failure(
            "routedeck_chat_stream_failed",
            request_id="chat-safe-log",
            error=RuntimeError(secret),
        )

    records = [
        record
        for record in caplog.records
        if record.getMessage()
        == "routedeck_chat_stream_failed error_type=RuntimeError"
    ]
    assert len(records) == 1
    record = records[0]
    assert record.exc_info is None
    assert getattr(record, "request_id") == "chat-safe-log"
    assert getattr(record, "error_type") == "RuntimeError"
    assert secret not in caplog.text


@pytest.mark.asyncio
async def test_assistant_delta_is_emitted_before_the_turn_is_committed(
    buyer_market: BuyerMarket,
) -> None:
    session = create_medusa_session(
        session_id="session-live-assistant-stream",
        market=buyer_market,
    )
    snapshot = SessionSnapshot(state=session)
    store = _StreamingStore(snapshot)
    runner = _StreamingRunner(store)
    dependencies = RouteDeckConversationDependencies(
        routedeck=SimpleNamespace(runner=runner, store=store),  # type: ignore[arg-type]
        agent=MedusaLangGraphAgentDriver(agent=_StreamingAgent(), runner=runner),  # type: ignore[arg-type]
    )
    stream = stream_agent_chat(
        dependencies=dependencies,
        session_id=session.session_id,
        request=ChatStreamRequest(
            request_id="chat-live-assistant-stream",
            expected_session_version=session.session_version,
            message="Hello",
        ),
        initial_snapshot=snapshot,
    )

    frames = [await anext(stream) for _ in range(4)]

    assert frames[-1].startswith("event: assistant_delta\n")
    assert '"content":"Hello "' in frames[-1]
    assert runner.complete_calls == 0

    remaining = [frame async for frame in stream]
    assert any(frame.startswith("event: assistant_end\n") for frame in remaining)
    assert runner.complete_calls == 1


@pytest.mark.asyncio
async def test_interrupt_persistence_failure_is_reported_as_outcome_unknown(
    buyer_market: BuyerMarket,
) -> None:
    session = create_medusa_session(
        session_id="session-chat-interrupt-failure",
        market=buyer_market,
    )
    snapshot = SessionSnapshot(state=session)
    store = _FailingInterruptStore(snapshot)
    runner = _FailingInterruptRunner(store)
    dependencies = RouteDeckConversationDependencies(
        routedeck=SimpleNamespace(runner=runner, store=store),  # type: ignore[arg-type]
        agent=MedusaLangGraphAgentDriver(agent=_FailingAgent(), runner=runner),  # type: ignore[arg-type]
    )

    frames = [
        frame
        async for frame in stream_agent_chat(
            dependencies=dependencies,
            session_id=session.session_id,
            request=ChatStreamRequest(
                request_id="chat-interrupt-failure",
                expected_session_version=session.session_version,
                message="Hello",
            ),
            initial_snapshot=snapshot,
        )
    ]
    body = "".join(frames)

    assert "event: chat_error" not in body
    assert '"status":"outcome_unknown"' in body
