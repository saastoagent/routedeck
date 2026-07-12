from __future__ import annotations

import hashlib
import json
import asyncio
from collections.abc import Mapping, Sequence
from datetime import timedelta
from typing import Any, cast

from jsonschema.validators import validator_for

from ..contracts.events import (
    CanonicalRouteDeckEvent,
    PublicEventPayload,
    RouteDeckEventKind,
)
from ..contracts.effects import SessionEffects
from ..contracts.navigation import DeepLinkPolicy
from ..contracts.failures import FailureKind
from ..contracts.operations import (
    DeliveryPhase,
    EntityInputSpec,
    OperationDisposition,
    OperationEvidence,
    OperationOutcome,
    OperationPhase,
    OperationRef,
    OperationRequest,
    OperationResult,
    OperationReview,
    OperationSpec,
    SafetyClass,
)
from ..contracts.projection import FrozenJsonObject
from ..contracts.session import (
    AttemptTerminalState,
    JournaledExecutionResult,
    Location,
    LocationParameter,
    OperationAttempt,
    OperationAttemptStatus,
    OperationState,
    PendingReview,
    PublicSessionState,
    ResumeCapabilityBinding,
    RouteDeckSession,
    SessionSnapshot,
    StoredOperationAttempt,
)
from ..ports.executor import ExecutionContext, OperationBinding, ResolvedEntityInput
from ..ports.notifier import notify_event_wakeup
from ..state.leases import TurnLease
from ..state.reducer import (
    NodeEntered,
    OperationStateStored,
    PrivateSessionStateStored,
    PublicEventsRecorded,
    PublicSessionStateStored,
    reduce_session_batch,
)
from ..state.effects import session_state_with_effects
from ..state.surfaces import surface_state_for_node


_REQUEST_FINGERPRINT_DOMAIN = "routedeck.operation-request.v1"
_OPERATION_SPEC_DOMAIN = "routedeck.operation-spec.v1"


