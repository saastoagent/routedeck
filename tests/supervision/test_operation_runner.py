from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from routedeck_core.app import bind_app, compile_app
from routedeck_core.contracts import operations
from routedeck_core.contracts.failures import FailureKind, RouteDeckFailure
from routedeck_core.contracts.navigation import DeepLinkPolicy
from routedeck_core.contracts.session import ResumeCapabilityBinding
from routedeck_core.state.session import create_session


class FailingNotifier:
    async def notify(self, session_id, events) -> None:
        del session_id, events
        raise RuntimeError("wakeup unavailable")


def test_operation_request_is_an_immutable_canonical_contract() -> None:
    request_type = getattr(operations, "OperationRequest")

    request = request_type(
        session_id="session-1",
        request_id="request-1",
        expected_session_version=1,
        operation_id="test.advance",
        source="surface",
        arguments={"quantity": 2},
    )

    assert request.arguments.to_dict() == {"quantity": 2}
    assert request.model_config["frozen"] is True


def test_operation_requires_at_least_one_allowed_invocation_source() -> None:
    with pytest.raises(ValidationError, match="allowed_sources"):
        operations.Operation(
            id="test.no_source",
            title="No source",
            description="Invalid operation without an invocation source.",
            safety_class=operations.SafetyClass.READ_EXTERNAL,
            allowed_sources=frozenset(),
            outcomes=("done",),
        )


def test_operation_runner_has_an_intentional_public_supervision_export() -> None:
    from routedeck_core.supervision import RouteDeckOperationRunner

    assert RouteDeckOperationRunner.__name__ == "RouteDeckOperationRunner"


def test_entity_inputs_are_explicit_and_unique() -> None:
    entity_input_type = getattr(operations, "EntityInput")

    operation = operations.Operation(
        id="cart.add_item",
        title="Add item",
        description="Test operation.",
        input_schema={
            "type": "object",
            "properties": {"variant_ref": {"type": "string"}},
            "required": ["variant_ref"],
            "additionalProperties": False,
        },
        entity_inputs=(
            entity_input_type(argument_name="variant_ref", entity_kind="variant"),
        ),
        safety_class=operations.SafetyClass.WRITE_EXTERNAL,
        allowed_sources=frozenset(operations.OperationSource),
        unknown_recovery_directive="reconcile_cart",
        outcomes=("added",),
    )

    assert operation.entity_inputs[0].argument_name == "variant_ref"
    with pytest.raises(ValidationError, match="entity input argument names"):
        operation.model_copy(
            update={
                "entity_inputs": (*operation.entity_inputs, *operation.entity_inputs)
            }
        ).__class__.model_validate(
            operation.model_copy(
                update={
                    "entity_inputs": (
                        *operation.entity_inputs,
                        *operation.entity_inputs,
                    )
                }
            ).model_dump()
        )


def test_operation_outcome_requires_a_typed_success_or_failure() -> None:
    delivery_phase = getattr(operations, "DeliveryPhase")
    outcome_type = getattr(operations, "OperationOutcome")
    failure = RouteDeckFailure(
        kind=FailureKind.BUSINESS,
        code="inventory_changed",
        phase="execute",
        correlation_id="correlation-1",
        operation_id="cart.add_item",
        request_id="request-1",
        public_message="The item is no longer available.",
    )

    succeeded = outcome_type(
        outcome="added",
        delivery_phase=delivery_phase.RESPONSE_RECEIVED,
        observation={"cart_ref": "private-cart"},
    )
    failed = outcome_type(
        delivery_phase=delivery_phase.NOT_SENT,
        failure=failure,
    )

    assert succeeded.observation.to_dict() == {"cart_ref": "private-cart"}
    assert failed.failure == failure
    with pytest.raises(ValidationError, match="outcome or failure"):
        outcome_type(delivery_phase=delivery_phase.NOT_SENT)
    with pytest.raises(ValidationError, match="not both"):
        outcome_type(
            outcome="added",
            delivery_phase=delivery_phase.RESPONSE_RECEIVED,
            failure=failure,
        )
    with pytest.raises(ValidationError, match="successful outcomes cannot be not_sent"):
        outcome_type(
            outcome="added",
            delivery_phase=delivery_phase.NOT_SENT,
        )


