from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import timedelta

import pytest

from routedeck_core.app.bindings import BoundRouteDeckApp
from routedeck_core.contracts.operations import (
    OperationDisposition,
    OperationRequest,
    OperationSource,
)
from routedeck_core.contracts.session import ReviewResolution
from routedeck_core.state.leases import TurnClaim, TurnOwnerKind


class FailingNotifier:
    async def notify(self, session_id, events) -> None:
        del session_id, events
        raise RuntimeError("wakeup unavailable")


def reviewed_request(
    *,
    request_id: str = "proposal-1",
    expected_session_version: int = 1,
    quantity: int = 2,
) -> OperationRequest:
    return OperationRequest(
        session_id="session-1",
        request_id=request_id,
        expected_session_version=expected_session_version,
        operation_id="test.reviewed_write",
        source=OperationSource.SURFACE,
        arguments={"quantity": quantity},
    )


@pytest.mark.asyncio
async def test_review_staging_freezes_arguments_authority_and_releases_lease(
    runner,
    store,
    executor,
) -> None:
    proposed = await runner.run(reviewed_request())
    persisted = await store.find_review("session-1", proposed.review.id)

    assert proposed.disposition is OperationDisposition.REQUIRES_REVIEW
    assert proposed.review is not None
    assert persisted is not None
    assert persisted.resolution is ReviewResolution.PENDING
    assert persisted.attempt.arguments[0].name == "quantity"
    assert persisted.attempt.arguments[0].value.to_python() == 2
    assert persisted.operation_spec_version.startswith("rdopspec1:")
    assert persisted.authoritative_context_fingerprint
    assert executor.calls == []
    assert store.active_turn("proposal-1") is None


@pytest.mark.asyncio
async def test_staged_review_survives_notifier_failure(
    runner_factory,
    store,
    caplog,
) -> None:
    runner = runner_factory(notifier=FailingNotifier())

    proposed = await runner.run(reviewed_request())
    persisted = await store.find_review("session-1", proposed.review.id)

    assert proposed.disposition is OperationDisposition.REQUIRES_REVIEW
    assert persisted is not None
    assert "RouteDeck event wakeup failed" in caplog.text


@pytest.mark.asyncio
async def test_review_acceptance_executes_frozen_arguments_exactly_once(
    runner,
    store,
    handlers,
    executor,
) -> None:
    proposed = await runner.run(reviewed_request(quantity=3))

    completed = await runner.accept_review(
        proposed.review.id,
        request_id="approve-1",
        expected_session_version=proposed.session_version,
    )
    replay_with_new_request = await runner.accept_review(
        proposed.review.id,
        request_id="approve-2",
        expected_session_version=completed.session_version,
    )

    assert completed.disposition is OperationDisposition.COMPLETED
    assert handlers["test.reviewed_write"].calls[0][0] == {"quantity": 3}
    assert executor.call_count("test.reviewed_write") == 1
    assert replay_with_new_request.failure.code == "review_already_resolved"
    persisted = await store.find_review("session-1", proposed.review.id)
    assert persisted.resolution is ReviewResolution.ACCEPTED
    assert persisted.resolved_request_id == "approve-1"


@pytest.mark.asyncio
async def test_review_rejection_is_terminal_and_never_executes(
    runner,
    executor,
) -> None:
    proposed = await runner.run(reviewed_request())

    rejected = await runner.reject_review(
        proposed.review.id,
        request_id="reject-1",
        expected_session_version=proposed.session_version,
    )
    later_accept = await runner.accept_review(
        proposed.review.id,
        request_id="approve-after-reject",
        expected_session_version=rejected.session_version,
    )

    assert rejected.disposition is OperationDisposition.FAILED
    assert rejected.failure.code == "review_rejected"
    assert later_accept.failure.code == "review_already_resolved"
    assert executor.calls == []


