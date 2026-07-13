from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from routedeck_core.contracts.events import CanonicalRouteDeckEvent, EventPage
from routedeck_core.contracts.retention import RouteDeckRetentionPolicy
from routedeck_core.contracts.session import RouteDeckSession, SessionSnapshot
from routedeck_core.ports.session_store import SessionStoreError, SessionStoreErrorCode
from routedeck_core.state.session import SESSION_SCHEMA_VERSION

from .codec import SensitiveCodec
from .lease import ApplicationLease
from .models import (
    EventRow,
    PrivateBlobRow,
    SessionCreationRequestRow,
    SessionRow,
    SessionTombstoneRow,
)
from .serialization import (
    deserialize_session,
    serialize_session,
    sync_conversation_blobs,
    sync_private_blobs,
)


class SessionRepository:
    def __init__(
        self,
        *,
        codec: SensitiveCodec,
        retention_policy: RouteDeckRetentionPolicy,
        expected_navgraph_version: str | None,
    ) -> None:
        self.codec = codec
        self.retention_policy = retention_policy
        self.expected_navgraph_version = expected_navgraph_version

    def insert(
        self,
        database: Session,
        initial: RouteDeckSession,
        *,
        now: datetime,
        lease: ApplicationLease,
    ) -> SessionSnapshot:
        self.validate_compatibility(initial)
        if database.get(SessionTombstoneRow, initial.session_id) is not None:
            raise SessionStoreError(SessionStoreErrorCode.SESSION_EXPIRED)
        serialized = serialize_session(initial, self.codec)
        idle_expires = now + self.retention_policy.unfinished_idle_ttl
        absolute_expires = now + self.retention_policy.unfinished_absolute_ttl
        row = SessionRow(
            session_id=initial.session_id,
            schema_version=initial.schema_version,
            navgraph_version=initial.navgraph_version,
            session_version=initial.session_version,
            projection_version=initial.projection_version,
            event_cursor=initial.event_cursor,
            state_json=serialized.state_json,
            created_at=now,
            updated_at=now,
            last_accessed_at=now,
            idle_expires_at=idle_expires,
            absolute_expires_at=absolute_expires,
            completed_at=None,
            expires_at=min(idle_expires, absolute_expires),
            owner_fencing_token=lease.fencing_token,
        )
        database.add(row)
        try:
            database.flush()
        except IntegrityError as error:
            raise SessionStoreError(
                SessionStoreErrorCode.SESSION_ALREADY_EXISTS
            ) from error
        sync_conversation_blobs(
            database,
            session_id=initial.session_id,
            conversation=serialized.conversation_blobs,
            now=now,
        )
        return SessionSnapshot(state=initial)

    def load_row(
        self,
        database: Session,
        session_id: str,
        *,
        now: datetime,
    ) -> SessionRow:
        row = database.scalar(
            select(SessionRow).where(SessionRow.session_id == session_id)
        )
        if row is None:
            if database.get(SessionTombstoneRow, session_id) is not None:
                raise SessionStoreError(SessionStoreErrorCode.SESSION_EXPIRED)
            raise SessionStoreError(SessionStoreErrorCode.SESSION_NOT_FOUND)
        if row.expires_at <= now:
            raise SessionStoreError(SessionStoreErrorCode.SESSION_EXPIRED)
        return row

    def require_version(
        self,
        database: Session,
        session_id: str,
        expected_session_version: int,
        *,
        now: datetime,
    ) -> SessionRow:
        row = database.scalar(
            select(SessionRow)
            .where(SessionRow.session_id == session_id)
            .with_for_update()
        )
        if row is None:
            self.load_row(database, session_id, now=now)
            raise AssertionError("unreachable")
        if row.expires_at <= now:
            raise SessionStoreError(SessionStoreErrorCode.SESSION_EXPIRED)
        if row.session_version != expected_session_version:
            raise SessionStoreError(SessionStoreErrorCode.VERSION_CONFLICT)
        return row

    def load(
        self,
        database: Session,
        session_id: str,
        *,
        now: datetime,
    ) -> SessionSnapshot:
        row = self.load_row(database, session_id, now=now)
        state = deserialize_session(database, row, self.codec)
        self.validate_compatibility(state)
        return SessionSnapshot(state=state)

    def create_for_request(
        self,
        database: Session,
        initial: RouteDeckSession,
        *,
        request_id: str,
        request_fingerprint: str,
        now: datetime,
        lease: ApplicationLease,
    ) -> SessionSnapshot:
        if not request_id or not request_fingerprint:
            raise ValueError("session creation request identity is required")
        existing = database.get(SessionCreationRequestRow, request_id)
        if existing is not None:
            if existing.request_fingerprint != request_fingerprint:
                raise SessionStoreError(SessionStoreErrorCode.REQUEST_ID_REUSED)
            return self.load(database, existing.session_id, now=now)
        snapshot = self.insert(database, initial, now=now, lease=lease)
        database.add(
            SessionCreationRequestRow(
                request_id=request_id,
                request_fingerprint=request_fingerprint,
                session_id=initial.session_id,
                created_at=now,
            )
        )
        try:
            database.flush()
        except IntegrityError as error:
            raise SessionStoreError(SessionStoreErrorCode.REQUEST_ID_REUSED) from error
        return snapshot

    def commit(
        self,
        database: Session,
        *,
        session_id: str,
        expected_session_version: int,
        next_state: RouteDeckSession,
        events: Sequence[CanonicalRouteDeckEvent],
        now: datetime,
        lease: ApplicationLease,
        complete_session: bool = False,
    ) -> SessionSnapshot:
        current = self.require_version(
            database,
            session_id,
            expected_session_version,
            now=now,
        )
        self._validate_next_state(current, next_state, events)
        serialized = serialize_session(next_state, self.codec)
        if current.completed_at is None and complete_session:
            completed_at = now
            idle_expires = current.idle_expires_at
            expires = completed_at + self.retention_policy.completed_ttl
        elif current.completed_at is None:
            completed_at = None
            idle_expires = now + self.retention_policy.unfinished_idle_ttl
            expires = min(idle_expires, current.absolute_expires_at)
        else:
            completed_at = current.completed_at
            idle_expires = current.idle_expires_at
            expires = completed_at + self.retention_policy.completed_ttl
        current.schema_version = next_state.schema_version
        current.navgraph_version = next_state.navgraph_version
        current.session_version = next_state.session_version
        current.projection_version = next_state.projection_version
        current.event_cursor = next_state.event_cursor
        current.state_json = serialized.state_json
        current.updated_at = now
        current.last_accessed_at = now
        current.idle_expires_at = idle_expires
        current.completed_at = completed_at
        current.expires_at = expires
        current.owner_fencing_token = lease.fencing_token
        sync_conversation_blobs(
            database,
            session_id=session_id,
            conversation=serialized.conversation_blobs,
            now=now,
        )
        sync_private_blobs(
            database,
            session_id=session_id,
            form_ids=tuple(draft.form_id for draft in next_state.private_state.drafts),
        )
        self._append_events(database, session_id, events, now=now)
        database.flush()
        return SessionSnapshot(state=next_state)

    def events_after(
        self,
        database: Session,
        *,
        session_id: str,
        cursor: int,
        limit: int,
        now: datetime,
    ) -> EventPage:
        session = self.load_row(database, session_id, now=now)
        if cursor > session.event_cursor:
            raise SessionStoreError(SessionStoreErrorCode.VERSION_CONFLICT)
        retained = database.scalar(
            select(func.min(EventRow.cursor)).where(EventRow.session_id == session_id)
        )
        if session.event_cursor > cursor and (
            retained is None or cursor < retained - 1
        ):
            return EventPage(
                events=(),
                next_cursor=cursor,
                has_more=False,
                reset_required=True,
                retained_from_cursor=(retained or session.event_cursor),
            )
        rows = database.scalars(
            select(EventRow)
            .where(EventRow.session_id == session_id, EventRow.cursor > cursor)
            .order_by(EventRow.cursor)
            .limit(limit + 1)
        ).all()
        has_more = len(rows) > limit
        events = tuple(
            CanonicalRouteDeckEvent.model_validate_json(row.event_json)
            for row in rows[:limit]
        )
        return EventPage(
            events=events,
            next_cursor=events[-1].cursor if events else cursor,
            has_more=has_more,
        )

    def load_private_blob(
        self,
        database: Session,
        *,
        session_id: str,
        form_id: str,
        now: datetime,
    ) -> bytes | None:
        self.load_row(database, session_id, now=now)
        row = database.get(PrivateBlobRow, (session_id, form_id))
        if row is None:
            return None
        self.codec.decrypt(row.ciphertext)
        return row.ciphertext

    def put_private_blob(
        self,
        database: Session,
        *,
        session_id: str,
        form_id: str,
        encrypted_value: bytes,
        now: datetime,
    ) -> None:
        self.codec.decrypt(encrypted_value)
        row = database.get(PrivateBlobRow, (session_id, form_id))
        if row is None:
            database.add(
                PrivateBlobRow(
                    session_id=session_id,
                    form_id=form_id,
                    ciphertext=encrypted_value,
                    updated_at=now,
                )
            )
        else:
            row.ciphertext = encrypted_value
            row.updated_at = now

    def cleanup_expired(self, database: Session, *, now: datetime) -> int:
        rows = database.scalars(
            select(SessionRow)
            .where(SessionRow.expires_at <= now)
            .order_by(SessionRow.expires_at, SessionRow.session_id)
            .limit(self.retention_policy.cleanup_batch_size)
            .with_for_update()
        ).all()
        for row in rows:
            tombstone = database.get(SessionTombstoneRow, row.session_id)
            if tombstone is None:
                database.add(
                    SessionTombstoneRow(
                        session_id=row.session_id,
                        expired_at=now,
                    )
                )
            else:
                tombstone.expired_at = now
            database.delete(row)
        cutoff = now - self.retention_policy.event_retention_ttl
        expired_events = database.scalars(
            select(EventRow)
            .where(EventRow.created_at < cutoff)
            .order_by(EventRow.created_at)
            .limit(self.retention_policy.cleanup_batch_size)
        ).all()
        for event in expired_events:
            database.delete(event)
        return len(rows) + len(expired_events)

    def _validate_next_state(
        self,
        current: SessionRow,
        next_state: RouteDeckSession,
        events: Sequence[CanonicalRouteDeckEvent],
    ) -> None:
        if next_state.session_id != current.session_id:
            raise ValueError("next state belongs to another session")
        self.validate_compatibility(next_state)
        if next_state.session_version < current.session_version:
            raise SessionStoreError(SessionStoreErrorCode.VERSION_CONFLICT)
        if next_state.projection_version < current.projection_version:
            raise SessionStoreError(SessionStoreErrorCode.VERSION_CONFLICT)
        expected_cursors = tuple(
            range(current.event_cursor + 1, current.event_cursor + len(events) + 1)
        )
        if tuple(event.cursor for event in events) != expected_cursors:
            raise ValueError("durable event cursors must be contiguous")
        if next_state.event_cursor != current.event_cursor + len(events):
            raise ValueError("session event cursor must match appended events")
        for event in events:
            if event.session_id != next_state.session_id:
                raise ValueError("durable event belongs to another session")
            if event.session_version != next_state.session_version:
                raise ValueError("durable event session version mismatch")

    def _append_events(
        self,
        database: Session,
        session_id: str,
        events: Sequence[CanonicalRouteDeckEvent],
        *,
        now: datetime,
    ) -> None:
        for event in events:
            database.add(
                EventRow(
                    session_id=session_id,
                    cursor=event.cursor,
                    event_id=event.event_id,
                    event_type=event.event_type.value,
                    session_version=event.session_version,
                    projection_version=event.projection_version,
                    created_at=event.created_at,
                    event_json=event.model_dump_json(),
                )
            )
        cutoff = now - self.retention_policy.event_retention_ttl
        database.execute(
            delete(EventRow).where(
                EventRow.session_id == session_id,
                EventRow.created_at < cutoff,
            )
        )
        overflow = database.scalar(
            select(EventRow.cursor)
            .where(EventRow.session_id == session_id)
            .order_by(EventRow.cursor.desc())
            .offset(self.retention_policy.max_events_per_session)
            .limit(1)
        )
        if overflow is not None:
            database.execute(
                delete(EventRow).where(
                    EventRow.session_id == session_id,
                    EventRow.cursor <= overflow,
                )
            )

    def validate_compatibility(self, state: RouteDeckSession) -> None:
        if state.schema_version != SESSION_SCHEMA_VERSION:
            raise SessionStoreError(SessionStoreErrorCode.SESSION_UPGRADE_REQUIRED)
        if (
            self.expected_navgraph_version is not None
            and state.navgraph_version != self.expected_navgraph_version
        ):
            raise SessionStoreError(SessionStoreErrorCode.SESSION_UPGRADE_REQUIRED)


__all__ = ["SessionRepository"]