def test_write_operations_require_explicit_unknown_outcome_recovery() -> None:
    with pytest.raises(ValidationError, match="unknown recovery directive"):
        operations.Operation(
            id="cart.add_item",
            title="Add item",
            description="Test operation.",
            safety_class=operations.SafetyClass.WRITE_EXTERNAL,
            allowed_sources=frozenset(operations.OperationSource),
            outcomes=("added",),
        )

    operation = operations.Operation(
        id="cart.add_item",
        title="Add item",
        description="Test operation.",
        safety_class=operations.SafetyClass.WRITE_EXTERNAL,
        allowed_sources=frozenset(operations.OperationSource),
        outcomes=("added",),
        unknown_recovery_directive="reconcile_cart",
        unknown_recovery_operation_refs=(operations.OperationRef(id="cart.open"),),
    )

    assert operation.unknown_recovery_directive == "reconcile_cart"
    assert operation.unknown_recovery_operation_refs == (
        operations.OperationRef(id="cart.open"),
    )


@pytest.mark.parametrize(
    "recovery_fields",
    (
        {"unknown_recovery_directive": "retry_read"},
        {
            "unknown_recovery_operation_refs": (
                operations.OperationRef(id="catalog.refresh"),
            )
        },
    ),
)
def test_non_write_operations_reject_unknown_outcome_recovery_fields(
    recovery_fields: dict[str, object],
) -> None:
    with pytest.raises(ValidationError, match="only for write_external"):
        operations.Operation(
            id="catalog.list",
            title="List catalog",
            description="Test operation.",
            safety_class=operations.SafetyClass.READ_EXTERNAL,
            allowed_sources=frozenset(operations.OperationSource),
            outcomes=("listed",),
            **recovery_fields,
        )


def test_operation_result_requires_review_metadata_for_review_disposition() -> None:
    evidence_type = getattr(operations, "OperationEvidence")
    phase_type = getattr(operations, "OperationPhase")
    result_type = getattr(operations, "OperationResult")
    disposition = getattr(operations, "OperationDisposition")
    review_type = getattr(operations, "OperationReview")

    evidence = evidence_type(
        source=operations.OperationSource.SURFACE,
        phases=(phase_type.RECEIVED, phase_type.REVIEW_STAGED),
        attempt_id="attempt-1",
        request_fingerprint="fingerprint-1",
    )
    review = review_type(
        id="review-1",
        expires_at=datetime(2030, 1, 1, tzinfo=UTC),
    )
    result = result_type(
        disposition=disposition.REQUIRES_REVIEW,
        session_id="session-1",
        request_id="request-1",
        operation_id="checkout.place_order",
        session_version=2,
        projection_version=1,
        evidence=evidence,
        review=review,
    )

    assert result.review == review
    with pytest.raises(ValidationError, match="review metadata"):
        result_type(
            disposition=disposition.REQUIRES_REVIEW,
            session_id="session-1",
            request_id="request-1",
            operation_id="checkout.place_order",
            session_version=2,
            projection_version=1,
            evidence=evidence,
        )


def test_operation_evidence_rejects_reversed_lifecycle_phases() -> None:
    with pytest.raises(ValidationError, match="lifecycle order"):
        operations.OperationEvidence(
            source=operations.OperationSource.AGENT,
            phases=(
                operations.OperationPhase.STATE_COMMITTED,
                operations.OperationPhase.EXECUTION_CLAIMED,
            ),
            attempt_id="attempt-1",
            request_fingerprint="fingerprint-1",
        )


def test_operation_result_dispositions_cover_needs_input_and_pending() -> None:
    assert operations.OperationDisposition.NEEDS_INPUT.value == "needs_input"
    assert operations.OperationDisposition.PENDING.value == "pending"


def test_completed_result_rejects_failure_or_review_payloads() -> None:
    failure = RouteDeckFailure(
        kind=FailureKind.INTERNAL,
        code="unexpected_result",
        phase="execute",
        correlation_id="correlation-1",
        operation_id="test.advance",
        request_id="request-1",
        public_message="The operation could not be completed.",
    )
    evidence = operations.OperationEvidence(
        source=operations.OperationSource.SYSTEM,
        phases=(operations.OperationPhase.RECEIVED,),
        attempt_id="attempt-1",
        request_fingerprint="fingerprint-1",
    )

    with pytest.raises(ValidationError, match="completed payload"):
        operations.OperationResult(
            disposition=operations.OperationDisposition.COMPLETED,
            session_id="session-1",
            request_id="request-1",
            operation_id="test.advance",
            session_version=2,
            projection_version=2,
            evidence=evidence,
            outcome="advanced",
            failure=failure,
        )


