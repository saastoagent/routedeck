from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from medusa_agent.api.chat import (
    ChatStreamRequest,
    MedusaChatDependencies,
    _log_chat_failure,
    stream_agent_chat,
)
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


def test_chat_failure_logging_excludes_exception_message_and_traceback(caplog) -> None:
    secret = "private-cart-id-must-not-enter-logs"

    with caplog.at_level(logging.ERROR, logger="medusa_agent.api.chat"):
        _log_chat_failure(
            "medusa_chat_stream_failed",
            request_id="chat-safe-log",
            error=RuntimeError(secret),
        )

    records = [
        record
        for record in caplog.records
        if record.getMessage() == "medusa_chat_stream_failed error_type=RuntimeError"
    ]
    assert len(records) == 1
    record = records[0]
    assert record.exc_info is None
    assert getattr(record, "request_id") == "chat-safe-log"
    assert getattr(record, "error_type") == "RuntimeError"
    assert secret not in caplog.text


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
    dependencies = MedusaChatDependencies(
        routedeck=SimpleNamespace(runner=runner, store=store),  # type: ignore[arg-type]
        agent=_FailingAgent(),
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
