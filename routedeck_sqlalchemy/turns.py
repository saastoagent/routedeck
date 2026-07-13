from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime

from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from routedeck_core.contracts.mutations import (
    MutationCommit,
    MutationKind,
    MutationRecord,
    MutationStatus,
)
from routedeck_core.contracts.retention import RouteDeckRetentionPolicy
from routedeck_core.contracts.session import SessionSnapshot
from routedeck_core.ports.session_store import SessionStoreError, SessionStoreErrorCode
from routedeck_core.state.leases import TurnClaim, TurnLease, TurnOwnerKind

from .lease import ApplicationLease
from .models import (
    ActiveChildAttemptRow,
    MutationJournalRow,
    OperationAttemptRow,
    TurnLeaseRow,
)
from .sessions import SessionRepository


class TurnRepository:
    def __init__(
        self,
        *,
        sessions: SessionRepository,
        retention_policy: RouteDeckRetentionPolicy,
    ) -> None:
        self.sessions = sessions
        self.retention_policy = retention_policy

    def find_mutation(
        self,
        database: Session,
        *,
        session_id: str,
        request_id: str,
        now: datetime,
    ) -> MutationRecord | None:
        self.sessions.load_row(database, session_id, now=now)
        row = database.get(MutationJournalRow, (session_id, request_id))
        if row is None:
            return None
        return MutationRecord(
            session_id=session_id,
            request_id=request_id,
            request_fingerprint=row.request_fingerprint,
            kind=MutationKind(row.mutation_kind),
            status=MutationStatus(row.status),
            result=json.loads(row.result_json),
            committed_session_version=row.committed_session_version,
            committed_projection_version=row.committed_projection_version,
            committed_event_cursor=row.committed_event_cursor,
        )

    def acquire(
        self,
        database: Session,
        claim: TurnClaim,
        *,
        now: datetime,
        application_lease: ApplicationLease,
    ) -> TurnLease:
        if database.get(MutationJournalRow, (claim.session_id, claim.request_id)):
            raise SessionStoreError(SessionStoreErrorCode.REQUEST_ID_REUSED)
        operation = database.scalar(
            select(OperationAttemptRow).where(
                OperationAttemptRow.session_id == claim.session_id,
                OperationAttemptRow.request_id == claim.request_id,
            )
        )
        if (
            operation is not None
            and operation.request_fingerprint != claim.request_fingerprint
        ):
            raise SessionStoreError(SessionStoreErrorCode.REQUEST_ID_REUSED)
        session = self.sessions.require_version(
            database,
            claim.session_id,
            claim.expected_session_version,
            now=now,
        )
        if database.get(TurnLeaseRow, claim.session_id) is not None:
            raise SessionStoreError(SessionStoreErrorCode.OPERATION_IN_PROGRESS)
        capability = secrets.token_urlsafe(32)
        database.add(
            TurnLeaseRow(
                session_id=claim.session_id,
                request_id=claim.request_id,
                request_fingerprint=claim.request_fingerprint,
                owner_kind=claim.owner_kind.value,
                parent_turn_id=claim.parent_turn_id,
                capability_hash=_capability_hash(capability),
                fencing_token=application_lease.fencing_token,
                acquired_at=now,
            )
        )
        if session.completed_at is None:
            idle_expires = now + self.retention_policy.unfinished_idle_ttl
            expires = min(idle_expires, session.absolute_expires_at)
        else:
            idle_expires = session.idle_expires_at
            expires = session.expires_at
        session.owner_fencing_token = application_lease.fencing_token
        session.last_accessed_at = now
        session.idle_expires_at = idle_expires
        session.expires_at = expires
        try:
            database.flush()
        except IntegrityError as error:
            raise SessionStoreError(
                SessionStoreErrorCode.OPERATION_IN_PROGRESS
            ) from error
        return TurnLease(
            capability=SecretStr(capability),
            fencing_token=application_lease.fencing_token,
            session_id=claim.session_id,
            request_id=claim.request_id,
        )

    def claim_child(
        self,
        database: Session,
        lease: TurnLease,
        *,
        request_id: str,
        request_fingerprint: str,
        now: datetime,
        application_lease: ApplicationLease,
    ) -> None:
        self.require_lease(database, lease, application_lease=application_lease)
        if database.get(ActiveChildAttemptRow, lease.session_id) is not None:
            raise SessionStoreError(SessionStoreErrorCode.OPERATION_IN_PROGRESS)
        previous = database.scalar(
            select(OperationAttemptRow).where(
                OperationAttemptRow.session_id == lease.session_id,
                OperationAttemptRow.request_id == request_id,
            )
        )
        mutation = database.get(MutationJournalRow, (lease.session_id, request_id))
        if previous is not None or mutation is not None:
            raise SessionStoreError(SessionStoreErrorCode.REQUEST_ID_REUSED)
        database.add(
            ActiveChildAttemptRow(
                session_id=lease.session_id,
                parent_request_id=lease.request_id,
                request_id=request_id,
                request_fingerprint=request_fingerprint,
                acquired_at=now,
            )
        )
        database.flush()

    def release_child(
        self,
        database: Session,
        lease: TurnLease,
        *,
        request_id: str,
        application_lease: ApplicationLease,
    ) -> None:
        self.require_lease(database, lease, application_lease=application_lease)
        row = database.get(ActiveChildAttemptRow, lease.session_id)
        if (
            row is None
            or row.parent_request_id != lease.request_id
            or row.request_id != request_id
        ):
            raise SessionStoreError(SessionStoreErrorCode.LEASE_MISMATCH)
        database.delete(row)

    def require_lease(
        self,
        database: Session,
        lease: TurnLease,
        *,
        application_lease: ApplicationLease,
    ) -> TurnLeaseRow:
        row = database.get(TurnLeaseRow, lease.session_id)
        if (
            row is None
            or row.request_id != lease.request_id
            or row.capability_hash
            != _capability_hash(lease.capability.get_secret_value())
            or row.fencing_token != lease.fencing_token
            or lease.fencing_token != application_lease.fencing_token
        ):
            raise SessionStoreError(SessionStoreErrorCode.LEASE_MISMATCH)
        return row

    def require_no_active_child(self, database: Session, session_id: str) -> None:
        if database.get(ActiveChildAttemptRow, session_id) is not None:
            raise SessionStoreError(SessionStoreErrorCode.OPERATION_IN_PROGRESS)

    def delete_lease(
        self,
        database: Session,
        lease: TurnLease,
        *,
        application_lease: ApplicationLease,
    ) -> None:
        row = self.require_lease(
            database,
            lease,
            application_lease=application_lease,
        )
        database.delete(row)

    def record_mutation(
        self,
        database: Session,
        lease: TurnLease,
        mutation: MutationCommit,
        snapshot: SessionSnapshot,
        *,
        now: datetime,
        application_lease: ApplicationLease,
    ) -> None:
        row = self.require_lease(
            database,
            lease,
            application_lease=application_lease,
        )
        self.record_mutation_from_row(
            database,
            row,
            mutation,
            snapshot,
            now=now,
        )

    def record_mutation_from_row(
        self,
        database: Session,
        lease_row: TurnLeaseRow,
        mutation: MutationCommit,
        snapshot: SessionSnapshot,
        *,
        now: datetime,
    ) -> None:
        expected_owner = {
            MutationKind.NAVIGATION: TurnOwnerKind.NAVIGATION,
            MutationKind.PRIVATE_FORM: TurnOwnerKind.SURFACE,
            MutationKind.CHAT: TurnOwnerKind.CHAT,
        }[mutation.kind]
        if lease_row.owner_kind != expected_owner.value:
            raise SessionStoreError(SessionStoreErrorCode.LEASE_MISMATCH)
        operation = database.scalar(
            select(OperationAttemptRow).where(
                OperationAttemptRow.session_id == lease_row.session_id,
                OperationAttemptRow.request_id == lease_row.request_id,
            )
        )
        if operation is not None:
            raise SessionStoreError(SessionStoreErrorCode.REQUEST_ID_REUSED)
        database.add(
            MutationJournalRow(
                session_id=lease_row.session_id,
                request_id=lease_row.request_id,
                request_fingerprint=lease_row.request_fingerprint,
                mutation_kind=mutation.kind.value,
                status=mutation.status.value,
                result_json=json.dumps(
                    mutation.result.to_python(),
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ),
                committed_session_version=snapshot.session_version,
                committed_projection_version=snapshot.projection_version,
                committed_event_cursor=snapshot.event_cursor,
                created_at=now,
            )
        )
        try:
            database.flush()
        except IntegrityError as error:
            raise SessionStoreError(SessionStoreErrorCode.REQUEST_ID_REUSED) from error


def capability_hash(value: str) -> str:
    return _capability_hash(value)


def _capability_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


__all__ = ["TurnRepository", "capability_hash"]