def test_operation_spec_rejects_duplicate_refs_and_non_string_entity_input() -> None:
    provider = operations.ProviderRef(id="test.provider")
    guard = operations.GuardRef(id="test.guard")

    with pytest.raises(ValidationError, match="provider refs"):
        operations.Operation(
            id="test.advance",
            title="Advance",
            description="Test operation.",
            safety_class=operations.SafetyClass.WRITE_EXTERNAL,
            allowed_sources=frozenset(operations.OperationSource),
            unknown_recovery_directive="Verify the write before retrying.",
            outcomes=("advanced",),
            provider_refs=(provider, provider),
        )
    with pytest.raises(ValidationError, match="string schema property"):
        operations.Operation(
            id="cart.add_item",
            title="Add",
            description="Test operation.",
            input_schema={
                "type": "object",
                "properties": {"variant_ref": {"type": "integer"}},
                "required": ["variant_ref"],
            },
            entity_inputs=(
                operations.EntityInput(
                    argument_name="variant_ref", entity_kind="variant"
                ),
            ),
            safety_class=operations.SafetyClass.WRITE_EXTERNAL,
            allowed_sources=frozenset(operations.OperationSource),
            unknown_recovery_directive="Verify the write before retrying.",
            outcomes=("added",),
            guard_refs=(guard,),
        )


def test_operation_outcome_schemas_are_declared_by_outcome() -> None:
    operation = operations.Operation(
        id="cart.create",
        title="Create cart",
        description="Test operation.",
        safety_class=operations.SafetyClass.WRITE_EXTERNAL,
        allowed_sources=frozenset(operations.OperationSource),
        unknown_recovery_directive="Verify cart creation before retrying.",
        outcomes=("created",),
        outcome_schemas={
            "created": {
                "type": "object",
                "properties": {"cart_id": {"type": "string"}},
                "required": ["cart_id"],
                "additionalProperties": False,
            }
        },
    )

    assert operation.outcome_schema_value("created")["type"] == "object"
    with pytest.raises(ValidationError, match="declared outcomes"):
        operations.Operation(
            id="cart.create",
            title="Create cart",
            description="Test operation.",
            safety_class=operations.SafetyClass.WRITE_EXTERNAL,
            allowed_sources=frozenset(operations.OperationSource),
            unknown_recovery_directive="Verify cart creation before retrying.",
            outcomes=("created",),
            outcome_schemas={"undeclared": {"type": "object"}},
        )


def operation_request(
    *,
    operation_id: str = "test.write",
    request_id: str = "request-1",
    expected_session_version: int = 1,
    source: str = "surface",
    arguments: dict[str, object] | None = None,
):
    return operations.OperationRequest(
        session_id="session-1",
        request_id=request_id,
        expected_session_version=expected_session_version,
        operation_id=operation_id,
        source=source,
        arguments=arguments if arguments is not None else {"quantity": 2},
    )


@pytest.mark.asyncio
async def test_runner_executes_declared_provider_guard_handler_and_commits(
    runner,
    provider,
    guard,
    executor,
    store,
    notifier,
) -> None:
    result = await runner.run(operation_request())

    assert result.disposition is operations.OperationDisposition.COMPLETED
    assert result.outcome == "written"
    assert provider.calls == ["request-1"]
    assert guard.calls == ["request-1"]
    assert executor.call_count("test.write") == 1
    assert store.active_turn("request-1") is None
    assert result.evidence.phases == (
        operations.OperationPhase.RECEIVED,
        operations.OperationPhase.LEASE_ACQUIRED,
        operations.OperationPhase.VALIDATED,
        operations.OperationPhase.CONTEXT_REFRESHED,
        operations.OperationPhase.GUARDS_PASSED,
        operations.OperationPhase.EXECUTION_CLAIMED,
        operations.OperationPhase.TOOL_STARTED,
        operations.OperationPhase.TOOL_SUCCEEDED,
        operations.OperationPhase.EXECUTION_RESULT_RECORDED,
        operations.OperationPhase.STATE_COMMITTED,
        operations.OperationPhase.COMPLETED,
    )
    assert len(notifier.notifications) == 1


