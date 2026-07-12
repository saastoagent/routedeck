from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from routedeck_core.contracts.conversation import (
    ConversationRole,
    FinalizedConversationTurn,
)
from routedeck_core.contracts.effects import SessionEffects
from routedeck_core.contracts.events import (
    CanonicalRouteDeckEvent,
    PublicEventPayload,
    RouteDeckEventKind,
)
from routedeck_core.contracts.failures import FailureKind, RouteDeckFailure
from routedeck_core.contracts.mutations import (
    MutationCommit,
    MutationKind,
    MutationStatus,
)
from routedeck_core.contracts.operations import (
    DeliveryPhase,
    OperationDisposition,
    OperationSource,
)
from routedeck_core.contracts.retention import RouteDeckRetentionPolicy
from routedeck_core.contracts.session import (
    AttemptTerminalState,
    Location,
    JournaledExecutionResult,
    OperationAttempt,
    OperationAttemptStatus,
    PrivateSessionState,
    PublicSessionState,
    RouteDeckSession,
    StoredOperationAttempt,
)
from routedeck_core.ports import SessionStoreError, SessionStoreErrorCode
from routedeck_core.state.leases import TurnClaim, TurnLease, TurnOwnerKind
from routedeck_core.state.reducer import (
    PublicEventsRecorded,
    PublicSessionStateStored,
    reduce_session_batch,
)
from routedeck_core.state.session import SESSION_SCHEMA_VERSION
from routedeck_sqlite import (
    FernetSensitiveCodec,
    RouteDeckInstanceLeaseLost,
    RouteDeckWorkerConfigurationError,
    SensitiveDataIntegrityError,
    SqliteSessionStore,
)


class MutableClock:
    def __init__(self) -> None:
        self.current = datetime(2026, 7, 12, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self.current

    def advance(self, delta: timedelta) -> None:
        self.current += delta


class NaiveClock:
    def now(self) -> datetime:
        return datetime(2026, 7, 12)


def _retention_policy(
    *,
    completed_ttl: timedelta = timedelta(seconds=5),
    event_retention_ttl: timedelta = timedelta(seconds=5),
    max_events_per_session: int = 20,
) -> RouteDeckRetentionPolicy:
    return RouteDeckRetentionPolicy(
        unfinished_idle_ttl=timedelta(minutes=1),
        unfinished_absolute_ttl=timedelta(minutes=5),
        completed_ttl=completed_ttl,
        event_retention_ttl=event_retention_ttl,
        max_events_per_session=max_events_per_session,
        retain_operation_journal_until_session_delete=True,
        cleanup_on_startup=False,
        cleanup_interval=timedelta(days=1),
        cleanup_batch_size=20,
    )


async def _open_store(
    tmp_path: Path,
    name: str,
    clock: MutableClock,
    *,
    retention_policy: RouteDeckRetentionPolicy | None = None,
    expected_navgraph_version: str | None = None,
) -> SqliteSessionStore:
    return await SqliteSessionStore.open(
        tmp_path / f"{name}.sqlite",
        instance_id=f"instance-{name}",
        codec=FernetSensitiveCodec(Fernet.generate_key()),
        clock=clock,
        retention_policy=retention_policy or _retention_policy(),
        lease_ttl=timedelta(seconds=30),
        expected_navgraph_version=expected_navgraph_version,
    )


def _session(
    session_id: str,
    *,
    navgraph_version: str = "nav-v1",
    schema_version: int = SESSION_SCHEMA_VERSION,
) -> RouteDeckSession:
    return RouteDeckSession(
        session_id=session_id,
        schema_version=schema_version,
        navgraph_version=navgraph_version,
        session_version=0,
        projection_version=0,
        event_cursor=0,
        next_history_entry_id=2,
        current=Location(node_id="entry", entry_id=1),
        private_state=PrivateSessionState(),
    )


async def _acquire(
    store: SqliteSessionStore,
    state: RouteDeckSession,
    request_id: str,
    *,
    owner_kind: TurnOwnerKind = TurnOwnerKind.NAVIGATION,
    fingerprint: str | None = None,
) -> TurnLease:
    return await store.acquire_turn(
        TurnClaim(
            session_id=state.session_id,
            expected_session_version=state.session_version,
            request_id=request_id,
            request_fingerprint=fingerprint or f"fingerprint-{request_id}",
            owner_kind=owner_kind,
        )
    )


def _public_transition(
    state: RouteDeckSession,
    *,
    status_code: str,
    event_count: int,
) -> RouteDeckSession:
    return reduce_session_batch(
        state,
        (
            PublicSessionStateStored(
                state=PublicSessionState(
                    status_code=status_code,
                    status_message=f"status {status_code}",
                )
            ),
            PublicEventsRecorded(count=event_count),
        ),
    )


def _event(
    state: RouteDeckSession,
    *,
    cursor: int,
    event_id: str,
    created_at: datetime,
    session_id: str | None = None,
    session_version: int | None = None,
) -> CanonicalRouteDeckEvent:
    return CanonicalRouteDeckEvent(
        event_id=event_id,
        cursor=cursor,
        event_type=RouteDeckEventKind.PROJECTION_CHANGED,
        session_id=session_id or state.session_id,
        session_version=(
            state.session_version if session_version is None else session_version
        ),
        projection_version=state.projection_version,
        created_at=created_at,
        payload=PublicEventPayload(
            node_id=state.current.node_id,
            status_code=state.public_state.status_code,
        ),
    )


def _attempt_record(
    request_id: str,
    *,
    attempt_id: str | None = None,
    fingerprint: str | None = None,
) -> StoredOperationAttempt:
    return StoredOperationAttempt(
        attempt=OperationAttempt(
            attempt_id=attempt_id or f"attempt-{request_id}",
            request_id=request_id,
            request_fingerprint=fingerprint or f"fingerprint-{request_id}",
            operation_id="catalog.refresh",
            source=OperationSource.SURFACE,
            expected_session_version=0,
            status=OperationAttemptStatus.RECEIVED,
        )
    )


def _set_owner_fence(database_path: Path, session_id: str, fencing_token: int) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE sessions SET owner_fencing_token = ? WHERE session_id = ?",
            (fencing_token, session_id),
        )


