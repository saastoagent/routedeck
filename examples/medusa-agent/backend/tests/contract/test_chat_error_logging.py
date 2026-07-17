from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from itertools import count

import pytest
from pydantic import SecretStr

from medusa_agent.composition import compile_medusa_app
from medusa_agent.session import BuyerMarket, create_medusa_session
from routedeck_core.contracts.conversation import (
    ConversationRole,
    FinalizedConversationTurn,
)
from routedeck_core.contracts.session import SessionSnapshot
from routedeck_core.ports import (
    AgentTurnCompleted,
    AssistantTextDelta,
    RouteDeckAgentEvent,
    RouteDeckAgentTurn,
    UserMessageTrigger,
)
from routedeck_core.state.leases import TurnLease
from routedeck_fastapi import (
    ConversationTurnRequest,
    RouteDeckDependencies,
    SseSettings,
    stream_agent_turn,
)
from routedeck_fastapi.conversation_stream import _log_failure


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


class _FailingDriver:
    async def stream(
        self,
        turn: RouteDeckAgentTurn,
    ) -> AsyncIterator[RouteDeckAgentEvent]:
        del turn
        raise RuntimeError("model stream unavailable")
        yield AssistantTextDelta("unreachable")


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


class _StreamingDriver:
    async def stream(
        self,
        turn: RouteDeckAgentTurn,
    ) -> AsyncIterator[RouteDeckAgentEvent]:
        assert isinstance(turn.trigger, UserMessageTrigger)
        yield AssistantTextDelta("Hello ")
        yield AssistantTextDelta("there.")
        assistant = FinalizedConversationTurn(
            turn_id="assistant-stream",
            role=ConversationRole.ASSISTANT,
            content="Hello there.",
            request_id=turn.request_id,
        )
        yield AgentTurnCompleted(
            turns=(turn.trigger.user_turn, assistant),
            assistant_turn_id=assistant.turn_id,
        )


def test_chat_failure_logging_excludes_exception_message_and_traceback(caplog) -> None:
    secret = "private-cart-id-must-not-enter-logs"

    with caplog.at_level(
        logging.ERROR,
        logger="routedeck_fastapi.conversation_stream",
    ):
        _log_failure(
            "routedeck_conversation_stream_failed",
            request_id="chat-safe-log",
            error=RuntimeError(secret),
        )

    records = [
        record
        for record in caplog.records
        if record.getMessage()
        == "routedeck_conversation_stream_failed error_type=RuntimeError"
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
    app = compile_medusa_app()
    session = create_medusa_session(
        app=app,
        session_id="session-live-assistant-stream",
        market=buyer_market,
    )
    snapshot = SessionSnapshot(state=session)
    store = _StreamingStore(snapshot)
    runner = _StreamingRunner(store)
    dependencies = RouteDeckDependencies(
        app=app,
        runner=runner,  # type: ignore[arg-type]
        store=store,  # type: ignore[arg-type]
        notifier=object(),  # type: ignore[arg-type]
        projector=object(),  # type: ignore[arg-type]
        private_form_codec=object(),  # type: ignore[arg-type]
        session_factory=lambda _session_id: session,
        agent_driver=_StreamingDriver(),
        sse=SseSettings(follow=False),
    )
    request_id = "chat-live-assistant-stream"
    stream = stream_agent_turn(
        dependencies=dependencies,
        session_id=session.session_id,
        request=ConversationTurnRequest(
            request_id=request_id,
            expected_session_version=session.session_version,
            trigger=UserMessageTrigger(
                message="Hello",
                user_turn=FinalizedConversationTurn(
                    turn_id="user-live-assistant-stream",
                    role=ConversationRole.USER,
                    content="Hello",
                    request_id=request_id,
                ),
            ),
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
    app = compile_medusa_app()
    session = create_medusa_session(
        app=app,
        session_id="session-chat-interrupt-failure",
        market=buyer_market,
    )
    snapshot = SessionSnapshot(state=session)
    store = _FailingInterruptStore(snapshot)
    runner = _FailingInterruptRunner(store)
    dependencies = RouteDeckDependencies(
        app=app,
        runner=runner,  # type: ignore[arg-type]
        store=store,  # type: ignore[arg-type]
        notifier=object(),  # type: ignore[arg-type]
        projector=object(),  # type: ignore[arg-type]
        private_form_codec=object(),  # type: ignore[arg-type]
        session_factory=lambda _session_id: session,
        agent_driver=_FailingDriver(),
        sse=SseSettings(follow=False),
    )
    request_id = "chat-interrupt-failure"

    frames = [
        frame
        async for frame in stream_agent_turn(
            dependencies=dependencies,
            session_id=session.session_id,
            request=ConversationTurnRequest(
                request_id=request_id,
                expected_session_version=session.session_version,
                trigger=UserMessageTrigger(
                    message="Hello",
                    user_turn=FinalizedConversationTurn(
                        turn_id="user-interrupt-failure",
                        role=ConversationRole.USER,
                        content="Hello",
                        request_id=request_id,
                    ),
                ),
            ),
            initial_snapshot=snapshot,
        )
    ]
    body = "".join(frames)

    assert "event: chat_error" not in body
    assert '"status":"outcome_unknown"' in body
