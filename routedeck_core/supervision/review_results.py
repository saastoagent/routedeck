from __future__ import annotations


from ..contracts.failures import FailureKind
from ..contracts.operations import (
    OperationDisposition,
    OperationPhase,
    OperationRequest,
    OperationResult,
    OperationSource,
)
from ..contracts.projection import FrozenJsonObject
from ..contracts.session import (
    PendingReview,
    StoredOperationAttempt,
)
from ..ports.session_store import SessionStoreError, SessionStoreErrorCode
from .outcomes import (
    canonical_request_fingerprint,
)

from .review_base import ReviewRuntimePorts


class ReviewResultMixin(ReviewRuntimePorts):
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




__all__ = ["ReviewResultMixin"]
