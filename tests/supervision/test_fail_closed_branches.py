from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest
from pydantic import SecretStr

from routedeck_core.contracts.conversation import (
    ConversationRole,
    ConversationToolCall,
    FinalizedConversationTurn,
)
from routedeck_core.contracts.effects import (
    EntityBindingEffect,
    EntityKindEffects,
    ExactRouteParameter,
    PublicSurfaceEffect,
    SessionEffects,
)
from routedeck_core.contracts.failures import FailureKind, RouteDeckFailure
from routedeck_core.contracts.operations import (
    DeliveryPhase,
    OperationDisposition,
    OperationOutcome,
    OperationRequest,
    OperationSource,
)
from routedeck_core.contracts.projection import (
    FrozenJson,
    FrozenJsonObject,
    PublicEntityHandle,
    PublicValue,
)
from routedeck_core.contracts.session import (
    Location,
    OperationArgument,
    OperationAttempt,
    SessionSnapshot,
    StoredOperationAttempt,
)
from routedeck_core.validation import RouteDeckValidationError
from routedeck_core.state.leases import TurnClaim, TurnOwnerKind
from routedeck_core.ports.session_store import SessionStoreError, SessionStoreErrorCode
from routedeck_core.supervision.runner import RouteEntryInvocation


def request(
    *,
    request_id: str = "branch-request",
    operation_id: str = "test.write",
    source: OperationSource = OperationSource.SURFACE,
    expected_session_version: int = 1,
    arguments: dict[str, object] | None = None,
) -> OperationRequest:
    return OperationRequest(
        session_id="session-1",
        request_id=request_id,
        expected_session_version=expected_session_version,
        operation_id=operation_id,
        source=source,
        arguments=(
            FrozenJsonObject(
                arguments
                if arguments is not None
                else ({"quantity": 2} if operation_id != "test.read" else {})
            )
        ),
    )


def failure(
    request_id: str = "branch-request",
    *,
    kind: FailureKind = FailureKind.INTERNAL,
) -> RouteDeckFailure:
    return RouteDeckFailure(
        kind=kind,
        code="operation_failed",
        phase="execute",
        correlation_id="safe-correlation",
        operation_id="test.write",
        request_id=request_id,
        public_message="The operation failed.",
    )


def attempt_for(
    operation_request: OperationRequest,
    *,
    context_fingerprint: str | None = "context-fingerprint",
) -> OperationAttempt:
    return OperationAttempt(
        attempt_id=f"attempt:{operation_request.request_id}",
        request_id=operation_request.request_id,
        request_fingerprint=f"fingerprint:{operation_request.request_id}",
        operation_id=operation_request.operation_id,
        source=operation_request.source,
        expected_session_version=operation_request.expected_session_version,
        arguments=tuple(
            OperationArgument(name=name, value=FrozenJson(value))
            for name, value in operation_request.arguments.to_dict().items()
        ),
        context_fingerprint=context_fingerprint,
    )


@pytest.mark.parametrize(
    "overrides, message",
    (
        ({"review_ttl": timedelta(0)}, "review_ttl"),
        ({"resume_capability_ttl": timedelta(0)}, "resume_capability_ttl"),
    ),
)
def test_runner_rejects_non_durable_runtime_configuration(
    runner_factory,
    overrides,
    message,
) -> None:
    with pytest.raises(ValueError, match=message):
        runner_factory(**overrides)


@pytest.mark.asyncio
async def test_run_rejects_partial_review_history_and_route_source_mismatch(
    runner,
) -> None:
    agent_request = request(
        request_id="invalid-review-history",
        operation_id="test.reviewed_write",
        source=OperationSource.AGENT,
    )
    user_marker = FinalizedConversationTurn(
        turn_id="user-marker",
        role=ConversationRole.USER,
        content="place the order",
        request_id="parent-turn",
    )
    tool_call = ConversationToolCall(
        call_id="call-1",
        name=agent_request.operation_id,
        arguments=agent_request.arguments,
    )

    with pytest.raises(ValueError, match="review turns require"):
        await runner.run(agent_request, review_turns=(user_marker,))
    with pytest.raises(ValueError, match="review turns require"):
        await runner.run(agent_request, review_tool_call=tool_call)
    with pytest.raises(ValueError, match="Route operation sources"):
        await runner.run(
            request(
                request_id="route-source-without-entry", source=OperationSource.ROUTE
            )
        )
    with pytest.raises(ValueError, match="Route operation sources"):
        await runner.run(
            request(request_id="surface-source-with-entry"),
            route_entry=RouteEntryInvocation(location=Location(node_id="test.start")),
        )


