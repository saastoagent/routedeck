from __future__ import annotations

import asyncio
import hashlib
import json
import secrets
import sqlite3
import uuid
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Self, TypeVar

from pydantic import SecretStr

from routedeck_core.contracts.conversation import (
    ConversationRole,
    ConversationTurn,
    ConversationTurnStatus,
    FinalizedConversationTurn,
)
from routedeck_core.contracts.events import (
    CanonicalRouteDeckEvent,
    EventPage,
    PublicEventPayload,
    RouteDeckEventKind,
)
from routedeck_core.contracts.failures import FailureKind, RouteDeckFailure
from routedeck_core.contracts.mutations import (
    MutationCommit,
    MutationKind,
    MutationRecord,
    MutationStatus,
)
from routedeck_core.contracts.operations import (
    OperationDisposition,
)
from routedeck_core.contracts.projection import FrozenJsonObject
from routedeck_core.contracts.retention import RouteDeckRetentionPolicy
from routedeck_core.contracts.session import (
    AttemptTerminalState,
    JournaledExecutionResult,
    OperationAttemptStatus,
    PendingReview,
    RouteDeckSession,
    SessionSnapshot,
    StoredOperationAttempt,
)
from routedeck_core.ports.clock import Clock
from routedeck_core.ports.session_store import SessionStoreError, SessionStoreErrorCode
from routedeck_core.state.leases import (
    ExecutionClaim,
    TurnClaim,
    TurnLease,
    TurnOwnerKind,
)
from routedeck_core.state.reducer import (
    ConversationTurnsStored,
    PublicEventsRecorded,
    PublicSessionStateStored,
    reduce_session_batch,
)
from routedeck_core.state.session import SESSION_SCHEMA_VERSION

from .codec import SensitiveCodec
from .connection import (
    SqliteConnectionSettings,
    immediate_transaction,
    open_sqlite_connection,
)
from .instance_lease import (
    ApplicationLease,
    RouteDeckInstanceLeaseLost,
    RouteDeckWorkerConfigurationError,
    acquire_application_lease,
    assert_application_lease,
    heartbeat_application_lease,
    release_application_lease,
)
from .migrations import migrate


T = TypeVar("T")


class UtcClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)
class SqliteSessionStore:
    """Durable, fenced, single-worker implementation of RouteDeckSessionStore."""

    def __init__(
        self,
        *,
        database_path: Path,
        connection: sqlite3.Connection,
        instance_lease: ApplicationLease,
        instance_lease_ttl: timedelta,
        codec: SensitiveCodec,
        clock: Clock,
        retention_policy: RouteDeckRetentionPolicy,
        expected_navgraph_version: str | None,
    ) -> None:
        self.database_path = database_path
        self._connection = connection
        self._instance_lease = instance_lease
        self._instance_lease_ttl = instance_lease_ttl
        self.codec = codec
        self.clock = clock
        self.retention_policy = retention_policy
        self.expected_navgraph_version = expected_navgraph_version
        self._connection_lock = asyncio.Lock()
        self._closed = False
        self._background_failure: BaseException | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._cleanup_task: asyncio.Task[None] | None = None

    @classmethod
    async def open(
        cls,
        database_path: str | Path,
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
                "routedeck_sqlite supports exactly one application worker"
            )
        if not isinstance(codec, SensitiveCodec):
            raise TypeError("SqliteSessionStore requires a SensitiveCodec")
        if lease_ttl <= timedelta(seconds=3):
            raise ValueError("lease_ttl must be greater than three seconds")
        effective_clock = clock or UtcClock()
        effective_retention = (
            retention_policy or RouteDeckRetentionPolicy.standalone_default()
        )
        resolved = Path(database_path).expanduser().resolve()
        now = _aware_utc(effective_clock.now())

        def initialize() -> tuple[sqlite3.Connection, ApplicationLease]:
            connection = open_sqlite_connection(
                resolved,
                settings=SqliteConnectionSettings(busy_timeout=busy_timeout),
            )
            try:
                migrate(connection)
                lease = acquire_application_lease(
                    connection,
                    instance_id=instance_id,
                    now=now,
                    ttl=lease_ttl,
                )
                return connection, lease
            except BaseException:
                connection.close()
                raise

        connection, lease = await asyncio.to_thread(initialize)
        store = cls(
            database_path=resolved,
            connection=connection,
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
            store._heartbeat_task = asyncio.create_task(
                store._heartbeat_loop(),
                name=f"routedeck-sqlite-heartbeat:{instance_id}",
            )
            store._cleanup_task = asyncio.create_task(
                store._cleanup_loop(),
                name=f"routedeck-sqlite-cleanup:{instance_id}",
            )
            return store
        except BaseException:
            await store._close_connection(release=True)
            raise

    async def __aenter__(self) -> Self:
        self._ensure_open()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def close(self) -> None:
        if self._closed:
            return
        tasks = tuple(
            task
            for task in (self._heartbeat_task, self._cleanup_task)
            if task is not None
        )
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await self._close_connection(release=True)

    async def create(self, initial: RouteDeckSession) -> SessionSnapshot:
        self._validate_session_compatibility(initial)

        def write(connection: sqlite3.Connection, now: datetime) -> SessionSnapshot:
            return self._insert_session(connection, initial, now)

        return await self._write(write)

    async def create_for_request(
        self,
        initial: RouteDeckSession,
        request_id: str,
        request_fingerprint: str,
    ) -> SessionSnapshot:
        if not request_id or not request_fingerprint:
            raise ValueError("session creation request identity is required")
        self._validate_session_compatibility(initial)

        def write(connection: sqlite3.Connection, now: datetime) -> SessionSnapshot:
            existing = connection.execute(
                "SELECT request_fingerprint, session_id "
                "FROM session_creation_requests WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            if existing is not None:
                if str(existing["request_fingerprint"]) != request_fingerprint:
                    raise SessionStoreError(SessionStoreErrorCode.REQUEST_ID_REUSED)
                row = self._load_session_row(
                    connection,
                    str(existing["session_id"]),
                    now,
                )
                return SessionSnapshot(state=self._deserialize_state(connection, row))
            snapshot = self._insert_session(connection, initial, now)
            connection.execute(
                """
                INSERT INTO session_creation_requests(
                    request_id, request_fingerprint, session_id, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    request_id,
                    request_fingerprint,
                    initial.session_id,
                    now.isoformat(),
                ),
            )
            return snapshot

        return await self._write(write)

    async def load(self, session_id: str) -> SessionSnapshot:
        def read(connection: sqlite3.Connection, now: datetime) -> SessionSnapshot:
            row = self._load_session_row(connection, session_id, now)
            state = self._deserialize_state(connection, row)
            self._validate_session_compatibility(state)
            return SessionSnapshot(state=state)

        return await self._read(read)

    async def find_attempt(
        self,
        session_id: str,
        request_id: str,
    ) -> StoredOperationAttempt | None:
        def read(
            connection: sqlite3.Connection, now: datetime
        ) -> StoredOperationAttempt | None:
            self._load_session_row(connection, session_id, now)
            row = connection.execute(
                "SELECT record_json FROM operation_attempts "
                "WHERE session_id = ? AND request_id = ?",
                (session_id, request_id),
            ).fetchone()
            return (
                StoredOperationAttempt.model_validate_json(str(row["record_json"]))
                if row is not None
                else None
            )

        return await self._read(read)

    async def find_review(
        self,
        session_id: str,
        review_id: str,
    ) -> PendingReview | None:
        def read(connection: sqlite3.Connection, now: datetime) -> PendingReview | None:
            self._load_session_row(connection, session_id, now)
            row = connection.execute(
                "SELECT record_json FROM reviews WHERE session_id = ? AND review_id = ?",
                (session_id, review_id),
            ).fetchone()
            return (
                PendingReview.model_validate_json(str(row["record_json"]))
                if row is not None
                else None
            )

        return await self._read(read)

    async def find_mutation(
        self,
        session_id: str,
        request_id: str,
    ) -> MutationRecord | None:
        def read(
            connection: sqlite3.Connection,
            now: datetime,
        ) -> MutationRecord | None:
            self._load_session_row(connection, session_id, now)
            row = connection.execute(
                "SELECT * FROM mutation_journal "
                "WHERE session_id = ? AND request_id = ?",
                (session_id, request_id),
            ).fetchone()
            if row is None:
                return None
            return MutationRecord(
                session_id=session_id,
                request_id=request_id,
                request_fingerprint=str(row["request_fingerprint"]),
                kind=MutationKind(str(row["mutation_kind"])),
                status=MutationStatus(str(row["status"])),
                result=json.loads(str(row["result_json"])),
                committed_session_version=int(row["committed_session_version"]),
                committed_projection_version=int(row["committed_projection_version"]),
                committed_event_cursor=int(row["committed_event_cursor"]),
            )

        return await self._read(read)

    async def acquire_turn(self, claim: TurnClaim) -> TurnLease:
        capability = secrets.token_urlsafe(32)

        def write(connection: sqlite3.Connection, now: datetime) -> TurnLease:
            recorded_mutation = connection.execute(
                "SELECT 1 FROM mutation_journal "
                "WHERE session_id = ? AND request_id = ?",
                (claim.session_id, claim.request_id),
            ).fetchone()
            if recorded_mutation is not None:
                raise SessionStoreError(SessionStoreErrorCode.REQUEST_ID_REUSED)
            recorded_operation = connection.execute(
                "SELECT request_fingerprint FROM operation_attempts "
                "WHERE session_id = ? AND request_id = ?",
                (claim.session_id, claim.request_id),
            ).fetchone()
            if (
                recorded_operation is not None
                and str(recorded_operation["request_fingerprint"])
                != claim.request_fingerprint
            ):
                raise SessionStoreError(SessionStoreErrorCode.REQUEST_ID_REUSED)
            row = self._require_session_version(
                connection, claim.session_id, claim.expected_session_version, now
            )
            if (
                connection.execute(
                    "SELECT 1 FROM turn_leases WHERE session_id = ?",
                    (claim.session_id,),
                ).fetchone()
                is not None
            ):
                raise SessionStoreError(SessionStoreErrorCode.OPERATION_IN_PROGRESS)
            connection.execute(
                """
                INSERT INTO turn_leases(
                    session_id, request_id, request_fingerprint, owner_kind,
                    parent_turn_id, capability_hash, fencing_token, acquired_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    claim.session_id,
                    claim.request_id,
                    claim.request_fingerprint,
                    claim.owner_kind.value,
                    claim.parent_turn_id,
                    _capability_hash(capability),
                    self._instance_lease.fencing_token,
                    now.isoformat(),
                ),
            )
            if row["completed_at"] is None:
                idle_expires = now + self.retention_policy.unfinished_idle_ttl
                absolute_expires = datetime.fromisoformat(
                    str(row["absolute_expires_at"])
                )
                expires = min(idle_expires, absolute_expires)
            else:
                idle_expires = datetime.fromisoformat(str(row["idle_expires_at"]))
                expires = datetime.fromisoformat(str(row["expires_at"]))
            changed = connection.execute(
                """
                UPDATE sessions SET owner_fencing_token = ?, last_accessed_at = ?,
                    idle_expires_at = ?, expires_at = ?
                WHERE session_id = ? AND session_version = ?
                  AND owner_fencing_token <= ?
                """,
                (
                    self._instance_lease.fencing_token,
                    now.isoformat(),
                    idle_expires.isoformat(),
                    expires.isoformat(),
                    claim.session_id,
                    int(row["session_version"]),
                    self._instance_lease.fencing_token,
                ),
            ).rowcount
            if changed != 1:
                raise SessionStoreError(SessionStoreErrorCode.VERSION_CONFLICT)
            return TurnLease(
                capability=SecretStr(capability),
                fencing_token=self._instance_lease.fencing_token,
                session_id=claim.session_id,
                request_id=claim.request_id,
            )

        return await self._write(write)

    async def claim_child_attempt(
        self,
        lease: TurnLease,
        request_id: str,
        request_fingerprint: str,
    ) -> None:
        def write(connection: sqlite3.Connection, now: datetime) -> None:
            self._require_turn_lease(connection, lease)
            if (
                connection.execute(
                    "SELECT 1 FROM active_child_attempts WHERE session_id = ?",
                    (lease.session_id,),
                ).fetchone()
                is not None
            ):
                raise SessionStoreError(SessionStoreErrorCode.OPERATION_IN_PROGRESS)
            previous = connection.execute(
                "SELECT request_fingerprint FROM operation_attempts "
                "WHERE session_id = ? AND request_id = ?",
                (lease.session_id, request_id),
            ).fetchone()
            mutation = connection.execute(
                "SELECT 1 FROM mutation_journal "
                "WHERE session_id = ? AND request_id = ?",
                (lease.session_id, request_id),
            ).fetchone()
            if previous is not None or mutation is not None:
                raise SessionStoreError(SessionStoreErrorCode.REQUEST_ID_REUSED)
            connection.execute(
                """
                INSERT INTO active_child_attempts(
                    session_id, parent_request_id, request_id,
                    request_fingerprint, acquired_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    lease.session_id,
                    lease.request_id,
                    request_id,
                    request_fingerprint,
                    now.isoformat(),
                ),
            )

        await self._write(write)

    async def release_child_attempt(
        self,
        lease: TurnLease,
        request_id: str,
    ) -> None:
        def write(connection: sqlite3.Connection, now: datetime) -> None:
            del now
            self._require_turn_lease(connection, lease)
            changed = connection.execute(
                "DELETE FROM active_child_attempts "
                "WHERE session_id = ? AND parent_request_id = ? AND request_id = ?",
                (lease.session_id, lease.request_id, request_id),
            ).rowcount
            if changed != 1:
                raise SessionStoreError(SessionStoreErrorCode.LEASE_MISMATCH)

        await self._write(write)

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
        return await self._commit_with_lease(
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
        capability = secrets.token_urlsafe(32)

        def write(connection: sqlite3.Connection, now: datetime) -> ExecutionClaim:
            self._require_turn_lease(connection, lease)
            attempt = record.attempt
            if (
                connection.execute(
                    "SELECT 1 FROM execution_claims WHERE attempt_id = ?",
                    (attempt.attempt_id,),
                ).fetchone()
                is not None
            ):
                raise SessionStoreError(SessionStoreErrorCode.EXECUTION_ALREADY_CLAIMED)
            if attempt.parent_turn_id is not None:
                child = connection.execute(
                    "SELECT request_id FROM active_child_attempts WHERE session_id = ?",
                    (lease.session_id,),
                ).fetchone()
                if child is None or str(child["request_id"]) != attempt.request_id:
                    raise SessionStoreError(SessionStoreErrorCode.LEASE_MISMATCH)
            if attempt.resumed_review_id is not None:
                self._accept_review_record(connection, lease.session_id, record, now)
            self._upsert_attempt(
                connection,
                lease.session_id,
                record,
                now,
                phase="execution_claimed",
            )
            connection.execute(
                """
                INSERT INTO execution_claims(
                    attempt_id, session_id, request_id, capability_hash,
                    fencing_token, status, claimed_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'claimed', ?, ?)
                """,
                (
                    attempt.attempt_id,
                    lease.session_id,
                    attempt.request_id,
                    _capability_hash(capability),
                    self._instance_lease.fencing_token,
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
            return ExecutionClaim(
                capability=SecretStr(capability),
                fencing_token=self._instance_lease.fencing_token,
                session_id=lease.session_id,
                request_id=attempt.request_id,
                attempt_id=attempt.attempt_id,
            )

        return await self._write(write)

    async def recover_execution_claim(
        self,
        lease: TurnLease,
        attempt_id: str,
    ) -> ExecutionClaim:
        capability = secrets.token_urlsafe(32)

        def write(connection: sqlite3.Connection, now: datetime) -> ExecutionClaim:
            self._require_turn_lease(connection, lease)
            row = connection.execute(
                "SELECT session_id, request_id FROM execution_claims WHERE attempt_id = ?",
                (attempt_id,),
            ).fetchone()
            if row is None or str(row["session_id"]) != lease.session_id:
                raise SessionStoreError(SessionStoreErrorCode.LEASE_MISMATCH)
            changed = connection.execute(
                """
                UPDATE execution_claims
                SET capability_hash = ?, fencing_token = ?, updated_at = ?
                WHERE attempt_id = ? AND session_id = ? AND fencing_token <= ?
                """,
                (
                    _capability_hash(capability),
                    self._instance_lease.fencing_token,
                    now.isoformat(),
                    attempt_id,
                    lease.session_id,
                    self._instance_lease.fencing_token,
                ),
            ).rowcount
            if changed != 1:
                raise SessionStoreError(SessionStoreErrorCode.LEASE_MISMATCH)
            return ExecutionClaim(
                capability=SecretStr(capability),
                fencing_token=self._instance_lease.fencing_token,
                session_id=lease.session_id,
                request_id=str(row["request_id"]),
                attempt_id=attempt_id,
            )

        return await self._write(write)

    async def record_execution_result(
        self,
        claim: ExecutionClaim,
        result: JournaledExecutionResult,
        record: StoredOperationAttempt,
    ) -> None:
        if record.journaled_result != result:
            raise SessionStoreError(SessionStoreErrorCode.RESULT_MISMATCH)

        def write(connection: sqlite3.Connection, now: datetime) -> None:
            self._require_execution_claim(connection, claim)
            if (
                result.attempt_id != claim.attempt_id
                or result.request_id != claim.request_id
            ):
                raise SessionStoreError(SessionStoreErrorCode.RESULT_MISMATCH)
            self._upsert_attempt(
                connection,
                claim.session_id,
                record,
                now,
                phase="execution_result_recorded",
            )
            try:
                connection.execute(
                    """
                    INSERT INTO execution_results(
                        result_id, attempt_id, session_id, result_json,
                        record_json, result_fingerprint, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        result.result_id,
                        result.attempt_id,
                        claim.session_id,
                        result.model_dump_json(),
                        record.model_dump_json(),
                        result.result_fingerprint,
                        now.isoformat(),
                    ),
                )
            except sqlite3.IntegrityError as error:
                existing = connection.execute(
                    "SELECT result_json FROM execution_results WHERE attempt_id = ?",
                    (result.attempt_id,),
                ).fetchone()
                if (
                    existing is None
                    or str(existing["result_json"]) != result.model_dump_json()
                ):
                    raise SessionStoreError(
                        SessionStoreErrorCode.RESULT_MISMATCH
                    ) from error
            connection.execute(
                "UPDATE execution_claims SET status = 'result_recorded', updated_at = ? "
                "WHERE attempt_id = ? AND fencing_token = ?",
                (now.isoformat(), claim.attempt_id, claim.fencing_token),
            )

        await self._write(write)

    async def record_execution_started(
        self,
        claim: ExecutionClaim,
        record: StoredOperationAttempt,
    ) -> None:
        def write(connection: sqlite3.Connection, now: datetime) -> None:
            self._require_execution_claim(connection, claim)
            self._upsert_attempt(
                connection,
                claim.session_id,
                record,
                now,
                phase="tool_started",
            )
            changed = connection.execute(
                """
                UPDATE execution_claims SET status = 'started', updated_at = ?
                WHERE attempt_id = ? AND fencing_token = ?
                """,
                (now.isoformat(), claim.attempt_id, claim.fencing_token),
            ).rowcount
            if changed != 1:
                raise SessionStoreError(SessionStoreErrorCode.LEASE_MISMATCH)

        await self._write(write)

    async def commit_state(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        events: Sequence[CanonicalRouteDeckEvent],
        mutation: MutationCommit,
    ) -> SessionSnapshot:
        return await self._commit_with_lease(
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

        def write(connection: sqlite3.Connection, now: datetime) -> SessionSnapshot:
            self._require_turn_lease(connection, lease)
            self._require_no_active_child(connection, lease.session_id)
            snapshot = self._commit_session(
                connection,
                lease.session_id,
                expected_session_version,
                next_state,
                events,
                now,
            )
            self._record_mutation(connection, lease, mutation, snapshot, now)
            self._delete_turn_lease(connection, lease)
            return snapshot

        return await self._write(write)

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

        def write(connection: sqlite3.Connection, now: datetime) -> SessionSnapshot:
            self._require_turn_lease(connection, lease)
            self._require_no_active_child(connection, lease.session_id)
            snapshot = self._commit_session(
                connection,
                lease.session_id,
                expected_session_version,
                next_state,
                events,
                now,
            )
            self._record_mutation(connection, lease, mutation, snapshot, now)
            self._delete_turn_lease(connection, lease)
            return snapshot

        return await self._write(write)

    async def commit_attempt(
        self,
        claim: ExecutionClaim,
        expected_session_version: int,
        next_state: RouteDeckSession,
        events: Sequence[CanonicalRouteDeckEvent],
        record: StoredOperationAttempt,
    ) -> SessionSnapshot:
        return await self._commit_with_claim(
            claim,
            expected_session_version,
            next_state,
            events,
            record,
            journal_phase="state_committed",
            complete_session=self._record_completes_session(record),
        )

    async def commit_supervision(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        events: Sequence[CanonicalRouteDeckEvent],
        record: StoredOperationAttempt,
    ) -> SessionSnapshot:
        return await self._commit_with_lease(
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
        return await self._commit_with_claim(
            claim,
            expected_session_version,
            next_state,
            events,
            record,
            journal_phase="external_outcome_unknown",
        )

    async def release_turn(self, lease: TurnLease) -> None:
        def write(connection: sqlite3.Connection, now: datetime) -> None:
            del now
            self._require_turn_lease(connection, lease)
            self._require_no_active_child(connection, lease.session_id)
            self._delete_turn_lease(connection, lease)

        await self._write(write)

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

        def read(connection: sqlite3.Connection, now: datetime) -> EventPage:
            session = self._load_session_row(connection, session_id, now)
            current_cursor = int(session["event_cursor"])
            if cursor > current_cursor:
                raise SessionStoreError(SessionStoreErrorCode.VERSION_CONFLICT)
            retained = connection.execute(
                "SELECT MIN(cursor) AS first_cursor FROM events WHERE session_id = ?",
                (session_id,),
            ).fetchone()["first_cursor"]
            if current_cursor > cursor and (
                retained is None or cursor < int(retained) - 1
            ):
                retained_cursor = (
                    int(retained) if retained is not None else current_cursor
                )
                return EventPage(
                    events=(),
                    next_cursor=cursor,
                    has_more=False,
                    reset_required=True,
                    retained_from_cursor=retained_cursor,
                )
            rows = connection.execute(
                "SELECT event_json FROM events "
                "WHERE session_id = ? AND cursor > ? ORDER BY cursor LIMIT ?",
                (session_id, cursor, limit + 1),
            ).fetchall()
            has_more = len(rows) > limit
            page_rows = rows[:limit]
            events = tuple(
                CanonicalRouteDeckEvent.model_validate_json(str(row["event_json"]))
                for row in page_rows
            )
            return EventPage(
                events=events,
                next_cursor=events[-1].cursor if events else cursor,
                has_more=has_more,
            )

        return await self._read(read)

    async def load_private_blob(
        self,
        session_id: str,
        form_id: str,
    ) -> bytes | None:
        def read(connection: sqlite3.Connection, now: datetime) -> bytes | None:
            self._load_session_row(connection, session_id, now)
            row = connection.execute(
                "SELECT ciphertext FROM private_blobs WHERE session_id = ? AND form_id = ?",
                (session_id, form_id),
            ).fetchone()
            if row is None:
                return None
            ciphertext = bytes(row["ciphertext"])
            self.codec.decrypt(ciphertext)
            return ciphertext

        return await self._read(read)

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

        def write(connection: sqlite3.Connection, now: datetime) -> SessionSnapshot:
            self._require_turn_lease(connection, lease)
            snapshot = self._commit_session(
                connection,
                lease.session_id,
                expected_session_version,
                next_state,
                events,
                now,
            )
            connection.execute(
                """
                INSERT INTO private_blobs(session_id, form_id, ciphertext, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id, form_id) DO UPDATE SET
                    ciphertext = excluded.ciphertext,
                    updated_at = excluded.updated_at
                """,
                (lease.session_id, form_id, encrypted_value, now.isoformat()),
            )
            self._record_mutation(connection, lease, mutation, snapshot, now)
            return snapshot

        return await self._write(write)

    async def cleanup_expired(self) -> int:
        def write(connection: sqlite3.Connection, now: datetime) -> int:
            rows = connection.execute(
                "SELECT session_id FROM sessions WHERE expires_at <= ? "
                "ORDER BY expires_at, session_id LIMIT ?",
                (now.isoformat(), self.retention_policy.cleanup_batch_size),
            ).fetchall()
            session_ids = tuple(str(row["session_id"]) for row in rows)
            for session_id in session_ids:
                connection.execute(
                    "INSERT INTO session_tombstones(session_id, expired_at) VALUES (?, ?) "
                    "ON CONFLICT(session_id) DO UPDATE SET expired_at = excluded.expired_at",
                    (session_id, now.isoformat()),
                )
                connection.execute(
                    "DELETE FROM sessions WHERE session_id = ?", (session_id,)
                )
            cutoff = (now - self.retention_policy.event_retention_ttl).isoformat()
            event_rows = connection.execute(
                "SELECT rowid FROM events WHERE created_at < ? ORDER BY created_at LIMIT ?",
                (cutoff, self.retention_policy.cleanup_batch_size),
            ).fetchall()
            if event_rows:
                placeholders = ",".join("?" for _ in event_rows)
                connection.execute(
                    f"DELETE FROM events WHERE rowid IN ({placeholders})",
                    tuple(int(row["rowid"]) for row in event_rows),
                )
            return len(session_ids) + len(event_rows)

        return await self._write(write)

    async def _commit_with_lease(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        events: Sequence[CanonicalRouteDeckEvent],
        *,
        record: StoredOperationAttempt | None = None,
        journal_phase: str | None = None,
        mutation: MutationCommit | None = None,
    ) -> SessionSnapshot:
        def write(connection: sqlite3.Connection, now: datetime) -> SessionSnapshot:
            self._require_turn_lease(connection, lease)
            snapshot = self._commit_session(
                connection,
                lease.session_id,
                expected_session_version,
                next_state,
                events,
                now,
            )
            if record is not None:
                self._upsert_attempt(
                    connection,
                    lease.session_id,
                    record,
                    now,
                    phase=journal_phase or record.attempt.status.value,
                )
            if mutation is not None:
                self._record_mutation(connection, lease, mutation, snapshot, now)
            return snapshot

        return await self._write(write)

    async def _commit_with_claim(
        self,
        claim: ExecutionClaim,
        expected_session_version: int,
        next_state: RouteDeckSession,
        events: Sequence[CanonicalRouteDeckEvent],
        record: StoredOperationAttempt,
        *,
        journal_phase: str,
        complete_session: bool = False,
    ) -> SessionSnapshot:
        def write(connection: sqlite3.Connection, now: datetime) -> SessionSnapshot:
            self._require_execution_claim(connection, claim)
            if record.attempt.attempt_id != claim.attempt_id:
                raise SessionStoreError(SessionStoreErrorCode.RESULT_MISMATCH)
            snapshot = self._commit_session(
                connection,
                claim.session_id,
                expected_session_version,
                next_state,
                events,
                now,
                complete_session=complete_session,
            )
            self._upsert_attempt(
                connection,
                claim.session_id,
                record,
                now,
                phase=journal_phase,
            )
            connection.execute(
                "UPDATE execution_claims SET status = ?, updated_at = ? "
                "WHERE attempt_id = ? AND fencing_token = ?",
                (
                    journal_phase,
                    now.isoformat(),
                    claim.attempt_id,
                    claim.fencing_token,
                ),
            )
            return snapshot

        return await self._write(write)

    def _commit_session(
        self,
        connection: sqlite3.Connection,
        session_id: str,
        expected_session_version: int,
        next_state: RouteDeckSession,
        events: Sequence[CanonicalRouteDeckEvent],
        now: datetime,
        *,
        complete_session: bool = False,
    ) -> SessionSnapshot:
        current = self._require_session_version(
            connection, session_id, expected_session_version, now
        )
        self._validate_next_state(current, next_state, events)
        state_json, conversation = self._serialize_state(next_state)
        raw_completed_at = current["completed_at"]
        absolute_expires = datetime.fromisoformat(str(current["absolute_expires_at"]))
        if raw_completed_at is None and complete_session:
            completed_at = now
            idle_expires = datetime.fromisoformat(str(current["idle_expires_at"]))
            expires = completed_at + self.retention_policy.completed_ttl
        elif raw_completed_at is None:
            completed_at = None
            idle_expires = now + self.retention_policy.unfinished_idle_ttl
            expires = min(idle_expires, absolute_expires)
        else:
            completed_at = datetime.fromisoformat(str(raw_completed_at))
            idle_expires = datetime.fromisoformat(str(current["idle_expires_at"]))
            expires = completed_at + self.retention_policy.completed_ttl
        changed = connection.execute(
            """
            UPDATE sessions SET
                schema_version = ?, navgraph_version = ?, session_version = ?,
                projection_version = ?, event_cursor = ?, state_json = ?,
                updated_at = ?, last_accessed_at = ?, idle_expires_at = ?,
                completed_at = ?, expires_at = ?, owner_fencing_token = ?
            WHERE session_id = ? AND session_version = ?
              AND owner_fencing_token <= ?
            """,
            (
                next_state.schema_version,
                next_state.navgraph_version,
                next_state.session_version,
                next_state.projection_version,
                next_state.event_cursor,
                state_json,
                now.isoformat(),
                now.isoformat(),
                idle_expires.isoformat(),
                completed_at.isoformat() if completed_at is not None else None,
                expires.isoformat(),
                self._instance_lease.fencing_token,
                session_id,
                expected_session_version,
                self._instance_lease.fencing_token,
            ),
        ).rowcount
        if changed != 1:
            raise SessionStoreError(SessionStoreErrorCode.VERSION_CONFLICT)
        self._sync_conversation_blobs(connection, session_id, conversation, now)
        self._sync_private_blobs(
            connection,
            session_id,
            tuple(draft.form_id for draft in next_state.private_state.drafts),
        )
        self._append_events(connection, session_id, events, now)
        return SessionSnapshot(state=next_state)

    @staticmethod
    def _record_completes_session(record: StoredOperationAttempt) -> bool:
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

    def _validate_next_state(
        self,
        current: sqlite3.Row,
        next_state: RouteDeckSession,
        events: Sequence[CanonicalRouteDeckEvent],
    ) -> None:
        if next_state.session_id != str(current["session_id"]):
            raise ValueError("next state belongs to another session")
        self._validate_session_compatibility(next_state)
        current_session_version = int(current["session_version"])
        current_projection_version = int(current["projection_version"])
        current_event_cursor = int(current["event_cursor"])
        if next_state.session_version < current_session_version:
            raise SessionStoreError(SessionStoreErrorCode.VERSION_CONFLICT)
        if next_state.projection_version < current_projection_version:
            raise SessionStoreError(SessionStoreErrorCode.VERSION_CONFLICT)
        expected_cursors = tuple(
            range(current_event_cursor + 1, current_event_cursor + len(events) + 1)
        )
        event_cursors = tuple(event.cursor for event in events)
        if event_cursors != expected_cursors:
            raise ValueError("durable event cursors must be contiguous")
        if next_state.event_cursor != current_event_cursor + len(events):
            raise ValueError("session event cursor must match appended events")
        for event in events:
            if event.session_id != next_state.session_id:
                raise ValueError("durable event belongs to another session")
            if event.session_version != next_state.session_version:
                raise ValueError("durable event session version mismatch")

    def _append_events(
        self,
        connection: sqlite3.Connection,
        session_id: str,
        events: Sequence[CanonicalRouteDeckEvent],
        now: datetime,
    ) -> None:
        for event in events:
            connection.execute(
                """
                INSERT INTO events(
                    session_id, cursor, event_id, event_type, session_version,
                    projection_version, created_at, event_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    event.cursor,
                    event.event_id,
                    event.event_type.value,
                    event.session_version,
                    event.projection_version,
                    event.created_at.isoformat(),
                    event.model_dump_json(),
                ),
            )
        cutoff = (now - self.retention_policy.event_retention_ttl).isoformat()
        connection.execute(
            "DELETE FROM events WHERE session_id = ? AND created_at < ?",
            (session_id, cutoff),
        )
        overflow = connection.execute(
            "SELECT cursor FROM events WHERE session_id = ? "
            "ORDER BY cursor DESC LIMIT 1 OFFSET ?",
            (session_id, self.retention_policy.max_events_per_session),
        ).fetchone()
        if overflow is not None:
            connection.execute(
                "DELETE FROM events WHERE session_id = ? AND cursor <= ?",
                (session_id, int(overflow["cursor"])),
            )

    def _upsert_attempt(
        self,
        connection: sqlite3.Connection,
        session_id: str,
        record: StoredOperationAttempt,
        now: datetime,
        *,
        phase: str,
    ) -> None:
        attempt = record.attempt
        existing = connection.execute(
            "SELECT attempt_id, request_fingerprint, created_at FROM operation_attempts "
            "WHERE session_id = ? AND request_id = ?",
            (session_id, attempt.request_id),
        ).fetchone()
        if existing is not None and (
            str(existing["attempt_id"]) != attempt.attempt_id
            or str(existing["request_fingerprint"]) != attempt.request_fingerprint
        ):
            raise SessionStoreError(SessionStoreErrorCode.REQUEST_ID_REUSED)
        created_at = (
            str(existing["created_at"]) if existing is not None else now.isoformat()
        )
        connection.execute(
            """
            INSERT INTO operation_attempts(
                attempt_id, session_id, request_id, request_fingerprint,
                record_json, review_id, status, fencing_token, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id, request_id) DO UPDATE SET
                record_json = excluded.record_json,
                review_id = excluded.review_id,
                status = excluded.status,
                fencing_token = excluded.fencing_token,
                updated_at = excluded.updated_at
            """,
            (
                attempt.attempt_id,
                session_id,
                attempt.request_id,
                attempt.request_fingerprint,
                record.model_dump_json(),
                record.review.review_id if record.review is not None else None,
                attempt.status.value,
                self._instance_lease.fencing_token,
                created_at,
                now.isoformat(),
            ),
        )
        connection.execute(
            """
            INSERT INTO operation_journal(
                session_id, attempt_id, phase, record_json, created_at, fencing_token
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                attempt.attempt_id,
                phase,
                record.model_dump_json(),
                now.isoformat(),
                self._instance_lease.fencing_token,
            ),
        )
        if record.review is not None:
            review = record.review
            connection.execute(
                """
                INSERT INTO reviews(
                    review_id, session_id, attempt_id, record_json,
                    resolution, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(review_id) DO UPDATE SET
                    record_json = excluded.record_json,
                    resolution = excluded.resolution,
                    updated_at = excluded.updated_at
                """,
                (
                    review.review_id,
                    session_id,
                    review.attempt.attempt_id,
                    review.model_dump_json(),
                    review.resolution.value,
                    now.isoformat(),
                ),
            )

    def _accept_review_record(
        self,
        connection: sqlite3.Connection,
        session_id: str,
        record: StoredOperationAttempt,
        now: datetime,
    ) -> None:
        review = record.review
        if review is None or review.resolution.value != "accepted":
            raise SessionStoreError(SessionStoreErrorCode.REVIEW_ALREADY_RESOLVED)
        row = connection.execute(
            "SELECT record_json FROM reviews WHERE session_id = ? AND review_id = ?",
            (session_id, review.review_id),
        ).fetchone()
        if row is None:
            raise SessionStoreError(SessionStoreErrorCode.REVIEW_ALREADY_RESOLVED)
        current = PendingReview.model_validate_json(str(row["record_json"]))
        if current.resolution.value != "pending":
            raise SessionStoreError(SessionStoreErrorCode.REVIEW_ALREADY_RESOLVED)
        proposal_row = connection.execute(
            "SELECT record_json FROM operation_attempts "
            "WHERE session_id = ? AND request_id = ?",
            (session_id, current.attempt.request_id),
        ).fetchone()
        if proposal_row is None:
            raise SessionStoreError(SessionStoreErrorCode.PERSISTENCE_FAILURE)
        proposal = StoredOperationAttempt.model_validate_json(
            str(proposal_row["record_json"])
        ).model_copy(update={"review": review})
        self._upsert_attempt(
            connection,
            session_id,
            proposal,
            now,
            phase="review_resolved",
        )

    def _require_turn_lease(
        self,
        connection: sqlite3.Connection,
        lease: TurnLease,
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM turn_leases WHERE session_id = ?",
            (lease.session_id,),
        ).fetchone()
        if (
            row is None
            or str(row["request_id"]) != lease.request_id
            or str(row["capability_hash"])
            != _capability_hash(lease.capability.get_secret_value())
            or int(row["fencing_token"]) != lease.fencing_token
            or lease.fencing_token != self._instance_lease.fencing_token
        ):
            raise SessionStoreError(SessionStoreErrorCode.LEASE_MISMATCH)
        return row

    def _require_execution_claim(
        self,
        connection: sqlite3.Connection,
        claim: ExecutionClaim,
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM execution_claims WHERE attempt_id = ?",
            (claim.attempt_id,),
        ).fetchone()
        if (
            row is None
            or str(row["session_id"]) != claim.session_id
            or str(row["request_id"]) != claim.request_id
            or str(row["capability_hash"])
            != _capability_hash(claim.capability.get_secret_value())
            or int(row["fencing_token"]) != claim.fencing_token
            or claim.fencing_token != self._instance_lease.fencing_token
        ):
            raise SessionStoreError(SessionStoreErrorCode.LEASE_MISMATCH)
        return row

    def _require_no_active_child(
        self, connection: sqlite3.Connection, session_id: str
    ) -> None:
        if (
            connection.execute(
                "SELECT 1 FROM active_child_attempts WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            is not None
        ):
            raise SessionStoreError(SessionStoreErrorCode.OPERATION_IN_PROGRESS)

    def _delete_turn_lease(
        self, connection: sqlite3.Connection, lease: TurnLease
    ) -> None:
        changed = connection.execute(
            "DELETE FROM turn_leases WHERE session_id = ? AND request_id = ? "
            "AND capability_hash = ? AND fencing_token = ?",
            (
                lease.session_id,
                lease.request_id,
                _capability_hash(lease.capability.get_secret_value()),
                lease.fencing_token,
            ),
        ).rowcount
        if changed != 1:
            raise SessionStoreError(SessionStoreErrorCode.LEASE_MISMATCH)

    def _require_session_version(
        self,
        connection: sqlite3.Connection,
        session_id: str,
        expected_session_version: int,
        now: datetime,
    ) -> sqlite3.Row:
        row = self._load_session_row(connection, session_id, now)
        if int(row["session_version"]) != expected_session_version:
            raise SessionStoreError(SessionStoreErrorCode.VERSION_CONFLICT)
        return row

    def _load_session_row(
        self,
        connection: sqlite3.Connection,
        session_id: str,
        now: datetime,
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if row is None:
            if (
                connection.execute(
                    "SELECT 1 FROM session_tombstones WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
                is not None
            ):
                raise SessionStoreError(SessionStoreErrorCode.SESSION_EXPIRED)
            raise SessionStoreError(SessionStoreErrorCode.SESSION_NOT_FOUND)
        if datetime.fromisoformat(str(row["expires_at"])) <= now:
            raise SessionStoreError(SessionStoreErrorCode.SESSION_EXPIRED)
        return row

    def _insert_session(
        self,
        connection: sqlite3.Connection,
        initial: RouteDeckSession,
        now: datetime,
    ) -> SessionSnapshot:
        if (
            connection.execute(
                "SELECT 1 FROM session_tombstones WHERE session_id = ?",
                (initial.session_id,),
            ).fetchone()
            is not None
        ):
            raise SessionStoreError(SessionStoreErrorCode.SESSION_EXPIRED)
        state_json, conversation = self._serialize_state(initial)
        created = now.isoformat()
        idle_expires = now + self.retention_policy.unfinished_idle_ttl
        absolute_expires = now + self.retention_policy.unfinished_absolute_ttl
        expires = min(idle_expires, absolute_expires)
        try:
            connection.execute(
                """
                INSERT INTO sessions(
                    session_id, schema_version, navgraph_version,
                    session_version, projection_version, event_cursor,
                    state_json, created_at, updated_at, last_accessed_at,
                    idle_expires_at, absolute_expires_at, completed_at,
                    expires_at, owner_fencing_token
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
                """,
                (
                    initial.session_id,
                    initial.schema_version,
                    initial.navgraph_version,
                    initial.session_version,
                    initial.projection_version,
                    initial.event_cursor,
                    state_json,
                    created,
                    created,
                    created,
                    idle_expires.isoformat(),
                    absolute_expires.isoformat(),
                    expires.isoformat(),
                    self._instance_lease.fencing_token,
                ),
            )
        except sqlite3.IntegrityError as error:
            raise SessionStoreError(
                SessionStoreErrorCode.SESSION_ALREADY_EXISTS
            ) from error
        self._sync_conversation_blobs(
            connection,
            initial.session_id,
            conversation,
            now,
        )
        return SessionSnapshot(state=initial)

    def _serialize_state(self, state: RouteDeckSession) -> tuple[str, dict[str, bytes]]:
        payload = state.model_dump(mode="json")
        conversation_payload = payload.get("conversation")
        if not isinstance(conversation_payload, list):
            raise SessionStoreError(SessionStoreErrorCode.PERSISTENCE_FAILURE)
        encrypted: dict[str, bytes] = {}
        references: list[str] = []
        for index, turn in enumerate(state.conversation):
            item = conversation_payload[index]
            if not isinstance(item, dict) or item.get("turn_id") != turn.turn_id:
                raise SessionStoreError(SessionStoreErrorCode.PERSISTENCE_FAILURE)
            sensitive_turn = json.dumps(
                {
                    "format": "routedeck-conversation-turn-v2",
                    "content": turn.content,
                    "tool_call": (
                        turn.tool_call.model_dump(mode="json")
                        if turn.tool_call is not None
                        else None
                    ),
                    "tool_status": turn.tool_status,
                },
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            encrypted[turn.turn_id] = self.codec.encrypt(sensitive_turn)
            item["content"] = ""
            item["tool_call"] = None
            item["tool_status"] = None
            references.append(turn.turn_id)
        envelope = {
            "format": "routedeck-session-v1",
            "session": payload,
            "conversation_blob_refs": references,
        }
        return (
            json.dumps(
                envelope, ensure_ascii=False, separators=(",", ":"), sort_keys=True
            ),
            encrypted,
        )

    def _deserialize_state(
        self, connection: sqlite3.Connection, row: sqlite3.Row
    ) -> RouteDeckSession:
        try:
            stored_schema_version = int(row["schema_version"])
        except (IndexError, KeyError, TypeError, ValueError) as error:
            raise SessionStoreError(
                SessionStoreErrorCode.PERSISTENCE_FAILURE
            ) from error
        if stored_schema_version != SESSION_SCHEMA_VERSION:
            raise SessionStoreError(SessionStoreErrorCode.SESSION_UPGRADE_REQUIRED)
        try:
            envelope = json.loads(str(row["state_json"]))
        except (TypeError, json.JSONDecodeError) as error:
            raise SessionStoreError(
                SessionStoreErrorCode.PERSISTENCE_FAILURE
            ) from error
        if (
            not isinstance(envelope, dict)
            or envelope.get("format") != "routedeck-session-v1"
            or not isinstance(envelope.get("session"), dict)
            or not isinstance(envelope.get("conversation_blob_refs"), list)
        ):
            raise SessionStoreError(SessionStoreErrorCode.SESSION_UPGRADE_REQUIRED)
        payload = envelope["session"]
        conversation = payload.get("conversation")
        references = envelope["conversation_blob_refs"]
        if not isinstance(conversation, list) or len(conversation) != len(references):
            raise SessionStoreError(SessionStoreErrorCode.PERSISTENCE_FAILURE)
        blobs = {
            str(blob["turn_id"]): bytes(blob["ciphertext"])
            for blob in connection.execute(
                "SELECT turn_id, ciphertext FROM conversation_blobs WHERE session_id = ?",
                (str(row["session_id"]),),
            ).fetchall()
        }
        for index, turn_id in enumerate(references):
            if not isinstance(turn_id, str) or turn_id not in blobs:
                raise SessionStoreError(SessionStoreErrorCode.PERSISTENCE_FAILURE)
            item = conversation[index]
            if not isinstance(item, dict) or item.get("turn_id") != turn_id:
                raise SessionStoreError(SessionStoreErrorCode.PERSISTENCE_FAILURE)
            try:
                sensitive_turn = json.loads(
                    self.codec.decrypt(blobs[turn_id]).decode("utf-8")
                )
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise SessionStoreError(
                    SessionStoreErrorCode.PERSISTENCE_FAILURE
                ) from error
            if (
                not isinstance(sensitive_turn, dict)
                or sensitive_turn.get("format") != "routedeck-conversation-turn-v2"
                or not isinstance(sensitive_turn.get("content"), str)
                or not (
                    sensitive_turn.get("tool_call") is None
                    or isinstance(sensitive_turn.get("tool_call"), dict)
                )
                or not (
                    sensitive_turn.get("tool_status") is None
                    or sensitive_turn.get("tool_status") in ("success", "error")
                )
            ):
                raise SessionStoreError(SessionStoreErrorCode.PERSISTENCE_FAILURE)
            item["content"] = sensitive_turn["content"]
            item["tool_call"] = sensitive_turn["tool_call"]
            item["tool_status"] = sensitive_turn["tool_status"]
        state = RouteDeckSession.model_validate(payload)
        metadata = (
            state.schema_version,
            state.navgraph_version,
            state.session_version,
            state.projection_version,
            state.event_cursor,
        )
        stored_metadata = (
            int(row["schema_version"]),
            str(row["navgraph_version"]),
            int(row["session_version"]),
            int(row["projection_version"]),
            int(row["event_cursor"]),
        )
        if metadata != stored_metadata:
            raise SessionStoreError(SessionStoreErrorCode.PERSISTENCE_FAILURE)
        return state

    def _sync_conversation_blobs(
        self,
        connection: sqlite3.Connection,
        session_id: str,
        conversation: dict[str, bytes],
        now: datetime,
    ) -> None:
        for turn_id, ciphertext in conversation.items():
            connection.execute(
                """
                INSERT INTO conversation_blobs(session_id, turn_id, ciphertext, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id, turn_id) DO UPDATE SET
                    ciphertext = excluded.ciphertext,
                    updated_at = excluded.updated_at
                """,
                (session_id, turn_id, ciphertext, now.isoformat()),
            )
        if conversation:
            placeholders = ",".join("?" for _ in conversation)
            connection.execute(
                f"DELETE FROM conversation_blobs WHERE session_id = ? "
                f"AND turn_id NOT IN ({placeholders})",
                (session_id, *conversation),
            )
        else:
            connection.execute(
                "DELETE FROM conversation_blobs WHERE session_id = ?", (session_id,)
            )

    @staticmethod
    def _sync_private_blobs(
        connection: sqlite3.Connection,
        session_id: str,
        form_ids: tuple[str, ...],
    ) -> None:
        if form_ids:
            placeholders = ",".join("?" for _ in form_ids)
            connection.execute(
                f"DELETE FROM private_blobs WHERE session_id = ? "
                f"AND form_id NOT IN ({placeholders})",
                (session_id, *form_ids),
            )
            return
        connection.execute(
            "DELETE FROM private_blobs WHERE session_id = ?", (session_id,)
        )

    def _record_mutation(
        self,
        connection: sqlite3.Connection,
        lease: TurnLease,
        mutation: MutationCommit,
        snapshot: SessionSnapshot,
        now: datetime,
    ) -> None:
        lease_row = self._require_turn_lease(connection, lease)
        self._record_mutation_from_lease_row(
            connection,
            lease_row,
            mutation,
            snapshot,
            now,
        )

    def _record_mutation_from_lease_row(
        self,
        connection: sqlite3.Connection,
        lease_row: sqlite3.Row,
        mutation: MutationCommit,
        snapshot: SessionSnapshot,
        now: datetime,
    ) -> None:
        expected_owner = {
            MutationKind.NAVIGATION: TurnOwnerKind.NAVIGATION,
            MutationKind.PRIVATE_FORM: TurnOwnerKind.SURFACE,
            MutationKind.CHAT: TurnOwnerKind.CHAT,
        }[mutation.kind]
        if str(lease_row["owner_kind"]) != expected_owner.value:
            raise SessionStoreError(SessionStoreErrorCode.LEASE_MISMATCH)
        session_id = str(lease_row["session_id"])
        request_id = str(lease_row["request_id"])
        if (
            connection.execute(
                "SELECT 1 FROM operation_attempts "
                "WHERE session_id = ? AND request_id = ?",
                (session_id, request_id),
            ).fetchone()
            is not None
        ):
            raise SessionStoreError(SessionStoreErrorCode.REQUEST_ID_REUSED)
        try:
            connection.execute(
                """
                INSERT INTO mutation_journal(
                    session_id, request_id, request_fingerprint,
                    mutation_kind, status, result_json,
                    committed_session_version, committed_projection_version,
                    committed_event_cursor, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    request_id,
                    str(lease_row["request_fingerprint"]),
                    mutation.kind.value,
                    mutation.status.value,
                    json.dumps(
                        mutation.result.to_python(),
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                    snapshot.session_version,
                    snapshot.projection_version,
                    snapshot.event_cursor,
                    now.isoformat(),
                ),
            )
        except sqlite3.IntegrityError as error:
            raise SessionStoreError(SessionStoreErrorCode.REQUEST_ID_REUSED) from error

    def _validate_session_compatibility(self, state: RouteDeckSession) -> None:
        if state.schema_version != SESSION_SCHEMA_VERSION:
            raise SessionStoreError(SessionStoreErrorCode.SESSION_UPGRADE_REQUIRED)
        if (
            self.expected_navgraph_version is not None
            and state.navgraph_version != self.expected_navgraph_version
        ):
            raise SessionStoreError(SessionStoreErrorCode.SESSION_UPGRADE_REQUIRED)

    async def _recover_abandoned_turns(self) -> None:
        while True:
            recovered = await self._write(self._recover_abandoned_turn_batch)
            if recovered < self.retention_policy.cleanup_batch_size:
                return

    def _recover_abandoned_turn_batch(
        self, connection: sqlite3.Connection, now: datetime
    ) -> int:
        rows = connection.execute(
            "SELECT * FROM turn_leases ORDER BY acquired_at LIMIT ?",
            (self.retention_policy.cleanup_batch_size,),
        ).fetchall()
        for lease_row in rows:
            session_id = str(lease_row["session_id"])
            if str(lease_row["owner_kind"]) == "chat":
                session_row = self._load_session_row(connection, session_id, now)
                session = self._deserialize_state(connection, session_row)
                request_id = str(lease_row["request_id"])
                failure = RouteDeckFailure(
                    kind=FailureKind.INTERNAL,
                    code="turn_interrupted",
                    phase="restart_recovery",
                    correlation_id=f"restart-{uuid.uuid4().hex}",
                    request_id=request_id,
                    public_message="The previous assistant turn was interrupted.",
                )
                interrupted = ConversationTurn(
                    turn_id=f"restart-turn-{uuid.uuid4().hex}",
                    role=ConversationRole.ASSISTANT,
                    content="",
                    request_id=request_id,
                    status=ConversationTurnStatus.INTERRUPTED,
                )
                public_state = session.public_state.model_copy(
                    update={
                        "status_code": "turn_interrupted",
                        "status_message": failure.public_message,
                        "failure": failure,
                    }
                )
                next_state = reduce_session_batch(
                    session,
                    (
                        ConversationTurnsStored(turns=(interrupted,)),
                        PublicSessionStateStored(state=public_state),
                        PublicEventsRecorded(count=1),
                    ),
                )
                event = CanonicalRouteDeckEvent(
                    event_id=f"restart-event-{uuid.uuid4().hex}",
                    cursor=next_state.event_cursor,
                    event_type=RouteDeckEventKind.TURN_INTERRUPTED,
                    session_id=session_id,
                    session_version=next_state.session_version,
                    projection_version=next_state.projection_version,
                    created_at=now,
                    payload=PublicEventPayload(
                        node_id=next_state.current.node_id,
                        request_id=request_id,
                        status_code="turn_interrupted",
                        failure=failure,
                    ),
                )
                snapshot = self._commit_session(
                    connection,
                    session_id,
                    session.session_version,
                    next_state,
                    (event,),
                    now,
                )
                self._record_mutation_from_lease_row(
                    connection,
                    lease_row,
                    MutationCommit(
                        kind=MutationKind.CHAT,
                        status=MutationStatus.TURN_INTERRUPTED,
                        result=FrozenJsonObject(
                            {
                                "code": failure.code,
                                "message": failure.public_message,
                            }
                        ),
                    ),
                    snapshot,
                    now,
                )
            connection.execute(
                "DELETE FROM active_child_attempts WHERE session_id = ?", (session_id,)
            )
            connection.execute(
                "DELETE FROM turn_leases WHERE session_id = ?", (session_id,)
            )
        return len(rows)

    async def _heartbeat_loop(self) -> None:
        interval = self._instance_lease_ttl.total_seconds() / 3
        try:
            while True:
                await asyncio.sleep(interval)
                now = _aware_utc(self.clock.now())

                def heartbeat() -> None:
                    self._instance_lease = heartbeat_application_lease(
                        self._connection,
                        self._instance_lease,
                        now=now,
                        ttl=self._instance_lease_ttl,
                    )

                async with self._connection_lock:
                    await asyncio.to_thread(heartbeat)
        except asyncio.CancelledError:
            raise
        except BaseException as error:
            self._background_failure = error

    async def _cleanup_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(
                    self.retention_policy.cleanup_interval.total_seconds()
                )
                await self.cleanup_expired()
        except asyncio.CancelledError:
            raise
        except BaseException as error:
            self._background_failure = error

    async def _write(self, operation: Callable[[sqlite3.Connection, datetime], T]) -> T:
        self._ensure_open()
        now = _aware_utc(self.clock.now())

        def run() -> T:
            with immediate_transaction(self._connection):
                assert_application_lease(
                    self._connection, self._instance_lease, now=now
                )
                return operation(self._connection, now)

        try:
            async with self._connection_lock:
                return await asyncio.to_thread(run)
        except (SessionStoreError, RouteDeckInstanceLeaseLost):
            raise
        except sqlite3.Error as error:
            raise SessionStoreError(
                SessionStoreErrorCode.PERSISTENCE_FAILURE
            ) from error

    async def _read(self, operation: Callable[[sqlite3.Connection, datetime], T]) -> T:
        self._ensure_open()
        now = _aware_utc(self.clock.now())

        def run() -> T:
            assert_application_lease(self._connection, self._instance_lease, now=now)
            return operation(self._connection, now)

        try:
            async with self._connection_lock:
                return await asyncio.to_thread(run)
        except (SessionStoreError, RouteDeckInstanceLeaseLost):
            raise
        except sqlite3.Error as error:
            raise SessionStoreError(
                SessionStoreErrorCode.PERSISTENCE_FAILURE
            ) from error

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("SqliteSessionStore is closed")
        if self._background_failure is not None:
            raise RouteDeckInstanceLeaseLost(
                "RouteDeck SQLite background maintenance failed"
            ) from self._background_failure

    async def _close_connection(self, *, release: bool) -> None:
        if self._closed:
            return
        failure: BaseException | None = None
        now = _aware_utc(self.clock.now())
        async with self._connection_lock:
            if release:
                try:
                    await asyncio.to_thread(
                        release_application_lease,
                        self._connection,
                        self._instance_lease,
                        now=now,
                    )
                except RouteDeckInstanceLeaseLost as error:
                    failure = error
            await asyncio.to_thread(self._connection.close)
            self._closed = True
        if failure is not None:
            raise failure


def _capability_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("RouteDeck clocks must return timezone-aware timestamps")
    return value.astimezone(timezone.utc)


__all__ = ["SqliteSessionStore", "UtcClock"]
