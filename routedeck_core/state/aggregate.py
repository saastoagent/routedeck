from __future__ import annotations

from typing import Self

from ..contracts.conversation import ConversationTurn
from ..contracts.projection import DataClassification
from ..contracts.interactions import RouteDeckInteractionState
from ..contracts.session import (
    Location,
    OperationState,
    PrivateDraft,
    PrivateSessionState,
    PublicSessionState,
    RouteDeckSession,
)
from .history import enter_location


class RouteDeckSessionAggregate:
    """Transaction-scoped owner of canonical RouteDeck session mutations.

    The aggregate exposes named domain operations instead of accepting a generic
    event stream. ``commit`` normalizes all changes into one session/projection
    version advance, matching the persistence transaction that stores the result.
    """

    def __init__(self, session: RouteDeckSession) -> None:
        self._original = session
        self._candidate = session

    def store_private_draft(self, draft: PrivateDraft) -> Self:
        drafts = list(self._candidate.private_state.drafts)
        for index, candidate in enumerate(drafts):
            if candidate.form_id != draft.form_id:
                continue
            if candidate == draft:
                return self
            drafts[index] = draft
            break
        else:
            drafts.append(draft)
        private_state = self._candidate.private_state.model_copy(
            update={"drafts": tuple(drafts)}
        )
        self._candidate = self._candidate.model_copy(
            update={"private_state": private_state}
        )
        return self

    def enter_node(self, location: Location) -> Self:
        current = self._candidate.current
        if (
            location.node_id == current.node_id
            and location.route_params == current.route_params
        ):
            return self
        canonical_location = location.model_copy(
            update={"entry_id": self._candidate.next_history_entry_id}
        )
        history = enter_location(
            current=current,
            back_stack=self._candidate.back_stack,
            location=canonical_location,
        )
        self._candidate = self._candidate.model_copy(
            update={
                "current": history.current,
                "back_stack": history.back_stack,
                "forward_stack": history.forward_stack,
                "next_history_entry_id": self._candidate.next_history_entry_id + 1,
            }
        )
        return self

    def replace_history(
        self,
        *,
        current: Location,
        back_stack: tuple[Location, ...],
        forward_stack: tuple[Location, ...],
    ) -> Self:
        next_history = (current, back_stack, forward_stack)
        current_history = (
            self._candidate.current,
            self._candidate.back_stack,
            self._candidate.forward_stack,
        )
        if next_history == current_history:
            return self
        self._candidate = self._candidate.model_copy(
            update={
                "current": current,
                "back_stack": back_stack,
                "forward_stack": forward_stack,
            }
        )
        return self

    def append_conversation_turns(
        self,
        turns: tuple[ConversationTurn, ...],
    ) -> Self:
        if turns:
            self._candidate = self._candidate.model_copy(
                update={"conversation": (*self._candidate.conversation, *turns)}
            )
        return self

    def set_interaction(self, interaction: RouteDeckInteractionState) -> Self:
        if interaction != self._candidate.interaction:
            self._candidate = self._candidate.model_copy(
                update={"interaction": interaction}
            )
        return self

    def set_operation_state(self, operation: OperationState | None) -> Self:
        if operation != self._candidate.operation:
            self._candidate = self._candidate.model_copy(
                update={"operation": operation}
            )
        return self

    def set_public_state(self, state: PublicSessionState) -> Self:
        if state != self._candidate.public_state:
            self._candidate = self._candidate.model_copy(update={"public_state": state})
        return self

    def set_private_state(self, state: PrivateSessionState) -> Self:
        if state != self._candidate.private_state:
            self._candidate = self._candidate.model_copy(update={"private_state": state})
        return self

    def record_public_events(self, count: int) -> Self:
        if count < 0:
            raise ValueError("Public event count cannot be negative")
        if count:
            self._candidate = self._candidate.model_copy(
                update={"event_cursor": self._candidate.event_cursor + count}
            )
        return self

    def commit(self) -> RouteDeckSession:
        candidate = self._candidate.model_copy(
            update={
                "session_version": self._original.session_version,
                "projection_version": self._original.projection_version,
                "event_cursor": self._original.event_cursor,
            }
        )
        canonical_changed = candidate != self._original
        public_changed = _public_signature(candidate) != _public_signature(
            self._original
        )
        cursor_changed = (
            self._candidate.event_cursor != self._original.event_cursor
        )
        if not canonical_changed and not cursor_changed:
            return self._original
        return candidate.model_copy(
            update={
                "session_version": (
                    self._original.session_version + 1
                    if canonical_changed
                    else self._original.session_version
                ),
                "projection_version": (
                    self._original.projection_version + 1
                    if public_changed
                    else self._original.projection_version
                ),
                "event_cursor": self._candidate.event_cursor,
            }
        )


def _public_signature(session: RouteDeckSession) -> tuple[object, ...]:
    return (
        session.current,
        _current_resume_handle_signature(session),
        session.back_stack,
        session.forward_stack,
        session.interaction,
        _projectable_public_state_signature(session.public_state),
    )


def _current_resume_handle_signature(session: RouteDeckSession) -> tuple[str, ...]:
    return tuple(
        capability.handle
        for capability in session.private_state.resume_capabilities
        if capability.session_id == session.session_id
        and capability.node_id == session.current.node_id
        and capability.route_params == session.current.route_params
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


__all__ = ["RouteDeckSessionAggregate"]
