from __future__ import annotations

import asyncio
from typing import Any, cast


from ..contracts.failures import FailureKind
from ..contracts.operations import (
    DeliveryPhase,
    OperationDisposition,
    OperationOutcome,
    OperationPhase,
    OperationRef,
    OperationRequest,
    OperationResult,
    Operation,
)
from ..contracts.projection import FrozenJsonObject
from ..contracts.session import (
    OperationAttempt,
    OperationAttemptStatus,
    PendingReview,
    RouteDeckSession,
    StoredOperationAttempt,
)
from ..ports.executor import ExecutionContext, OperationBinding, ResolvedEntityInput
from ..state.leases import TurnLease

from .outcome_base import OutcomeRuntimePorts


class OutcomeExecutionMixin(OutcomeRuntimePorts):
    async def _execute_attempt(
        self,
        *,
        request: OperationRequest,
        operation: Operation,
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
        operation: Operation,
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



__all__ = ["OutcomeExecutionMixin"]
