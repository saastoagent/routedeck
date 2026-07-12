from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from .projection import FrozenJsonObject


class _FrozenContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class MutationKind(StrEnum):
    NAVIGATION = "navigation"
    PRIVATE_FORM = "private_form"
    CHAT = "chat"


class MutationStatus(StrEnum):
    COMPLETED = "completed"
    REQUIRES_REVIEW = "requires_review"
    TURN_INTERRUPTED = "turn_interrupted"


class MutationCommit(_FrozenContract):
    """Public-safe result metadata committed with one canonical mutation."""

    kind: MutationKind
    status: MutationStatus
    result: FrozenJsonObject = Field(default_factory=lambda: FrozenJsonObject({}))


class MutationRecord(MutationCommit):
    """Durable request identity and the exact version it committed."""

    session_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    request_fingerprint: str = Field(min_length=1)
    committed_session_version: int = Field(ge=0)
    committed_projection_version: int = Field(ge=0)
    committed_event_cursor: int = Field(ge=0)


__all__ = [
    "MutationCommit",
    "MutationKind",
    "MutationRecord",
    "MutationStatus",
]