@pytest.mark.asyncio
async def test_session_bound_self_transition_rotates_handle_and_projection_together(
    runner_factory,
    bound_app,
    store,
) -> None:
    application = bound_app.app.application
    feature = application.features[0]
    node = feature.nodes[0]
    session_bound_node = node.model_copy(
        update={
            "route": node.route.model_copy(
                update={"deep_link_policy": DeepLinkPolicy.SESSION_BOUND}
            )
        }
    )
    session_bound_application = application.model_copy(
        update={
            "features": (
                feature.model_copy(update={"nodes": (session_bound_node,)}),
            )
        }
    )
    compiled = compile_app(session_bound_application)
    session_bound_app = bind_app(compiled, bound_app.bindings)
    previous = store.sessions["session-1"]
    initial_capability = ResumeCapabilityBinding(
        handle="resume-initial",
        session_id=previous.session_id,
        node_id=session_bound_node.id,
        expires_at=datetime(2030, 1, 1, tzinfo=UTC),
    )
    initial = create_session(
        app=compiled,
        session_id=previous.session_id,
        private_state=previous.private_state.model_copy(
            update={"resume_capabilities": (initial_capability,)}
        ),
        public_state=previous.public_state,
    )
    store.sessions[initial.session_id] = initial
    runner = runner_factory(app=session_bound_app)

    result = await runner.run(operation_request())
    committed = store.sessions[initial.session_id]
    current_capabilities = tuple(
        capability
        for capability in committed.private_state.resume_capabilities
        if capability.node_id == committed.current.node_id
        and capability.route_params == committed.current.route_params
    )

    assert result.disposition is operations.OperationDisposition.COMPLETED
    assert len(current_capabilities) == 1
    assert current_capabilities[0].handle != initial_capability.handle
    assert committed.projection_version == initial.projection_version + 1
    assert result.projection_version == committed.projection_version


@pytest.mark.asyncio
async def test_runner_blocks_disallowed_source_before_product_execution(
    runner_factory,
    bound_app,
    provider,
    guard,
    executor,
) -> None:
    restricted = bound_app.app.operations["test.write"].model_copy(
        update={"allowed_sources": frozenset({operations.OperationSource.SURFACE})}
    )
    operation_catalog = dict(bound_app.app.operations)
    operation_catalog[restricted.id] = restricted
    restricted_app = replace(bound_app.app, operations=operation_catalog)
    runner = runner_factory(app=replace(bound_app, app=restricted_app))

    result = await runner.run(
        operation_request(source=operations.OperationSource.AGENT)
    )

    assert result.disposition is operations.OperationDisposition.BLOCKED
    assert result.failure is not None
    assert result.failure.code == "operation_source_not_allowed"
    assert result.failure.phase == "source_validation"
    assert provider.calls == []
    assert guard.calls == []
    assert executor.call_count("test.write") == 0


@pytest.mark.asyncio
async def test_committed_operation_result_survives_notifier_failure(
    runner_factory,
    store,
    caplog,
) -> None:
    runner = runner_factory(notifier=FailingNotifier())

    result = await runner.run(operation_request())
    recorded = await store.find_attempt("session-1", "request-1")

    assert result.disposition is operations.OperationDisposition.COMPLETED
    assert recorded is not None
    assert recorded.disposition is operations.OperationDisposition.COMPLETED
    assert "RouteDeck event wakeup failed" in caplog.text


@pytest.mark.asyncio
async def test_ui_and_agent_sources_use_identical_supervision_phases(
    runner,
    executor,
) -> None:
    ui = await runner.run(operation_request(request_id="ui-1"))
    agent = await runner.run(
        operation_request(
            request_id="agent-1",
            expected_session_version=ui.session_version,
            source="agent",
        )
    )

    assert ui.evidence.phases == agent.evidence.phases
    assert executor.call_count("test.write") == 2


