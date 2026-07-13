from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta, timezone
from typing import Self, TypeVar

from sqlalchemy.orm import Session

from routedeck_core.contracts.conversation import (
    FinalizedConversationTurn,
)
from routedeck_core.contracts.events import (
    CanonicalRouteDeckEvent,
    EventPage,
)
from routedeck_core.contracts.failures import RouteDeckFailure
from routedeck_core.contracts.mutations import (
    MutationCommit,
)
from routedeck_core.contracts.retention import RouteDeckRetentionPolicy
from routedeck_core.contracts.session import (
    JournaledExecutionResult,
    PendingReview,
    RouteDeckSession,
    SessionSnapshot,
    StoredOperationAttempt,
)
from routedeck_core.ports.clock import Clock
from routedeck_core.state.leases import ExecutionClaim, TurnClaim, TurnLease

from .codec import SensitiveCodec
from .commits import SqlAlchemyCommitCoordinator
from .database import DatabaseRuntime, open_database
from .lease import (
    ApplicationLease,
    RouteDeckWorkerConfigurationError,
    acquire_application_lease,
)
from .operations import OperationRepository
from .recovery import recover_abandoned_turn_batch
from .runtime import SqlAlchemyStoreRuntime, aware_utc
from .sessions import SessionRepository
from .turns import TurnRepository


T = TypeVar("T")


class UtcClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


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

    @property
    def dialect_name(self) -> str:
        return self._runtime.database.dialect_name

    @property
    def database_url(self) -> str:
        return self._runtime.database.database_url

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
        if worker_count != 1:
            raise RouteDeckWorkerConfigurationError(
                "RouteDeck SQLAlchemy persistence supports one application worker"
            )
        if not isinstance(codec, SensitiveCodec):
            raise TypeError("SqlAlchemySessionStore requires a SensitiveCodec")
        if lease_ttl <= timedelta(seconds=3):
            raise ValueError("lease_ttl must be greater than three seconds")
        effective_clock = clock or UtcClock()
        effective_retention = (
            retention_policy or RouteDeckRetentionPolicy.standalone_default()
        )
        now = aware_utc(effective_clock.now())

        def initialize() -> tuple[DatabaseRuntime, ApplicationLease]:
            database = open_database(database_url, busy_timeout=busy_timeout)
            try:
                with database.session_factory() as session, session.begin():
                    lease = acquire_application_lease(
                        session,
                        instance_id=instance_id,
                        now=now,
                        ttl=lease_ttl,
                    )
                return database, lease
            except BaseException:
                database.dispose()
                raise

        database, lease = await asyncio.to_thread(initialize)
        store = cls(
            database=database,
            instance_lease=lease,
            instance_lease_ttl=lease_ttl,
            codec=codec,
            clock=effective_clock,
            retention_policy=effective_retention,
            expected_navgraph_version=expected_navgraph_version,
        )
        try:
            await store._recover_abandoned_turns()
            if effective_retention.cleanup_on_startup:
                await store.cleanup_expired()
            store._runtime.start(
                instance_id=instance_id,
                cleanup_interval=effective_retention.cleanup_interval,
                cleanup=store.cleanup_expired,
            )
            return store
        except BaseException:
            await store.close()
            raise

    async def __aenter__(self) -> Self:
        self._runtime.ensure_open()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self._runtime.close()

    async def create(self, initial: RouteDeckSession) -> SessionSnapshot:
        return await self._write(
            lambda database, now: self.sessions.insert(
                database,
                initial,
                now=now,
                lease=self._runtime.application_lease,
            )
        )

    async def load(self, session_id: str) -> SessionSnapshot:
        return await self._read(
            lambda database, now: self.sessions.load(
                database,
                session_id,
                now=now,
            )
        )

    async def create_for_request(
        self,
        initial: RouteDeckSession,
        request_id: str,
        request_fingerprint: str,
    ) -> SessionSnapshot:
        return await self._write(
            lambda database, now: self.sessions.create_for_request(
                database,
                initial,
                request_id=request_id,
                request_fingerprint=request_fingerprint,
                now=now,
                lease=self._runtime.application_lease,
            )
        )

    async def find_attempt(
        self,
        session_id: str,
        request_id: str,
    ) -> StoredOperationAttempt | None:
        return await self._read(
            lambda database, now: self.operations.find_attempt(
                database,
                session_id=session_id,
                request_id=request_id,
                now=now,
            )
        )

    async def find_review(
        self,
        session_id: str,
        review_id: str,
    ) -> PendingReview | None:
        return await self._read(
            lambda database, now: self.operations.find_review(
                database,
                session_id=session_id,
                review_id=review_id,
                now=now,
            )
        )

    async def find_mutation(
        self,
        session_id: str,
        request_id: str,
    ):
        return await self._read(
            lambda database, now: self.turns.find_mutation(
                database,
                session_id=session_id,
                request_id=request_id,
                now=now,
            )
        )

    async def acquire_turn(self, claim: TurnClaim) -> TurnLease:
        return await self._write(
            lambda database, now: self.turns.acquire(
                database,
                claim,
                now=now,
                application_lease=self._runtime.application_lease,
            )
        )

    async def claim_child_attempt(
        self,
        lease: TurnLease,
        request_id: str,
        request_fingerprint: str,
    ) -> None:
        await self._write(
            lambda database, now: self.turns.claim_child(
                database,
                lease,
                request_id=request_id,
                request_fingerprint=request_fingerprint,
                now=now,
                application_lease=self._runtime.application_lease,
            )
        )

    async def release_child_attempt(
        self,
        lease: TurnLease,
        request_id: str,
    ) -> None:
        await self._write(
            lambda database, _now: self.turns.release_child(
                database,
                lease,
                request_id=request_id,
                application_lease=self._runtime.application_lease,
            )
        )

    async def stage_review(
        self,
        lease: TurnLease,
        expected_session_version: int,
        record: StoredOperationAttempt,
        next_state: RouteDeckSession,
        events: Sequence[CanonicalRouteDeckEvent],
        parent_mutation: MutationCommit | None = None,
    ) -> SessionSnapshot:
        if record.review is None:
            raise ValueError("stage_review requires a review record")
        return await self.commits.with_lease(
            lease,
            expected_session_version,
            next_state,
            events,
            record=record,
            journal_phase="review_staged",
            mutation=parent_mutation,
        )

    async def claim_execution(
        self,
        lease: TurnLease,
        record: StoredOperationAttempt,
    ) -> ExecutionClaim:
        return await self._write(
            lambda database, now: self.operations.claim_execution(
                database,
                lease,
                record,
                now=now,
                application_lease=self._runtime.application_lease,
            )
        )

    async def recover_execution_claim(
        self,
        lease: TurnLease,
        attempt_id: str,
    ) -> ExecutionClaim:
        return await self._write(
            lambda database, now: self.operations.recover_execution_claim(
                database,
                lease,
                attempt_id,
                now=now,
                application_lease=self._runtime.application_lease,
            )
        )

    async def record_execution_result(
        self,
        claim: ExecutionClaim,
        result: JournaledExecutionResult,
        record: StoredOperationAttempt,
    ) -> None:
        await self._write(
            lambda database, now: self.operations.record_execution_result(
                database,
                claim,
                result,
                record,
                now=now,
                application_lease=self._runtime.application_lease,
            )
        )

    async def record_execution_started(
        self,
        claim: ExecutionClaim,
        record: StoredOperationAttempt,
    ) -> None:
        await self._write(
            lambda database, now: self.operations.record_execution_started(
                database,
                claim,
                record,
                now=now,
                application_lease=self._runtime.application_lease,
            )
        )

    async def commit_state(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        events: Sequence[CanonicalRouteDeckEvent],
        mutation: MutationCommit,
    ) -> SessionSnapshot:
        return await self.commits.with_lease(
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
        events: Sequence[CanonicalRouteDeckEvent],
        mutation: MutationCommit,
    ) -> SessionSnapshot:
        finalized = tuple(turns)
        if not finalized or any(
            turn.request_id != lease.request_id for turn in finalized
        ):
            raise ValueError("finalized turns must belong to their turn lease")

        def finalize(database: Session, now: datetime) -> SessionSnapshot:
            self.turns.require_lease(
                database,
                lease,
                application_lease=self._runtime.application_lease,
            )
            self.turns.require_no_active_child(database, lease.session_id)
            snapshot = self.sessions.commit(
                database,
                session_id=lease.session_id,
                expected_session_version=expected_session_version,
                next_state=next_state,
                events=events,
                now=now,
                lease=self._runtime.application_lease,
            )
            self.turns.record_mutation(
                database,
                lease,
                mutation,
                snapshot,
                now=now,
                application_lease=self._runtime.application_lease,
            )
            self.turns.delete_lease(
                database,
                lease,
                application_lease=self._runtime.application_lease,
            )
            return snapshot

        return await self._write(finalize)

    async def interrupt_turn(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        failure: RouteDeckFailure,
        events: Sequence[CanonicalRouteDeckEvent],
        mutation: MutationCommit,
    ) -> SessionSnapshot:
        if failure.request_id not in {None, lease.request_id}:
            raise ValueError("turn failure belongs to another request")

        def interrupt(database: Session, now: datetime) -> SessionSnapshot:
            self.turns.require_lease(
                database,
                lease,
                application_lease=self._runtime.application_lease,
            )
            self.turns.require_no_active_child(database, lease.session_id)
            snapshot = self.sessions.commit(
                database,
                session_id=lease.session_id,
                expected_session_version=expected_session_version,
                next_state=next_state,
                events=events,
                now=now,
                lease=self._runtime.application_lease,
            )
            self.turns.record_mutation(
                database,
                lease,
                mutation,
                snapshot,
                now=now,
                application_lease=self._runtime.application_lease,
            )
            self.turns.delete_lease(
                database,
                lease,
                application_lease=self._runtime.application_lease,
            )
            return snapshot

        return await self._write(interrupt)

    async def commit_attempt(
        self,
        claim: ExecutionClaim,
        expected_session_version: int,
        next_state: RouteDeckSession,
        events: Sequence[CanonicalRouteDeckEvent],
        record: StoredOperationAttempt,
    ) -> SessionSnapshot:
        return await self.commits.with_claim(
            claim,
            expected_session_version,
            next_state,
            events,
            record,
            journal_phase="state_committed",
            complete_session=self.operations.record_completes_session(record),
        )

    async def commit_supervision(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        events: Sequence[CanonicalRouteDeckEvent],
        record: StoredOperationAttempt,
    ) -> SessionSnapshot:
        return await self.commits.with_lease(
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
        events: Sequence[CanonicalRouteDeckEvent],
    ) -> SessionSnapshot:
        return await self.commits.with_claim(
            claim,
            expected_session_version,
            next_state,
            events,
            record,
            journal_phase="external_outcome_unknown",
        )

    async def release_turn(self, lease: TurnLease) -> None:
        await self._write(
            lambda database, _now: self.commits.release_turn(database, lease)
        )

    async def events_after(
        self,
        session_id: str,
        cursor: int,
        limit: int,
    ) -> EventPage:
        if cursor < 0:
            raise ValueError("event cursor must be non-negative")
        if limit <= 0 or limit > 1_000:
            raise ValueError("event page limit must be between 1 and 1000")
        return await self._read(
            lambda database, now: self.sessions.events_after(
                database,
                session_id=session_id,
                cursor=cursor,
                limit=limit,
                now=now,
            )
        )

    async def load_private_blob(
        self,
        session_id: str,
        form_id: str,
    ) -> bytes | None:
        return await self._read(
            lambda database, now: self.sessions.load_private_blob(
                database,
                session_id=session_id,
                form_id=form_id,
                now=now,
            )
        )

    async def save_private_blob(
        self,
        lease: TurnLease,
        expected_session_version: int,
        form_id: str,
        encrypted_value: bytes,
        next_state: RouteDeckSession,
        events: Sequence[CanonicalRouteDeckEvent],
        mutation: MutationCommit,
    ) -> SessionSnapshot:
        if not form_id:
            raise ValueError("form_id is required")
        self.codec.decrypt(encrypted_value)

        def save(database: Session, now: datetime) -> SessionSnapshot:
            self.turns.require_lease(
                database,
                lease,
                application_lease=self._runtime.application_lease,
            )
            snapshot = self.sessions.commit(
                database,
                session_id=lease.session_id,
                expected_session_version=expected_session_version,
                next_state=next_state,
                events=events,
                now=now,
                lease=self._runtime.application_lease,
            )
            self.sessions.put_private_blob(
                database,
                session_id=lease.session_id,
                form_id=form_id,
                encrypted_value=encrypted_value,
                now=now,
            )
            self.turns.record_mutation(
                database,
                lease,
                mutation,
                snapshot,
                now=now,
                application_lease=self._runtime.application_lease,
            )
            return snapshot

        return await self._write(save)

    async def cleanup_expired(self) -> int:
        return await self._write(
            lambda database, now: self.sessions.cleanup_expired(database, now=now)
        )

    async def _recover_abandoned_turns(self) -> None:
        while True:
            recovered = await self._write(self._recover_abandoned_turn_batch)
            if recovered < self.retention_policy.cleanup_batch_size:
                return

    def _recover_abandoned_turn_batch(
        self,
        database: Session,
        now: datetime,
    ) -> int:
        return recover_abandoned_turn_batch(
            database,
            now,
            sessions=self.sessions,
            turns=self.turns,
            codec=self.codec,
            retention_policy=self.retention_policy,
            application_lease=self._runtime.application_lease,
        )

    async def _write(
        self,
        operation: Callable[[Session, datetime], T],
    ) -> T:
        return await self._runtime.write(operation)

    async def _read(
        self,
        operation: Callable[[Session, datetime], T],
    ) -> T:
        return await self._runtime.write(operation)


__all__ = ["SqlAlchemySessionStore", "UtcClock"]
