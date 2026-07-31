from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .conversation_projection import PublicConversationTurn


JAVASCRIPT_MAX_SAFE_INTEGER = 9_007_199_254_740_991


class _ConversationSsePayload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ConversationStreamStartPayload(_ConversationSsePayload):
    request_id: str = Field(min_length=1, max_length=256)
    session_version: int = Field(ge=0, le=JAVASCRIPT_MAX_SAFE_INTEGER)


class ConversationSnapshotPayload(_ConversationSsePayload):
    turns: tuple[PublicConversationTurn, ...]


class ConversationUserMessagePayload(_ConversationSsePayload):
    content: str = Field(min_length=1)
    request_id: str = Field(min_length=1, max_length=256)
    turn_id: str = Field(min_length=1)


class ConversationAssistantDeltaPayload(_ConversationSsePayload):
    content: str = Field(min_length=1)
    request_id: str = Field(min_length=1, max_length=256)


class ConversationAssistantResetPayload(_ConversationSsePayload):
    request_id: str = Field(min_length=1, max_length=256)


class ConversationAssistantEndPayload(_ConversationSsePayload):
    request_id: str = Field(min_length=1, max_length=256)
    session_version: int = Field(ge=0, le=JAVASCRIPT_MAX_SAFE_INTEGER)
    projection_version: int = Field(ge=0, le=JAVASCRIPT_MAX_SAFE_INTEGER)
    turn_id: str = Field(min_length=1)


class ConversationReviewRequiredPayload(_ConversationSsePayload):
    status: Literal["requires_review"]
    operation_id: str = Field(min_length=1)
    review_id: str = Field(min_length=1)
    expires_at: str = Field(min_length=1)


class ConversationChatErrorPayload(_ConversationSsePayload):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)


class ConversationStreamEndPayload(_ConversationSsePayload):
    request_id: str = Field(min_length=1, max_length=256)
    status: Literal[
        "completed",
        "requires_review",
        "rejected",
        "turn_interrupted",
        "outcome_unknown",
    ]


ConversationSsePayload = (
    ConversationStreamStartPayload
    | ConversationSnapshotPayload
    | ConversationUserMessagePayload
    | ConversationAssistantDeltaPayload
    | ConversationAssistantResetPayload
    | ConversationAssistantEndPayload
    | ConversationReviewRequiredPayload
    | ConversationChatErrorPayload
    | ConversationStreamEndPayload
)

_PAYLOAD_MODELS: dict[str, type[_ConversationSsePayload]] = {
    "stream_start": ConversationStreamStartPayload,
    "conversation_snapshot": ConversationSnapshotPayload,
    "user_message": ConversationUserMessagePayload,
    "assistant_delta": ConversationAssistantDeltaPayload,
    "assistant_reset": ConversationAssistantResetPayload,
    "assistant_end": ConversationAssistantEndPayload,
    "review_required": ConversationReviewRequiredPayload,
    "chat_error": ConversationChatErrorPayload,
    "stream_end": ConversationStreamEndPayload,
}


def encode_conversation_sse(
    event: str,
    data: Mapping[str, object],
) -> str:
    """Validate and encode one public legacy conversation SSE payload."""

    try:
        payload_model = _PAYLOAD_MODELS[event]
    except KeyError as error:
        raise ValueError(f"unsupported conversation SSE event: {event}") from error
    payload = payload_model.model_validate(dict(data)).model_dump(mode="json")
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return f"event: {event}\ndata: {encoded}\n\n"


__all__ = [
    "ConversationAssistantDeltaPayload",
    "ConversationAssistantEndPayload",
    "ConversationAssistantResetPayload",
    "ConversationChatErrorPayload",
    "ConversationReviewRequiredPayload",
    "ConversationSnapshotPayload",
    "ConversationSsePayload",
    "ConversationStreamEndPayload",
    "ConversationStreamStartPayload",
    "ConversationUserMessagePayload",
    "encode_conversation_sse",
]
