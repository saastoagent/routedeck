from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from ..contracts.conversation import ConversationTurn
from ..contracts.projection import DataClassification
from ..contracts.session import (
    Location,
    OperationState,
    PrivateDraft,
    PrivateSessionState,
    PublicSessionState,
    RouteDeckSession,
)
from .history import enter_location


class _ReducerEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class PrivateDraftStored(_ReducerEvent):
    draft: PrivateDraft


class NodeEntered(_ReducerEvent):
    location: Location


class HistoryReplaced(_ReducerEvent):
    current: Location
    back_stack: tuple[Location, ...]
    forward_stack: tuple[Location, ...]


class ConversationTurnsStored(_ReducerEvent):
    turns: tuple[ConversationTurn, ...]


class OperationStateStored(_ReducerEvent):
    operation: OperationState | None


class PublicSessionStateStored(_ReducerEvent):
    state: PublicSessionState


class PrivateSessionStateStored(_ReducerEvent):
    state: PrivateSessionState


class PublicEventsRecorded(_ReducerEvent):
    count: int = Field(ge=0)


SessionReducerEvent = (
    PrivateDraftStored
    | NodeEntered
    | HistoryReplaced
    | ConversationTurnsStored
    | OperationStateStored
    | PrivateSessionStateStored
    | PublicSessionStateStored
    | PublicEventsRecorded
)


def reduce_session(
    session: RouteDeckSession,
    event: SessionReducerEvent | object,
) -> RouteDeckSession:
    """Apply one pure canonical mutation without clocks, I/O, or persistence."""

    if type(event) is PrivateDraftStored:
        return _store_private_draft(session, event.draft)
    if type(event) is NodeEntered:
        return _enter_node(session, event.location)
    if type(event) is HistoryReplaced:
        return _replace_history(session, event)
    if type(event) is ConversationTurnsStored:
        return _store_conversation_turns(session, event.turns)
    if type(event) is OperationStateStored:
        return _store_operation_state(session, event)
    if type(event) is PrivateSessionStateStored:
        return _store_private_state(session, event.state)
    if type(event) is PublicSessionStateStored:
        return _store_public_state(session, event.state)
    if type(event) is PublicEventsRecorded:
        return _record_public_events(session, event.count)
    raise TypeError(f"Unsupported RouteDeck reducer event: {type(event).__name__}")


def reduce_session_batch(
    session: RouteDeckSession,
    events: Sequence[SessionReducerEvent],
) -> RouteDeckSession:
    """Apply one transactional mutation and normalize its revisions exactly once."""

    candidate = session
    for event in events:
        candidate = reduce_session(candidate, event)

    normalized = candidate.model_copy(
        update={
            "session_version": session.session_version,
            "projection_version": session.projection_version,
            "event_cursor": session.event_cursor,
        }
    )
    canonical_changed = normalized != session
    public_changed = _public_signature(normalized) != _public_signature(session)
    cursor_changed = candidate.event_cursor != session.event_cursor
    if not canonical_changed and not cursor_changed:
        return session
    return normalized.model_copy(
        update={
            "session_version": (
                session.session_version + 1
                if canonical_changed
                else session.session_version
            ),
            "projection_version": (
                session.projection_version + 1
                if public_changed
                else session.projection_version
            ),
            "event_cursor": candidate.event_cursor,
        }
    )


def _public_signature(session: RouteDeckSession) -> tuple[object, ...]:
    return (
        session.current,
        session.back_stack,
        session.forward_stack,
        _projectable_public_state_signature(session.public_state),
    )


def _projectable_public_state_signature(
    state: PublicSessionState,
) -> tuple[object, ...]:
    public_surface_values = tuple(
        (
            surface.surface_id,
            tuple(
                value
                for value in surface.values
                if value.classification is DataClassification.PUBLIC
            ),
        )
        for surface in state.surface_state
    )
    return (
        state.entity_handles,
        tuple(item for item in public_surface_values if item[1]),
        state.status_code,
        state.status_message,
        state.failure,
        tuple(sorted(state.disabled_operation_ids)),
    )


