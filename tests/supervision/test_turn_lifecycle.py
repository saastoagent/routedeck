from __future__ import annotations

import asyncio

import pytest
from pydantic import SecretStr

from routedeck_core.contracts.conversation import (
    ConversationRole,
    ConversationTurnStatus,
    FinalizedConversationTurn,
)
from routedeck_core.contracts.failures import FailureKind, RouteDeckFailure
from routedeck_core.contracts.operations import OperationRequest, OperationSource
from routedeck_core.state.leases import TurnClaim, TurnLease, TurnOwnerKind
from routedeck_core.ports.session_store import SessionStoreError, SessionStoreErrorCode


class FailingNotifier:
    async def notify(self, session_id, events) -> None:
        del session_id, events
        raise RuntimeError("wakeup unavailable")


def chat_claim(
    *, request_id: str = "turn-1", expected_session_version: int = 1
) -> TurnClaim:
    return TurnClaim(
        session_id="session-1",
        expected_session_version=expected_session_version,
        request_id=request_id,
        request_fingerprint=f"fingerprint:{request_id}",
        owner_kind=TurnOwnerKind.CHAT,
    )


def tool_request(*, request_id: str, expected_session_version: int) -> OperationRequest:
    return OperationRequest(
        session_id="session-1",
        request_id=request_id,
        expected_session_version=expected_session_version,
        operation_id="test.write",
        source=OperationSource.AGENT,
        arguments={"quantity": 2},
    )


def finalized_turns(
    request_id: str = "turn-1",
) -> tuple[FinalizedConversationTurn, ...]:
    return (
        FinalizedConversationTurn(
            turn_id="user-turn-1",
            role=ConversationRole.USER,
            content="hello",
            request_id=request_id,
        ),
        FinalizedConversationTurn(
            turn_id="assistant-turn-1",
            role=ConversationRole.ASSISTANT,
            content="welcome",
            request_id=request_id,
        ),
    )


@pytest.mark.asyncio
async def test_chat_turn_projects_authoritative_interaction_ownership_until_completion(
    runner,
    store,
) -> None:
    turn = await runner.begin_turn(chat_claim(request_id="turn-visible"))

    active = (await store.load("session-1")).state.model_dump(mode="json")
    assert active.get("interaction") == {
        "phase": "active",
        "owner": "chat",
    }

    completed = await runner.complete_turn(
        turn,
        expected_session_version=active["session_version"],
        turns=finalized_turns("turn-visible"),
    )
    assert completed.state.model_dump(mode="json").get("interaction") == {
        "phase": "idle",
        "owner": None,
    }


@pytest.mark.asyncio
async def test_agent_child_attempts_share_one_serial_parent_turn_lease(
    runner,
    store,
) -> None:
    turn = await runner.begin_turn(chat_claim())

    first = await runner.run(
        tool_request(request_id="tool-1", expected_session_version=2),
        turn=turn,
    )
    second = await runner.run(
        tool_request(
            request_id="tool-2", expected_session_version=first.session_version
        ),
        turn=turn,
    )
    snapshot = await runner.complete_turn(
        turn,
        expected_session_version=second.session_version,
        turns=finalized_turns(),
    )

    assert store.turn_claim_counts["turn-1"] == 1
    assert store.child_attempts["turn-1"] == ["tool-1", "tool-2"]
    assert [turn.status for turn in snapshot.state.conversation] == [
        ConversationTurnStatus.FINALIZED,
        ConversationTurnStatus.FINALIZED,
    ]
    assert store.active_turn("turn-1") is None


@pytest.mark.asyncio
async def test_model_only_turn_finalizes_and_releases_lease(runner, store) -> None:
    turn = await runner.begin_turn(chat_claim(request_id="turn-text"))

    snapshot = await runner.complete_turn(
        turn,
        expected_session_version=2,
        turns=finalized_turns("turn-text"),
    )

    assert snapshot.state.conversation[-1].content == "welcome"
    assert store.active_turn("turn-text") is None


@pytest.mark.asyncio
async def test_finalized_turn_survives_notifier_failure(
    runner_factory,
    store,
    caplog,
) -> None:
    runner = runner_factory(notifier=FailingNotifier())
    turn = await runner.begin_turn(chat_claim(request_id="turn-notify"))

    snapshot = await runner.complete_turn(
        turn,
        expected_session_version=2,
        turns=finalized_turns("turn-notify"),
    )

    assert snapshot.state.conversation[-1].content == "welcome"
    assert store.active_turn("turn-notify") is None
    assert "RouteDeck event wakeup failed" in caplog.text


@pytest.mark.asyncio
async def test_interrupted_turn_persists_no_partial_assistant_content(
    runner,
    store,
) -> None:
    turn = await runner.begin_turn(chat_claim(request_id="turn-crash"))
    failure = RouteDeckFailure(
        kind=FailureKind.INTERNAL,
        code="turn_interrupted",
        phase="model_turn",
        correlation_id="safe-correlation",
        request_id="turn-crash",
        public_message="The turn was interrupted.",
    )

    snapshot = await runner.interrupt_turn(
        turn,
        expected_session_version=2,
        failure=failure,
    )

    assert snapshot.state.conversation[-1].status is ConversationTurnStatus.INTERRUPTED
    assert snapshot.state.conversation[-1].content == ""
    assert "partial assistant sentinel" not in snapshot.state.model_dump_json()
    assert store.active_turn("turn-crash") is None


