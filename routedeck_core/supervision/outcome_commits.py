from __future__ import annotations

from typing import Any


from ..contracts.effects import SessionEffects
from ..contracts.navigation import DeepLinkPolicy
from ..contracts.failures import FailureKind
from ..contracts.operations import (
    DeliveryPhase,
    OperationDisposition,
    OperationOutcome,
    OperationPhase,
    OperationRequest,
    OperationResult,
    Operation,
)
from ..contracts.session import (
    AttemptTerminalState,
    JournaledExecutionResult,
    Location,
    LocationParameter,
    OperationAttempt,
    OperationAttemptStatus,
    OperationState,
    ResumeCapabilityBinding,
    RouteDeckSession,
    StoredOperationAttempt,
)
from ..ports.notifier import notify_event_wakeup
from ..state.aggregate import RouteDeckSessionAggregate
from ..state.effects import session_state_with_effects
from ..state.surfaces import surface_state_for_node

from .outcome_base import OutcomeRuntimePorts


class OutcomeCommitMixin(OutcomeRuntimePorts):
    async def _commit_success(
        self,
        *,
        request: OperationRequest,
        operation: Operation,
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
            node for node in self.app.app.graph.nodes if node.id == transition.target.id
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
        aggregate = RouteDeckSessionAggregate(session)
        if (
            transition.target.id != session.current.node_id
            or result.effects.route_params is not None
        ):
            aggregate.enter_node(
                Location(
                    node_id=transition.target.id,
                    route_params=target_route_params,
                )
            )
        next_state = (
            aggregate.set_private_state(private_state)
            .set_operation_state(operation_state)
            .set_public_state(public_state)
            .record_public_events(1)
            .commit()
        )
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
        next_state = (
            RouteDeckSessionAggregate(session)
            .set_operation_state(
                OperationState(
                    active_attempt=failed_attempt,
                    pending_review=recorded_record.review,
                    journaled_result=result,
                )
            )
            .set_public_state(public_state)
            .record_public_events(1)
            .commit()
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
        operation: Operation,
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
            for node in self.app.app.graph.nodes
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
        next_state = (
            RouteDeckSessionAggregate(current)
            .set_operation_state(
                OperationState(
                    active_attempt=unknown_attempt,
                    pending_review=base_record.review,
                )
            )
            .set_private_state(private_state)
            .set_public_state(public_state)
            .record_public_events(1)
            .commit()
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



__all__ = ["OutcomeCommitMixin"]