def _store_private_draft(
    session: RouteDeckSession,
    draft: PrivateDraft,
) -> RouteDeckSession:
    drafts = list(session.private_state.drafts)
    for index, candidate in enumerate(drafts):
        if candidate.form_id != draft.form_id:
            continue
        if candidate == draft:
            return session
        drafts[index] = draft
        break
    else:
        drafts.append(draft)
    frozen_drafts = tuple(drafts)
    private_state = session.private_state.model_copy(update={"drafts": frozen_drafts})
    return session.model_copy(
        update={
            "private_state": private_state,
            "session_version": session.session_version + 1,
        }
    )


def _enter_node(
    session: RouteDeckSession,
    location: Location,
) -> RouteDeckSession:
    if (
        location.node_id == session.current.node_id
        and location.route_params == session.current.route_params
    ):
        return session
    canonical_location = location.model_copy(
        update={"entry_id": session.next_history_entry_id}
    )
    history = enter_location(
        current=session.current,
        back_stack=session.back_stack,
        location=canonical_location,
    )
    return session.model_copy(
        update={
            "current": history.current,
            "back_stack": history.back_stack,
            "forward_stack": history.forward_stack,
            "next_history_entry_id": session.next_history_entry_id + 1,
            "session_version": session.session_version + 1,
            "projection_version": session.projection_version + 1,
        }
    )


def _replace_history(
    session: RouteDeckSession,
    event: HistoryReplaced,
) -> RouteDeckSession:
    next_history = (event.current, event.back_stack, event.forward_stack)
    current_history = (session.current, session.back_stack, session.forward_stack)
    if next_history == current_history:
        return session
    return session.model_copy(
        update={
            "current": event.current,
            "back_stack": event.back_stack,
            "forward_stack": event.forward_stack,
            "session_version": session.session_version + 1,
            "projection_version": session.projection_version + 1,
        }
    )


def _store_conversation_turns(
    session: RouteDeckSession,
    turns: tuple[ConversationTurn, ...],
) -> RouteDeckSession:
    if not turns:
        return session
    conversation = (*session.conversation, *turns)
    return session.model_copy(
        update={
            "conversation": conversation,
            "session_version": session.session_version + 1,
        }
    )


def _store_operation_state(
    session: RouteDeckSession,
    event: OperationStateStored,
) -> RouteDeckSession:
    if event.operation == session.operation:
        return session
    return session.model_copy(
        update={
            "operation": event.operation,
            "session_version": session.session_version + 1,
        }
    )


def _store_public_state(
    session: RouteDeckSession,
    state: PublicSessionState,
) -> RouteDeckSession:
    if state == session.public_state:
        return session
    projection_changed = _projectable_public_state_signature(
        state
    ) != _projectable_public_state_signature(session.public_state)
    return session.model_copy(
        update={
            "public_state": state,
            "session_version": session.session_version + 1,
            "projection_version": (
                session.projection_version + 1
                if projection_changed
                else session.projection_version
            ),
        }
    )


def _store_private_state(
    session: RouteDeckSession,
    state: PrivateSessionState,
) -> RouteDeckSession:
    if state == session.private_state:
        return session
    return session.model_copy(
        update={
            "private_state": state,
            "session_version": session.session_version + 1,
        }
    )


def _record_public_events(
    session: RouteDeckSession,
    count: int,
) -> RouteDeckSession:
    if count == 0:
        return session
    return session.model_copy(update={"event_cursor": session.event_cursor + count})


__all__ = [
    "ConversationTurnsStored",
    "HistoryReplaced",
    "NodeEntered",
    "OperationStateStored",
    "PrivateDraftStored",
    "PrivateSessionStateStored",
    "PublicEventsRecorded",
    "PublicSessionStateStored",
    "SessionReducerEvent",
    "reduce_session",
    "reduce_session_batch",
]