@pytest.mark.asyncio
async def test_unknown_operation_and_foreign_turn_fail_before_execution(
    runner,
    executor,
) -> None:
    missing = await runner.run(
        request(request_id="missing-operation", operation_id="test.missing")
    )
    turn = await runner.begin_turn(
        TurnClaim(
            session_id="session-1",
            expected_session_version=1,
            request_id="parent-turn",
            request_fingerprint="parent-fingerprint",
            owner_kind=TurnOwnerKind.CHAT,
        )
    )
    foreign_request = request(
        request_id="foreign-child",
        operation_id="test.read",
        source=OperationSource.AGENT,
        arguments={},
    ).model_copy(update={"session_id": "session-other"})

    with pytest.raises(ValueError, match="does not belong"):
        await runner._lease_for(
            request=foreign_request,
            fingerprint="foreign-fingerprint",
            turn=turn,
        )

    assert missing.failure is not None
    assert missing.failure.code == "operation_not_available"
    assert executor.calls == []


@pytest.mark.asyncio
async def test_route_entry_and_supervision_failure_helpers_reject_invalid_contracts(
    runner,
    store,
) -> None:
    operation_request = request()
    operation_attempt = attempt_for(operation_request)
    lease = await store.acquire_turn(
        TurnClaim(
            session_id="session-1",
            expected_session_version=1,
            request_id=operation_request.request_id,
            request_fingerprint=operation_attempt.request_fingerprint,
            owner_kind=TurnOwnerKind.SYSTEM,
        )
    )
    session = store.sessions["session-1"]

    with pytest.raises(ValueError, match="canonical history IDs"):
        runner._route_entry_session(
            session,
            operation_request,
            RouteEntryInvocation(location=Location(node_id="test.start", entry_id=1)),
        )
    with pytest.raises(ValueError, match="no declared entry operation"):
        runner._route_entry_session(
            session,
            operation_request,
            RouteEntryInvocation(location=Location(node_id="test.start")),
        )
    with pytest.raises(RuntimeError, match="failure disposition"):
        await runner._commit_supervision_failure(
            request=operation_request,
            attempt=operation_attempt,
            session=session,
            lease=lease,
            disposition=OperationDisposition.COMPLETED,
            failure=failure(),
            phases=runner._supervised_phases(),
        )


@pytest.mark.asyncio
async def test_external_cancellation_is_unknown_and_never_replayed(
    runner,
    handlers,
    executor,
    store,
) -> None:
    handlers["test.write"].raises = asyncio.CancelledError()

    result = await runner.run(request(request_id="cancelled-write"))
    replay = await runner.run(
        request(request_id="cancelled-write", expected_session_version=0)
    )

    assert result.disposition is OperationDisposition.EXTERNAL_OUTCOME_UNKNOWN
    assert replay == result
    assert result.failure is not None
    assert result.failure.code == "external_outcome_unknown"
    assert executor.call_count("test.write") == 1
    assert (
        "test.write" in store.sessions["session-1"].public_state.disabled_operation_ids
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation_id", "expected_code", "expected_disposition"),
    (
        (
            "test.write",
            "external_outcome_unknown",
            OperationDisposition.EXTERNAL_OUTCOME_UNKNOWN,
        ),
        ("test.read", "invalid_executor_result", OperationDisposition.FAILED),
    ),
)
async def test_untyped_executor_result_is_never_treated_as_success(
    runner,
    executor,
    monkeypatch,
    operation_id,
    expected_code,
    expected_disposition,
) -> None:
    async def invalid_execute(*_args, **_kwargs):
        return {"outcome": "forged"}

    monkeypatch.setattr(executor, "execute", invalid_execute)

    result = await runner.run(
        request(
            request_id=f"untyped:{operation_id}",
            operation_id=operation_id,
            arguments={} if operation_id == "test.read" else {"quantity": 2},
        )
    )

    assert result.disposition is expected_disposition
    assert result.failure is not None
    assert result.failure.code == expected_code