@pytest.mark.asyncio
async def test_review_acceptance_refreshes_authority_and_invalidates_stale_proposal(
    runner,
    provider,
    guard,
    executor,
    store,
) -> None:
    proposed = await runner.run(reviewed_request())
    provider.values = {"revision": 2}

    stale = await runner.accept_review(
        proposed.review.id,
        request_id="approve-stale",
        expected_session_version=proposed.session_version,
    )

    assert stale.disposition is OperationDisposition.FAILED
    assert stale.failure.code == "review_stale"
    assert executor.calls == []
    assert guard.calls == ["proposal-1", "approve-stale"]
    persisted = await store.find_review("session-1", proposed.review.id)
    assert persisted.resolution is ReviewResolution.STALE


@pytest.mark.asyncio
async def test_expired_review_cannot_execute(
    runner,
    clock,
    executor,
    store,
) -> None:
    proposed = await runner.run(reviewed_request())
    clock.advance(timedelta(minutes=11))

    expired = await runner.accept_review(
        proposed.review.id,
        request_id="approve-expired",
        expected_session_version=proposed.session_version,
    )

    assert expired.failure.code == "review_expired"
    assert executor.calls == []
    persisted = await store.find_review("session-1", proposed.review.id)
    assert persisted.resolution is ReviewResolution.EXPIRED


@pytest.mark.asyncio
async def test_operation_spec_change_invalidates_review(
    runner,
    executor,
) -> None:
    proposed = await runner.run(reviewed_request())
    operations = dict(runner.app.app.operations)
    operations["test.reviewed_write"] = operations["test.reviewed_write"].model_copy(
        update={"description": "Changed after proposal."}
    )
    runner.app = BoundRouteDeckApp(
        app=replace(runner.app.app, operations=operations),
        bindings=runner.app.bindings,
    )

    stale = await runner.accept_review(
        proposed.review.id,
        request_id="approve-spec-stale",
        expected_session_version=proposed.session_version,
    )

    assert stale.failure.code == "review_stale"
    assert executor.calls == []


@pytest.mark.asyncio
async def test_review_lookup_is_session_scoped_and_non_enumerating(
    runner,
    executor,
) -> None:
    proposed = await runner.run(reviewed_request())

    missing = await runner.accept_review(
        proposed.review.id,
        request_id="cross-session-approval",
        expected_session_version=proposed.session_version,
        session_id="session-other",
    )

    assert missing.failure.code == "review_not_found"
    assert executor.calls == []


@pytest.mark.asyncio
async def test_concurrent_accept_and_reject_have_one_atomic_winner(
    runner,
    executor,
) -> None:
    proposed = await runner.run(reviewed_request())

    accepted, rejected = await asyncio.gather(
        runner.accept_review(
            proposed.review.id,
            request_id="approve-race",
            expected_session_version=proposed.session_version,
        ),
        runner.reject_review(
            proposed.review.id,
            request_id="reject-race",
            expected_session_version=proposed.session_version,
        ),
    )

    codes = {
        result.failure.code
        for result in (accepted, rejected)
        if result.failure is not None
    }
    assert executor.call_count("test.reviewed_write") <= 1
    assert (
        sum(
            result.disposition is OperationDisposition.COMPLETED
            or result.failure.code == "review_rejected"
            for result in (accepted, rejected)
        )
        == 1
    )
    assert codes & {
        "review_already_resolved",
        "operation_in_progress",
        "version_conflict",
    }


@pytest.mark.asyncio
async def test_review_staging_ends_and_releases_parent_agent_turn(
    runner,
    store,
) -> None:
    turn = await runner.begin_turn(
        TurnClaim(
            session_id="session-1",
            expected_session_version=1,
            request_id="agent-turn-1",
            request_fingerprint="agent-turn-fingerprint",
            owner_kind=TurnOwnerKind.CHAT,
        )
    )
    request = reviewed_request().model_copy(update={"source": OperationSource.AGENT})

    proposed = await runner.run(request, turn=turn)

    assert proposed.disposition is OperationDisposition.REQUIRES_REVIEW
    assert store.active_turn("agent-turn-1") is None
