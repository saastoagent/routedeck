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


class EntryTurnOccurrence(StrEnum):
    ONCE_PER_SESSION_NODE = "once_per_session_node"


class EntryTurnDeclaration(_FrozenContract):
    """Declare one product-authored assistant turn on entry to a node."""

    id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._-]+$")
    occurrence: EntryTurnOccurrence = EntryTurnOccurrence.ONCE_PER_SESSION_NODE


class ConversationRunKind(StrEnum):
    USER_MESSAGE = "user_message"
    ASSISTANT_INITIATED = "assistant_initiated"


class ConversationRunStage(StrEnum):
    STARTING = "starting"
    AWAITING_MODEL = "awaiting_model"
    GENERATING = "generating"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"


class ConversationRunFailure(_FrozenContract):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)


class ConversationRunReview(_FrozenContract):
    operation_id: str = Field(min_length=1)
    review_id: str = Field(min_length=1)
    expires_at: str = Field(min_length=1)


class ConversationRunSnapshot(_FrozenContract):
    request_id: str = Field(min_length=1, max_length=256)
    kind: ConversationRunKind
    stage: ConversationRunStage
    cursor: int = Field(ge=1)
    assistant_content: str = ""
    user_message: str | None = None
    user_turn_id: str | None = Field(default=None, min_length=1)
    session_version: int | None = Field(default=None, ge=0)
    projection_version: int | None = Field(default=None, ge=0)
    turn_id: str | None = Field(default=None, min_length=1)
    failure: ConversationRunFailure | None = None
    review: ConversationRunReview | None = None

    @property
    def terminal(self) -> bool:
        return self.stage in {
            ConversationRunStage.COMPLETED,
            ConversationRunStage.INTERRUPTED,
        }


class ConversationInputPolicy(_FrozenContract):
    """Static node policy for whether a conversation composer may accept input."""

    enabled: bool
    disabled_message: str | None

    @model_validator(mode="after")
    def _disabled_message_matches_enabled_state(self) -> ConversationInputPolicy:
        message = self.disabled_message
        if self.enabled and message is not None:
            raise ValueError(
                "disabled_message must be omitted when conversation input is enabled"
            )
        if not self.enabled and (message is None or not message.strip()):
            raise ValueError(
                "disabled_message is required when conversation input is disabled"
            )
        return self


class ConversationToolCall(_FrozenContract):
    """Framework-neutral metadata needed to replay one observed tool call.

    The SQLAlchemy adapter encrypts this metadata with the turn content because
    model preambles and arguments may echo sensitive user data.
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
    "ConversationInputPolicy",
    "ConversationRunFailure",
    "ConversationRunKind",
    "ConversationRunReview",
    "ConversationRunSnapshot",
    "ConversationRunStage",
    "ConversationRole",
    "ConversationToolCall",
    "ConversationTurn",
    "ConversationTurnStatus",
    "EntryTurnDeclaration",
    "EntryTurnOccurrence",
    "FinalizedConversationTurn",
]
