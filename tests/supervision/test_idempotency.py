from __future__ import annotations

from datetime import UTC, datetime
from typing import get_type_hints

from routedeck_core.contracts.operations import (
    DeliveryPhase,
    EntityInput,
    OperationRequest,
    OperationSource,
    Operation,
    SafetyClass,
)
from routedeck_core.contracts.failures import FailureKind, RouteDeckFailure
from routedeck_core.contracts.projection import FrozenJson
from routedeck_core.contracts import session as session_contracts


def test_request_fingerprint_is_canonical_domain_separated_and_version_independent() -> (
    None
):
    from routedeck_core.supervision.outcomes import canonical_request_fingerprint

    first = OperationRequest(
        session_id="session-1",
        request_id="request-1",
        expected_session_version=1,
        operation_id="cart.add_item",
        source=OperationSource.AGENT,
        arguments={"quantity": 2, "variant_ref": "variant-public-1"},
    )
    retried = first.model_copy(
        update={
            "expected_session_version": 99,
            "arguments": {"variant_ref": "variant-public-1", "quantity": 2},
        }
    )
    entity_inputs = (
        EntityInput(argument_name="variant_ref", entity_kind="variant"),
    )

    first_fingerprint = canonical_request_fingerprint(
        first,
        entity_inputs=entity_inputs,
        parent_turn_id="turn-1",
    )
    retry_fingerprint = canonical_request_fingerprint(
        retried,
        entity_inputs=entity_inputs,
        parent_turn_id="turn-1",
    )

    assert first_fingerprint == retry_fingerprint
    assert first_fingerprint.startswith("rdop1:")
    assert first_fingerprint != canonical_request_fingerprint(
        retried.model_copy(update={"source": OperationSource.SURFACE}),
        entity_inputs=entity_inputs,
        parent_turn_id="turn-1",
    )
    assert first_fingerprint != canonical_request_fingerprint(
        retried,
        entity_inputs=entity_inputs,
        parent_turn_id="turn-2",
    )


def test_stored_attempt_aggregates_review_and_journal_evidence() -> None:
    OperationAttempt = getattr(session_contracts, "OperationAttempt")
    OperationArgument = getattr(session_contracts, "OperationArgument")
    PendingReview = getattr(session_contracts, "PendingReview")
    JournaledExecutionResult = getattr(session_contracts, "JournaledExecutionResult")
    ReviewResolution = getattr(session_contracts, "ReviewResolution")
    StoredOperationAttempt = getattr(session_contracts, "StoredOperationAttempt")

    attempt = OperationAttempt(
        attempt_id="attempt-1",
        request_id="request-1",
        request_fingerprint="fingerprint-1",
        operation_id="checkout.place_order",
        source=OperationSource.SURFACE,
        expected_session_version=4,
        arguments=(OperationArgument(name="cart_ref", value=FrozenJson("cart-1")),),
        context_fingerprint="context-1",
    )
    review = PendingReview(
        review_id="review-1",
        attempt=attempt,
        operation_spec_version="1",
        proposal_fingerprint="proposal-1",
        projection_version=3,
        authoritative_context_fingerprint="context-1",
        expires_at=datetime(2030, 1, 1, tzinfo=UTC),
        resolution=ReviewResolution.PENDING,
    )
    result = JournaledExecutionResult(
        result_id="result-1",
        attempt_id="attempt-1",
        request_id="request-1",
        operation_id="checkout.place_order",
        outcome="order_created",
        delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
        result_fingerprint="result-fingerprint-1",
        observation={"order_ref": "private-order-1"},
    )

    stored = StoredOperationAttempt(
        attempt=attempt,
        review=review,
        journaled_result=result,
    )

    assert stored.review is review
    assert stored.journaled_result is result

    failure = RouteDeckFailure(
        kind=FailureKind.BUSINESS,
        code="checkout_failed",
        phase="execute",
        correlation_id="correlation-1",
        operation_id="checkout.place_order",
        request_id="request-1",
        public_message="Checkout failed.",
    )
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="not both"):
        JournaledExecutionResult(
            result_id="result-2",
            attempt_id="attempt-1",
            request_id="request-1",
            operation_id="checkout.place_order",
            outcome="order_created",
            delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
            result_fingerprint="result-fingerprint-2",
            failure=failure,
        )

    with pytest.raises(ValidationError, match="successful outcomes cannot be not_sent"):
        JournaledExecutionResult(
            result_id="result-3",
            attempt_id="attempt-1",
            request_id="request-1",
            operation_id="checkout.place_order",
            outcome="order_created",
            delivery_phase=DeliveryPhase.NOT_SENT,
            result_fingerprint="result-fingerprint-3",
        )


def test_operation_arguments_cannot_embed_sensitive_values() -> None:
    import pytest
    from pydantic import ValidationError

    OperationArgument = getattr(session_contracts, "OperationArgument")

    with pytest.raises(ValidationError):
        OperationArgument(
            name="email",
            value=FrozenJson("sensitive-email-sentinel@example.invalid"),
            sensitive=True,
        )


def test_operation_spec_version_is_derived_from_the_canonical_declaration() -> None:
    from routedeck_core.supervision.outcomes import canonical_operation_spec_version

    original = Operation(
        id="test.advance",
        title="Advance",
        description="Test operation.",
        input_schema={
            "type": "object",
            "properties": {"quantity": {"type": "integer"}},
        },
        safety_class=SafetyClass.WRITE_EXTERNAL,
        unknown_recovery_directive="Verify the write before retrying.",
        outcomes=("advanced",),
    )
    changed = original.model_copy(
        update={
            "input_schema": original.input_schema.__class__(
                {
                    "type": "object",
                    "properties": {"quantity": {"type": "integer", "minimum": 1}},
                }
            )
        }
    )

    assert canonical_operation_spec_version(original).startswith("rdopspec1:")
    assert canonical_operation_spec_version(
        original
    ) != canonical_operation_spec_version(changed)


def test_session_store_finds_durable_attempt_aggregates_and_resolved_reviews() -> None:
    import inspect

    from routedeck_core.ports.session_store import RouteDeckSessionStore

    StoredOperationAttempt = getattr(session_contracts, "StoredOperationAttempt")
    PendingReview = getattr(session_contracts, "PendingReview")
    attempt_hints = get_type_hints(RouteDeckSessionStore.find_attempt)
    review_hints = get_type_hints(RouteDeckSessionStore.find_review)

    assert attempt_hints["return"] == StoredOperationAttempt | None
    assert review_hints["return"] == PendingReview | None
    assert tuple(inspect.signature(RouteDeckSessionStore.stage_review).parameters) == (
        "self",
        "lease",
        "expected_session_version",
        "record",
        "next_state",
        "events",
        "parent_mutation",
    )
    assert tuple(
        inspect.signature(
            RouteDeckSessionStore.mark_external_outcome_unknown
        ).parameters
    ) == (
        "self",
        "claim",
        "expected_session_version",
        "record",
        "next_state",
        "events",
    )
    assert tuple(
        inspect.signature(RouteDeckSessionStore.record_execution_started).parameters
    ) == ("self", "claim", "record")
    assert tuple(
        inspect.signature(RouteDeckSessionStore.record_execution_result).parameters
    ) == ("self", "claim", "result", "record")