def _retention_row(
    database_path: Path,
    session_id: str,
) -> tuple[str | None, str, int]:
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT completed_at, expires_at, session_version "
            "FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    assert row is not None
    return (
        str(row[0]) if row[0] is not None else None,
        str(row[1]),
        int(row[2]),
    )


async def _commit_completed_operation(
    store: SqliteSessionStore,
    state: RouteDeckSession,
    clock: MutableClock,
    *,
    request_id: str,
) -> RouteDeckSession:
    lease = await _acquire(
        store,
        state,
        request_id,
        owner_kind=TurnOwnerKind.SURFACE,
    )
    claimed_record = _attempt_record(request_id)
    claim = await store.claim_execution(lease, claimed_record)
    result = JournaledExecutionResult(
        result_id=f"result-{request_id}",
        attempt_id=claimed_record.attempt.attempt_id,
        request_id=request_id,
        operation_id=claimed_record.attempt.operation_id,
        outcome="completed",
        delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
        result_fingerprint=f"result-fingerprint-{request_id}",
        effects=SessionEffects(complete_session=True),
    )
    recorded_attempt = claimed_record.attempt.model_copy(
        update={"status": OperationAttemptStatus.RESULT_RECORDED}
    )
    recorded_record = claimed_record.model_copy(
        update={
            "attempt": recorded_attempt,
            "journaled_result": result,
        }
    )
    await store.record_execution_result(claim, result, recorded_record)

    durable = await store.find_attempt(state.session_id, request_id)
    assert durable is not None
    assert durable.journaled_result is not None
    assert durable.journaled_result.effects.complete_session is True
    assert _retention_row(store.database_path, state.session_id)[0] is None

    next_state = _public_transition(
        state,
        status_code="completed",
        event_count=1,
    )
    event = _event(
        next_state,
        cursor=next_state.event_cursor,
        event_id=f"event-{request_id}",
        created_at=clock.now(),
    )
    completed_attempt = recorded_attempt.model_copy(
        update={
            "status": OperationAttemptStatus.COMPLETED,
            "terminal": AttemptTerminalState.COMPLETED,
        }
    )
    final_record = recorded_record.model_copy(
        update={
            "attempt": completed_attempt,
            "disposition": OperationDisposition.COMPLETED,
            "committed_session_version": next_state.session_version,
            "committed_projection_version": next_state.projection_version,
        }
    )
    committed = await store.commit_attempt(
        claim,
        state.session_version,
        next_state,
        (event,),
        final_record,
    )
    await store.release_turn(lease)
    return committed.state