def canonical_request_fingerprint(
    request: OperationRequest,
    *,
    entity_inputs: Sequence[EntityInputSpec] = (),
    parent_turn_id: str | None = None,
) -> str:
    """Fingerprint request identity without coupling retries to a state version."""

    raw_arguments: object = request.arguments
    if hasattr(raw_arguments, "to_dict"):
        arguments = raw_arguments.to_dict()
    elif isinstance(raw_arguments, Mapping):
        arguments = dict(raw_arguments)
    else:
        raise TypeError("Operation arguments must be a JSON object")
    entity_handles = [
        {
            "argument_name": entity_input.argument_name,
            "entity_kind": entity_input.entity_kind,
            "public_handle": arguments.get(entity_input.argument_name),
        }
        for entity_input in entity_inputs
    ]
    payload = {
        "domain": _REQUEST_FINGERPRINT_DOMAIN,
        "session_id": request.session_id,
        "operation_id": request.operation_id,
        "source": request.source.value,
        "arguments": arguments,
        "entity_handles": entity_handles,
        "parent_turn_id": parent_turn_id,
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"rdop1:{hashlib.sha256(canonical).hexdigest()}"


def canonical_json_fingerprint(domain: str, value: Any) -> str:
    """Hash a typed JSON value under an explicit protocol domain."""

    canonical = json.dumps(
        {"domain": domain, "value": value},
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def canonical_operation_spec_version(operation: OperationSpec) -> str:
    digest = canonical_json_fingerprint(
        _OPERATION_SPEC_DOMAIN,
        operation.model_dump(mode="json"),
    )
    return f"rdopspec1:{digest}"


class OutcomeLifecycleMixin:
    app: Any
    store: Any
    executor: Any
    notifier: Any
    clock: Any
    id_factory: Any
    resume_capability_ttl: timedelta
    _failure: Any
    _failure_result: Any
    _supervised_phases: Any
    _current_node: Any
    _commit_supervision_failure: Any

    async def _execute_attempt(
        self,
        *,
        request: OperationRequest,
        operation: OperationSpec,
        attempt: OperationAttempt,
        session: RouteDeckSession,
        lease: TurnLease,
        provider_values: FrozenJsonObject,
        resolved_entities: tuple[ResolvedEntityInput, ...],
        review: PendingReview | None = None,
        commit_session: RouteDeckSession | None = None,
    ) -> OperationResult:
        commit_base = commit_session or session
        if attempt.context_fingerprint is None:
            raise RuntimeError(
                "Execution requires an authoritative context fingerprint"
            )
        handler = self.app.bindings.handlers.get(OperationRef(id=operation.id))
        if handler is None:
            return await self._commit_supervision_failure(
                request=request,
                attempt=attempt,
                session=commit_base,
                lease=lease,
                disposition=OperationDisposition.BLOCKED,
                failure=self._failure(
                    request,
                    kind=FailureKind.CONTRACT,
                    code="missing_operation_binding",
                    phase="execution_claim",
                    message="The operation has no registered implementation.",
                ),
                phases=self._supervised_phases(),
                review=review,
            )
        binding = OperationBinding(operation=operation, handler=cast(Any, handler))
        claimed_attempt = attempt.model_copy(
            update={"status": OperationAttemptStatus.EXECUTION_CLAIMED}
        )
        claimed_record = StoredOperationAttempt(
            attempt=claimed_attempt,
            review=review,
            disposition=OperationDisposition.PENDING,
            evidence=self._evidence(
                claimed_attempt,
                (*self._supervised_phases(), OperationPhase.EXECUTION_CLAIMED),
            ),
            committed_session_version=session.session_version,
            committed_projection_version=session.projection_version,
        )
        claim = await self.store.claim_execution(lease, claimed_record)
        started_attempt = claimed_attempt.model_copy(
            update={"status": OperationAttemptStatus.TOOL_STARTED}
        )
        started_record = claimed_record.model_copy(
            update={
                "attempt": started_attempt,
                "evidence": self._evidence(
                    started_attempt,
                    (
                        *self._supervised_phases(),
                        OperationPhase.EXECUTION_CLAIMED,
                        OperationPhase.TOOL_STARTED,
                    ),
                ),
            }
        )
        try:
            await self.store.record_execution_started(claim, started_record)
        except Exception:
            failure = self._failure(
                request,
                kind=FailureKind.PERSISTENCE,
                code="execution_start_not_recorded",
                phase="send_boundary",
                message="The operation could not be started safely.",
                delivery_phase=DeliveryPhase.NOT_SENT,
            )
            return self._failure_result(
                request=request,
                fingerprint=attempt.request_fingerprint,
                attempt_id=attempt.attempt_id,
                session_version=session.session_version,
                projection_version=session.projection_version,
                disposition=OperationDisposition.FAILED,
                failure=failure,
                phases=(
                    *self._supervised_phases(),
                    OperationPhase.EXECUTION_CLAIMED,
                ),
                delivery_phase=DeliveryPhase.NOT_SENT,
            )
        context = ExecutionContext(
            session_id=session.session_id,
            request_id=request.request_id,
            attempt_id=attempt.attempt_id,
            node_id=session.current.node_id,
            source=request.source,
            context_fingerprint=attempt.context_fingerprint,
            provider_values=provider_values,
            resolved_entities=resolved_entities,
        )
        try:
            outcome = await self.executor.execute(
                binding,
                request.arguments.to_dict(),
                context,
            )
        except asyncio.CancelledError:
            if self._is_external_write(operation):
                return await self._mark_unknown(
                    request=request,
                    operation=operation,
                    attempt=attempt,
                    claim=claim,
                    reason_code="executor_outcome_unknown",
                    delivery_phase=DeliveryPhase.POSSIBLY_SENT,
                )
            raise
        except Exception:
            if self._is_external_write(operation):
                return await self._mark_unknown(
                    request=request,
                    operation=operation,
                    attempt=attempt,
                    claim=claim,
                    reason_code="executor_outcome_unknown",
                    delivery_phase=DeliveryPhase.POSSIBLY_SENT,
                )
            outcome = OperationOutcome(
                delivery_phase=DeliveryPhase.POSSIBLY_SENT,
                failure=self._failure(
                    request,
                    kind=FailureKind.INTERNAL,
                    code="executor_failed",
                    phase="execute",
                    message="The operation could not be completed.",
                    delivery_phase=DeliveryPhase.POSSIBLY_SENT,
                ),
            )
        if not isinstance(outcome, OperationOutcome):
            if self._is_external_write(operation):
                return await self._mark_unknown(
                    request=request,
                    operation=operation,
                    attempt=attempt,
                    claim=claim,
                    reason_code="invalid_executor_result",
                    delivery_phase=DeliveryPhase.POSSIBLY_SENT,
                )
            outcome = OperationOutcome(
                delivery_phase=DeliveryPhase.POSSIBLY_SENT,
                failure=self._failure(
                    request,
                    kind=FailureKind.PROVIDER_PROTOCOL,
                    code="invalid_executor_result",
                    phase="execute",
                    message="The operation returned an invalid result.",
                    delivery_phase=DeliveryPhase.POSSIBLY_SENT,
                ),
            )
        if not self._valid_outcome_observation(operation, outcome):
            if (
                self._is_external_write(operation)
                and outcome.delivery_phase is not DeliveryPhase.NOT_SENT
            ):
                return await self._mark_unknown(
                    request=request,
                    operation=operation,
                    attempt=attempt,
                    claim=claim,
                    reason_code="invalid_outcome_observation",
                    delivery_phase=outcome.delivery_phase,
                )
            outcome = OperationOutcome(
                delivery_phase=outcome.delivery_phase,
                failure=self._failure(
                    request,
                    kind=FailureKind.PROVIDER_PROTOCOL,
                    code="invalid_outcome_observation",
                    phase="outcome_validation",
                    message="The operation returned an invalid typed observation.",
                    delivery_phase=outcome.delivery_phase,
                ),
            )
        if not self._valid_outcome_effects(
            session=session,
            operation=operation,
            outcome=outcome,
        ):
            if (
                self._is_external_write(operation)
                and outcome.delivery_phase is not DeliveryPhase.NOT_SENT
            ):
                return await self._mark_unknown(
                    request=request,
                    operation=operation,
                    attempt=attempt,
                    claim=claim,
                    reason_code="invalid_session_effects",
                    delivery_phase=outcome.delivery_phase,
                )
            outcome = OperationOutcome(
                delivery_phase=outcome.delivery_phase,
                failure=self._failure(
                    request,
                    kind=FailureKind.PROVIDER_PROTOCOL,
                    code="invalid_session_effects",
                    phase="outcome_validation",
                    message="The operation returned invalid state effects.",
                    delivery_phase=outcome.delivery_phase,
                ),
            )
        if self._unknown_write_outcome(operation, outcome):
            return await self._mark_unknown(
                request=request,
                operation=operation,
                attempt=attempt,
                claim=claim,
                reason_code="external_outcome_unknown",
                delivery_phase=outcome.delivery_phase,
                effects=outcome.effects,
            )

        result = self._journaled_result(request, attempt, operation, outcome)
        recorded_attempt = attempt.model_copy(
            update={"status": OperationAttemptStatus.RESULT_RECORDED}
        )
        recorded_record = started_record.model_copy(
            update={
                "attempt": recorded_attempt,
                "journaled_result": result,
                "evidence": self._evidence(
                    recorded_attempt,
                    (
                        *self._supervised_phases(),
                        OperationPhase.EXECUTION_CLAIMED,
                        OperationPhase.TOOL_STARTED,
                        (
                            OperationPhase.TOOL_SUCCEEDED
                            if result.outcome is not None
                            else OperationPhase.TOOL_FAILED
                        ),
                        OperationPhase.EXECUTION_RESULT_RECORDED,
                    ),
                    result=result,
                ),
                "failure": result.failure,
            }
        )
        try:
            await self.store.record_execution_result(claim, result, recorded_record)
        except Exception:
            if self._is_external_write(operation):
                return await self._mark_unknown(
                    request=request,
                    operation=operation,
                    attempt=attempt,
                    claim=claim,
                    reason_code="execution_result_not_journaled",
                    delivery_phase=outcome.delivery_phase,
                )
            return self._failure_result(
                request=request,
                fingerprint=attempt.request_fingerprint,
                attempt_id=attempt.attempt_id,
                session_version=session.session_version,
                projection_version=session.projection_version,
                disposition=OperationDisposition.FAILED,
                failure=self._failure(
                    request,
                    kind=FailureKind.PERSISTENCE,
                    code="execution_result_not_journaled",
                    phase="result_journal",
                    message="The operation result could not be recorded.",
                ),
                phases=(
                    *self._supervised_phases(),
                    OperationPhase.EXECUTION_CLAIMED,
                    OperationPhase.TOOL_STARTED,
                    OperationPhase.TOOL_SUCCEEDED,
                ),
            )

        if result.failure is not None:
            return await self._commit_failure(
                request=request,
                attempt=attempt,
                session=commit_base,
                claim=claim,
                result=result,
                recorded_record=recorded_record,
            )
        return await self._commit_success(
            request=request,
            operation=operation,
            attempt=attempt,
            session=session,
            commit_session=commit_base,
            claim=claim,
            result=result,
            recorded_record=recorded_record,
        )

    async def _recover_non_write_started(
        self,
        *,
        request: OperationRequest,
        operation: OperationSpec,
        stored: StoredOperationAttempt,
        session: RouteDeckSession,
        claim: Any,
    ) -> OperationResult:
        failure = self._failure(
            request,
            kind=FailureKind.INTERNAL,
            code="execution_interrupted",
            phase="execution_recovery",
            message="The operation was interrupted before its result was recorded.",
            delivery_phase=DeliveryPhase.POSSIBLY_SENT,
        )
        outcome = OperationOutcome(
            delivery_phase=DeliveryPhase.POSSIBLY_SENT,
            failure=failure,
        )
        result = self._journaled_result(
            request,
            stored.attempt,
            operation,
            outcome,
        )
        recorded_attempt = stored.attempt.model_copy(
            update={
                "status": OperationAttemptStatus.RESULT_RECORDED,
                "failure": failure,
            }
        )
        recorded_record = stored.model_copy(
            update={
                "attempt": recorded_attempt,
                "journaled_result": result,
                "evidence": self._evidence(
                    recorded_attempt,
                    (
                        *self._supervised_phases(),
                        OperationPhase.EXECUTION_CLAIMED,
                        OperationPhase.TOOL_STARTED,
                        OperationPhase.TOOL_FAILED,
                        OperationPhase.EXECUTION_RESULT_RECORDED,
                    ),
                    result=result,
                ),
                "failure": failure,
            }
        )
        await self.store.record_execution_result(claim, result, recorded_record)
        return await self._commit_failure(
            request=request,
            attempt=stored.attempt,
            session=session,
            claim=claim,
            result=result,
            recorded_record=recorded_record,
        )

    async def _commit_success(
        self,
        *,
        request: OperationRequest,
        operation: OperationSpec,
        attempt: OperationAttempt,
        session: RouteDeckSession,
        commit_session: RouteDeckSession | None = None,
        claim: Any,
        result: JournaledExecutionResult,
        recorded_record: StoredOperationAttempt,
    ) -> OperationResult:
        commit_base = commit_session or session
        if result.outcome is None:
            raise RuntimeError("Successful journal result is missing an outcome")
        transition = self._transition_for(
            node_id=session.current.node_id,
            operation_id=operation.id,
            outcome=result.outcome,
        )
        if transition is None:
            if self._is_external_write(operation):
                failure = self._failure(
                    request,
                    kind=FailureKind.EXTERNAL_OUTCOME_UNKNOWN,
                    code="external_outcome_unknown",
                    phase="outcome_validation",
                    message="The external outcome is uncertain; do not submit again.",
                    delivery_phase=result.delivery_phase,
                )
                # A typed result was journaled, so transition absence is a contract
                # failure rather than permission to call the handler again.
                return self._failure_result(
                    request=request,
                    fingerprint=attempt.request_fingerprint,
                    attempt_id=attempt.attempt_id,
                    session_version=session.session_version,
                    projection_version=session.projection_version,
                    disposition=OperationDisposition.FAILED,
                    failure=failure,
                    phases=(
                        *self._supervised_phases(),
                        OperationPhase.EXECUTION_CLAIMED,
                        OperationPhase.TOOL_STARTED,
                        OperationPhase.TOOL_SUCCEEDED,
                        OperationPhase.EXECUTION_RESULT_RECORDED,
                    ),
                )
            raise RuntimeError("Declared operation outcome has no compiled transition")
        replayed_outcome = OperationOutcome(
            outcome=result.outcome,
            delivery_phase=result.delivery_phase,
            observation=result.observation,
            effects=result.effects,
        )
        if not self._valid_outcome_effects(
            session=session,
            operation=operation,
            outcome=replayed_outcome,
        ):
            raise RuntimeError(
                "Journaled execution result contains invalid state effects"
            )
        completed_attempt = attempt.model_copy(
            update={
                "status": OperationAttemptStatus.COMPLETED,
                "terminal": AttemptTerminalState.COMPLETED,
            }
        )
        operation_state = OperationState(
            active_attempt=completed_attempt,
            pending_review=recorded_record.review,
            journaled_result=result,
        )
        private_state, effected_public_state = session_state_with_effects(
            session,
            result.effects,
        )
        target_node = next(
            node for node in self.app.app.spec.nodes if node.id == transition.target.id
        )
        target_surface_state = surface_state_for_node(
            self.app.app,
            effected_public_state.surface_state,
            target_node,
        )
        target_route_params = (
            tuple(
                LocationParameter(name=item.name, value=item.value)
                for item in result.effects.route_params
            )
            if result.effects.route_params is not None
            else (
                session.current.route_params
                if transition.target.id == session.current.node_id
                else ()
            )
        )
        if target_node.route.deep_link_policy is DeepLinkPolicy.SESSION_BOUND:
            now = self.clock.now()
            capabilities = tuple(
                capability
                for capability in private_state.resume_capabilities
                if capability.expires_at > now
                and not (
                    capability.node_id == target_node.id
                    and capability.route_params == target_route_params
                )
            )
            private_state = private_state.model_copy(
                update={
                    "resume_capabilities": (
                        *capabilities,
                        ResumeCapabilityBinding(
                            handle=self.id_factory("resume"),
                            session_id=session.session_id,
                            node_id=target_node.id,
                            expires_at=now + self.resume_capability_ttl,
                            route_params=target_route_params,
                        ),
                    )
                }
            )
        recovered_operation_ids = {
            candidate.id
            for candidate in self.app.app.operations.values()
            if operation.id
            in {recovery.id for recovery in candidate.unknown_recovery_operation_refs}
        }
        public_state = effected_public_state.model_copy(
            update={
                "surface_state": target_surface_state,
                "status_code": "ready",
                "status_message": None,
                "failure": None,
                "disabled_operation_ids": tuple(
                    operation_id
                    for operation_id in effected_public_state.disabled_operation_ids
                    if operation_id not in recovered_operation_ids
                ),
            }
        )
        reducer_events: list[object] = []
        if (
            transition.target.id != session.current.node_id
            or result.effects.route_params is not None
        ):
            reducer_events.append(
                NodeEntered(
                    location=Location(
                        node_id=transition.target.id,
                        route_params=target_route_params,
                    )
                )
            )
        reducer_events.extend(
            (
                PrivateSessionStateStored(state=private_state),
                OperationStateStored(operation=operation_state),
                PublicSessionStateStored(state=public_state),
                PublicEventsRecorded(count=1),
            )
        )
        next_state = reduce_session_batch(session, cast(Any, tuple(reducer_events)))
        if commit_session is not None and session.current != commit_base.current:
            next_state = next_state.model_copy(
                update={
                    "session_version": commit_base.session_version + 1,
                    "projection_version": commit_base.projection_version + 1,
                    "event_cursor": commit_base.event_cursor + 1,
                }
            )
        event = self._operation_event(next_state, request, public_state)
        final_record = recorded_record.model_copy(
            update={
                "attempt": completed_attempt,
                "disposition": OperationDisposition.COMPLETED,
                "evidence": self._evidence(
                    completed_attempt,
                    (
                        *self._supervised_phases(),
                        OperationPhase.EXECUTION_CLAIMED,
                        OperationPhase.TOOL_STARTED,
                        OperationPhase.TOOL_SUCCEEDED,
                        OperationPhase.EXECUTION_RESULT_RECORDED,
                        OperationPhase.STATE_COMMITTED,
                        OperationPhase.COMPLETED,
                    ),
                    result=result,
                ),
                "committed_session_version": next_state.session_version,
                "committed_projection_version": next_state.projection_version,
            }
        )
        try:
            snapshot = await self.store.commit_attempt(
                claim,
                commit_base.session_version,
                next_state,
                (event,),
                final_record,
            )
        except Exception:
            return self._state_commit_failure_result(
                request=request,
                attempt=attempt,
                session=commit_base,
                result=result,
                tool_phase=OperationPhase.TOOL_SUCCEEDED,
            )
        await notify_event_wakeup(self.notifier, session.session_id, (event,))
        stored = await self.store.find_attempt(session.session_id, request.request_id)
        if stored is not None:
            replay = self._result_from_stored(stored, session_id=session.session_id)
            if replay is not None:
                return replay
        return self._completed_result(request, attempt, result, snapshot)

    async def _commit_failure(
        self,
        *,
        request: OperationRequest,
        attempt: OperationAttempt,
        session: RouteDeckSession,
        claim: Any,
        result: JournaledExecutionResult,
        recorded_record: StoredOperationAttempt,
    ) -> OperationResult:
        if result.failure is None:
            raise RuntimeError("Failed journal result is missing a failure")
        failed_attempt = attempt.model_copy(
            update={
                "status": OperationAttemptStatus.FAILED,
                "terminal": AttemptTerminalState.FAILED,
                "failure": result.failure,
            }
        )
        public_state = session.public_state.model_copy(
            update={
                "status_code": result.failure.code,
                "status_message": result.failure.public_message,
                "failure": result.failure,
            }
        )
        next_state = reduce_session_batch(
            session,
            (
                OperationStateStored(
                    operation=OperationState(
                        active_attempt=failed_attempt,
                        pending_review=recorded_record.review,
                        journaled_result=result,
                    )
                ),
                PublicSessionStateStored(state=public_state),
                PublicEventsRecorded(count=1),
            ),
        )
        event = self._operation_event(next_state, request, public_state)
        final_record = recorded_record.model_copy(
            update={
                "attempt": failed_attempt,
                "disposition": OperationDisposition.FAILED,
                "evidence": self._evidence(
                    failed_attempt,
                    (
                        *self._supervised_phases(),
                        OperationPhase.EXECUTION_CLAIMED,
                        OperationPhase.TOOL_STARTED,
                        OperationPhase.TOOL_FAILED,
                        OperationPhase.EXECUTION_RESULT_RECORDED,
                        OperationPhase.STATE_COMMITTED,
                        OperationPhase.COMPLETED,
                    ),
                    result=result,
                ),
                "committed_session_version": next_state.session_version,
                "committed_projection_version": next_state.projection_version,
                "failure": result.failure,
            }
        )
        try:
            snapshot = await self.store.commit_attempt(
                claim,
                session.session_version,
                next_state,
                (event,),
                final_record,
            )
        except Exception:
            return self._state_commit_failure_result(
                request=request,
                attempt=attempt,
                session=session,
                result=result,
                tool_phase=OperationPhase.TOOL_FAILED,
            )
        await notify_event_wakeup(self.notifier, session.session_id, (event,))
        return self._failure_result(
            request=request,
            fingerprint=attempt.request_fingerprint,
            attempt_id=attempt.attempt_id,
            session_version=snapshot.session_version,
            projection_version=snapshot.projection_version,
            disposition=OperationDisposition.FAILED,
            failure=result.failure,
            phases=(
                *self._supervised_phases(),
                OperationPhase.EXECUTION_CLAIMED,
                OperationPhase.TOOL_STARTED,
                OperationPhase.TOOL_FAILED,
                OperationPhase.EXECUTION_RESULT_RECORDED,
                OperationPhase.STATE_COMMITTED,
                OperationPhase.COMPLETED,
            ),
            delivery_phase=result.delivery_phase,
            result=result,
        )

    async def _mark_unknown(
        self,
        *,
        request: OperationRequest,
        operation: OperationSpec,
        attempt: OperationAttempt,
        claim: Any,
        reason_code: str,
        delivery_phase: DeliveryPhase,
        effects: SessionEffects | None = None,
    ) -> OperationResult:
        if operation.unknown_recovery_directive is None:
            raise RuntimeError(
                "Unknown external outcomes require an explicit recovery directive"
            )
        failure = self._failure(
            request,
            kind=FailureKind.EXTERNAL_OUTCOME_UNKNOWN,
            code="external_outcome_unknown",
            phase=reason_code,
            message="The external outcome is uncertain; do not submit again.",
            delivery_phase=delivery_phase,
            recovery_directive=operation.unknown_recovery_directive,
        )
        current = (await self.store.load(request.session_id)).state
        unknown_effects = effects or SessionEffects()
        if not unknown_effects.is_empty:
            failure_outcome = OperationOutcome(
                delivery_phase=delivery_phase,
                failure=failure,
                effects=unknown_effects,
            )
            if not self._valid_outcome_effects(
                session=current,
                operation=operation,
                outcome=failure_outcome,
            ):
                raise RuntimeError("Unknown outcome contains invalid recovery effects")
        private_state, effected_public_state = session_state_with_effects(
            current,
            unknown_effects,
        )
        current_node = next(
            node
            for node in self.app.app.spec.nodes
            if node.id == current.current.node_id
        )
        current_surface_ids = {
            surface.id for surface in current_node.surfaces.declared_surfaces()
        }
        unknown_attempt = attempt.model_copy(
            update={
                "status": OperationAttemptStatus.EXTERNAL_OUTCOME_UNKNOWN,
                "terminal": AttemptTerminalState.EXTERNAL_OUTCOME_UNKNOWN,
                "failure": failure,
            }
        )
        disabled = tuple(
            dict.fromkeys(
                (*current.public_state.disabled_operation_ids, request.operation_id)
            )
        )
        public_state = effected_public_state.model_copy(
            update={
                "surface_state": tuple(
                    surface
                    for surface in effected_public_state.surface_state
                    if surface.surface_id in current_surface_ids
                ),
                "status_code": "external_outcome_unknown",
                "status_message": failure.public_message,
                "failure": failure,
                "disabled_operation_ids": disabled,
            }
        )
        existing = await self.store.find_attempt(request.session_id, request.request_id)
        base_record = existing or StoredOperationAttempt(attempt=unknown_attempt)
        next_state = reduce_session_batch(
            current,
            (
                OperationStateStored(
                    operation=OperationState(
                        active_attempt=unknown_attempt,
                        pending_review=base_record.review,
                    )
                ),
                PrivateSessionStateStored(state=private_state),
                PublicSessionStateStored(state=public_state),
                PublicEventsRecorded(count=1),
            ),
        )
        event = self._operation_event(next_state, request, public_state)
        final_record = base_record.model_copy(
            update={
                "attempt": unknown_attempt,
                "disposition": OperationDisposition.EXTERNAL_OUTCOME_UNKNOWN,
                "evidence": self._evidence(
                    unknown_attempt,
                    (
                        *self._supervised_phases(),
                        OperationPhase.EXECUTION_CLAIMED,
                        OperationPhase.TOOL_STARTED,
                        OperationPhase.TOOL_OUTCOME_UNKNOWN,
                        OperationPhase.STATE_COMMITTED,
                        OperationPhase.COMPLETED,
                    ),
                    delivery_phase=delivery_phase,
                ),
                "committed_session_version": next_state.session_version,
                "committed_projection_version": next_state.projection_version,
                "failure": failure,
            }
        )
        snapshot = await self.store.mark_external_outcome_unknown(
            claim,
            current.session_version,
            final_record,
            next_state,
            (event,),
        )
        await notify_event_wakeup(self.notifier, request.session_id, (event,))
        stored = await self.store.find_attempt(request.session_id, request.request_id)
        if stored is not None:
            replay = self._result_from_stored(stored, session_id=request.session_id)
            if replay is not None:
                return replay
        return self._failure_result(
            request=request,
            fingerprint=attempt.request_fingerprint,
            attempt_id=attempt.attempt_id,
            session_version=snapshot.session_version,
            projection_version=snapshot.projection_version,
            disposition=OperationDisposition.EXTERNAL_OUTCOME_UNKNOWN,
            failure=failure,
            phases=(
                *self._supervised_phases(),
                OperationPhase.EXECUTION_CLAIMED,
                OperationPhase.TOOL_STARTED,
                OperationPhase.TOOL_OUTCOME_UNKNOWN,
                OperationPhase.STATE_COMMITTED,
                OperationPhase.COMPLETED,
            ),
            delivery_phase=delivery_phase,
        )

    def _journaled_result(
        self,
        request: OperationRequest,
        attempt: OperationAttempt,
        operation: OperationSpec,
        outcome: OperationOutcome,
    ) -> JournaledExecutionResult:
        value = {
            "attempt_id": attempt.attempt_id,
            "request_id": request.request_id,
            "operation_id": operation.id,
            "outcome": outcome.outcome,
            "delivery_phase": outcome.delivery_phase.value,
            "observation": outcome.observation.to_dict(),
            "effects": outcome.effects.model_dump(mode="json"),
            "failure": (
                outcome.failure.model_dump(mode="json")
                if outcome.failure is not None
                else None
            ),
        }
        return JournaledExecutionResult(
            result_id=self.id_factory("result"),
            attempt_id=attempt.attempt_id,
            request_id=request.request_id,
            operation_id=operation.id,
            outcome=outcome.outcome,
            delivery_phase=outcome.delivery_phase,
            result_fingerprint=canonical_json_fingerprint(
                "routedeck.execution-result.v1",
                value,
            ),
            observation=outcome.observation,
            effects=outcome.effects,
            failure=outcome.failure,
        )

    def _valid_outcome_effects(
        self,
        *,
        session: RouteDeckSession,
        operation: OperationSpec,
        outcome: OperationOutcome,
    ) -> bool:
        if outcome.outcome is None:
            if outcome.effects.is_empty:
                return True
            if (
                not self._is_external_write(operation)
                or outcome.failure is None
                or outcome.failure.kind is FailureKind.BUSINESS
                or outcome.delivery_phase is DeliveryPhase.NOT_SENT
                or outcome.effects.route_params is not None
            ):
                return False
            current = next(
                (
                    node
                    for node in self.app.app.spec.nodes
                    if node.id == session.current.node_id
                ),
                None,
            )
            if current is None:
                return False
            return self._valid_effects_for_node(
                session=session,
                effects=outcome.effects,
                target=current,
                allow_undeclared_empty_replacements=False,
            )
        transition = self._transition_for(
            node_id=session.current.node_id,
            operation_id=operation.id,
            outcome=outcome.outcome,
        )
        if transition is None:
            return outcome.effects.is_empty
        target = next(
            (
                node
                for node in self.app.app.spec.nodes
                if node.id == transition.target.id
            ),
            None,
        )
        if target is None:
            return False

        if not self._valid_effects_for_node(
            session=session,
            effects=outcome.effects,
            target=target,
            allow_undeclared_empty_replacements=True,
        ):
            return False

        expected_route_names = set(self.app.app.routes.path_parameter_names(target.id))
        if outcome.effects.route_params is None:
            if transition.target.id != session.current.node_id and expected_route_names:
                return False
        else:
            route_values = {
                parameter.name: parameter.value
                for parameter in outcome.effects.route_params
            }
            if set(route_values) != expected_route_names:
                return False
            try:
                self.app.app.routes.validate_path_bindings(
                    target.id,
                    route_values,
                )
            except Exception:
                return False

        try:
            session_state_with_effects(session, outcome.effects)
        except Exception:
            return False
        return True

    def _valid_effects_for_node(
        self,
        *,
        session: RouteDeckSession,
        effects: SessionEffects,
        target: Any,
        allow_undeclared_empty_replacements: bool,
    ) -> bool:
        target_entity_kinds = {
            provider.entity_kind for provider in target.entity_providers
        }
        target_operation_ids = {item.id for item in target.operations}
        for replacement in effects.replace_entities:
            if replacement.entity_kind not in target_entity_kinds and not (
                allow_undeclared_empty_replacements and not replacement.bindings
            ):
                return False
            for binding in replacement.bindings:
                if not set(binding.allowed_operation_ids) <= target_operation_ids:
                    return False

        surfaces = {
            surface.id: surface for surface in target.surfaces.declared_surfaces()
        }
        for update in effects.surface_updates:
            surface = surfaces.get(update.surface_id)
            if surface is None:
                return False
            values = {value.name: value.value.to_python() for value in update.values}
            if not self._valid_json_object(
                surface.public_props_schema_value(),
                values,
            ):
                return False
        try:
            session_state_with_effects(session, effects)
        except Exception:
            return False
        return True

    def _transition_for(
        self,
        *,
        node_id: str,
        operation_id: str,
        outcome: str,
    ) -> Any | None:
        return next(
            (
                candidate
                for candidate in self.app.app.spec.transitions
                if candidate.source.id == node_id
                and candidate.operation.id == operation_id
                and candidate.outcome == outcome
            ),
            None,
        )

    def _unknown_write_outcome(
        self,
        operation: OperationSpec,
        outcome: OperationOutcome,
    ) -> bool:
        if not self._is_external_write(operation):
            return False
        if outcome.delivery_phase is DeliveryPhase.POSSIBLY_SENT:
            return True
        if (
            outcome.delivery_phase is DeliveryPhase.RESPONSE_RECEIVED
            and outcome.failure is not None
            and outcome.failure.kind is not FailureKind.BUSINESS
        ):
            return True
        if outcome.outcome is not None and outcome.outcome not in operation.outcomes:
            return outcome.delivery_phase is DeliveryPhase.RESPONSE_RECEIVED
        return False

    @staticmethod
    def _valid_outcome_observation(
        operation: OperationSpec,
        outcome: OperationOutcome,
    ) -> bool:
        values = outcome.observation.to_dict()
        if outcome.outcome is None:
            return not values
        schema = operation.outcome_schema_value(outcome.outcome)
        if schema is None:
            return not values
        return OutcomeLifecycleMixin._valid_json_object(schema, values)

    @staticmethod
    def _valid_json_object(
        schema: Mapping[str, object],
        values: Mapping[str, object],
    ) -> bool:
        if not schema:
            return not values
        try:
            schema_value = cast(dict[Any, Any], schema)
            validator_type = validator_for(schema_value)
            validator_type.check_schema(schema_value)
            return validator_type(schema_value).is_valid(cast(Any, values))
        except Exception:
            return False

    @staticmethod
    def _is_external_write(operation: OperationSpec) -> bool:
        return operation.safety_class in {
            SafetyClass.WRITE_EXTERNAL,
            SafetyClass.DESTRUCTIVE,
            SafetyClass.CREDENTIAL,
            SafetyClass.ADMIN,
        }

    def _state_commit_failure_result(
        self,
        *,
        request: OperationRequest,
        attempt: OperationAttempt,
        session: RouteDeckSession,
        result: JournaledExecutionResult,
        tool_phase: OperationPhase,
    ) -> OperationResult:
        failure = self._failure(
            request,
            kind=FailureKind.PERSISTENCE,
            code="state_commit_failed",
            phase="state_commit",
            message="The recorded operation result could not be applied yet.",
            delivery_phase=result.delivery_phase,
        )
        return self._failure_result(
            request=request,
            fingerprint=attempt.request_fingerprint,
            attempt_id=attempt.attempt_id,
            session_version=session.session_version,
            projection_version=session.projection_version,
            disposition=OperationDisposition.FAILED,
            failure=failure,
            phases=(
                *self._supervised_phases(),
                OperationPhase.EXECUTION_CLAIMED,
                OperationPhase.TOOL_STARTED,
                tool_phase,
                OperationPhase.EXECUTION_RESULT_RECORDED,
            ),
            delivery_phase=result.delivery_phase,
            result=result,
        )

    @staticmethod
    def _evidence(
        attempt: OperationAttempt,
        phases: tuple[OperationPhase, ...],
        *,
        result: JournaledExecutionResult | None = None,
        delivery_phase: DeliveryPhase | None = None,
    ) -> OperationEvidence:
        return OperationEvidence(
            source=attempt.source,
            phases=phases,
            attempt_id=attempt.attempt_id,
            request_fingerprint=attempt.request_fingerprint,
            delivery_phase=(
                result.delivery_phase if result is not None else delivery_phase
            ),
            result_id=result.result_id if result is not None else None,
            result_fingerprint=(
                result.result_fingerprint if result is not None else None
            ),
        )

    def _completed_result(
        self,
        request: OperationRequest,
        attempt: OperationAttempt,
        result: JournaledExecutionResult,
        snapshot: SessionSnapshot,
    ) -> OperationResult:
        if result.outcome is None:
            raise RuntimeError("Completed result is missing an outcome")
        return OperationResult(
            disposition=OperationDisposition.COMPLETED,
            session_id=request.session_id,
            request_id=request.request_id,
            operation_id=request.operation_id,
            session_version=snapshot.session_version,
            projection_version=snapshot.projection_version,
            evidence=OperationEvidence(
                source=request.source,
                phases=(
                    *self._supervised_phases(),
                    OperationPhase.EXECUTION_CLAIMED,
                    OperationPhase.TOOL_STARTED,
                    OperationPhase.TOOL_SUCCEEDED,
                    OperationPhase.EXECUTION_RESULT_RECORDED,
                    OperationPhase.STATE_COMMITTED,
                    OperationPhase.COMPLETED,
                ),
                attempt_id=attempt.attempt_id,
                request_fingerprint=attempt.request_fingerprint,
                delivery_phase=result.delivery_phase,
                result_id=result.result_id,
                result_fingerprint=result.result_fingerprint,
            ),
            outcome=result.outcome,
        )

    def _result_from_stored(
        self,
        stored: StoredOperationAttempt,
        *,
        session_id: str,
    ) -> OperationResult | None:
        if (
            stored.disposition is None
            or stored.evidence is None
            or stored.committed_session_version is None
            or stored.committed_projection_version is None
        ):
            return None
        review = None
        if (
            stored.review is not None
            and stored.disposition is OperationDisposition.REQUIRES_REVIEW
        ):
            review = OperationReview(
                id=stored.review.review_id,
                expires_at=stored.review.expires_at,
            )
        outcome = None
        failure = None
        if stored.disposition is not OperationDisposition.PENDING:
            outcome = (
                stored.journaled_result.outcome
                if stored.journaled_result is not None
                else None
            )
            failure = stored.failure or (
                stored.journaled_result.failure
                if stored.journaled_result is not None
                else None
            )
        return OperationResult(
            disposition=stored.disposition,
            session_id=session_id,
            request_id=stored.attempt.request_id,
            operation_id=stored.attempt.operation_id,
            session_version=stored.committed_session_version,
            projection_version=stored.committed_projection_version,
            evidence=stored.evidence,
            review=review,
            outcome=outcome,
            failure=failure,
        )

    def _operation_event(
        self,
        state: RouteDeckSession,
        request: OperationRequest,
        public_state: PublicSessionState,
    ) -> CanonicalRouteDeckEvent:
        return CanonicalRouteDeckEvent(
            event_id=self.id_factory("event"),
            cursor=state.event_cursor,
            event_type=RouteDeckEventKind.OPERATION_CHANGED,
            session_id=state.session_id,
            session_version=state.session_version,
            projection_version=state.projection_version,
            created_at=self.clock.now(),
            payload=PublicEventPayload(
                node_id=state.current.node_id,
                operation_id=request.operation_id,
                request_id=request.request_id,
                status_code=public_state.status_code,
                failure=public_state.failure,
            ),
        )


__all__ = [
    "OutcomeLifecycleMixin",
    "canonical_json_fingerprint",
    "canonical_operation_spec_version",
    "canonical_request_fingerprint",
]
