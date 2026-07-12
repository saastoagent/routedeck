from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest

from routedeck_core.app.bindings import BoundRouteDeckApp
from routedeck_core.contracts.failures import FailureKind, RouteDeckFailure
from routedeck_core.contracts.operations import (
    OperationDisposition,
    OperationRef,
    OperationRequest,
)
from routedeck_core.supervision.guards import GuardDecision


def request(
    *,
    request_id: str = "durable-1",
    expected_session_version: int = 1,
    operation_id: str = "test.write",
    arguments: dict[str, object] | None = None,
) -> OperationRequest:
    return OperationRequest(
        session_id="session-1",
        request_id=request_id,
        expected_session_version=expected_session_version,
        operation_id=operation_id,
        source="surface",
        arguments=arguments if arguments is not None else {"quantity": 2},
    )


@pytest.mark.asyncio
async def test_provider_failure_is_durable_and_same_id_replays_without_refresh(
    runner,
    provider,
    guard,
    executor,
    store,
) -> None:
    provider.raises = RuntimeError("private provider sentinel")

    failed = await runner.run(request())
    replay = await runner.run(request(expected_session_version=0))
    changed = await runner.run(
        request(
            expected_session_version=failed.session_version,
            arguments={"quantity": 3},
        )
    )

    assert failed.disposition is OperationDisposition.BLOCKED
    assert failed.failure is not None
    assert failed.failure.code == "context_provider_failed"
    assert replay == failed
    assert changed.failure is not None
    assert changed.failure.code == "request_id_reused"
    assert provider.calls == ["durable-1"]
    assert guard.calls == []
    assert executor.calls == []
    assert await store.find_attempt("session-1", "durable-1") is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "decision_factory, expected_disposition",
    (
        (GuardDecision.blocked, OperationDisposition.BLOCKED),
        (GuardDecision.needs_input, OperationDisposition.NEEDS_INPUT),
    ),
)
async def test_denied_guard_disposition_is_durable_and_replayed(
    runner,
    guard,
    executor,
    store,
    decision_factory,
    expected_disposition,
) -> None:
    failure = RouteDeckFailure(
        kind=FailureKind.GUARD,
        code="durable_guard_denial",
        phase="guard",
        correlation_id="correlation-guard",
        operation_id="test.write",
        request_id="durable-1",
        public_message="The operation cannot continue.",
    )
    guard.decision = decision_factory(failure)

    denied = await runner.run(request())
    replay = await runner.run(request(expected_session_version=0))

    assert denied.disposition is expected_disposition
    assert replay == denied
    assert len(guard.calls) == 1
    assert executor.calls == []
    assert await store.find_attempt("session-1", "durable-1") is not None


@pytest.mark.asyncio
async def test_missing_handler_binding_after_validation_is_durable(
    runner_factory,
    bound_app,
    provider,
    guard,
    executor,
    store,
) -> None:
    bindings = replace(
        bound_app.bindings,
        handlers={
            ref: handler
            for ref, handler in bound_app.bindings.handlers.items()
            if ref != OperationRef(id="test.write")
        },
    )
    malformed = BoundRouteDeckApp(app=bound_app.app, bindings=bindings)
    runner = runner_factory(app=malformed)

    blocked = await runner.run(request())
    replay = await runner.run(request(expected_session_version=0))

    assert blocked.disposition is OperationDisposition.BLOCKED
    assert blocked.failure is not None
    assert blocked.failure.code == "missing_operation_binding"
    assert replay == blocked
    assert provider.calls == ["durable-1"]
    assert guard.calls == ["durable-1"]
    assert executor.calls == []
    assert await store.find_attempt("session-1", "durable-1") is not None


@pytest.mark.asyncio
async def test_live_execution_replays_observed_pending_versions(
    runner,
    handlers,
    executor,
    store,
) -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    handlers["test.write"].started_event = started
    handlers["test.write"].release_event = release

    running = asyncio.create_task(runner.run(request()))
    await started.wait()
    pending = await runner.run(request(expected_session_version=0))
    release.set()
    completed = await running

    assert pending.disposition is OperationDisposition.PENDING
    assert pending.session_version == 1
    assert pending.projection_version == 1
    assert completed.disposition is OperationDisposition.COMPLETED
    assert executor.call_count("test.write") == 1
    assert store.turn_claim_counts["durable-1"] == 1


