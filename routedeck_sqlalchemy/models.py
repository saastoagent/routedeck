from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import DateTime, TypeDecorator


class Base(DeclarativeBase):
    pass


class UtcDateTime(TypeDecorator[datetime]):
    """Persist UTC timestamps consistently across SQLite and PostgreSQL."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, _dialect: object):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("RouteDeck timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    def process_result_value(self, value: datetime | None, _dialect: object):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class SchemaMigrationRow(Base):
    __tablename__ = "schema_migrations"

    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    applied_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)


class ApplicationLeaseRow(Base):
    __tablename__ = "application_lease"

    slot: Mapped[int] = mapped_column(Integer, primary_key=True)
    instance_id: Mapped[str] = mapped_column(String(255), nullable=False)
    fencing_token: Mapped[int] = mapped_column(Integer, nullable=False)
    heartbeat_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(UtcDateTime())


class SessionRow(Base):
    __tablename__ = "sessions"
    __table_args__ = (Index("sessions_expiry", "expires_at", "session_id"),)

    session_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    navgraph_version: Mapped[str] = mapped_column(String(255), nullable=False)
    session_version: Mapped[int] = mapped_column(Integer, nullable=False)
    projection_version: Mapped[int] = mapped_column(Integer, nullable=False)
    event_cursor: Mapped[int] = mapped_column(Integer, nullable=False)
    state_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    last_accessed_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    idle_expires_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    absolute_expires_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    owner_fencing_token: Mapped[int] = mapped_column(Integer, nullable=False)


class SessionTombstoneRow(Base):
    __tablename__ = "session_tombstones"

    session_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    expired_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)


class TurnLeaseRow(Base):
    __tablename__ = "turn_leases"

    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.session_id", ondelete="CASCADE"), primary_key=True
    )
    request_id: Mapped[str] = mapped_column(String(255), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_turn_id: Mapped[str | None] = mapped_column(String(255))
    capability_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    fencing_token: Mapped[int] = mapped_column(Integer, nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)


class ActiveChildAttemptRow(Base):
    __tablename__ = "active_child_attempts"
    __table_args__ = (UniqueConstraint("session_id", "request_id"),)

    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.session_id", ondelete="CASCADE"), primary_key=True
    )
    parent_request_id: Mapped[str] = mapped_column(String(255), nullable=False)
    request_id: Mapped[str] = mapped_column(String(255), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(255), nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)


class OperationAttemptRow(Base):
    __tablename__ = "operation_attempts"
    __table_args__ = (
        UniqueConstraint("session_id", "request_id"),
        Index("operation_attempts_review", "session_id", "review_id"),
    )

    attempt_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False
    )
    request_id: Mapped[str] = mapped_column(String(255), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(255), nullable=False)
    record_json: Mapped[str] = mapped_column(Text, nullable=False)
    review_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    fencing_token: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)


class OperationJournalRow(Base):
    __tablename__ = "operation_journal"
    __table_args__ = (Index("operation_journal_attempt", "attempt_id", "journal_id"),)

    journal_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False
    )
    attempt_id: Mapped[str] = mapped_column(
        ForeignKey("operation_attempts.attempt_id", ondelete="CASCADE"), nullable=False
    )
    phase: Mapped[str] = mapped_column(String(64), nullable=False)
    record_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    fencing_token: Mapped[int] = mapped_column(Integer, nullable=False)


class ReviewRow(Base):
    __tablename__ = "reviews"
    __table_args__ = (Index("reviews_session", "session_id", "review_id"),)

    review_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False
    )
    attempt_id: Mapped[str] = mapped_column(
        ForeignKey("operation_attempts.attempt_id", ondelete="CASCADE"), nullable=False
    )
    record_json: Mapped[str] = mapped_column(Text, nullable=False)
    resolution: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)


class ExecutionClaimRow(Base):
    __tablename__ = "execution_claims"

    attempt_id: Mapped[str] = mapped_column(
        ForeignKey("operation_attempts.attempt_id", ondelete="CASCADE"),
        primary_key=True,
    )
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False
    )
    request_id: Mapped[str] = mapped_column(String(255), nullable=False)
    capability_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    fencing_token: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    claimed_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)


class ExecutionResultRow(Base):
    __tablename__ = "execution_results"

    result_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    attempt_id: Mapped[str] = mapped_column(
        ForeignKey("operation_attempts.attempt_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False
    )
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
    record_json: Mapped[str] = mapped_column(Text, nullable=False)
    result_fingerprint: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)


class EventRow(Base):
    __tablename__ = "events"
    __table_args__ = (Index("events_retention", "session_id", "created_at", "cursor"),)

    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.session_id", ondelete="CASCADE"), primary_key=True
    )
    cursor: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    session_version: Mapped[int] = mapped_column(Integer, nullable=False)
    projection_version: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    event_json: Mapped[str] = mapped_column(Text, nullable=False)


class PrivateBlobRow(Base):
    __tablename__ = "private_blobs"

    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.session_id", ondelete="CASCADE"), primary_key=True
    )
    form_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)


class ConversationBlobRow(Base):
    __tablename__ = "conversation_blobs"

    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.session_id", ondelete="CASCADE"), primary_key=True
    )
    turn_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)


class SessionCreationRequestRow(Base):
    __tablename__ = "session_creation_requests"

    request_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    request_fingerprint: Mapped[str] = mapped_column(String(255), nullable=False)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.session_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)


class MutationJournalRow(Base):
    __tablename__ = "mutation_journal"

    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.session_id", ondelete="CASCADE"), primary_key=True
    )
    request_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    request_fingerprint: Mapped[str] = mapped_column(String(255), nullable=False)
    mutation_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
    committed_session_version: Mapped[int] = mapped_column(Integer, nullable=False)
    committed_projection_version: Mapped[int] = mapped_column(Integer, nullable=False)
    committed_event_cursor: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)


__all__ = [name for name in globals() if name.endswith("Row") or name == "Base"]
