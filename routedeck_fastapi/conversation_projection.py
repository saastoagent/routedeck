from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from routedeck_core.contracts.conversation import (
    ConversationRole,
    ConversationTurnStatus,
)
from routedeck_core.contracts.session import SessionSnapshot


class PublicConversationTurn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    turn_id: str
    request_id: str | None
    role: Literal["user", "assistant"]
    content: str


def public_conversation(snapshot: SessionSnapshot) -> list[dict[str, object]]:
    return [
        PublicConversationTurn(
            turn_id=turn.turn_id,
            request_id=turn.request_id,
            role=("user" if turn.role is ConversationRole.USER else "assistant"),
            content=turn.content,
        ).model_dump(mode="json")
        for turn in snapshot.state.conversation
        if turn.status is ConversationTurnStatus.FINALIZED
        and turn.role in {ConversationRole.USER, ConversationRole.ASSISTANT}
    ]


__all__ = ["PublicConversationTurn", "public_conversation"]