@pytest.mark.asyncio
async def test_blocked_guard_never_invokes_executor(
    runner,
    guard,
    executor,
    store,
) -> None:
    guard.decision = __import__(
        "routedeck_core.supervision.guards", fromlist=["GuardDecision"]
    ).GuardDecision.blocked(
        RouteDeckFailure(
            kind=FailureKind.GUARD,
            code="operation_blocked",
            phase="guard",
            correlation_id="correlation-1",
            operation_id="test.write",
            request_id="request-1",
            public_message="The operation is not currently allowed.",
        )
    )

    result = await runner.run(operation_request())

    assert result.disposition is operations.OperationDisposition.BLOCKED
    assert result.failure.code == "operation_blocked"
    assert executor.calls == []
    assert store.active_turn("request-1") is None


@pytest.mark.asyncio
async def test_invalid_input_and_unknown_keys_fail_before_context_refresh(
    runner,
    provider,
    executor,
) -> None:
    invalid = await runner.run(
        operation_request(arguments={"quantity": 0, "unexpected": True})
    )

    assert invalid.disposition is operations.OperationDisposition.BLOCKED
    assert invalid.failure.code == "invalid_operation_input"
    assert provider.calls == []
    assert executor.calls == []


@pytest.mark.asyncio
async def test_entity_input_resolves_only_an_operation_allowlisted_same_kind_handle(
    runner,
    handlers,
    executor,
) -> None:
    valid = await runner.run(
        operation_request(
            operation_id="test.bound_write",
            arguments={"item_ref": "item-public-1"},
        )
    )
    private_context = handlers["test.bound_write"].calls[0][1]
    forged = await runner.run(
        operation_request(
            operation_id="test.bound_write",
            request_id="request-forged",
            expected_session_version=valid.session_version,
            arguments={"item_ref": "private-item-sentinel"},
        )
    )

    assert valid.disposition is operations.OperationDisposition.COMPLETED
    assert private_context.private_entity_id("item_ref") == "private-item-sentinel"
    assert "private-item-sentinel" not in valid.model_dump_json()
    assert forged.disposition is operations.OperationDisposition.BLOCKED
    assert forged.failure.code == "invalid_entity_reference"
    assert executor.call_count("test.bound_write") == 1


@pytest.mark.asyncio
async def test_same_request_replays_before_stale_version_and_never_reexecutes(
    runner,
    executor,
) -> None:
    completed = await runner.run(operation_request())
    replay = await runner.run(operation_request(expected_session_version=0))

    assert replay == completed
    assert executor.call_count("test.write") == 1


@pytest.mark.asyncio
async def test_request_id_reuse_with_changed_arguments_or_source_is_rejected(
    runner,
    executor,
) -> None:
    completed = await runner.run(operation_request())
    changed_arguments = await runner.run(
        operation_request(
            expected_session_version=completed.session_version,
            arguments={"quantity": 3},
        )
    )
    changed_source = await runner.run(
        operation_request(
            expected_session_version=completed.session_version,
            source="agent",
        )
    )

    assert changed_arguments.failure.code == "request_id_reused"
    assert changed_source.failure.code == "request_id_reused"
    assert executor.call_count("test.write") == 1


@pytest.mark.asyncio
async def test_undeclared_executor_outcome_becomes_unknown_for_a_sent_write(
    runner,
    handlers,
    store,
    executor,
) -> None:
    handlers["test.write"].next_outcome = operations.OperationOutcome(
        outcome="handler_selected_target",
        delivery_phase=operations.DeliveryPhase.RESPONSE_RECEIVED,
    )

    result = await runner.run(operation_request())
    snapshot = await store.load("session-1")

    assert (
        result.disposition is operations.OperationDisposition.EXTERNAL_OUTCOME_UNKNOWN
    )
    assert result.failure.code == "external_outcome_unknown"
    assert "test.write" in snapshot.state.public_state.disabled_operation_ids
    assert executor.call_count("test.write") == 1


@pytest.mark.asyncio
async def test_sensitive_or_malformed_argument_is_absent_from_all_serialized_records(
    runner,
    store,
) -> None:
    sentinel = "sensitive-email-sentinel@example.invalid"

    result = await runner.run(operation_request(arguments={"quantity": sentinel}))
    snapshot = await store.load("session-1")

    assert result.failure.code == "invalid_operation_input"
    assert sentinel not in result.model_dump_json()
    assert sentinel not in snapshot.state.model_dump_json()
    assert await store.find_attempt("session-1", "request-1") is None
