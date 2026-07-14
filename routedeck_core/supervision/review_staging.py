from __future__ import annotations

import json

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
    OperationSpec,
)
from ..contracts.mutations import MutationCommit, MutationKind, MutationStatus
from ..contracts.interactions import RouteDeckInteractionState
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
from ..ports.notifier import notify_event_wakeup
from ..state.aggregate import RouteDeckSessionAggregate
from ..state.effects import session_state_with_effects
from ..state.leases import TurnLease
from .outcomes import (
    canonical_json_fingerprint,
    canonical_operation_spec_version,
)

from .review_base import ReviewRuntimePorts


class ReviewStagingMixin(ReviewRuntimePorts):
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
        provisional_state = (
            RouteDeckSessionAggregate(session)
            .append_conversation_turns(conversation_turns)
            .set_interaction(
                RouteDeckInteractionState() if review_turns else session.interaction
            )
            .set_operation_state(
                OperationState(
                    active_attempt=pending_attempt,
                    pending_review=provisional_review,
                )
            )
            .set_public_state(public_state)
            .record_public_events(1)
            .commit()
        )
        review = provisional_review.model_copy(
            update={"projection_version": provisional_state.projection_version}
        )
        next_state = (
            RouteDeckSessionAggregate(session)
            .append_conversation_turns(conversation_turns)
            .set_interaction(
                RouteDeckInteractionState() if review_turns else session.interaction
            )
            .set_operation_state(
                OperationState(
                    active_attempt=pending_attempt,
                    pending_review=review,
                )
            )
            .set_public_state(public_state)
            .record_public_events(1)
            .commit()
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
        next_state = (
            RouteDeckSessionAggregate(session)
            .set_operation_state(
                OperationState(
                    active_attempt=attempt,
                    pending_review=resolved_review,
                )
            )
            .set_public_state(public_state)
            .record_public_events(1)
            .commit()
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



__all__ = ["ReviewStagingMixin"]