@pytest.mark.asyncio
async def test_non_write_invalid_observation_and_effects_are_definitive_failures(
    runner,
    handlers,
    executor,
) -> None:
    handlers["test.read"].next_outcome = OperationOutcome(
        outcome="read",
        delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
        observation=FrozenJsonObject({"undeclared": True}),
    )
    invalid_observation = await runner.run(
        request(
            request_id="read-invalid-observation",
            operation_id="test.read",
            arguments={},
        )
    )
    handlers["test.read"].next_outcome = OperationOutcome(
        outcome="read",
        delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
        effects=SessionEffects(
            surface_updates=(PublicSurfaceEffect(surface_id="missing.surface"),)
        ),
    )
    invalid_effects = await runner.run(
        request(
            request_id="read-invalid-effects",
            operation_id="test.read",
            expected_session_version=invalid_observation.session_version,
            arguments={},
        )
    )

    assert invalid_observation.failure is not None
    assert invalid_observation.failure.code == "invalid_outcome_observation"
    assert invalid_effects.failure is not None
    assert invalid_effects.failure.code == "invalid_session_effects"
    assert executor.call_count("test.read") == 2


@pytest.mark.asyncio
async def test_non_write_result_journal_failure_stays_definitive(
    runner,
    store,
    executor,
) -> None:
    store.fail_record_result = True

    result = await runner.run(
        request(
            request_id="read-journal-failure",
            operation_id="test.read",
            arguments={},
        )
    )

    assert result.disposition is OperationDisposition.FAILED
    assert result.failure is not None
    assert result.failure.code == "execution_result_not_journaled"
    assert executor.call_count("test.read") == 1


@pytest.mark.parametrize(
    "effects",
    (
        SessionEffects(
            route_params=(ExactRouteParameter(name="unexpected", value="value"),)
        ),
        SessionEffects(
            replace_entities=(
                EntityKindEffects(
                    entity_kind="undeclared-kind",
                    bindings=(
                        EntityBindingEffect(
                            public=PublicEntityHandle(
                                entity_kind="undeclared-kind",
                                handle="new-handle",
                            ),
                            private_id=SecretStr("private-id"),
                            allowed_operation_ids=("test.write",),
                        ),
                    ),
                ),
            )
        ),
        SessionEffects(
            replace_entities=(
                EntityKindEffects(
                    entity_kind="item",
                    bindings=(
                        EntityBindingEffect(
                            public=PublicEntityHandle(
                                entity_kind="item",
                                handle="new-item",
                            ),
                            private_id=SecretStr("private-id"),
                            allowed_operation_ids=("missing.operation",),
                        ),
                    ),
                ),
            )
        ),
        SessionEffects(
            surface_updates=(PublicSurfaceEffect(surface_id="missing.surface"),)
        ),
        SessionEffects(
            surface_updates=(
                PublicSurfaceEffect(
                    surface_id="test.active",
                    values=(PublicValue(name="undeclared", value=FrozenJson(True)),),
                ),
            )
        ),
        SessionEffects(remove_private_form_ids=("missing-private-form",)),
    ),
)
def test_success_effects_must_match_exact_target_node_contract(
    runner,
    store,
    effects,
) -> None:
    outcome = OperationOutcome(
        outcome="written",
        delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
        effects=effects,
    )

    assert not runner._valid_outcome_effects(
        session=store.sessions["session-1"],
        operation=runner.app.app.operations["test.write"],
        outcome=outcome,
    )


def test_failure_recovery_effects_require_a_current_node_and_external_write(
    runner,
    store,
) -> None:
    effects = SessionEffects(remove_private_form_ids=("missing-private-form",))
    recovery = OperationOutcome(
        delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
        failure=failure(),
        effects=effects,
    )
    missing_node = store.sessions["session-1"].model_copy(
        update={"current": Location(node_id="missing.node")}
    )

    assert not runner._valid_outcome_effects(
        session=store.sessions["session-1"],
        operation=runner.app.app.operations["test.read"],
        outcome=recovery,
    )
    with pytest.raises(RouteDeckValidationError, match="missing.node"):
        runner._valid_outcome_effects(
            session=missing_node,
            operation=runner.app.app.operations["test.write"],
            outcome=recovery,
        )


