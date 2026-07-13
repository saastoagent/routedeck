from __future__ import annotations

import secrets
from datetime import datetime

from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from routedeck_core.contracts.operations import OperationDisposition
from routedeck_core.contracts.session import (
    AttemptTerminalState,
    JournaledExecutionResult,
    OperationAttemptStatus,
    PendingReview,
    StoredOperationAttempt,
)
from routedeck_core.ports.session_store import SessionStoreError, SessionStoreErrorCode
from routedeck_core.state.leases import ExecutionClaim, TurnLease

from .lease import ApplicationLease
from .models import (
    ActiveChildAttemptRow,
    ExecutionClaimRow,
    ExecutionResultRow,
    OperationAttemptRow,
    OperationJournalRow,
    ReviewRow,
)
from .sessions import SessionRepository
from .turns import TurnRepository, capability_hash


class OperationRepository:
    def __init__(
        self,
        *,
        sessions: SessionRepository,
        turns: TurnRepository,
    ) -> None:
        self.sessions = sessions
        self.turns = turns

    def find_attempt(
        self,
        database: Session,
        *,
        session_id: str,
        request_id: str,
        now: datetime,
    ) -> StoredOperationAttempt | None:
        self.sessions.load_row(database, session_id, now=now)
        row = database.scalar(
            select(OperationAttemptRow).where(
                OperationAttemptRow.session_id == session_id,
                OperationAttemptRow.request_id == request_id,
            )
        )
        return (
            StoredOperationAttempt.model_validate_json(row.record_json)
            if row is not None
            else None
        )

    def find_review(
        self,
        database: Session,
        *,
        session_id: str,
        review_id: str,
        now: datetime,
    ) -> PendingReview | None:
        self.sessions.load_row(database, session_id, now=now)
        row = database.get(ReviewRow, review_id)
        if row is None or row.session_id != session_id:
            return None
        return PendingReview.model_validate_json(row.record_json)

    def upsert_attempt(
        self,
        database: Session,
        *,
        session_id: str,
        record: StoredOperationAttempt,
        now: datetime,
        phase: str,
        application_lease: ApplicationLease,
    ) -> None:
        attempt = record.attempt
        row = database.scalar(
            select(OperationAttemptRow).where(
                OperationAttemptRow.session_id == session_id,
                OperationAttemptRow.request_id == attempt.request_id,
            )
        )
        if row is not None and (
            row.attempt_id != attempt.attempt_id
            or row.request_fingerprint != attempt.request_fingerprint
        ):
            raise SessionStoreError(SessionStoreErrorCode.REQUEST_ID_REUSED)
        if row is None:
            row = OperationAttemptRow(
                attempt_id=attempt.attempt_id,
                session_id=session_id,
                request_id=attempt.request_id,
                request_fingerprint=attempt.request_fingerprint,
                record_json=record.model_dump_json(),
                review_id=record.review.review_id if record.review else None,
                status=attempt.status.value,
                fencing_token=application_lease.fencing_token,
                created_at=now,
                updated_at=now,
            )
            database.add(row)
        else:
            row.record_json = record.model_dump_json()
            row.review_id = record.review.review_id if record.review else None
            row.status = attempt.status.value
            row.fencing_token = application_lease.fencing_token
            row.updated_at = now
        try:
            database.flush()
        except IntegrityError as error:
            raise SessionStoreError(SessionStoreErrorCode.REQUEST_ID_REUSED) from error
        database.add(
            OperationJournalRow(
                session_id=session_id,
                attempt_id=attempt.attempt_id,
                phase=phase,
                record_json=record.model_dump_json(),
                created_at=now,
                fencing_token=application_lease.fencing_token,
            )
        )
        if record.review is not None:
            review = record.review
            review_row = database.get(ReviewRow, review.review_id)
            if review_row is None:
                database.add(
                    ReviewRow(
                        review_id=review.review_id,
                        session_id=session_id,
                        attempt_id=review.attempt.attempt_id,
                        record_json=review.model_dump_json(),
                        resolution=review.resolution.value,
                        updated_at=now,
                    )
                )
            else:
                review_row.record_json = review.model_dump_json()
                review_row.resolution = review.resolution.value
                review_row.updated_at = now
        database.flush()

    def claim_execution(
        self,
        database: Session,
        lease: TurnLease,
        record: StoredOperationAttempt,
        *,
        now: datetime,
        application_lease: ApplicationLease,
    ) -> ExecutionClaim:
        self.turns.require_lease(
            database,
            lease,
            application_lease=application_lease,
        )
        attempt = record.attempt
        if database.get(ExecutionClaimRow, attempt.attempt_id) is not None:
            raise SessionStoreError(SessionStoreErrorCode.EXECUTION_ALREADY_CLAIMED)
        if attempt.parent_turn_id is not None:
            child = database.get(ActiveChildAttemptRow, lease.session_id)
            if child is None or child.request_id != attempt.request_id:
                raise SessionStoreError(SessionStoreErrorCode.LEASE_MISMATCH)
        if attempt.resumed_review_id is not None:
            self._accept_review(
                database,
                session_id=lease.session_id,
                record=record,
                now=now,
                application_lease=application_lease,
            )
        self.upsert_attempt(
            database,
            session_id=lease.session_id,
            record=record,
            now=now,
            phase="execution_claimed",
            application_lease=application_lease,
        )
        capability = secrets.token_urlsafe(32)
        database.add(
            ExecutionClaimRow(
                attempt_id=attempt.attempt_id,
                session_id=lease.session_id,
                request_id=attempt.request_id,
                capability_hash=capability_hash(capability),
                fencing_token=application_lease.fencing_token,
                status="claimed",
                claimed_at=now,
                updated_at=now,
            )
        )
        database.flush()
        return ExecutionClaim(
            capability=SecretStr(capability),
            fencing_token=application_lease.fencing_token,
            session_id=lease.session_id,
            request_id=attempt.request_id,
            attempt_id=attempt.attempt_id,
        )

    def recover_execution_claim(
        self,
        database: Session,
        lease: TurnLease,
        attempt_id: str,
        *,
        now: datetime,
        application_lease: ApplicationLease,
    ) -> ExecutionClaim:
        self.turns.require_lease(
            database,
            lease,
            application_lease=application_lease,
        )
        row = database.get(ExecutionClaimRow, attempt_id)
        if row is None or row.session_id != lease.session_id:
            raise SessionStoreError(SessionStoreErrorCode.LEASE_MISMATCH)
        capability = secrets.token_urlsafe(32)
        row.capability_hash = capability_hash(capability)
        row.fencing_token = application_lease.fencing_token
        row.updated_at = now
        database.flush()
        return ExecutionClaim(
            capability=SecretStr(capability),
            fencing_token=application_lease.fencing_token,
            session_id=lease.session_id,
            request_id=row.request_id,
            attempt_id=attempt_id,
        )

    def record_execution_started(
        self,
        database: Session,
        claim: ExecutionClaim,
        record: StoredOperationAttempt,
        *,
        now: datetime,
        application_lease: ApplicationLease,
    ) -> None:
        row = self.require_execution_claim(
            database,
            claim,
            application_lease=application_lease,
        )
        self.upsert_attempt(
            database,
            session_id=claim.session_id,
            record=record,
            now=now,
            phase="tool_started",
            application_lease=application_lease,
        )
        row.status = "started"
        row.updated_at = now

    def record_execution_result(
        self,
        database: Session,
        claim: ExecutionClaim,
        result: JournaledExecutionResult,
        record: StoredOperationAttempt,
        *,
        now: datetime,
        application_lease: ApplicationLease,
    ) -> None:
        if record.journaled_result != result:
            raise SessionStoreError(SessionStoreErrorCode.RESULT_MISMATCH)
        claim_row = self.require_execution_claim(
            database,
            claim,
            application_lease=application_lease,
        )
        if (
            result.attempt_id != claim.attempt_id
            or result.request_id != claim.request_id
        ):
            raise SessionStoreError(SessionStoreErrorCode.RESULT_MISMATCH)
        self.upsert_attempt(
            database,
            session_id=claim.session_id,
            record=record,
            now=now,
            phase="execution_result_recorded",
            application_lease=application_lease,
        )
        existing = database.scalar(
            select(ExecutionResultRow).where(
                ExecutionResultRow.attempt_id == result.attempt_id
            )
        )
        result_json = result.model_dump_json()
        if existing is None:
            database.add(
                ExecutionResultRow(
                    result_id=result.result_id,
                    attempt_id=result.attempt_id,
                    session_id=claim.session_id,
                    result_json=result_json,
                    record_json=record.model_dump_json(),
                    result_fingerprint=result.result_fingerprint,
                    created_at=now,
                )
            )
        elif existing.result_json != result_json:
            raise SessionStoreError(SessionStoreErrorCode.RESULT_MISMATCH)
        claim_row.status = "result_recorded"
        claim_row.updated_at = now
        try:
            database.flush()
        except IntegrityError as error:
            raise SessionStoreError(SessionStoreErrorCode.RESULT_MISMATCH) from error

    def require_execution_claim(
        self,
        database: Session,
        claim: ExecutionClaim,
        *,
        application_lease: ApplicationLease,
    ) -> ExecutionClaimRow:
        row = database.get(ExecutionClaimRow, claim.attempt_id)
        if (
            row is None
            or row.session_id != claim.session_id
            or row.request_id != claim.request_id
            or row.capability_hash
            != capability_hash(claim.capability.get_secret_value())
            or row.fencing_token != claim.fencing_token
            or claim.fencing_token != application_lease.fencing_token
        ):
            raise SessionStoreError(SessionStoreErrorCode.LEASE_MISMATCH)
        return row

    @staticmethod
    def record_completes_session(record: StoredOperationAttempt) -> bool:
        result = record.journaled_result
        if result is None or not result.effects.complete_session:
            return False
        if (
            result.outcome is None
            or result.failure is not None
            or result.attempt_id != record.attempt.attempt_id
            or result.request_id != record.attempt.request_id
            or result.operation_id != record.attempt.operation_id
            or record.disposition is not OperationDisposition.COMPLETED
            or record.attempt.status is not OperationAttemptStatus.COMPLETED
            or record.attempt.terminal is not AttemptTerminalState.COMPLETED
        ):
            raise SessionStoreError(SessionStoreErrorCode.RESULT_MISMATCH)
        return True

    def _accept_review(
        self,
        database: Session,
        *,
        session_id: str,
        record: StoredOperationAttempt,
        now: datetime,
        application_lease: ApplicationLease,
    ) -> None:
        review = record.review
        if review is None or review.resolution.value != "accepted":
            raise SessionStoreError(SessionStoreErrorCode.REVIEW_ALREADY_RESOLVED)
        row = database.get(ReviewRow, review.review_id)
        if row is None or row.session_id != session_id:
            raise SessionStoreError(SessionStoreErrorCode.REVIEW_ALREADY_RESOLVED)
        current = PendingReview.model_validate_json(row.record_json)
        if current.resolution.value != "pending":
            raise SessionStoreError(SessionStoreErrorCode.REVIEW_ALREADY_RESOLVED)
        proposal_row = database.scalar(
            select(OperationAttemptRow).where(
                OperationAttemptRow.session_id == session_id,
                OperationAttemptRow.request_id == current.attempt.request_id,
            )
        )
        if proposal_row is None:
            raise SessionStoreError(SessionStoreErrorCode.PERSISTENCE_FAILURE)
        proposal = StoredOperationAttempt.model_validate_json(
            proposal_row.record_json
        ).model_copy(update={"review": review})
        self.upsert_attempt(
            database,
            session_id=session_id,
            record=proposal,
            now=now,
            phase="review_resolved",
            application_lease=application_lease,
        )


__all__ = ["OperationRepository"]
