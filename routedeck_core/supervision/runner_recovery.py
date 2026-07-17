from __future__ import annotations

from typing import Any


from ..contracts.failures import FailureKind
from ..contracts.operations import (
    DeliveryPhase,
    OperationDisposition,
    OperationPhase,
    OperationRequest,
    OperationResult,
    Operation,
)
from ..contracts.session import (
    AttemptTerminalState,
    OperationAttemptStatus,
    OperationState,
    RouteDeckSession,
    StoredOperationAttempt,
)
from ..ports.notifier import notify_event_wakeup
from ..ports.session_store import (
    SessionStoreError,
)
from ..state.aggregate import RouteDeckSessionAggregate
from ..state.leases import TurnClaim, TurnOwnerKind

from .runner_base import RunnerRuntimePorts
from .runner_contracts import RouteEntryInvocation


class RunnerRecoveryMixin(RunnerRuntimePorts):
    async def _recover_stored_attempt(
        self,
        *,
        request: OperationRequest,
        operation: Operation | None,
        stored: StoredOperationAttempt,
        fingerprint: str,
        route_entry: RouteEntryInvocation | None,
    ) -> OperationResult:
        current = (await self.store.load(request.session_id)).state
        try:
            lease = await self.store.acquire_turn(
                TurnClaim(
                    session_id=request.session_id,
                    expected_session_version=current.session_version,
                    request_id=request.request_id,
                    request_fingerprint=fingerprint,
                    owner_kind=TurnOwnerKind.SYSTEM,
                )
            )
        except SessionStoreError as error:
            if (
                error.code.value == "operation_in_progress"
                and stored.disposition is OperationDisposition.PENDING
            ):
                replay = self._result_from_stored(
                    stored,
                    session_id=request.session_id,
                )
                if replay is None:
                    raise RuntimeError(
                        "Pending attempts require observed durable versions"
                    ) from error
                return replay
            return self._store_conflict_result(
                request=request,
                fingerprint=fingerprint,
                error=error,
            )
        try:
            claim = await self.store.recover_execution_claim(
                lease, stored.attempt.attempt_id
            )
            commit_session = (await self.store.load(request.session_id)).state
            session = (
                self._route_entry_session(commit_session, request, route_entry)
                if route_entry is not None
                else commit_session
            )
            if stored.journaled_result is not None:
                if operation is None:
                    raise RuntimeError(
                        "Stored execution cannot recover without its operation spec"
                    )
                if stored.journaled_result.failure is not None:
                    return await self._commit_failure(
                        request=request,
                        attempt=stored.attempt,
                        session=commit_session,
                        claim=claim,
                        result=stored.journaled_result,
                        recorded_record=stored,
                    )
                return await self._commit_success(
                    request=request,
                    operation=operation,
                    attempt=stored.attempt,
                    session=session,
                    commit_session=commit_session,
                    claim=claim,
                    result=stored.journaled_result,
                    recorded_record=stored,
                )
            phases = stored.evidence.phases if stored.evidence is not None else ()
            if (
                stored.attempt.status is OperationAttemptStatus.TOOL_STARTED
                or OperationPhase.TOOL_STARTED in phases
            ):
                if operation is None:
                    raise RuntimeError(
                        "Stored execution cannot recover without its operation spec"
                    )
                if not self._is_external_write(operation):
                    return await self._recover_non_write_started(
                        request=request,
                        operation=operation,
                        stored=stored,
                        session=commit_session,
                        claim=claim,
                    )
                return await self._mark_unknown(
                    request=request,
                    operation=operation,
                    attempt=stored.attempt,
                    claim=claim,
                    reason_code="tool_started_without_journal",
                    delivery_phase=DeliveryPhase.POSSIBLY_SENT,
                )
            return await self._commit_not_sent_recovery(
                request=request,
                stored=stored,
                session=commit_session,
                claim=claim,
            )
        finally:
            await self.store.release_turn(lease)

    async def _commit_not_sent_recovery(
        self,
        *,
        request: OperationRequest,
        stored: StoredOperationAttempt,
        session: RouteDeckSession,
        claim: Any,
    ) -> OperationResult:
        failure = self._failure(
            request,
            kind=FailureKind.PERSISTENCE,
            code="execution_interrupted_not_sent",
            phase="execution_recovery",
            message="The operation was interrupted before it was sent.",
            delivery_phase=DeliveryPhase.NOT_SENT,
        )
        attempt = stored.attempt.model_copy(
            update={
                "status": OperationAttemptStatus.INTERRUPTED,
                "terminal": AttemptTerminalState.INTERRUPTED,
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
            .set_operation_state(OperationState(active_attempt=attempt))
            .set_public_state(public_state)
            .record_public_events(1)
            .commit()
        )
        event = self._operation_event(next_state, request, public_state)
        phases = (
            *self._supervised_phases(),
            OperationPhase.EXECUTION_CLAIMED,
            OperationPhase.STATE_COMMITTED,
            OperationPhase.COMPLETED,
        )
        evidence = self._evidence(
            attempt,
            phases,
            delivery_phase=DeliveryPhase.NOT_SENT,
        )
        record = stored.model_copy(
            update={
                "attempt": attempt,
                "disposition": OperationDisposition.FAILED,
                "evidence": evidence,
                "committed_session_version": next_state.session_version,
                "committed_projection_version": next_state.projection_version,
                "failure": failure,
            }
        )
        snapshot = await self.store.commit_attempt(
            claim,
            session.session_version,
            next_state,
            (event,),
            record,
        )
        await notify_event_wakeup(self.notifier, session.session_id, (event,))
        return self._failure_result(
            request=request,
            fingerprint=stored.attempt.request_fingerprint,
            attempt_id=stored.attempt.attempt_id,
            session_version=snapshot.session_version,
            projection_version=snapshot.projection_version,
            disposition=OperationDisposition.FAILED,
            failure=failure,
            phases=phases,
            delivery_phase=DeliveryPhase.NOT_SENT,
        )



__all__ = ["RunnerRecoveryMixin"]
