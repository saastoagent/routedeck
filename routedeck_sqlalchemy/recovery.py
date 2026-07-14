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
from routedeck_core.contracts.mutations import (
    MutationCommit,
    MutationKind,
    MutationStatus,
)
from routedeck_core.contracts.projection import FrozenJsonObject
from routedeck_core.contracts.retention import RouteDeckRetentionPolicy
from routedeck_core.state.aggregate import RouteDeckSessionAggregate

from .codec import SensitiveCodec
from .lease import ApplicationLease
from .models import ActiveChildAttemptRow, TurnLeaseRow
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
    rows = database.scalars(
        select(TurnLeaseRow)
        .order_by(TurnLeaseRow.acquired_at)
        .limit(retention_policy.cleanup_batch_size)
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
    return len(rows)


__all__ = ["recover_abandoned_turn_batch"]
