from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from typing import Self, TypeVar

from sqlalchemy.orm import Session

from routedeck_core.contracts.conversation import FinalizedConversationTurn
from routedeck_core.contracts.events import EventPage, RouteDeckEvent
from routedeck_core.contracts.failures import RouteDeckFailure
from routedeck_core.contracts.mutations import MutationCommit, MutationRecord
from routedeck_core.contracts.retention import RouteDeckRetentionPolicy
from routedeck_core.contracts.session import (
    JournaledExecutionResult,
    PendingReview,
    RouteDeckSession,
    SessionSnapshot,
    StoredOperationAttempt,
)
from routedeck_core.ports.clock import Clock
from routedeck_core.ports.codec import SensitiveCodec
from routedeck_core.state.leases import ExecutionClaim, TurnClaim, TurnLease

from .commits import SqlAlchemyCommitCoordinator
from .database import DatabaseRuntime
from .lease import ApplicationLease
from .operations import OperationRepository
from .runtime import SqlAlchemyStoreRuntime
from .sessions import SessionRepository
from .store_parts.commits import _CommitTransactions
from .store_parts.events import _EventTransactions
from .store_parts.lifecycle import _StoreLifecycle
from .store_parts.maintenance import _MaintenanceTransactions
from .store_parts.private_forms import _PrivateFormTransactions
from .store_parts.sessions import _SessionTransactions
from .store_parts.supervision import _SupervisionTransactions
from .store_parts.turns import _TurnTransactions
from .turns import TurnRepository


T = TypeVar("T")