@pytest.mark.asyncio
async def test_forged_parent_turn_is_rejected_before_provider_invocation(
    runner,
    provider,
) -> None:
    real = await runner.begin_turn(chat_claim())
    forged = TurnLease(
        capability=SecretStr("forged-turn-capability"),
        fencing_token=real.fencing_token,
        session_id=real.session_id,
        request_id=real.request_id,
    )

    result = await runner.run(
        tool_request(request_id="forged-tool", expected_session_version=2),
        turn=forged,
    )

    assert result.failure.code in {"persistence_failure", "operation_in_progress"}
    assert provider.calls == []


@pytest.mark.asyncio
async def test_child_request_identity_is_bound_to_parent_turn(runner) -> None:
    first_turn = await runner.begin_turn(chat_claim(request_id="turn-1"))
    first = await runner.run(
        tool_request(request_id="tool-shared", expected_session_version=2),
        turn=first_turn,
    )
    await runner.complete_turn(
        first_turn,
        expected_session_version=first.session_version,
        turns=finalized_turns(),
    )
    second_turn = await runner.begin_turn(
        chat_claim(
            request_id="turn-2",
            expected_session_version=first.session_version + 1,
        )
    )

    reused = await runner.run(
        tool_request(
            request_id="tool-shared",
            expected_session_version=first.session_version + 2,
        ),
        turn=second_turn,
    )

    assert reused.failure.code == "request_id_reused"


@pytest.mark.asyncio
async def test_finalized_content_cannot_be_attached_to_another_turn(runner) -> None:
    turn = await runner.begin_turn(chat_claim(request_id="turn-owned"))

    with pytest.raises(ValueError, match="another turn"):
        await runner.complete_turn(
            turn,
            expected_session_version=2,
            turns=finalized_turns("turn-forged"),
        )


@pytest.mark.asyncio
async def test_begin_turn_rejects_non_chat_owner_and_stale_version(runner) -> None:
    review_claim = chat_claim().model_copy(update={"owner_kind": TurnOwnerKind.REVIEW})

    with pytest.raises(ValueError, match="chat turn claim"):
        await runner.begin_turn(review_claim)
    with pytest.raises(SessionStoreError) as stale:
        await runner.begin_turn(chat_claim(expected_session_version=0))

    assert stale.value.code is SessionStoreErrorCode.VERSION_CONFLICT


@pytest.mark.asyncio
async def test_complete_turn_rejects_empty_and_unfinalized_content(runner) -> None:
    from routedeck_core.contracts.conversation import ConversationTurn

    turn = await runner.begin_turn(chat_claim(request_id="turn-content-validation"))

    with pytest.raises(ValueError, match="finalized conversation turns"):
        await runner.complete_turn(turn, expected_session_version=2, turns=())
    with pytest.raises(ValueError, match="finalized conversation turns"):
        await runner.complete_turn(
            turn,
            expected_session_version=2,
            turns=(
                ConversationTurn(
                    turn_id="draft-turn",
                    role=ConversationRole.ASSISTANT,
                    content="not finalized",
                    request_id="turn-content-validation",
                    status=ConversationTurnStatus.INTERRUPTED,
                ),
            ),
        )


@pytest.mark.asyncio
async def test_interrupt_turn_rejects_failure_from_another_request(runner) -> None:
    turn = await runner.begin_turn(chat_claim(request_id="turn-owned-failure"))
    foreign_failure = RouteDeckFailure(
        kind=FailureKind.INTERNAL,
        code="turn_interrupted",
        phase="model_turn",
        correlation_id="safe-correlation",
        request_id="different-turn",
        public_message="The turn was interrupted.",
    )

    with pytest.raises(ValueError, match="another request"):
        await runner.interrupt_turn(
            turn,
            expected_session_version=2,
            failure=foreign_failure,
        )


@pytest.mark.asyncio
async def test_concurrent_child_writes_allow_only_one_executor_crossing(
    runner,
    handlers,
    executor,
) -> None:
    turn = await runner.begin_turn(chat_claim())
    started = asyncio.Event()
    release = asyncio.Event()
    handlers["test.write"].started_event = started
    handlers["test.write"].release_event = release

    first_task = asyncio.create_task(
        runner.run(
            tool_request(request_id="tool-first", expected_session_version=2),
            turn=turn,
        )
    )
    await started.wait()
    second = await runner.run(
        tool_request(request_id="tool-second", expected_session_version=2),
        turn=turn,
    )
    release.set()
    first = await first_task

    assert first.disposition.value == "completed"
    assert second.failure.code == "operation_in_progress"
    assert executor.call_count("test.write") == 1


@pytest.mark.asyncio
async def test_turn_cannot_finalize_or_interrupt_with_active_child(
    runner,
    handlers,
) -> None:
    turn = await runner.begin_turn(chat_claim())
    started = asyncio.Event()
    release = asyncio.Event()
    handlers["test.write"].started_event = started
    handlers["test.write"].release_event = release
    child_task = asyncio.create_task(
        runner.run(
            tool_request(request_id="tool-active", expected_session_version=2),
            turn=turn,
        )
    )
    await started.wait()
    failure = RouteDeckFailure(
        kind=FailureKind.INTERNAL,
        code="turn_interrupted",
        phase="model_turn",
        correlation_id="safe-correlation",
        request_id="turn-1",
        public_message="The turn was interrupted.",
    )

    with pytest.raises(SessionStoreError) as complete_error:
        await runner.complete_turn(
            turn,
            expected_session_version=2,
            turns=finalized_turns(),
        )
    with pytest.raises(SessionStoreError) as interrupt_error:
        await runner.interrupt_turn(
            turn,
            expected_session_version=2,
            failure=failure,
        )
    assert complete_error.value.code is SessionStoreErrorCode.OPERATION_IN_PROGRESS
    assert interrupt_error.value.code is SessionStoreErrorCode.OPERATION_IN_PROGRESS
    release.set()
    await child_task
