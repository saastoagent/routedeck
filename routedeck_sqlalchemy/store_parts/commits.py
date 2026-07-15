from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.orm import Session

from routedeck_core.contracts.conversation import FinalizedConversationTurn
from routedeck_core.contracts.events import RouteDeckEvent
from routedeck_core.contracts.failures import RouteDeckFailure
from routedeck_core.contracts.mutations import MutationCommit
from routedeck_core.contracts.session import (
    RouteDeckSession,
    SessionSnapshot,
    StoredOperationAttempt,
)
from routedeck_core.state.leases import ExecutionClaim, TurnLease

from ..commits import SqlAlchemyCommitCoordinator
from ..operations import OperationRepository
from ..sessions import SessionRepository
from ..turns import TurnRepository
from .lifecycle import _StoreLifecycle


class _CommitTransactions:
    def __init__(
        self,
        *,
        lifecycle: _StoreLifecycle,
        sessions: SessionRepository,
        turns: TurnRepository,
        operations: OperationRepository,
        commits: SqlAlchemyCommitCoordinator,
    ) -> None:
        self._lifecycle = lifecycle
        self._sessions = sessions
        self._turns = turns
        self._operations = operations
        self._commits = commits

    async def commit_state(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
        mutation: MutationCommit,
    ) -> SessionSnapshot:
        return await self._commits.with_lease(
            lease,
            expected_session_version,
            next_state,
            events,
            mutation=mutation,
        )

    async def finalize_turn(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        turns: Sequence[FinalizedConversationTurn],
        events: Sequence[RouteDeckEvent],
        mutation: MutationCommit,
    ) -> SessionSnapshot:
        finalized = tuple(turns)
        if not finalized or any(
            turn.request_id != lease.request_id for turn in finalized
        ):
            raise ValueError("finalized turns must belong to their turn lease")

        def finalize(database: Session, now: datetime) -> SessionSnapshot:
            self._turns.require_lease(
                database,
                lease,
                application_lease=self._lifecycle.runtime.application_lease,
            )
            self._turns.require_no_active_child(database, lease.session_id)
            snapshot = self._sessions.commit(
                database,
                session_id=lease.session_id,
                expected_session_version=expected_session_version,
                next_state=next_state,
                events=events,
                now=now,
                lease=self._lifecycle.runtime.application_lease,
            )
            self._turns.record_mutation(
                database,
                lease,
                mutation,
                snapshot,
                now=now,
                application_lease=self._lifecycle.runtime.application_lease,
            )
            self._turns.delete_lease(
                database,
                lease,
                application_lease=self._lifecycle.runtime.application_lease,
            )
            return snapshot

        return await self._lifecycle.write(finalize)

    async def interrupt_turn(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        failure: RouteDeckFailure,
        events: Sequence[RouteDeckEvent],
        mutation: MutationCommit,
    ) -> SessionSnapshot:
        if failure.request_id not in {None, lease.request_id}:
            raise ValueError("turn failure belongs to another request")

        def interrupt(database: Session, now: datetime) -> SessionSnapshot:
            self._turns.require_lease(
                database,
                lease,
                application_lease=self._lifecycle.runtime.application_lease,
            )
            self._turns.require_no_active_child(database, lease.session_id)
            snapshot = self._sessions.commit(
                database,
                session_id=lease.session_id,
                expected_session_version=expected_session_version,
                next_state=next_state,
                events=events,
                now=now,
                lease=self._lifecycle.runtime.application_lease,
            )
            self._turns.record_mutation(
                database,
                lease,
                mutation,
                snapshot,
                now=now,
                application_lease=self._lifecycle.runtime.application_lease,
            )
            self._turns.delete_lease(
                database,
                lease,
                application_lease=self._lifecycle.runtime.application_lease,
            )
            return snapshot

        return await self._lifecycle.write(interrupt)

    async def commit_attempt(
        self,
        claim: ExecutionClaim,
        expected_session_version: int,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
        record: StoredOperationAttempt,
    ) -> SessionSnapshot:
        return await self._commits.with_claim(
            claim,
            expected_session_version,
            next_state,
            events,
            record,
            journal_phase="state_committed",
            complete_session=self._operations.record_completes_session(record),
        )

    async def commit_supervision(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
        record: StoredOperationAttempt,
    ) -> SessionSnapshot:
        return await self._commits.with_lease(
            lease,
            expected_session_version,
            next_state,
            events,
            record=record,
            journal_phase="supervision_committed",
        )

    async def mark_external_outcome_unknown(
        self,
        claim: ExecutionClaim,
        expected_session_version: int,
        record: StoredOperationAttempt,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
    ) -> SessionSnapshot:
        return await self._commits.with_claim(
            claim,
            expected_session_version,
            next_state,
            events,
            record,
            journal_phase="external_outcome_unknown",
        )

    async def release_turn(self, lease: TurnLease) -> None:
        await self._lifecycle.write(
            lambda database, _now: self._commits.release_turn(database, lease)
        )
