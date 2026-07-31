from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from routedeck_core.contracts.conversation import (
    ConversationRole,
    ConversationTurn,
    ConversationTurnStatus,
)
from routedeck_core.contracts.events import (
    RouteDeckEvent,
    PublicEventPayload,
    RouteDeckEventType,
)
from routedeck_core.contracts.failures import FailureKind, RouteDeckFailure
from routedeck_core.contracts.interactions import (
    RouteDeckInteractionOwnerType,
    RouteDeckInteractionState,
)
from routedeck_core.contracts.mutations import (
    MutationCommit,
    MutationKind,
    MutationStatus,
)
from routedeck_core.contracts.projection import FrozenJsonObject
from routedeck_core.contracts.retention import RouteDeckRetentionPolicy
from routedeck_core.ports import SensitiveCodec
from routedeck_core.ports.session_store import (
    SessionStoreError,
    SessionStoreErrorCode,
)
from routedeck_core.state.aggregate import RouteDeckSessionAggregate

from .lease import ApplicationLease
from .models import ActiveChildAttemptRow, SessionRow, TurnLeaseRow
from .serialization import deserialize_session
from .sessions import SessionRepository
from .turns import TurnRepository


def recover_abandoned_turn_batch(
    database: Session,
    now: datetime,
    *,
    sessions: SessionRepository,
    turns: TurnRepository,
    codec: SensitiveCodec,
    retention_policy: RouteDeckRetentionPolicy,
    application_lease: ApplicationLease,
) -> int:
    batch_size = retention_policy.cleanup_batch_size
    rows = database.scalars(
        select(TurnLeaseRow)
        .order_by(TurnLeaseRow.acquired_at)
        .limit(batch_size)
        .with_for_update()
    ).all()
    for lease_row in rows:
        session_id = lease_row.session_id
        if lease_row.owner_kind == "chat":
            session_row = sessions.load_row(database, session_id, now=now)
            session = deserialize_session(database, session_row, codec)
            request_id = lease_row.request_id
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
            next_state = (
                RouteDeckSessionAggregate(session)
                .append_conversation_turns((interrupted,))
                .set_interaction(RouteDeckInteractionState())
                .set_public_state(public_state)
                .record_public_events(1)
                .commit()
            )
            event = RouteDeckEvent(
                event_id=f"restart-event-{uuid.uuid4().hex}",
                cursor=next_state.event_cursor,
                event_type=RouteDeckEventType.TURN_INTERRUPTED,
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
            snapshot = sessions.commit(
                database,
                session_id=session_id,
                expected_session_version=session.session_version,
                next_state=next_state,
                events=(event,),
                now=now,
                lease=application_lease,
            )
            turns.record_mutation_from_row(
                database,
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
                now=now,
            )
        child = database.get(ActiveChildAttemptRow, session_id)
        if child is not None:
            database.delete(child)
        database.delete(lease_row)
    legacy_rows: list[SessionRow] = []
    remaining = batch_size - len(rows)
    if remaining > 0:
        legacy_statement = (
            select(SessionRow)
            .outerjoin(
                TurnLeaseRow,
                TurnLeaseRow.session_id == SessionRow.session_id,
            )
            .where(TurnLeaseRow.session_id.is_(None))
            .where(SessionRow.state_json.contains('"phase":"active"'))
            .where(SessionRow.state_json.contains('"owner":"chat"'))
            .where(
                SessionRow.state_json.contains('"status":"turn_interrupted"')
            )
        )
        if sessions.expected_navgraph_version is not None:
            legacy_statement = legacy_statement.where(
                SessionRow.navgraph_version == sessions.expected_navgraph_version
            )
        legacy_rows = list(
            database.scalars(
                legacy_statement
                .order_by(SessionRow.updated_at, SessionRow.session_id)
                .limit(remaining)
                .with_for_update()
            ).all()
        )
    for session_row in legacy_rows:
        session = deserialize_session(database, session_row, codec)
        if (
            session.interaction.phase.value != "active"
            or session.interaction.owner is not RouteDeckInteractionOwnerType.CHAT
            or not session.conversation
            or session.conversation[-1].status
            is not ConversationTurnStatus.INTERRUPTED
            or session.public_state.status_code != "turn_interrupted"
        ):
            raise SessionStoreError(SessionStoreErrorCode.PERSISTENCE_FAILURE)
        repaired = (
            RouteDeckSessionAggregate(session)
            .set_interaction(RouteDeckInteractionState())
            .commit()
        )
        sessions.commit(
            database,
            session_id=session.session_id,
            expected_session_version=session.session_version,
            next_state=repaired,
            events=(),
            now=now,
            lease=application_lease,
        )
    return len(rows) + len(legacy_rows)


__all__ = ["recover_abandoned_turn_batch"]
