from __future__ import annotations

from typing import Any


from ..contracts.failures import FailureKind, FailureSafeDetails, RouteDeckFailure
from ..contracts.operations import (
    DeliveryPhase,
    OperationDisposition,
    OperationEvidence,
    OperationPhase,
    OperationRequest,
    OperationResult,
    OperationSource,
    ReviewPolicy,
)
from ..contracts.session import (
    AttemptTerminalState,
    JournaledExecutionResult,
    OperationAttempt,
    OperationAttemptStatus,
    OperationState,
    RouteDeckSession,
    StoredOperationAttempt,
)
from ..ports.notifier import notify_event_wakeup
from ..state.aggregate import RouteDeckSessionAggregate
from ..state.leases import TurnClaim, TurnLease, TurnOwnerKind

from .runner_base import RunnerRuntimePorts
from .runner_contracts import RouteEntryInvocation


class RunnerSupportMixin(RunnerRuntimePorts):
    async def _lease_for(
        self,
        *,
        request: OperationRequest,
        fingerprint: str,
        turn: TurnLease | None,
    ) -> tuple[TurnLease, bool]:
        if turn is not None:
            if turn.session_id != request.session_id:
                raise ValueError("Turn lease does not belong to the request session")
            await self.store.claim_child_attempt(
                turn,
                request.request_id,
                fingerprint,
            )
            return turn, False
        owner = {
            OperationSource.SURFACE: TurnOwnerKind.SURFACE,
            OperationSource.AGENT: TurnOwnerKind.CHAT,
            OperationSource.SYSTEM: TurnOwnerKind.SYSTEM,
            OperationSource.ROUTE: TurnOwnerKind.NAVIGATION,
        }[request.source]
        lease = await self.store.acquire_turn(
            TurnClaim(
                session_id=request.session_id,
                expected_session_version=request.expected_session_version,
                request_id=request.request_id,
                request_fingerprint=fingerprint,
                owner_kind=owner,
            )
        )
        return lease, True

    def _route_entry_session(
        self,
        session: RouteDeckSession,
        request: OperationRequest,
        invocation: RouteEntryInvocation,
    ) -> RouteDeckSession:
        location = invocation.location
        if location.entry_id is not None:
            raise ValueError(
                "Route entry locations cannot supply canonical history IDs"
            )
        node = next(
            (
                candidate
                for candidate in self.app.app.spec.nodes
                if candidate.id == location.node_id
            ),
            None,
        )
        if node is None or node.entry is None:
            raise ValueError("The matched route has no declared entry operation")
        if node.entry.operation.id != request.operation_id:
            raise ValueError("The route entry operation does not match the request")
        operation = self.app.app.operations.get(request.operation_id)
        if operation is None or self._is_external_write(operation):
            raise ValueError(
                "Route entry operations must be declared non-write operations"
            )
        if operation.review_policy is ReviewPolicy.REQUIRED:
            raise ValueError("Route entry operations cannot require review")
        route_params = {item.name: item.value for item in location.route_params}
        arguments = {
            binding.argument: route_params[binding.parameter]
            for binding in node.entry.bindings
        }
        if request.arguments.to_dict() != arguments:
            raise ValueError("Route entry arguments do not match their exact bindings")
        canonical = location.model_copy(
            update={"entry_id": session.next_history_entry_id}
        )
        return session.model_copy(
            update={
                "current": canonical,
                "back_stack": (*session.back_stack, session.current),
                "forward_stack": (),
                "next_history_entry_id": session.next_history_entry_id + 1,
            }
        )

    async def _commit_supervision_failure(
        self,
        *,
        request: OperationRequest,
        attempt: OperationAttempt,
        session: RouteDeckSession,
        lease: TurnLease,
        disposition: OperationDisposition,
        failure: RouteDeckFailure,
        phases: tuple[OperationPhase, ...],
        review: Any | None = None,
    ) -> OperationResult:
        if disposition not in {
            OperationDisposition.BLOCKED,
            OperationDisposition.NEEDS_INPUT,
            OperationDisposition.FAILED,
        }:
            raise RuntimeError("Supervision failures require a failure disposition")
        failed_attempt = attempt.model_copy(
            update={
                "status": OperationAttemptStatus.FAILED,
                "terminal": AttemptTerminalState.FAILED,
                "failure": failure,
            }
        )
        public_state = session.public_state.model_copy(
            update={
                "status_code": failure.code,
                "status_message": failure.public_message,
                "failure": failure,
            }
        )
        next_state = (
            RouteDeckSessionAggregate(session)
            .set_operation_state(
                OperationState(
                    active_attempt=failed_attempt,
                    pending_review=review,
                )
            )
            .set_public_state(public_state)
            .record_public_events(1)
            .commit()
        )
        event = self._operation_event(next_state, request, public_state)
        final_phases = (
            *phases,
            OperationPhase.STATE_COMMITTED,
            OperationPhase.COMPLETED,
        )
        record = StoredOperationAttempt(
            attempt=failed_attempt,
            review=review,
            disposition=disposition,
            evidence=self._evidence(failed_attempt, final_phases),
            committed_session_version=next_state.session_version,
            committed_projection_version=next_state.projection_version,
            failure=failure,
        )
        snapshot = await self.store.commit_supervision(
            lease,
            session.session_version,
            next_state,
            (event,),
            record,
        )
        await notify_event_wakeup(self.notifier, session.session_id, (event,))
        return self._failure_result(
            request=request,
            fingerprint=attempt.request_fingerprint,
            attempt_id=attempt.attempt_id,
            session_version=snapshot.session_version,
            projection_version=snapshot.projection_version,
            disposition=disposition,
            failure=failure,
            phases=final_phases,
        )

    def _preflight_failure(
        self,
        request: OperationRequest,
        fingerprint: str,
        session: RouteDeckSession,
        *,
        code: str,
        message: str,
    ) -> OperationResult:
        return self._failure_result(
            request=request,
            fingerprint=fingerprint,
            attempt_id=self.id_factory("attempt"),
            session_version=session.session_version,
            projection_version=session.projection_version,
            disposition=OperationDisposition.BLOCKED,
            failure=self._failure(
                request,
                kind=FailureKind.CONTRACT,
                code=code,
                phase="operation_validation",
                message=message,
            ),
            phases=(OperationPhase.RECEIVED,),
        )

    def _failure(
        self,
        request: OperationRequest,
        *,
        kind: FailureKind,
        code: str,
        phase: str,
        message: str,
        delivery_phase: DeliveryPhase | None = None,
        recovery_directive: str | None = None,
    ) -> RouteDeckFailure:
        return RouteDeckFailure(
            kind=kind,
            code=code,
            phase=phase,
            correlation_id=self.id_factory("correlation"),
            operation_id=request.operation_id,
            request_id=request.request_id,
            public_message=message,
            recovery_directive=recovery_directive,
            safe_details=FailureSafeDetails(
                delivery_phase=(
                    delivery_phase.value if delivery_phase is not None else None
                )
            ),
        )

    def _failure_result(
        self,
        *,
        request: OperationRequest,
        fingerprint: str,
        attempt_id: str,
        session_version: int,
        projection_version: int,
        disposition: OperationDisposition,
        failure: RouteDeckFailure,
        phases: tuple[OperationPhase, ...],
        delivery_phase: DeliveryPhase | None = None,
        result: JournaledExecutionResult | None = None,
    ) -> OperationResult:
        return OperationResult(
            disposition=disposition,
            session_id=request.session_id,
            request_id=request.request_id,
            operation_id=request.operation_id,
            session_version=session_version,
            projection_version=projection_version,
            evidence=OperationEvidence(
                source=request.source,
                phases=phases,
                attempt_id=attempt_id,
                request_fingerprint=fingerprint,
                delivery_phase=delivery_phase,
                result_id=result.result_id if result is not None else None,
                result_fingerprint=(
                    result.result_fingerprint if result is not None else None
                ),
            ),
            failure=failure,
        )

    @staticmethod
    def _supervised_phases() -> tuple[OperationPhase, ...]:
        return (
            OperationPhase.RECEIVED,
            OperationPhase.LEASE_ACQUIRED,
            OperationPhase.VALIDATED,
            OperationPhase.CONTEXT_REFRESHED,
            OperationPhase.GUARDS_PASSED,
        )




__all__ = ["RunnerSupportMixin"]
