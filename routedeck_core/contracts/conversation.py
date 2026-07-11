from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _FrozenContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ConversationRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ConversationTurnStatus(StrEnum):
    FINALIZED = "finalized"
    INTERRUPTED = "turn_interrupted"


class ConversationTurn(_FrozenContract):
    turn_id: str = Field(min_length=1)
    role: ConversationRole
    content: str
    request_id: str | None = None
    status: ConversationTurnStatus


class FinalizedConversationTurn(ConversationTurn):
    status: Literal[ConversationTurnStatus.FINALIZED] = ConversationTurnStatus.FINALIZED


__all__ = [
    "ConversationRole",
    "ConversationTurn",
    "ConversationTurnStatus",
    "FinalizedConversationTurn",
]
