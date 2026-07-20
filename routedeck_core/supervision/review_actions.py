from __future__ import annotations


from ..contracts.operations import (
    OperationDisposition,
    OperationPhase,
    OperationResult,
)
from ..contracts.session import (
    OperationAttempt,
    ReviewResolution,
)
from ..ports.session_store import SessionStoreError
from ..state.leases import TurnClaim, TurnOwnerKind
from .outcomes import (
    canonical_operation_spec_version,
    canonical_request_fingerprint,
)

from .review_base import ReviewRuntimePorts


class ReviewActionMixin(ReviewRuntimePorts):
    async def accept_review(
        self,
        review_id: str,
        request_id: str,
        expected_session_version: int,
        *,
        session_id: str,
    ) -> OperationResult:
        if not session_id:
            raise ValueError("session_id must be non-empty")
        target_session_id = session_id
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
        session_id: str,
    ) -> OperationResult:
        if not session_id:
            raise ValueError("session_id must be non-empty")
        target_session_id = session_id
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



__all__ = ["ReviewActionMixin"]
