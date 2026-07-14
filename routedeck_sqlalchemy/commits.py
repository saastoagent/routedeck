from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.orm import Session

from routedeck_core.contracts.events import RouteDeckEvent
from routedeck_core.contracts.mutations import MutationCommit
from routedeck_core.contracts.session import (
    RouteDeckSession,
    SessionSnapshot,
    StoredOperationAttempt,
)
from routedeck_core.ports.session_store import SessionStoreError, SessionStoreErrorCode
from routedeck_core.state.leases import ExecutionClaim, TurnLease

from .operations import OperationRepository
from .runtime import SqlAlchemyStoreRuntime
from .sessions import SessionRepository
from .turns import TurnRepository


class SqlAlchemyCommitCoordinator:
    """Coordinate fenced session, operation, and mutation commits."""

    def __init__(
        self,
        *,
        runtime: SqlAlchemyStoreRuntime,
        sessions: SessionRepository,
        turns: TurnRepository,
        operations: OperationRepository,
    ) -> None:
        self.runtime = runtime
        self.sessions = sessions
        self.turns = turns
        self.operations = operations

    async def with_lease(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
        *,
        record: StoredOperationAttempt | None = None,
        journal_phase: str | None = None,
        mutation: MutationCommit | None = None,
    ) -> SessionSnapshot:
        def commit(database: Session, now: datetime) -> SessionSnapshot:
            self.turns.require_lease(
                database,
                lease,
                application_lease=self.runtime.application_lease,
            )
            snapshot = self.sessions.commit(
                database,
                session_id=lease.session_id,
                expected_session_version=expected_session_version,
                next_state=next_state,
                events=events,
                now=now,
                lease=self.runtime.application_lease,
            )
            if record is not None:
                self.operations.upsert_attempt(
                    database,
                    session_id=lease.session_id,
                    record=record,
                    now=now,
                    phase=journal_phase or record.attempt.status.value,
                    application_lease=self.runtime.application_lease,
                )
            if mutation is not None:
                self.turns.record_mutation(
                    database,
                    lease,
                    mutation,
                    snapshot,
                    now=now,
                    application_lease=self.runtime.application_lease,
                )
            return snapshot

        return await self.runtime.write(commit)

    async def with_claim(
        self,
        claim: ExecutionClaim,
        expected_session_version: int,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
        record: StoredOperationAttempt,
        *,
        journal_phase: str,
        complete_session: bool = False,
    ) -> SessionSnapshot:
        def commit(database: Session, now: datetime) -> SessionSnapshot:
            claim_row = self.operations.require_execution_claim(
                database,
                claim,
                application_lease=self.runtime.application_lease,
            )
            if record.attempt.attempt_id != claim.attempt_id:
                raise SessionStoreError(SessionStoreErrorCode.RESULT_MISMATCH)
            snapshot = self.sessions.commit(
                database,
                session_id=claim.session_id,
                expected_session_version=expected_session_version,
                next_state=next_state,
                events=events,
                now=now,
                lease=self.runtime.application_lease,
                complete_session=complete_session,
            )
            self.operations.upsert_attempt(
                database,
                session_id=claim.session_id,
                record=record,
                now=now,
                phase=journal_phase,
                application_lease=self.runtime.application_lease,
            )
            claim_row.status = journal_phase
            claim_row.updated_at = now
            return snapshot

        return await self.runtime.write(commit)

    def release_turn(self, database: Session, lease: TurnLease) -> None:
        self.turns.require_no_active_child(database, lease.session_id)
        self.turns.delete_lease(
            database,
            lease,
            application_lease=self.runtime.application_lease,
        )


__all__ = ["SqlAlchemyCommitCoordinator"]
