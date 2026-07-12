from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

from ..contracts.conversation import (
    ConversationRole,
    ConversationToolCall,
    FinalizedConversationTurn,
)
from ..contracts.effects import PublicSurfaceEffect, SessionEffects
from ..contracts.failures import FailureKind
from ..contracts.operations import (
    OperationDisposition,
    OperationPhase,
    OperationRequest,
    OperationResult,
    OperationReview,
    OperationSource,
    OperationSpec,
)
from ..contracts.mutations import MutationCommit, MutationKind, MutationStatus
from ..contracts.projection import FrozenJson, FrozenJsonObject, PublicValue
from ..contracts.session import (
    AttemptTerminalState,
    OperationAttempt,
    OperationAttemptStatus,
    OperationState,
    PendingReview,
    ReviewResolution,
    RouteDeckSession,
    StoredOperationAttempt,
)
from ..ports.session_store import SessionStoreError, SessionStoreErrorCode
from ..ports.notifier import notify_event_wakeup
from ..state.leases import TurnClaim, TurnLease, TurnOwnerKind
from ..state.effects import session_state_with_effects
from ..state.reducer import (
    ConversationTurnsStored,
    OperationStateStored,
    PublicEventsRecorded,
    PublicSessionStateStored,
    reduce_session_batch,
)
from .outcomes import (
    canonical_json_fingerprint,
    canonical_operation_spec_version,
    canonical_request_fingerprint,
)