@pytest.mark.asyncio
async def test_store_rejects_invalid_configuration_and_incompatible_sessions(
    tmp_path: Path,
) -> None:
    key = Fernet.generate_key()
    with pytest.raises(RouteDeckWorkerConfigurationError):
        await SqliteSessionStore.open(
            tmp_path / "workers.sqlite",
            instance_id="workers",
            codec=FernetSensitiveCodec(key),
            worker_count=2,
        )
    with pytest.raises(TypeError, match="SensitiveCodec"):
        await SqliteSessionStore.open(
            tmp_path / "codec.sqlite",
            instance_id="codec",
            codec=object(),  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="greater than three seconds"):
        await SqliteSessionStore.open(
            tmp_path / "lease-ttl.sqlite",
            instance_id="lease-ttl",
            codec=FernetSensitiveCodec(key),
            lease_ttl=timedelta(seconds=3),
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        await SqliteSessionStore.open(
            tmp_path / "naive-clock.sqlite",
            instance_id="naive-clock",
            codec=FernetSensitiveCodec(key),
            clock=NaiveClock(),
        )

    clock = MutableClock()
    store = await _open_store(
        tmp_path,
        "compatibility",
        clock,
        expected_navgraph_version="nav-v2",
    )
    try:
        with pytest.raises(SessionStoreError) as schema_error:
            await store.create(_session("old-schema", schema_version=1))
        assert schema_error.value.code is SessionStoreErrorCode.SESSION_UPGRADE_REQUIRED

        with pytest.raises(SessionStoreError) as navgraph_error:
            await store.create(_session("old-navgraph"))
        assert (
            navgraph_error.value.code is SessionStoreErrorCode.SESSION_UPGRADE_REQUIRED
        )

        created = await store.create(_session("compatible", navgraph_version="nav-v2"))
        assert created.session_id == "compatible"
        with pytest.raises(SessionStoreError) as duplicate:
            await store.create(_session("compatible", navgraph_version="nav-v2"))
        assert duplicate.value.code is SessionStoreErrorCode.SESSION_ALREADY_EXISTS

        with pytest.raises(ValueError, match="request identity"):
            await store.create_for_request(
                _session("missing-request", navgraph_version="nav-v2"),
                "",
                "fingerprint",
            )

        store._background_failure = RuntimeError("maintenance failed")
        with pytest.raises(RouteDeckInstanceLeaseLost, match="maintenance failed"):
            await store.load("compatible")
        store._background_failure = None
    finally:
        await store.close()

    await store.close()
    with pytest.raises(RuntimeError, match="closed"):
        await store.load("compatible")


@pytest.mark.asyncio
async def test_completed_expired_and_tombstoned_sessions_fail_closed(
    tmp_path: Path,
) -> None:
    clock = MutableClock()
    store = await _open_store(tmp_path, "expiry", clock)
    try:
        with pytest.raises(SessionStoreError) as missing:
            await store.load("does-not-exist")
        assert missing.value.code is SessionStoreErrorCode.SESSION_NOT_FOUND

        created = await store.create(_session("completed"))
        completed_at = clock.now()
        completed_state = await _commit_completed_operation(
            store,
            created.state,
            clock,
            request_id="complete-checkout",
        )
        stored_completed_at, fixed_expires_at, stored_version = _retention_row(
            store.database_path,
            created.session_id,
        )
        assert stored_completed_at == completed_at.isoformat()
        assert fixed_expires_at == (completed_at + timedelta(seconds=5)).isoformat()
        assert stored_version == completed_state.session_version

        clock.advance(timedelta(seconds=3))
        completed_lease = await _acquire(
            store,
            completed_state,
            "completed-access",
        )
        await store.release_turn(completed_lease)
        assert (
            _retention_row(store.database_path, created.session_id)[1]
            == fixed_expires_at
        )

        clock.advance(timedelta(seconds=3))
        with pytest.raises(SessionStoreError) as expired_row:
            await store.load(created.session_id)
        assert expired_row.value.code is SessionStoreErrorCode.SESSION_EXPIRED
        assert await store.cleanup_expired() == 1

        with pytest.raises(SessionStoreError) as tombstoned:
            await store.load(created.session_id)
        assert tombstoned.value.code is SessionStoreErrorCode.SESSION_EXPIRED
        with pytest.raises(SessionStoreError) as recreate:
            await store.create(_session(created.session_id))
        assert recreate.value.code is SessionStoreErrorCode.SESSION_EXPIRED

    finally:
        await store.close()


@pytest.mark.asyncio
async def test_turn_leases_request_identity_children_and_owner_fencing(
    tmp_path: Path,
) -> None:
    clock = MutableClock()
    store = await _open_store(tmp_path, "turn-leases", clock)
    try:
        created = await store.create(_session("turn-session"))
        lease = await _acquire(store, created.state, "nav-parent")

        with pytest.raises(SessionStoreError) as in_progress:
            await _acquire(store, created.state, "competitor")
        assert in_progress.value.code is SessionStoreErrorCode.OPERATION_IN_PROGRESS

        forged = lease.model_copy(update={"capability": SecretStr("forged")})
        with pytest.raises(SessionStoreError) as forged_error:
            await store.release_turn(forged)
        assert forged_error.value.code is SessionStoreErrorCode.LEASE_MISMATCH

        await store.claim_child_attempt(lease, "child", "fingerprint-child")
        with pytest.raises(SessionStoreError) as second_child:
            await store.claim_child_attempt(lease, "second-child", "fingerprint-second")
        assert second_child.value.code is SessionStoreErrorCode.OPERATION_IN_PROGRESS
        with pytest.raises(SessionStoreError) as wrong_child:
            await store.release_child_attempt(lease, "wrong-child")
        assert wrong_child.value.code is SessionStoreErrorCode.LEASE_MISMATCH
        await store.release_child_attempt(lease, "child")

        committed = await store.commit_state(
            lease,
            created.session_version,
            created.state,
            (),
            MutationCommit(
                kind=MutationKind.NAVIGATION,
                status=MutationStatus.COMPLETED,
            ),
        )
        mutation = await store.find_mutation(created.session_id, "nav-parent")
        assert mutation is not None
        assert mutation.committed_session_version == committed.session_version

        with pytest.raises(SessionStoreError) as child_reuse:
            await store.claim_child_attempt(
                lease,
                "nav-parent",
                "fingerprint-nav-parent",
            )
        assert child_reuse.value.code is SessionStoreErrorCode.REQUEST_ID_REUSED
        await store.release_turn(lease)

        with pytest.raises(SessionStoreError) as mutation_reuse:
            await _acquire(store, created.state, "nav-parent")
        assert mutation_reuse.value.code is SessionStoreErrorCode.REQUEST_ID_REUSED
        with pytest.raises(SessionStoreError) as version_conflict:
            await store.acquire_turn(
                TurnClaim(
                    session_id=created.session_id,
                    expected_session_version=99,
                    request_id="wrong-version",
                    request_fingerprint="fingerprint-wrong-version",
                    owner_kind=TurnOwnerKind.NAVIGATION,
                )
            )
        assert version_conflict.value.code is SessionStoreErrorCode.VERSION_CONFLICT

        operation_lease = await _acquire(
            store,
            created.state,
            "operation-parent",
            owner_kind=TurnOwnerKind.SURFACE,
        )
        record = _attempt_record("operation-request")
        await store.commit_supervision(
            operation_lease,
            created.session_version,
            created.state,
            (),
            record,
        )
        assert await store.find_attempt(created.session_id, "missing") is None
        assert (
            await store.find_attempt(created.session_id, "operation-request") == record
        )
        assert await store.find_review(created.session_id, "missing") is None
        with pytest.raises(SessionStoreError) as child_operation_reuse:
            await store.claim_child_attempt(
                operation_lease,
                "operation-request",
                "fingerprint-operation-request",
            )
        assert (
            child_operation_reuse.value.code is SessionStoreErrorCode.REQUEST_ID_REUSED
        )
        await store.release_turn(operation_lease)

        with pytest.raises(SessionStoreError) as operation_reuse:
            await _acquire(
                store,
                created.state,
                "operation-request",
                fingerprint="different-fingerprint",
            )
        assert operation_reuse.value.code is SessionStoreErrorCode.REQUEST_ID_REUSED

        fenced = await store.create(_session("owner-fenced"))
        _set_owner_fence(store.database_path, fenced.session_id, 999)
        with pytest.raises(SessionStoreError) as stale_owner:
            await _acquire(store, fenced.state, "stale-owner")
        assert stale_owner.value.code is SessionStoreErrorCode.VERSION_CONFLICT
        _set_owner_fence(
            store.database_path,
            fenced.session_id,
            store._instance_lease.fencing_token,
        )
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_event_retention_pagination_and_cleanup_signal_resync(
    tmp_path: Path,
) -> None:
    clock = MutableClock()
    policy = _retention_policy(max_events_per_session=2)
    store = await _open_store(
        tmp_path,
        "event-retention",
        clock,
        retention_policy=policy,
    )
    try:
        created = await store.create(_session("event-session"))
        lease = await _acquire(store, created.state, "event-commit")
        next_state = _public_transition(
            created.state,
            status_code="events-written",
            event_count=3,
        )
        events = tuple(
            _event(
                next_state,
                cursor=cursor,
                event_id=f"event-{cursor}",
                created_at=clock.now(),
            )
            for cursor in range(1, 4)
        )
        await store.commit_state(
            lease,
            created.session_version,
            next_state,
            events,
            MutationCommit(
                kind=MutationKind.NAVIGATION,
                status=MutationStatus.COMPLETED,
            ),
        )
        await store.release_turn(lease)

        with pytest.raises(ValueError, match="non-negative"):
            await store.events_after(created.session_id, -1, 1)
        with pytest.raises(ValueError, match="between 1 and 1000"):
            await store.events_after(created.session_id, 0, 0)
        with pytest.raises(ValueError, match="between 1 and 1000"):
            await store.events_after(created.session_id, 0, 1_001)
        with pytest.raises(SessionStoreError) as cursor_ahead:
            await store.events_after(created.session_id, 4, 1)
        assert cursor_ahead.value.code is SessionStoreErrorCode.VERSION_CONFLICT

        reset = await store.events_after(created.session_id, 0, 1)
        assert reset.reset_required is True
        assert reset.retained_from_cursor == 2
        first = await store.events_after(created.session_id, 1, 1)
        assert [event.cursor for event in first.events] == [2]
        assert first.has_more is True
        second = await store.events_after(created.session_id, 2, 1)
        assert [event.cursor for event in second.events] == [3]
        assert second.has_more is False

        clock.advance(timedelta(seconds=6))
        assert await store.cleanup_expired() == 2
        fully_pruned = await store.events_after(created.session_id, 0, 10)
        assert fully_pruned.reset_required is True
        assert fully_pruned.retained_from_cursor == 3
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_commit_validation_and_stale_owner_fencing_preserve_state(
    tmp_path: Path,
) -> None:
    clock = MutableClock()
    store = await _open_store(tmp_path, "commit-validation", clock)
    try:
        created = await store.create(_session("validated-session"))
        lease = await _acquire(store, created.state, "validated-commit")
        mutation = MutationCommit(
            kind=MutationKind.NAVIGATION,
            status=MutationStatus.COMPLETED,
        )

        invalid_cases: tuple[
            tuple[RouteDeckSession, tuple[CanonicalRouteDeckEvent, ...], object], ...
        ] = (
            (
                created.state.model_copy(update={"session_id": "another-session"}),
                (),
                ValueError,
            ),
            (
                created.state.model_copy(update={"schema_version": 1}),
                (),
                SessionStoreErrorCode.SESSION_UPGRADE_REQUIRED,
            ),
            (
                created.state.model_copy(update={"session_version": -1}),
                (),
                SessionStoreErrorCode.VERSION_CONFLICT,
            ),
            (
                created.state.model_copy(update={"projection_version": -1}),
                (),
                SessionStoreErrorCode.VERSION_CONFLICT,
            ),
        )
        for next_state, events, expected in invalid_cases:
            if expected is ValueError:
                with pytest.raises(ValueError):
                    await store.commit_state(
                        lease,
                        created.session_version,
                        next_state,
                        events,
                        mutation,
                    )
            else:
                with pytest.raises(SessionStoreError) as captured:
                    await store.commit_state(
                        lease,
                        created.session_version,
                        next_state,
                        events,
                        mutation,
                    )
                assert captured.value.code is expected

        event_state = created.state.model_copy(
            update={"session_version": 1, "projection_version": 1, "event_cursor": 1}
        )
        invalid_events = (
            (
                event_state,
                (
                    _event(
                        event_state,
                        cursor=2,
                        event_id="noncontiguous",
                        created_at=clock.now(),
                    ),
                ),
            ),
            (
                created.state,
                (
                    _event(
                        created.state,
                        cursor=1,
                        event_id="cursor-mismatch",
                        created_at=clock.now(),
                    ),
                ),
            ),
            (
                event_state,
                (
                    _event(
                        event_state,
                        cursor=1,
                        event_id="wrong-session",
                        created_at=clock.now(),
                        session_id="another-session",
                    ),
                ),
            ),
            (
                event_state,
                (
                    _event(
                        event_state,
                        cursor=1,
                        event_id="wrong-version",
                        created_at=clock.now(),
                        session_version=0,
                    ),
                ),
            ),
        )
        for next_state, events in invalid_events:
            with pytest.raises(ValueError):
                await store.commit_state(
                    lease,
                    created.session_version,
                    next_state,
                    events,
                    mutation,
                )

        _set_owner_fence(store.database_path, created.session_id, 999)
        with pytest.raises(SessionStoreError) as fenced_commit:
            await store.commit_state(
                lease,
                created.session_version,
                created.state,
                (),
                mutation,
            )
        assert fenced_commit.value.code is SessionStoreErrorCode.VERSION_CONFLICT
        _set_owner_fence(
            store.database_path,
            created.session_id,
            store._instance_lease.fencing_token,
        )
        await store.release_turn(lease)
        assert (await store.load(created.session_id)).state == created.state
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_sqlite_write_failure_rolls_back_state_event_and_mutation(
    tmp_path: Path,
) -> None:
    clock = MutableClock()
    store = await _open_store(tmp_path, "atomic-rollback", clock)
    try:
        created = await store.create(_session("rollback-session"))
        first_lease = await _acquire(store, created.state, "first-event")
        first_state = _public_transition(
            created.state,
            status_code="first",
            event_count=1,
        )
        first_event = _event(
            first_state,
            cursor=1,
            event_id="duplicate-event-id",
            created_at=clock.now(),
        )
        committed = await store.commit_state(
            first_lease,
            created.session_version,
            first_state,
            (first_event,),
            MutationCommit(
                kind=MutationKind.NAVIGATION,
                status=MutationStatus.COMPLETED,
            ),
        )
        await store.release_turn(first_lease)

        second_lease = await _acquire(store, committed.state, "second-event")
        second_state = _public_transition(
            committed.state,
            status_code="second",
            event_count=1,
        )
        duplicate = _event(
            second_state,
            cursor=2,
            event_id=first_event.event_id,
            created_at=clock.now(),
        )
        with pytest.raises(SessionStoreError) as persistence_failure:
            await store.commit_state(
                second_lease,
                committed.session_version,
                second_state,
                (duplicate,),
                MutationCommit(
                    kind=MutationKind.NAVIGATION,
                    status=MutationStatus.COMPLETED,
                ),
            )
        assert (
            persistence_failure.value.code is SessionStoreErrorCode.PERSISTENCE_FAILURE
        )

        reloaded = await store.load(created.session_id)
        assert reloaded.state == committed.state
        assert await store.find_mutation(created.session_id, "second-event") is None
        replay = await store.events_after(created.session_id, 0, 10)
        assert [event.event_id for event in replay.events] == [first_event.event_id]
        await store.release_turn(second_lease)
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_private_blob_and_read_failures_are_not_silently_recovered(
    tmp_path: Path,
) -> None:
    clock = MutableClock()
    store = await _open_store(tmp_path, "read-failure", clock)
    try:
        created = await store.create(_session("private-session"))
        lease = await _acquire(
            store,
            created.state,
            "private-write",
            owner_kind=TurnOwnerKind.SURFACE,
        )
        with pytest.raises(ValueError, match="form_id is required"):
            await store.save_private_blob(
                lease,
                created.session_version,
                "",
                store.codec.encrypt(b"private"),
                created.state,
                (),
                MutationCommit(
                    kind=MutationKind.PRIVATE_FORM,
                    status=MutationStatus.COMPLETED,
                ),
            )
        with pytest.raises(SensitiveDataIntegrityError):
            await store.save_private_blob(
                lease,
                created.session_version,
                "contact",
                b"not-authenticated-ciphertext",
                created.state,
                (),
                MutationCommit(
                    kind=MutationKind.PRIVATE_FORM,
                    status=MutationStatus.COMPLETED,
                ),
            )
        await store.release_turn(lease)

        with sqlite3.connect(store.database_path) as connection:
            connection.execute("DROP TABLE private_blobs")
        with pytest.raises(SessionStoreError) as read_failure:
            await store.load_private_blob(created.session_id, "contact")
        assert read_failure.value.code is SessionStoreErrorCode.PERSISTENCE_FAILURE
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_interrupt_turn_validates_failure_identity_and_commits_terminal_mutation(
    tmp_path: Path,
) -> None:
    clock = MutableClock()
    store = await _open_store(tmp_path, "interrupt", clock)
    try:
        created = await store.create(_session("interrupt-session"))
        lease = await _acquire(
            store,
            created.state,
            "chat-request",
            owner_kind=TurnOwnerKind.CHAT,
        )
        wrong_failure = RouteDeckFailure(
            kind=FailureKind.INTERNAL,
            code="interrupted",
            phase="chat",
            correlation_id="correlation-wrong",
            request_id="another-request",
            public_message="The turn was interrupted.",
        )
        with pytest.raises(ValueError, match="another request"):
            await store.interrupt_turn(
                lease,
                created.session_version,
                created.state,
                wrong_failure,
                (),
                MutationCommit(
                    kind=MutationKind.CHAT,
                    status=MutationStatus.TURN_INTERRUPTED,
                ),
            )

        generic_failure = wrong_failure.model_copy(update={"request_id": None})
        snapshot = await store.interrupt_turn(
            lease,
            created.session_version,
            created.state,
            generic_failure,
            (),
            MutationCommit(
                kind=MutationKind.CHAT,
                status=MutationStatus.TURN_INTERRUPTED,
            ),
        )
        assert snapshot.state == created.state
        recorded = await store.find_mutation(created.session_id, "chat-request")
        assert recorded is not None
        assert recorded.status is MutationStatus.TURN_INTERRUPTED
        with pytest.raises(SessionStoreError) as consumed_lease:
            await store.release_turn(lease)
        assert consumed_lease.value.code is SessionStoreErrorCode.LEASE_MISMATCH

        second = await store.create(_session("finalize-validation"))
        second_lease = await _acquire(
            store,
            second.state,
            "finalize-request",
            owner_kind=TurnOwnerKind.CHAT,
        )
        with pytest.raises(ValueError, match="finalized turns"):
            await store.finalize_turn(
                second_lease,
                second.session_version,
                second.state,
                (),
                (),
                MutationCommit(
                    kind=MutationKind.CHAT,
                    status=MutationStatus.COMPLETED,
                ),
            )
        wrong_turn = FinalizedConversationTurn(
            turn_id="wrong-turn",
            role=ConversationRole.USER,
            content="wrong request",
            request_id="another-request",
        )
        with pytest.raises(ValueError, match="finalized turns"):
            await store.finalize_turn(
                second_lease,
                second.session_version,
                second.state,
                (wrong_turn,),
                (),
                MutationCommit(
                    kind=MutationKind.CHAT,
                    status=MutationStatus.COMPLETED,
                ),
            )
        await store.release_turn(second_lease)
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_operation_journal_rejects_conflicting_claims_and_request_identities(
    tmp_path: Path,
) -> None:
    clock = MutableClock()
    store = await _open_store(tmp_path, "operation-invariants", clock)
    try:
        created = await store.create(_session("operation-session"))
        lease = await _acquire(
            store,
            created.state,
            "operation-request",
            owner_kind=TurnOwnerKind.SURFACE,
        )
        record = _attempt_record(lease.request_id)

        with pytest.raises(ValueError, match="requires a review record"):
            await store.stage_review(
                lease,
                created.session_version,
                record,
                created.state,
                (),
            )

        claim = await store.claim_execution(lease, record)
        with pytest.raises(SessionStoreError) as duplicate_claim:
            await store.claim_execution(lease, record)
        assert (
            duplicate_claim.value.code
            is SessionStoreErrorCode.EXECUTION_ALREADY_CLAIMED
        )

        with pytest.raises(SessionStoreError) as missing_recovery:
            await store.recover_execution_claim(lease, "missing-attempt")
        assert missing_recovery.value.code is SessionStoreErrorCode.LEASE_MISMATCH

        forged_claim = claim.model_copy(update={"capability": SecretStr("forged")})
        with pytest.raises(SessionStoreError) as forged_execution:
            await store.record_execution_started(forged_claim, record)
        assert forged_execution.value.code is SessionStoreErrorCode.LEASE_MISMATCH

        result = JournaledExecutionResult(
            result_id="result-operation-request",
            attempt_id=record.attempt.attempt_id,
            request_id=record.attempt.request_id,
            operation_id=record.attempt.operation_id,
            outcome="refreshed",
            delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
            result_fingerprint="result-fingerprint",
        )
        with pytest.raises(SessionStoreError) as missing_recorded_result:
            await store.record_execution_result(claim, result, record)
        assert (
            missing_recorded_result.value.code is SessionStoreErrorCode.RESULT_MISMATCH
        )

        wrong_result = result.model_copy(update={"request_id": "another-request"})
        wrong_result_record = record.model_copy(
            update={"journaled_result": wrong_result}
        )
        with pytest.raises(SessionStoreError) as wrong_result_identity:
            await store.record_execution_result(
                claim,
                wrong_result,
                wrong_result_record,
            )
        assert wrong_result_identity.value.code is SessionStoreErrorCode.RESULT_MISMATCH

        conflicting_record = _attempt_record(
            lease.request_id,
            attempt_id="conflicting-attempt",
            fingerprint="conflicting-fingerprint",
        )
        with pytest.raises(SessionStoreError) as request_reuse:
            await store.claim_execution(lease, conflicting_record)
        assert request_reuse.value.code is SessionStoreErrorCode.REQUEST_ID_REUSED

        with pytest.raises(SessionStoreError) as mismatched_commit:
            await store.commit_attempt(
                claim,
                created.session_version,
                created.state,
                (),
                conflicting_record,
            )
        assert mismatched_commit.value.code is SessionStoreErrorCode.RESULT_MISMATCH

        await store.claim_child_attempt(
            lease, "active-child", "active-child-fingerprint"
        )
        with pytest.raises(SessionStoreError) as active_child:
            await store.release_turn(lease)
        assert active_child.value.code is SessionStoreErrorCode.OPERATION_IN_PROGRESS
        await store.release_child_attempt(lease, "active-child")

        with pytest.raises(SessionStoreError) as wrong_mutation_owner:
            await store.commit_state(
                lease,
                created.session_version,
                created.state,
                (),
                MutationCommit(
                    kind=MutationKind.NAVIGATION,
                    status=MutationStatus.COMPLETED,
                ),
            )
        assert wrong_mutation_owner.value.code is SessionStoreErrorCode.LEASE_MISMATCH

        with pytest.raises(SessionStoreError) as operation_mutation_collision:
            await store.commit_state(
                lease,
                created.session_version,
                created.state,
                (),
                MutationCommit(
                    kind=MutationKind.PRIVATE_FORM,
                    status=MutationStatus.COMPLETED,
                ),
            )
        assert (
            operation_mutation_collision.value.code
            is SessionStoreErrorCode.REQUEST_ID_REUSED
        )
        await store.release_turn(lease)
    finally:
        await store.close()