def test_json_validation_and_request_fingerprinting_fail_closed(runner) -> None:
    malformed_request = OperationRequest.model_construct(
        session_id="session-1",
        request_id="malformed-arguments",
        expected_session_version=1,
        operation_id="test.read",
        source=OperationSource.SURFACE,
        arguments=["not", "an", "object"],
    )

    from routedeck_core.supervision.outcomes import canonical_request_fingerprint

    with pytest.raises(TypeError, match="JSON object"):
        canonical_request_fingerprint(malformed_request)
    assert runner._valid_json_object({}, {})
    assert not runner._valid_json_object({}, {"unexpected": True})
    assert not runner._valid_json_object({"type": 7}, {})


def test_completed_and_stored_result_helpers_reject_incomplete_durable_records(
    runner,
    store,
) -> None:
    operation_request = request(request_id="result-contract")
    operation = runner.app.app.operations["test.write"]
    operation_attempt = attempt_for(operation_request)
    result = runner._journaled_result(
        operation_request,
        operation_attempt,
        operation,
        OperationOutcome(
            outcome="written",
            delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
        ),
    )
    snapshot = SessionSnapshot(state=store.sessions["session-1"])

    completed = runner._completed_result(
        operation_request,
        operation_attempt,
        result,
        snapshot,
    )
    assert completed.outcome == "written"
    with pytest.raises(RuntimeError, match="missing an outcome"):
        runner._completed_result(
            operation_request,
            operation_attempt,
            result.model_copy(update={"outcome": None}),
            snapshot,
        )
    assert (
        runner._result_from_stored(
            StoredOperationAttempt(attempt=operation_attempt),
            session_id="session-1",
        )
        is None
    )


@pytest.mark.asyncio
async def test_commit_helpers_reject_corrupt_journal_records_before_state_write(
    runner,
    store,
) -> None:
    operation_request = request(request_id="corrupt-journal")
    operation = runner.app.app.operations["test.write"]
    operation_attempt = attempt_for(operation_request)
    success = runner._journaled_result(
        operation_request,
        operation_attempt,
        operation,
        OperationOutcome(
            outcome="written",
            delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
        ),
    )
    record = StoredOperationAttempt(attempt=operation_attempt)

    with pytest.raises(RuntimeError, match="missing an outcome"):
        await runner._commit_success(
            request=operation_request,
            operation=operation,
            attempt=operation_attempt,
            session=store.sessions["session-1"],
            claim=None,
            result=success.model_copy(update={"outcome": None}),
            recorded_record=record,
        )
    with pytest.raises(RuntimeError, match="missing a failure"):
        await runner._commit_failure(
            request=operation_request,
            attempt=operation_attempt,
            session=store.sessions["session-1"],
            claim=None,
            result=success,
            recorded_record=record,
        )
    with pytest.raises(RuntimeError, match="recovery directive"):
        await runner._mark_unknown(
            request=operation_request,
            operation=operation.model_copy(update={"unknown_recovery_directive": None}),
            attempt=operation_attempt,
            claim=None,
            reason_code="test_unknown",
            delivery_phase=DeliveryPhase.POSSIBLY_SENT,
        )


@pytest.mark.asyncio
async def test_missing_compiled_transition_is_never_silently_accepted(
    runner,
    store,
) -> None:
    operation_request = request(request_id="orphan-outcome")
    operation_attempt = attempt_for(operation_request)
    record = StoredOperationAttempt(attempt=operation_attempt)
    external_operation = runner.app.app.operations["test.write"].model_copy(
        update={"outcomes": ("orphan",), "outcome_schemas": FrozenJsonObject({})}
    )
    external_result = runner._journaled_result(
        operation_request,
        operation_attempt,
        external_operation,
        OperationOutcome(
            outcome="orphan",
            delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
        ),
    )
    external = await runner._commit_success(
        request=operation_request,
        operation=external_operation,
        attempt=operation_attempt,
        session=store.sessions["session-1"],
        claim=None,
        result=external_result,
        recorded_record=record,
    )

    read_request = request(
        request_id="orphan-read-outcome",
        operation_id="test.read",
        arguments={},
    )
    read_attempt = attempt_for(read_request)
    read_operation = runner.app.app.operations["test.read"].model_copy(
        update={"outcomes": ("orphan",)}
    )
    read_result = runner._journaled_result(
        read_request,
        read_attempt,
        read_operation,
        OperationOutcome(
            outcome="orphan",
            delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
        ),
    )
    with pytest.raises(RuntimeError, match="no compiled transition"):
        await runner._commit_success(
            request=read_request,
            operation=read_operation,
            attempt=read_attempt,
            session=store.sessions["session-1"],
            claim=None,
            result=read_result,
            recorded_record=StoredOperationAttempt(attempt=read_attempt),
        )

    assert external.disposition is OperationDisposition.FAILED
    assert external.failure is not None
    assert external.failure.code == "external_outcome_unknown"


