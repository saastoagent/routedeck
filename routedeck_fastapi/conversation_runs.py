from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from routedeck_core.conversation_runs import (
    ConversationRunCoordinator,
    ConversationRunCursorInvalid,
    ConversationRunNotFound,
    entry_turn_request_id,
)
from routedeck_core.contracts.conversation import (
    ConversationRunFailure,
    ConversationRunSnapshot,
    ConversationRunStage,
)
from routedeck_core.contracts.session import SessionSnapshot

from .dependencies import RouteDeckDependencies, RouteDeckDependencyUnavailable


class _ConversationRunPayload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ConversationRunFailurePayload(_ConversationRunPayload):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)


class ConversationRunReviewPayload(_ConversationRunPayload):
    operation_id: str = Field(min_length=1)
    review_id: str = Field(min_length=1)
    expires_at: str = Field(min_length=1)


class ConversationRunSnapshotPayload(_ConversationRunPayload):
    request_id: str = Field(min_length=1, max_length=256)
    kind: Literal["user_message", "assistant_initiated"]
    stage: Literal[
        "starting", "awaiting_model", "generating", "completed", "interrupted"
    ]
    cursor: int = Field(ge=1)
    assistant_content: str = ""
    user_message: str | None = None
    user_turn_id: str | None = Field(default=None, min_length=1)
    session_version: int | None = Field(default=None, ge=0)
    projection_version: int | None = Field(default=None, ge=0)
    turn_id: str | None = Field(default=None, min_length=1)
    failure: ConversationRunFailurePayload | None = None
    review: ConversationRunReviewPayload | None = None

    @classmethod
    def from_snapshot(
        cls, snapshot: ConversationRunSnapshot
    ) -> ConversationRunSnapshotPayload:
        return cls.model_validate(snapshot.model_dump(mode="python"))


class ConversationRunEnvelope(_ConversationRunPayload):
    run: ConversationRunSnapshotPayload

    @classmethod
    def from_snapshot(
        cls, snapshot: ConversationRunSnapshot
    ) -> ConversationRunEnvelope:
        return cls(run=ConversationRunSnapshotPayload.from_snapshot(snapshot))


def public_conversation_run_envelope(
    snapshot: ConversationRunSnapshot,
) -> dict[str, object]:
    return ConversationRunEnvelope.from_snapshot(snapshot).model_dump(mode="json")


def require_conversation_runs(
    dependencies: RouteDeckDependencies,
) -> ConversationRunCoordinator:
    coordinator = dependencies.conversation_runs
    if coordinator is None:
        raise RouteDeckDependencyUnavailable(
            "RouteDeck conversation runs require a runtime-owned coordinator"
        )
    return coordinator


async def ensure_current_node_entry_turn(
    *,
    dependencies: RouteDeckDependencies,
    session_id: str,
    snapshot: SessionSnapshot | None = None,
) -> ConversationRunSnapshot | None:
    current = snapshot or await dependencies.store.load(session_id)
    node = dependencies.app.require_node(current.state.current.node_id)
    if node.entry_turn is None:
        return None
    return await require_conversation_runs(
        dependencies
    ).ensure_declared_entry_run(current)


def encode_run_event(event: ConversationRunSnapshot) -> bytes:
    data = json.dumps(
        ConversationRunSnapshotPayload.from_snapshot(event).model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return f"id: {event.cursor}\nevent: conversation_run\ndata: {data}\n\n".encode(
        "utf-8"
    )


__all__ = [
    "ConversationRunCoordinator",
    "ConversationRunCursorInvalid",
    "ConversationRunEnvelope",
    "ConversationRunFailure",
    "ConversationRunFailurePayload",
    "ConversationRunNotFound",
    "ConversationRunReviewPayload",
    "ConversationRunSnapshot",
    "ConversationRunSnapshotPayload",
    "ConversationRunStage",
    "encode_run_event",
    "ensure_current_node_entry_turn",
    "entry_turn_request_id",
    "public_conversation_run_envelope",
    "require_conversation_runs",
]