class SqlAlchemySessionStore:
    """SQLAlchemy-backed RouteDeck authority for SQLite and PostgreSQL."""

    def __init__(
        self,
        *,
        database: DatabaseRuntime,
        instance_lease: ApplicationLease,
        instance_lease_ttl: timedelta,
        codec: SensitiveCodec,
        clock: Clock,
        retention_policy: RouteDeckRetentionPolicy,
        expected_navgraph_version: str | None,
    ) -> None:
        self._runtime = SqlAlchemyStoreRuntime(
            database=database,
            application_lease=instance_lease,
            lease_ttl=instance_lease_ttl,
            clock=clock,
        )
        self.codec = codec
        self.clock = clock
        self.retention_policy = retention_policy
        self.expected_navgraph_version = expected_navgraph_version
        self.sessions = SessionRepository(
            codec=codec,
            retention_policy=retention_policy,
            expected_navgraph_version=expected_navgraph_version,
        )
        self.turns = TurnRepository(
            sessions=self.sessions,
            retention_policy=retention_policy,
        )
        self.operations = OperationRepository(
            sessions=self.sessions,
            turns=self.turns,
        )
        self.commits = SqlAlchemyCommitCoordinator(
            runtime=self._runtime,
            sessions=self.sessions,
            turns=self.turns,
            operations=self.operations,
        )

        self._lifecycle = _StoreLifecycle(self._runtime)
        self._session_transactions = _SessionTransactions(
            lifecycle=self._lifecycle,
            sessions=self.sessions,
            operations=self.operations,
            turns=self.turns,
        )
        self._turn_transactions = _TurnTransactions(
            lifecycle=self._lifecycle,
            sessions=self.sessions,
            turns=self.turns,
        )
        self._supervision_transactions = _SupervisionTransactions(
            lifecycle=self._lifecycle,
            operations=self.operations,
            commits=self.commits,
        )
        self._commit_transactions = _CommitTransactions(
            lifecycle=self._lifecycle,
            sessions=self.sessions,
            turns=self.turns,
            operations=self.operations,
            commits=self.commits,
        )
        self._event_transactions = _EventTransactions(
            lifecycle=self._lifecycle,
            sessions=self.sessions,
        )
        self._private_form_transactions = _PrivateFormTransactions(
            lifecycle=self._lifecycle,
            codec=self.codec,
            sessions=self.sessions,
            turns=self.turns,
        )
        self._maintenance_transactions = _MaintenanceTransactions(
            lifecycle=self._lifecycle,
            codec=self.codec,
            retention_policy=self.retention_policy,
            sessions=self.sessions,
            turns=self.turns,
        )

    @property
    def dialect_name(self) -> str:
        return self._lifecycle.dialect_name

    @property
    def database_url(self) -> str:
        return self._lifecycle.database_url

    @classmethod
    async def open(
        cls,
        database_url: str,
        *,
        instance_id: str,
        codec: SensitiveCodec,
        clock: Clock | None = None,
        retention_policy: RouteDeckRetentionPolicy | None = None,
        busy_timeout: timedelta = timedelta(seconds=5),
        worker_count: int = 1,
        lease_ttl: timedelta = timedelta(seconds=30),
        expected_navgraph_version: str | None = None,
    ) -> Self:
        return await _StoreLifecycle.open_store(
            cls,
            database_url,
            instance_id=instance_id,
            codec=codec,
            clock=clock,
            retention_policy=retention_policy,
            busy_timeout=busy_timeout,
            worker_count=worker_count,
            lease_ttl=lease_ttl,
            expected_navgraph_version=expected_navgraph_version,
        )

    async def __aenter__(self) -> Self:
        self._lifecycle.ensure_open()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self._lifecycle.close()

    async def create(self, initial: RouteDeckSession) -> SessionSnapshot:
        return await self._session_transactions.create(initial)

    async def load(self, session_id: str) -> SessionSnapshot:
        return await self._session_transactions.load(session_id)

    async def create_for_request(
        self,
        initial: RouteDeckSession,
        request_id: str,
        request_fingerprint: str,
    ) -> SessionSnapshot:
        return await self._session_transactions.create_for_request(
            initial,
            request_id,
            request_fingerprint,
        )

    async def find_attempt(
        self,
        session_id: str,
        request_id: str,
    ) -> StoredOperationAttempt | None:
        return await self._session_transactions.find_attempt(
            session_id,
            request_id,
        )

    async def find_review(
        self,
        session_id: str,
        review_id: str,
    ) -> PendingReview | None:
        return await self._session_transactions.find_review(
            session_id,
            review_id,
        )

    async def find_mutation(
        self,
        session_id: str,
        request_id: str,
    ) -> MutationRecord | None:
        return await self._session_transactions.find_mutation(
            session_id,
            request_id,
        )

    async def acquire_turn(self, claim: TurnClaim) -> TurnLease:
        return await self._turn_transactions.acquire_turn(claim)

    async def start_turn(
        self,
        claim: TurnClaim,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
    ) -> TurnLease:
        return await self._turn_transactions.start_turn(
            claim,
            next_state,
            events,
        )

    async def claim_child_attempt(
        self,
        lease: TurnLease,
        request_id: str,
        request_fingerprint: str,
    ) -> None:
        await self._turn_transactions.claim_child_attempt(
            lease,
            request_id,
            request_fingerprint,
        )

    async def release_child_attempt(
        self,
        lease: TurnLease,
        request_id: str,
    ) -> None:
        await self._turn_transactions.release_child_attempt(
            lease,
            request_id,
        )

    async def stage_review(
        self,
        lease: TurnLease,
        expected_session_version: int,
        record: StoredOperationAttempt,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
        parent_mutation: MutationCommit | None = None,
    ) -> SessionSnapshot:
        return await self._supervision_transactions.stage_review(
            lease,
            expected_session_version,
            record,
            next_state,
            events,
            parent_mutation,
        )

    async def claim_execution(
        self,
        lease: TurnLease,
        record: StoredOperationAttempt,
    ) -> ExecutionClaim:
        return await self._supervision_transactions.claim_execution(
            lease,
            record,
        )

    async def recover_execution_claim(
        self,
        lease: TurnLease,
        attempt_id: str,
    ) -> ExecutionClaim:
        return await self._supervision_transactions.recover_execution_claim(
            lease,
            attempt_id,
        )

    async def record_execution_result(
        self,
        claim: ExecutionClaim,
        result: JournaledExecutionResult,
        record: StoredOperationAttempt,
    ) -> None:
        await self._supervision_transactions.record_execution_result(
            claim,
            result,
            record,
        )

    async def record_execution_started(
        self,
        claim: ExecutionClaim,
        record: StoredOperationAttempt,
    ) -> None:
        await self._supervision_transactions.record_execution_started(
            claim,
            record,
        )

    async def commit_state(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
        mutation: MutationCommit,
    ) -> SessionSnapshot:
        return await self._commit_transactions.commit_state(
            lease,
            expected_session_version,
            next_state,
            events,
            mutation,
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
        return await self._commit_transactions.finalize_turn(
            lease,
            expected_session_version,
            next_state,
            turns,
            events,
            mutation,
        )

    async def interrupt_turn(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        failure: RouteDeckFailure,
        events: Sequence[RouteDeckEvent],
        mutation: MutationCommit,
    ) -> SessionSnapshot:
        return await self._commit_transactions.interrupt_turn(
            lease,
            expected_session_version,
            next_state,
            failure,
            events,
            mutation,
        )

    async def commit_attempt(
        self,
        claim: ExecutionClaim,
        expected_session_version: int,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
        record: StoredOperationAttempt,
    ) -> SessionSnapshot:
        return await self._commit_transactions.commit_attempt(
            claim,
            expected_session_version,
            next_state,
            events,
            record,
        )

    async def commit_supervision(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
        record: StoredOperationAttempt,
    ) -> SessionSnapshot:
        return await self._commit_transactions.commit_supervision(
            lease,
            expected_session_version,
            next_state,
            events,
            record,
        )

    async def mark_external_outcome_unknown(
        self,
        claim: ExecutionClaim,
        expected_session_version: int,
        record: StoredOperationAttempt,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
    ) -> SessionSnapshot:
        return await self._commit_transactions.mark_external_outcome_unknown(
            claim,
            expected_session_version,
            record,
            next_state,
            events,
        )

    async def release_turn(self, lease: TurnLease) -> None:
        await self._commit_transactions.release_turn(lease)

    async def events_after(
        self,
        session_id: str,
        cursor: int,
        limit: int,
    ) -> EventPage:
        return await self._event_transactions.events_after(
            session_id,
            cursor,
            limit,
        )

    async def load_private_blob(
        self,
        session_id: str,
        form_id: str,
    ) -> bytes | None:
        return await self._private_form_transactions.load_private_blob(
            session_id,
            form_id,
        )

    async def save_private_blob(
        self,
        lease: TurnLease,
        expected_session_version: int,
        form_id: str,
        encrypted_value: bytes,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
        mutation: MutationCommit,
    ) -> SessionSnapshot:
        return await self._private_form_transactions.save_private_blob(
            lease,
            expected_session_version,
            form_id,
            encrypted_value,
            next_state,
            events,
            mutation,
        )

    async def cleanup_expired(self) -> int:
        return await self._maintenance_transactions.cleanup_expired()

    async def _recover_abandoned_turns(self) -> None:
        await self._maintenance_transactions.recover_abandoned_turns()

    def _recover_abandoned_turn_batch(
        self,
        database: Session,
        now: datetime,
    ) -> int:
        return self._maintenance_transactions.recover_abandoned_turn_batch(
            database,
            now,
        )

    async def _write(
        self,
        operation: Callable[[Session, datetime], T],
    ) -> T:
        return await self._lifecycle.write(operation)

    async def _read(
        self,
        operation: Callable[[Session, datetime], T],
    ) -> T:
        return await self._lifecycle.read(operation)


__all__ = ["SqlAlchemySessionStore"]