class ReviewLifecycleMixin:
    app: Any
    store: Any
    notifier: Any
    clock: Any
    id_factory: Any
    review_ttl: timedelta
    default_session_id: str
    _result_from_stored: Any
    _failure_result: Any
    _failure: Any
    _resolve_entities: Any
    _refresh_context: Any
    _context_fingerprint: Any
    _evaluate_guards: Any
    _execute_attempt: Any
    _evidence: Any
    _operation_event: Any
    _supervised_phases: Any
    _commit_supervision_failure: Any
    _valid_json_object: Any

    async def accept_review(
        self,
        review_id: str,
        request_id: str,
        expected_session_version: int,
        *,
        session_id: str | None = None,
    ) -> OperationResult:
        target_session_id = session_id or self.default_session_id
        review = await self.store.find_review(target_session_id, review_id)
        if review is None:
            return self._missing_review_result(
                session_id=target_session_id,
                request_id=request_id,
                expected_session_version=expected_session_version,
                code="review_not_found",
                message="That review is unavailable.",
            )
        request = self._review_operation_request(
            review=review,
            session_id=target_session_id,
            request_id=request_id,
            expected_session_version=expected_session_version,
        )
        operation = self.app.app.operations.get(review.attempt.operation_id)
        fingerprint = canonical_request_fingerprint(
            request,
            entity_inputs=operation.entity_inputs if operation is not None else (),
            parent_turn_id=f"review:{review_id}:accept",
        )
        stored = await self.store.find_attempt(target_session_id, request_id)
        if stored is not None:
            if stored.attempt.request_fingerprint != fingerprint:
                return self._request_id_reused_result(request, stored, fingerprint)
            replay = self._result_from_stored(stored, session_id=target_session_id)
            if replay is not None:
                return replay
        if review.resolution is not ReviewResolution.PENDING:
            return self._review_status_failure(
                request=request,
                fingerprint=fingerprint,
                review=review,
                code="review_already_resolved",
                message="That review has already been resolved.",
            )
        try:
            lease = await self.store.acquire_turn(
                TurnClaim(
                    session_id=target_session_id,
                    expected_session_version=expected_session_version,
                    request_id=request_id,
                    request_fingerprint=fingerprint,
                    owner_kind=TurnOwnerKind.REVIEW,
                )
            )
        except SessionStoreError as error:
            return self._store_conflict_result(
                request=request,
                fingerprint=fingerprint,
                error=error,
            )
        try:
            current_review = await self.store.find_review(target_session_id, review_id)
            if (
                current_review is None
                or current_review.resolution is not ReviewResolution.PENDING
            ):
                return self._review_status_failure(
                    request=request,
                    fingerprint=fingerprint,
                    review=review,
                    code="review_already_resolved",
                    message="That review has already been resolved.",
                )
            session = (await self.store.load(target_session_id)).state
            if session.session_version != expected_session_version:
                return self._review_status_failure(
                    request=request,
                    fingerprint=fingerprint,
                    review=current_review,
                    code="version_conflict",
                    message="The session changed before the review was accepted.",
                )
            if operation is None:
                return await self._resolve_invalid_review(
                    request=request,
                    fingerprint=fingerprint,
                    review=current_review,
                    resolution=ReviewResolution.STALE,
                    code="review_stale",
                    message="The reviewed operation has changed.",
                    session=session,
                    lease=lease,
                )
            if current_review.expires_at <= self.clock.now():
                return await self._resolve_invalid_review(
                    request=request,
                    fingerprint=fingerprint,
                    review=current_review,
                    resolution=ReviewResolution.EXPIRED,
                    code="review_expired",
                    message="That review has expired.",
                    session=session,
                    lease=lease,
                )
            if (
                current_review.operation_spec_version
                != canonical_operation_spec_version(operation)
                or current_review.projection_version != session.projection_version
            ):
                return await self._resolve_invalid_review(
                    request=request,
                    fingerprint=fingerprint,
                    review=current_review,
                    resolution=ReviewResolution.STALE,
                    code="review_stale",
                    message="The reviewed operation is no longer current.",
                    session=session,
                    lease=lease,
                )
            resolved_entities = self._resolve_entities(
                session=session,
                request=request,
                operation=operation,
            )
            if resolved_entities is None:
                return await self._resolve_invalid_review(
                    request=request,
                    fingerprint=fingerprint,
                    review=current_review,
                    resolution=ReviewResolution.STALE,
                    code="review_stale",
                    message="A reviewed reference is no longer current.",
                    session=session,
                    lease=lease,
                )
            attempt_id = self.id_factory("attempt")
            resumed_attempt = OperationAttempt(
                attempt_id=attempt_id,
                request_id=request_id,
                request_fingerprint=fingerprint,
                operation_id=operation.id,
                source=request.source,
                expected_session_version=expected_session_version,
                arguments=current_review.attempt.arguments,
                resumed_review_id=review_id,
            )
            provider_values, provider_failure = await self._refresh_context(
                session=session,
                request=request,
                operation=operation,
                attempt_id=attempt_id,
            )
            if provider_failure is not None:
                return await self._commit_supervision_failure(
                    request=request,
                    attempt=resumed_attempt,
                    session=session,
                    lease=lease,
                    disposition=OperationDisposition.FAILED,
                    failure=provider_failure,
                    phases=(
                        OperationPhase.RECEIVED,
                        OperationPhase.LEASE_ACQUIRED,
                        OperationPhase.VALIDATED,
                    ),
                    review=current_review,
                )
            context_fingerprint = self._context_fingerprint(
                provider_values=provider_values,
                resolved_entities=resolved_entities,
            )
            resumed_attempt = resumed_attempt.model_copy(
                update={"context_fingerprint": context_fingerprint}
            )
            guard_decision, guard_failure = await self._evaluate_guards(
                session=session,
                request=request,
                operation=operation,
                attempt_id=attempt_id,
                provider_values=provider_values,
                resolved_entities=resolved_entities,
            )
            if guard_failure is not None:
                return await self._commit_supervision_failure(
                    request=request,
                    attempt=resumed_attempt,
                    session=session,
                    lease=lease,
                    disposition=OperationDisposition.FAILED,
                    failure=guard_failure,
                    phases=(
                        OperationPhase.RECEIVED,
                        OperationPhase.LEASE_ACQUIRED,
                        OperationPhase.VALIDATED,
                        OperationPhase.CONTEXT_REFRESHED,
                    ),
                    review=current_review,
                )
            if (
                context_fingerprint != current_review.authoritative_context_fingerprint
                or (guard_decision is not None and not guard_decision.allowed)
            ):
                return await self._resolve_invalid_review(
                    request=request,
                    fingerprint=fingerprint,
                    review=current_review,
                    resolution=ReviewResolution.STALE,
                    code="review_stale",
                    message="The authoritative facts changed after review.",
                    session=session,
                    lease=lease,
                )
            accepted_review = current_review.model_copy(
                update={
                    "resolution": ReviewResolution.ACCEPTED,
                    "resolved_request_id": request_id,
                }
            )
            return await self._execute_attempt(
                request=request,
                operation=operation,
                attempt=resumed_attempt,
                session=session,
                lease=lease,
                provider_values=provider_values,
                resolved_entities=resolved_entities,
                review=accepted_review,
            )
        except SessionStoreError as error:
            return self._store_conflict_result(
                request=request,
                fingerprint=fingerprint,
                error=error,
            )
        finally:
            await self.store.release_turn(lease)

    async def reject_review(
        self,
        review_id: str,
        request_id: str,
        expected_session_version: int,
        *,
        session_id: str | None = None,
    ) -> OperationResult:
        target_session_id = session_id or self.default_session_id
        review = await self.store.find_review(target_session_id, review_id)
        if review is None:
            return self._missing_review_result(
                session_id=target_session_id,
                request_id=request_id,
                expected_session_version=expected_session_version,
                code="review_not_found",
                message="That review is unavailable.",
            )
        request = self._review_operation_request(
            review=review,
            session_id=target_session_id,
            request_id=request_id,
            expected_session_version=expected_session_version,
        )
        operation = self.app.app.operations.get(review.attempt.operation_id)
        fingerprint = canonical_request_fingerprint(
            request,
            entity_inputs=operation.entity_inputs if operation is not None else (),
            parent_turn_id=f"review:{review_id}:reject",
        )
        stored = await self.store.find_attempt(target_session_id, request_id)
        if stored is not None:
            if stored.attempt.request_fingerprint != fingerprint:
                return self._request_id_reused_result(request, stored, fingerprint)
            replay = self._result_from_stored(stored, session_id=target_session_id)
            if replay is not None:
                return replay
        if review.resolution is not ReviewResolution.PENDING:
            return self._review_status_failure(
                request=request,
                fingerprint=fingerprint,
                review=review,
                code="review_already_resolved",
                message="That review has already been resolved.",
            )
        try:
            lease = await self.store.acquire_turn(
                TurnClaim(
                    session_id=target_session_id,
                    expected_session_version=expected_session_version,
                    request_id=request_id,
                    request_fingerprint=fingerprint,
                    owner_kind=TurnOwnerKind.REVIEW,
                )
            )
        except SessionStoreError as error:
            return self._store_conflict_result(
                request=request,
                fingerprint=fingerprint,
                error=error,
            )
        try:
            current_review = await self.store.find_review(target_session_id, review_id)
            if (
                current_review is None
                or current_review.resolution is not ReviewResolution.PENDING
            ):
                return self._review_status_failure(
                    request=request,
                    fingerprint=fingerprint,
                    review=review,
                    code="review_already_resolved",
                    message="That review has already been resolved.",
                )
            session = (await self.store.load(target_session_id)).state
            if session.session_version != expected_session_version:
                return self._review_status_failure(
                    request=request,
                    fingerprint=fingerprint,
                    review=current_review,
                    code="version_conflict",
                    message="The session changed before the review was rejected.",
                )
            return await self._resolve_invalid_review(
                request=request,
                fingerprint=fingerprint,
                review=current_review,
                resolution=ReviewResolution.REJECTED,
                code="review_rejected",
                message="The reviewed operation was rejected.",
                session=session,
                lease=lease,
            )
        finally:
            await self.store.release_turn(lease)

    async def _stage_review(
        self,
        *,
        request: OperationRequest,
        operation: OperationSpec,
        attempt: OperationAttempt,
        session: RouteDeckSession,
        lease: TurnLease,
        provider_values: FrozenJsonObject,
        owns_lease: bool,
        review_turns: tuple[FinalizedConversationTurn, ...],
        review_tool_call: ConversationToolCall | None,
    ) -> OperationResult:
        del provider_values, owns_lease
        if attempt.context_fingerprint is None:
            raise RuntimeError("Reviewed attempts require authoritative context")
        pending_attempt = attempt.model_copy(
            update={"status": OperationAttemptStatus.REVIEW_PENDING}
        )
        operation_spec_version = canonical_operation_spec_version(operation)
        proposal_fingerprint = canonical_json_fingerprint(
            "routedeck.review-proposal.v1",
            {
                "request_fingerprint": attempt.request_fingerprint,
                "operation_spec_version": operation_spec_version,
                "context_fingerprint": attempt.context_fingerprint,
                "projection_version": session.projection_version,
            },
        )
        provisional_review = PendingReview(
            review_id=self.id_factory("review"),
            attempt=pending_attempt,
            operation_spec_version=operation_spec_version,
            proposal_fingerprint=proposal_fingerprint,
            projection_version=session.projection_version,
            authoritative_context_fingerprint=attempt.context_fingerprint,
            expires_at=self.clock.now() + self.review_ttl,
        )
        conversation_turns = review_turns
        if review_turns:
            if review_tool_call is None:
                raise RuntimeError("Agent review history requires tool-call metadata")
            conversation_turns = (
                *review_turns,
                FinalizedConversationTurn(
                    turn_id=self.id_factory("turn"),
                    role=ConversationRole.TOOL,
                    content=json.dumps(
                        {
                            "expires_at": provisional_review.expires_at.isoformat(),
                            "operation_id": operation.id,
                            "review_id": provisional_review.review_id,
                            "status": "requires_review",
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    request_id=lease.request_id,
                    tool_call=review_tool_call,
                    tool_status="success",
                ),
            )
        conversation_events = (
            (ConversationTurnsStored(turns=conversation_turns),)
            if conversation_turns
            else ()
        )
        review_public_state = session.public_state
        review_surface_id = operation.public_metadata_value().get("review_surface_id")
        if review_surface_id is not None:
            if not isinstance(review_surface_id, str) or not review_surface_id:
                raise RuntimeError("review_surface_id metadata must be a string")
            current_node = next(
                node
                for node in self.app.app.spec.nodes
                if node.id == session.current.node_id
            )
            surfaces = {
                surface.id: surface
                for surface in current_node.surfaces.declared_surfaces()
            }
            surface = surfaces.get(review_surface_id)
            if surface is None:
                raise RuntimeError("review surface is not declared on the current node")
            review_values = {
                "state": "pending",
                "review_id": provisional_review.review_id,
                "expires_at": provisional_review.expires_at.isoformat(),
            }
            if not self._valid_json_object(
                surface.public_props_schema_value(),
                review_values,
            ):
                raise RuntimeError("review surface values do not match its schema")
            _, review_public_state = session_state_with_effects(
                session,
                SessionEffects(
                    surface_updates=(
                        PublicSurfaceEffect(
                            surface_id=review_surface_id,
                            values=tuple(
                                PublicValue(name=name, value=FrozenJson(value))
                                for name, value in review_values.items()
                            ),
                        ),
                    )
                ),
            )
        public_state = review_public_state.model_copy(
            update={
                "status_code": "review_pending",
                "status_message": "This operation requires explicit review.",
                "failure": None,
            }
        )
        provisional_state = reduce_session_batch(
            session,
            (
                *conversation_events,
                OperationStateStored(
                    operation=OperationState(
                        active_attempt=pending_attempt,
                        pending_review=provisional_review,
                    )
                ),
                PublicSessionStateStored(state=public_state),
                PublicEventsRecorded(count=1),
            ),
        )
        review = provisional_review.model_copy(
            update={"projection_version": provisional_state.projection_version}
        )
        next_state = reduce_session_batch(
            session,
            (
                *conversation_events,
                OperationStateStored(
                    operation=OperationState(
                        active_attempt=pending_attempt,
                        pending_review=review,
                    )
                ),
                PublicSessionStateStored(state=public_state),
                PublicEventsRecorded(count=1),
            ),
        )
        event = self._operation_event(next_state, request, public_state)
        evidence = self._evidence(
            pending_attempt,
            (*self._supervised_phases(), OperationPhase.REVIEW_STAGED),
        )
        record = StoredOperationAttempt(
            attempt=pending_attempt,
            review=review,
            disposition=OperationDisposition.REQUIRES_REVIEW,
            evidence=evidence,
            committed_session_version=next_state.session_version,
            committed_projection_version=next_state.projection_version,
        )
        snapshot = await self.store.stage_review(
            lease,
            session.session_version,
            record,
            next_state,
            (event,),
            (
                MutationCommit(
                    kind=MutationKind.CHAT,
                    status=MutationStatus.REQUIRES_REVIEW,
                    result=FrozenJsonObject(
                        {
                            "expires_at": review.expires_at.isoformat(),
                            "operation_id": operation.id,
                            "review_id": review.review_id,
                        }
                    ),
                )
                if review_turns
                else None
            ),
        )
        await notify_event_wakeup(self.notifier, session.session_id, (event,))
        return OperationResult(
            disposition=OperationDisposition.REQUIRES_REVIEW,
            session_id=session.session_id,
            request_id=request.request_id,
            operation_id=operation.id,
            session_version=snapshot.session_version,
            projection_version=snapshot.projection_version,
            evidence=evidence,
            review=OperationReview(id=review.review_id, expires_at=review.expires_at),
        )

    async def _resolve_invalid_review(
        self,
        *,
        request: OperationRequest,
        fingerprint: str,
        review: PendingReview,
        resolution: ReviewResolution,
        code: str,
        message: str,
        session: RouteDeckSession,
        lease: TurnLease,
    ) -> OperationResult:
        failure = self._failure(
            request,
            kind=FailureKind.REVIEW,
            code=code,
            phase="review_resolution",
            message=message,
        )
        attempt = OperationAttempt(
            attempt_id=self.id_factory("attempt"),
            request_id=request.request_id,
            request_fingerprint=fingerprint,
            operation_id=review.attempt.operation_id,
            source=request.source,
            expected_session_version=request.expected_session_version,
            arguments=review.attempt.arguments,
            resumed_review_id=review.review_id,
            context_fingerprint=review.authoritative_context_fingerprint,
            status=OperationAttemptStatus.FAILED,
            terminal=(
                AttemptTerminalState.REVIEW_REJECTED
                if resolution is ReviewResolution.REJECTED
                else AttemptTerminalState.FAILED
            ),
            failure=failure,
        )
        resolved_review = review.model_copy(
            update={
                "resolution": resolution,
                "resolved_request_id": request.request_id,
            }
        )
        public_state = session.public_state.model_copy(
            update={
                "status_code": code,
                "status_message": failure.public_message,
                "failure": failure,
            }
        )
        next_state = reduce_session_batch(
            session,
            (
                OperationStateStored(
                    operation=OperationState(
                        active_attempt=attempt,
                        pending_review=resolved_review,
                    )
                ),
                PublicSessionStateStored(state=public_state),
                PublicEventsRecorded(count=1),
            ),
        )
        event = self._operation_event(next_state, request, public_state)
        phases = (
            OperationPhase.RECEIVED,
            OperationPhase.LEASE_ACQUIRED,
            OperationPhase.VALIDATED,
            OperationPhase.STATE_COMMITTED,
            OperationPhase.COMPLETED,
        )
        evidence = self._evidence(attempt, phases)
        record = StoredOperationAttempt(
            attempt=attempt,
            review=resolved_review,
            disposition=OperationDisposition.FAILED,
            evidence=evidence,
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
            fingerprint=fingerprint,
            attempt_id=attempt.attempt_id,
            session_version=snapshot.session_version,
            projection_version=snapshot.projection_version,
            disposition=OperationDisposition.FAILED,
            failure=failure,
            phases=phases,
        )

    @staticmethod
    def _review_arguments(review: PendingReview) -> FrozenJsonObject:
        return FrozenJsonObject(
            {
                argument.name: argument.value.to_python()
                for argument in review.attempt.arguments
            }
        )

    def _review_operation_request(
        self,
        *,
        review: PendingReview,
        session_id: str,
        request_id: str,
        expected_session_version: int,
    ) -> OperationRequest:
        return OperationRequest(
            session_id=session_id,
            request_id=request_id,
            expected_session_version=expected_session_version,
            operation_id=review.attempt.operation_id,
            source=OperationSource.SURFACE,
            arguments=self._review_arguments(review),
        )

    def _missing_review_result(
        self,
        *,
        session_id: str,
        request_id: str,
        expected_session_version: int,
        code: str,
        message: str,
    ) -> OperationResult:
        request = OperationRequest(
            session_id=session_id,
            request_id=request_id,
            expected_session_version=expected_session_version,
            operation_id="routedeck.review",
            source=OperationSource.SURFACE,
            arguments=FrozenJsonObject({}),
        )
        fingerprint = canonical_request_fingerprint(request)
        return self._failure_result(
            request=request,
            fingerprint=fingerprint,
            attempt_id=self.id_factory("attempt"),
            session_version=expected_session_version,
            projection_version=0,
            disposition=OperationDisposition.FAILED,
            failure=self._failure(
                request,
                kind=FailureKind.REVIEW,
                code=code,
                phase="review_lookup",
                message=message,
            ),
            phases=(OperationPhase.RECEIVED,),
        )

    def _review_status_failure(
        self,
        *,
        request: OperationRequest,
        fingerprint: str,
        review: PendingReview,
        code: str,
        message: str,
    ) -> OperationResult:
        return self._failure_result(
            request=request,
            fingerprint=fingerprint,
            attempt_id=self.id_factory("attempt"),
            session_version=request.expected_session_version,
            projection_version=review.projection_version,
            disposition=OperationDisposition.FAILED,
            failure=self._failure(
                request,
                kind=(
                    FailureKind.STATE_CONFLICT
                    if code == "version_conflict"
                    else FailureKind.REVIEW
                ),
                code=code,
                phase="review_validation",
                message=message,
            ),
            phases=(OperationPhase.RECEIVED,),
        )

    def _request_id_reused_result(
        self,
        request: OperationRequest,
        stored: StoredOperationAttempt,
        fingerprint: str,
    ) -> OperationResult:
        return self._failure_result(
            request=request,
            fingerprint=fingerprint,
            attempt_id=stored.attempt.attempt_id,
            session_version=(
                stored.committed_session_version
                if stored.committed_session_version is not None
                else request.expected_session_version
            ),
            projection_version=stored.committed_projection_version or 0,
            disposition=OperationDisposition.BLOCKED,
            failure=self._failure(
                request,
                kind=FailureKind.STATE_CONFLICT,
                code="request_id_reused",
                phase="idempotency",
                message="This request ID was already used for another operation.",
            ),
            phases=(OperationPhase.RECEIVED,),
        )

    def _store_conflict_result(
        self,
        *,
        request: OperationRequest,
        fingerprint: str,
        error: SessionStoreError,
    ) -> OperationResult:
        code = {
            SessionStoreErrorCode.OPERATION_IN_PROGRESS: "operation_in_progress",
            SessionStoreErrorCode.REVIEW_ALREADY_RESOLVED: "review_already_resolved",
            SessionStoreErrorCode.REQUEST_ID_REUSED: "request_id_reused",
            SessionStoreErrorCode.VERSION_CONFLICT: "version_conflict",
        }.get(error.code, "persistence_failure")
        return self._failure_result(
            request=request,
            fingerprint=fingerprint,
            attempt_id=self.id_factory("attempt"),
            session_version=request.expected_session_version,
            projection_version=0,
            disposition=OperationDisposition.FAILED,
            failure=self._failure(
                request,
                kind=(
                    FailureKind.STATE_CONFLICT
                    if code != "persistence_failure"
                    else FailureKind.PERSISTENCE
                ),
                code=code,
                phase="store_claim",
                message="The operation could not acquire durable execution authority.",
            ),
            phases=(OperationPhase.RECEIVED,),
        )


__all__ = ["ReviewLifecycleMixin"]
