from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .failures import RouteDeckFailure
from .projection import PublicEntityHandle, PublicValue


class _FrozenContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RouteDeckEventType(StrEnum):
    SESSION_CREATED = "session_created"
    PROJECTION_CHANGED = "projection_changed"
    NAVIGATION_CHANGED = "navigation_changed"
    OPERATION_CHANGED = "operation_changed"
    PRIVATE_FORM_CHANGED = "private_form_changed"
    TURN_FINALIZED = "turn_finalized"
    TURN_INTERRUPTED = "turn_interrupted"


class PublicEventPayload(_FrozenContract):
    node_id: str | None = None
    operation_id: str | None = None
    request_id: str | None = None
    status_code: str | None = None
    entity_handles: tuple[PublicEntityHandle, ...] = ()
    details: tuple[PublicValue, ...] = ()
    failure: RouteDeckFailure | None = None


class CanonicalRouteDeckEvent(_FrozenContract):
    """Canonical Task 4 event; the root legacy event remains a compatibility API."""

    event_id: str = Field(min_length=1)
    cursor: int = Field(ge=1)
    event_type: RouteDeckEventType
    session_id: str = Field(min_length=1)
    session_version: int = Field(ge=0)
    projection_version: int | None = Field(default=None, ge=0)
    created_at: datetime
    payload: PublicEventPayload

    @model_validator(mode="after")
    def _aware_timestamp(self) -> CanonicalRouteDeckEvent:
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return self

    @property
    def event_cursor(self) -> int:
        return self.cursor

    @property
    def type(self) -> RouteDeckEventType:
        return self.event_type


RouteDeckEvent = CanonicalRouteDeckEvent


class EventPage(_FrozenContract):
    events: tuple[CanonicalRouteDeckEvent, ...]
    next_cursor: int = Field(ge=0)
    has_more: bool
    reset_required: bool = False
    retained_from_cursor: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _reset_contract(self) -> EventPage:
        if self.reset_required:
            if self.events or self.has_more or self.retained_from_cursor is None:
                raise ValueError(
                    "reset-required event pages contain only the retained cursor"
                )
        elif self.retained_from_cursor is not None:
            raise ValueError("retained_from_cursor is valid only for reset pages")
        return self


__all__ = [
    "CanonicalRouteDeckEvent",
    "EventPage",
    "PublicEventPayload",
    "RouteDeckEvent",
    "RouteDeckEventType",
]