@pytest.mark.asyncio
async def test_review_stored_result_replays_review_metadata(runner, store) -> None:
    proposed = await runner.run(
        request(
            request_id="review-result-replay",
            operation_id="test.reviewed_write",
        )
    )
    stored = await store.find_attempt("session-1", "review-result-replay")

    assert stored is not None
    replay = runner._result_from_stored(stored, session_id="session-1")
    assert replay is not None
    assert replay.disposition is OperationDisposition.REQUIRES_REVIEW
    assert replay.review == proposed.review


@pytest.mark.asyncio
async def test_review_staging_rejects_incomplete_authority_and_ui_contracts(
    runner,
    store,
) -> None:
    operation_request = request(
        request_id="manual-review-stage",
        operation_id="test.reviewed_write",
    )
    operation = runner.app.app.operations["test.reviewed_write"]
    operation_attempt = attempt_for(operation_request)
    lease = await store.acquire_turn(
        TurnClaim(
            session_id="session-1",
            expected_session_version=1,
            request_id=operation_request.request_id,
            request_fingerprint=operation_attempt.request_fingerprint,
            owner_kind=TurnOwnerKind.SURFACE,
        )
    )
    session = store.sessions["session-1"]
    user_marker = FinalizedConversationTurn(
        turn_id="review-user-marker",
        role=ConversationRole.USER,
        content="place the order",
        request_id=lease.request_id,
    )

    with pytest.raises(RuntimeError, match="authoritative context"):
        await runner._stage_review(
            request=operation_request,
            operation=operation,
            attempt=operation_attempt.model_copy(update={"context_fingerprint": None}),
            session=session,
            lease=lease,
            provider_values=FrozenJsonObject({}),
            owns_lease=True,
            review_turns=(),
            review_tool_call=None,
        )
    with pytest.raises(RuntimeError, match="tool-call metadata"):
        await runner._stage_review(
            request=operation_request,
            operation=operation,
            attempt=operation_attempt,
            session=session,
            lease=lease,
            provider_values=FrozenJsonObject({}),
            owns_lease=True,
            review_turns=(user_marker,),
            review_tool_call=None,
        )

    invalid_metadata = (
        (FrozenJsonObject({"review_surface_id": 1}), "must be a string"),
        (FrozenJsonObject({"review_surface_id": "missing.surface"}), "not declared"),
        (FrozenJsonObject({"review_surface_id": "test.active"}), "do not match"),
    )
    for metadata, message in invalid_metadata:
        with pytest.raises(RuntimeError, match=message):
            await runner._stage_review(
                request=operation_request,
                operation=operation.model_copy(update={"public_metadata": metadata}),
                attempt=operation_attempt,
                session=session,
                lease=lease,
                provider_values=FrozenJsonObject({}),
                owns_lease=True,
                review_turns=(),
                review_tool_call=None,
            )


