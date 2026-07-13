from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from routedeck_core.contracts.conversation import (
    ConversationRole,
    ConversationTurnStatus,
    FinalizedConversationTurn,
)
from routedeck_core.contracts.events import (
    PublicEventPayload,
    RouteDeckEvent,
    RouteDeckEventType,
)
from routedeck_core.contracts.session import SessionSnapshot
from routedeck_testing.factories import session_factory


NOW = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)


def test_snapshot_exposes_canonical_state_and_version_metadata() -> None:
    session = session_factory()

    snapshot = SessionSnapshot(state=session)

    assert snapshot.state is session
    assert snapshot.session_id == session.session_id
    assert snapshot.session_version == session.session_version
    assert snapshot.projection_version == session.projection_version
    assert snapshot.event_cursor == session.event_cursor


def test_conversation_and_event_contracts_are_frozen_and_serializable() -> None:
    turn = FinalizedConversationTurn(
        turn_id="turn-1",
        role=ConversationRole.USER,
        content="hello",
        request_id="request-1",
    )
    event = RouteDeckEvent(
        event_id="event-1",
        cursor=1,
        event_type=RouteDeckEventType.TURN_FINALIZED,
        session_id="session-1",
        session_version=2,
        projection_version=1,
        created_at=NOW,
        payload=PublicEventPayload(node_id="buyer.home", status_code="ready"),
    )

    assert turn.status is ConversationTurnStatus.FINALIZED
    assert event.model_dump(mode="json")["payload"] == {
        "node_id": "buyer.home",
        "operation_id": None,
        "request_id": None,
        "status_code": "ready",
        "entity_handles": [],
        "details": [],
        "failure": None,
    }
    with pytest.raises(ValidationError):
        turn.content = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        event.payload.status_code = "changed"  # type: ignore[misc]


def test_event_contract_rejects_naive_time_and_undeclared_payload_fields() -> None:
    with pytest.raises(ValidationError):
        RouteDeckEvent(
            event_id="event-1",
            cursor=1,
            event_type=RouteDeckEventType.SESSION_CREATED,
            session_id="session-1",
            session_version=0,
            created_at=datetime(2026, 7, 11, 12, 0),
            payload=PublicEventPayload(),
        )

    with pytest.raises(ValidationError):
        PublicEventPayload.model_validate({"private_id": "cart_private_123"})