@pytest.mark.asyncio
async def test_completed_operation_release_failure_is_loud_and_replay_safe(
    runner,
    store,
    executor,
) -> None:
    store.fail_release_turn_once = True

    with pytest.raises(Exception, match="persistence_failure"):
        await runner.run(request())
    replay = await runner.run(request(expected_session_version=0))

    assert replay.disposition is OperationDisposition.COMPLETED
    assert executor.call_count("test.write") == 1


@pytest.mark.asyncio
async def test_missing_context_fingerprint_fails_before_executor(
    runner,
    executor,
) -> None:
    runner._context_fingerprint = lambda **_: None

    with pytest.raises(RuntimeError, match="authoritative context fingerprint"):
        await runner.run(request())

    assert executor.calls == []


@pytest.mark.asyncio
async def test_review_refresh_failure_is_durable_while_review_stays_pending(
    runner,
    provider,
    executor,
    store,
) -> None:
    proposal = await runner.run(
        request(
            request_id="review-proposal",
            operation_id="test.reviewed_write",
        )
    )
    assert proposal.review is not None
    provider.raises = RuntimeError("private approval refresh sentinel")

    failed = await runner.accept_review(
        proposal.review.id,
        request_id="review-approval",
        expected_session_version=proposal.session_version,
    )
    replay = await runner.accept_review(
        proposal.review.id,
        request_id="review-approval",
        expected_session_version=0,
    )
    persisted = await store.find_review("session-1", proposal.review.id)

    assert failed.disposition is OperationDisposition.FAILED
    assert failed.failure is not None
    assert failed.failure.code == "context_provider_failed"
    assert replay == failed
    assert persisted is not None
    assert persisted.resolution.value == "pending"
    assert provider.calls == ["review-proposal", "review-approval"]
    assert executor.calls == []


@pytest.mark.asyncio
async def test_non_write_executor_failure_is_journaled_and_replay_safe(
    runner,
    handlers,
    executor,
    store,
) -> None:
    handlers["test.read"].raises = RuntimeError("private read sentinel")
    read_request = request(
        request_id="read-failure",
        operation_id="test.read",
        arguments={},
    )

    failed = await runner.run(read_request)
    replay = await runner.run(
        read_request.model_copy(update={"expected_session_version": 0})
    )
    stored = await store.find_attempt("session-1", "read-failure")

    assert failed.disposition is OperationDisposition.FAILED
    assert replay == failed
    assert stored is not None
    assert stored.journaled_result is not None
    assert stored.journaled_result.failure is not None
    assert stored.journaled_result.failure.code == "executor_failed"
    assert (
        "test.read"
        not in store.sessions["session-1"].public_state.disabled_operation_ids
    )
    assert executor.call_count("test.read") == 1


@pytest.mark.asyncio
async def test_abandoned_non_write_tool_start_recovers_failed_without_reexecution(
    runner,
    handlers,
    executor,
    store,
) -> None:
    handlers["test.read"].raises = asyncio.CancelledError()
    read_request = request(
        request_id="read-cancelled",
        operation_id="test.read",
        arguments={},
    )

    with pytest.raises(asyncio.CancelledError):
        await runner.run(read_request)
    handlers["test.read"].raises = None
    recovered = await runner.run(
        read_request.model_copy(update={"expected_session_version": 0})
    )
    stored = await store.find_attempt("session-1", "read-cancelled")

    assert recovered.disposition is OperationDisposition.FAILED
    assert recovered.failure is not None
    assert recovered.failure.code == "execution_interrupted"
    assert stored is not None
    assert stored.journaled_result is not None
    assert (
        "test.read"
        not in store.sessions["session-1"].public_state.disabled_operation_ids
    )
    assert executor.call_count("test.read") == 1


@pytest.mark.asyncio
async def test_unpersistable_response_received_degrades_to_possibly_sent_on_recovery(
    runner,
    store,
    executor,
) -> None:
    store.fail_record_result = True
    store.fail_mark_unknown_once = True

    with pytest.raises(OSError, match="unknown-state commit unavailable"):
        await runner.run(request(request_id="compound-write"))
    recovered = await runner.run(
        request(request_id="compound-write", expected_session_version=0)
    )

    assert recovered.disposition is OperationDisposition.EXTERNAL_OUTCOME_UNKNOWN
    assert recovered.evidence.delivery_phase is not None
    assert recovered.evidence.delivery_phase.value == "possibly_sent"
    assert recovered.failure is not None
    assert recovered.failure.recovery_directive == "Verify the write before retrying."
    assert executor.call_count("test.write") == 1