@pytest.mark.asyncio
@pytest.mark.parametrize("resolution", ("accept", "reject"))
async def test_review_resolution_same_request_replays_without_second_effect(
    runner,
    store,
    executor,
    resolution,
) -> None:
    proposed = await runner.run(
        request(
            request_id=f"proposal-replay-{resolution}",
            operation_id="test.reviewed_write",
        )
    )
    resolver = runner.accept_review if resolution == "accept" else runner.reject_review
    resolved = await resolver(
        proposed.review.id,
        request_id=f"resolve-replay-{resolution}",
        expected_session_version=proposed.session_version,
        session_id="session-1",
    )
    replay = await resolver(
        proposed.review.id,
        request_id=f"resolve-replay-{resolution}",
        expected_session_version=0,
        session_id="session-1",
    )

    assert replay == resolved
    assert executor.call_count("test.reviewed_write") == (
        1 if resolution == "accept" else 0
    )
    assert store.turn_claim_counts[f"resolve-replay-{resolution}"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("resolution", ("accept", "reject"))
async def test_review_resolution_rejects_request_id_collision_before_locking(
    runner,
    store,
    executor,
    resolution,
) -> None:
    proposed = await runner.run(
        request(
            request_id=f"proposal-collision-{resolution}",
            operation_id="test.reviewed_write",
        )
    )
    proposal_record = await store.find_attempt(
        "session-1", f"proposal-collision-{resolution}"
    )
    assert proposal_record is not None
    collision_id = f"resolve-collision-{resolution}"
    colliding_attempt = proposal_record.attempt.model_copy(
        update={
            "request_id": collision_id,
            "request_fingerprint": "different-fingerprint",
        }
    )
    store.attempts[("session-1", collision_id)] = proposal_record.model_copy(
        update={"attempt": colliding_attempt, "review": None}
    )
    resolver = runner.accept_review if resolution == "accept" else runner.reject_review

    result = await resolver(
        proposed.review.id,
        request_id=collision_id,
        expected_session_version=proposed.session_version,
        session_id="session-1",
    )

    assert result.disposition is OperationDisposition.BLOCKED
    assert result.failure is not None
    assert result.failure.code == "request_id_reused"
    assert store.turn_claim_counts[collision_id] == 0
    assert executor.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("resolution", ("accept", "reject"))
async def test_review_resolution_handles_disappearing_review_after_lock(
    runner,
    store,
    executor,
    monkeypatch,
    resolution,
) -> None:
    proposed = await runner.run(
        request(
            request_id=f"proposal-vanish-{resolution}",
            operation_id="test.reviewed_write",
        )
    )
    original_find_review = store.find_review
    calls = 0

    async def vanishing_review(session_id: str, review_id: str):
        nonlocal calls
        calls += 1
        if calls == 1:
            return await original_find_review(session_id, review_id)
        return None

    monkeypatch.setattr(store, "find_review", vanishing_review)
    resolver = runner.accept_review if resolution == "accept" else runner.reject_review

    result = await resolver(
        proposed.review.id,
        request_id=f"resolve-vanish-{resolution}",
        expected_session_version=proposed.session_version,
        session_id="session-1",
    )

    assert result.failure is not None
    assert result.failure.code == "review_already_resolved"
    assert executor.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("resolution", ("accept", "reject"))
async def test_review_resolution_handles_version_change_after_lock(
    runner,
    store,
    executor,
    monkeypatch,
    resolution,
) -> None:
    proposed = await runner.run(
        request(
            request_id=f"proposal-version-race-{resolution}",
            operation_id="test.reviewed_write",
        )
    )
    original_acquire_turn = store.acquire_turn

    async def mutate_after_lock(claim):
        lease = await original_acquire_turn(claim)
        current = store.sessions[claim.session_id]
        store.sessions[claim.session_id] = current.model_copy(
            update={"session_version": current.session_version + 1}
        )
        return lease

    monkeypatch.setattr(store, "acquire_turn", mutate_after_lock)
    resolver = runner.accept_review if resolution == "accept" else runner.reject_review

    result = await resolver(
        proposed.review.id,
        request_id=f"resolve-version-race-{resolution}",
        expected_session_version=proposed.session_version,
        session_id="session-1",
    )

    assert result.failure is not None
    assert result.failure.code == "version_conflict"
    assert executor.calls == []


@pytest.mark.asyncio
async def test_review_acceptance_maps_execution_claim_race_to_typed_conflict(
    runner,
    store,
    executor,
    monkeypatch,
) -> None:
    proposed = await runner.run(
        request(request_id="proposal-claim-race", operation_id="test.reviewed_write")
    )

    async def reject_claim(*_args, **_kwargs):
        raise SessionStoreError(SessionStoreErrorCode.REVIEW_ALREADY_RESOLVED)

    monkeypatch.setattr(store, "claim_execution", reject_claim)

    result = await runner.accept_review(
        proposed.review.id,
        request_id="resolve-claim-race",
        expected_session_version=proposed.session_version,
        session_id="session-1",
    )

    assert result.failure is not None
    assert result.failure.code == "review_already_resolved"
    assert executor.calls == []
