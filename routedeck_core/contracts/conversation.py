from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .projection import FrozenJsonObject


class _FrozenContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ConversationRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ConversationTurnStatus(StrEnum):
    FINALIZED = "finalized"
    INTERRUPTED = "turn_interrupted"


class ConversationToolCall(_FrozenContract):
    """Framework-neutral metadata needed to replay one observed tool call.

    The SQLite adapter encrypts this metadata with the turn content because
    model preambles and arguments may echo buyer data.
    """

    call_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    arguments: FrozenJsonObject = FrozenJsonObject({})
    assistant_content: str = ""


class ConversationTurn(_FrozenContract):
    turn_id: str = Field(min_length=1)
    role: ConversationRole
    content: str
    request_id: str | None = None
    status: ConversationTurnStatus
    tool_call: ConversationToolCall | None = None
    tool_status: Literal["success", "error"] | None = None

    @model_validator(mode="after")
    def _tool_metadata_matches_role(self) -> ConversationTurn:
        has_tool_call = self.tool_call is not None
        has_tool_status = self.tool_status is not None
        if self.role is not ConversationRole.TOOL and (
            has_tool_call or has_tool_status
        ):
            raise ValueError("tool metadata belongs only to tool turns")
        if self.role is ConversationRole.TOOL and not has_tool_call:
            raise ValueError("tool turns require typed tool-call metadata")
        if has_tool_call != has_tool_status:
            raise ValueError("tool turns require call metadata and status together")
        return self


class FinalizedConversationTurn(ConversationTurn):
    status: Literal[ConversationTurnStatus.FINALIZED] = ConversationTurnStatus.FINALIZED


__all__ = [
    "ConversationRole",
    "ConversationToolCall",
    "ConversationTurn",
    "ConversationTurnStatus",
    "FinalizedConversationTurn",
]
