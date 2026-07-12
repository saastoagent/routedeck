from __future__ import annotations

import pytest

from routedeck_core.contracts.failures import FailureKind, RouteDeckFailure
from routedeck_core.contracts.operations import (
    DeliveryPhase,
    OperationDisposition,
    OperationOutcome,
    OperationRequest,
    OperationSource,
)


def request(
    *, request_id: str = "write-1", expected_session_version: int = 1
) -> OperationRequest:
    return OperationRequest(
        session_id="session-1",
        request_id=request_id,
        expected_session_version=expected_session_version,
        operation_id="test.write",
        source=OperationSource.SURFACE,
        arguments={"quantity": 2},
    )


def failure(kind: FailureKind, code: str, phase: DeliveryPhase) -> OperationOutcome:
    return OperationOutcome(
        delivery_phase=phase,
        failure=RouteDeckFailure(
            kind=kind,
            code=code,
            phase="execute",
            correlation_id="safe-correlation",
            operation_id="test.write",
            request_id="write-1",
            public_message="The operation could not be completed.",
        ),
    )


@pytest.mark.asyncio
async def test_possibly_sent_write_is_unknown_and_disabled(
    runner, handlers, store
) -> None:
    handlers["test.write"].next_outcome = failure(
        FailureKind.TRANSPORT,
        "upstream_timeout",
        DeliveryPhase.POSSIBLY_SENT,
    )

    result = await runner.run(request())

    assert result.disposition is OperationDisposition.EXTERNAL_OUTCOME_UNKNOWN
    assert result.evidence.delivery_phase is DeliveryPhase.POSSIBLY_SENT
    assert (
        "test.write"
        in (await store.load("session-1")).state.public_state.disabled_operation_ids
    )


@pytest.mark.asyncio
async def test_not_sent_write_is_definitive_failure_and_remains_reproposable(
    runner, handlers, store, executor
) -> None:
    handlers["test.write"].next_outcome = failure(
        FailureKind.TRANSPORT,
        "connection_refused",
        DeliveryPhase.NOT_SENT,
    )

    failed = await runner.run(request())
    handlers["test.write"].next_outcome = None
    retried = await runner.run(
        request(request_id="write-2", expected_session_version=failed.session_version)
    )

    assert failed.disposition is OperationDisposition.FAILED
    assert failed.evidence.delivery_phase is DeliveryPhase.NOT_SENT
    assert (
        "test.write"
        not in (await store.load("session-1")).state.public_state.disabled_operation_ids
    )
    assert retried.disposition is OperationDisposition.COMPLETED
    assert executor.call_count("test.write") == 2


@pytest.mark.asyncio
async def test_response_received_protocol_failure_for_write_is_still_unknown(
    runner, handlers
) -> None:
    handlers["test.write"].next_outcome = failure(
        FailureKind.PROVIDER_PROTOCOL,
        "malformed_response",
        DeliveryPhase.RESPONSE_RECEIVED,
    )

    result = await runner.run(request())

    assert result.disposition is OperationDisposition.EXTERNAL_OUTCOME_UNKNOWN
    assert result.evidence.delivery_phase is DeliveryPhase.RESPONSE_RECEIVED


@pytest.mark.asyncio
async def test_response_received_business_failure_is_definitive(
    runner, handlers, store
) -> None:
    handlers["test.write"].next_outcome = failure(
        FailureKind.BUSINESS,
        "inventory_changed",
        DeliveryPhase.RESPONSE_RECEIVED,
    )

    result = await runner.run(request())

    assert result.disposition is OperationDisposition.FAILED
    assert result.failure.code == "inventory_changed"
    assert (
        "test.write"
        not in (await store.load("session-1")).state.public_state.disabled_operation_ids
    )


@pytest.mark.asyncio
async def test_malformed_success_observation_is_unknown_and_never_applied(
    runner, handlers, store
) -> None:
    handlers["test.write"].next_outcome = OperationOutcome(
        outcome="written",
        delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
        observation={"receipt": 42},
    )

    result = await runner.run(request())

    assert result.disposition is OperationDisposition.EXTERNAL_OUTCOME_UNKNOWN
    assert result.evidence.delivery_phase is DeliveryPhase.RESPONSE_RECEIVED
    stored = await store.find_attempt("session-1", "write-1")
    assert stored.journaled_result is None


@pytest.mark.asyncio
async def test_valid_success_observation_is_durable_in_canonical_operation_state(
    runner, handlers, store
) -> None:
    handlers["test.write"].next_outcome = OperationOutcome(
        outcome="written",
        delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
        observation={"receipt": "receipt-1"},
    )

    result = await runner.run(request())
    snapshot = await store.load("session-1")

    assert result.disposition is OperationDisposition.COMPLETED
    assert snapshot.state.operation.journaled_result.observation.to_dict() == {
        "receipt": "receipt-1"
    }
