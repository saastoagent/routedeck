from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage


_LOGGER = logging.getLogger(__name__)


class ChatStreamFailure(RuntimeError):
    def __init__(self, code: str, public_message: str) -> None:
        super().__init__(code)
        self.code = code
        self.public_message = public_message


@dataclass(frozen=True)
class CompletedModelRun:
    output: AIMessage
    chunks: tuple[str, ...]


def final_assistant_message(messages: Sequence[BaseMessage]) -> AIMessage | None:
    for message in reversed(messages):
        if isinstance(message, AIMessage) and not message.tool_calls:
            return message
    return None


def final_assistant_was_streamed(
    assistant: AIMessage,
    completed_runs: Sequence[CompletedModelRun],
) -> bool:
    assistant_text = message_text(assistant)
    for run in completed_runs:
        if run.output.tool_calls or message_text(run.output) != assistant_text:
            continue
        if run.chunks and "".join(run.chunks) == assistant_text:
            return True
    return False


def model_run_id(event: Mapping[str, Any]) -> str:
    run_id = event.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise ChatStreamFailure(
            "agent_stream_contract_invalid",
            "The buyer agent returned an invalid streaming event.",
        )
    return run_id


def message_text(message: object) -> str:
    if isinstance(message, BaseMessage):
        return message.text
    return ""


def messages_from_output(output: object) -> tuple[BaseMessage, ...] | None:
    if not isinstance(output, Mapping):
        return None
    messages = output.get("messages")
    if not isinstance(messages, (list, tuple)) or any(
        not isinstance(message, BaseMessage) for message in messages
    ):
        return None
    return tuple(messages)


def review_event(value: object) -> dict[str, Any] | None:
    if not isinstance(value, ToolMessage) or not isinstance(value.artifact, Mapping):
        return None
    if value.artifact.get("disposition") != "requires_review":
        return None
    review = value.artifact.get("review")
    operation_id = value.artifact.get("operation_id")
    if not isinstance(review, Mapping) or not isinstance(operation_id, str):
        raise ChatStreamFailure(
            "review_result_invalid",
            "The buyer agent returned an invalid review result.",
        )
    review_id = review.get("id")
    expires_at = review.get("expires_at")
    if not isinstance(review_id, str) or not isinstance(expires_at, str):
        raise ChatStreamFailure(
            "review_result_invalid",
            "The buyer agent returned an invalid review result.",
        )
    return {
        "expires_at": expires_at,
        "operation_id": operation_id,
        "review_id": review_id,
        "status": "requires_review",
    }


async def close_event_stream(stream: object) -> None:
    close = getattr(stream, "aclose", None)
    if close is not None and callable(close):
        await close()


def sse(event: str, data: Mapping[str, Any]) -> str:
    payload = json.dumps(
        dict(data),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return f"event: {event}\ndata: {payload}\n\n"


def log_chat_failure(
    event: str,
    *,
    request_id: str,
    error: BaseException,
) -> None:
    """Log only allowlisted failure metadata; exception text may contain PII."""

    error_type = type(error).__name__
    _LOGGER.error(
        "%s error_type=%s",
        event,
        error_type,
        extra={
            "request_id": request_id,
            "error_type": error_type,
        },
    )


__all__ = [
    "ChatStreamFailure",
    "CompletedModelRun",
    "close_event_stream",
    "final_assistant_was_streamed",
    "final_assistant_message",
    "log_chat_failure",
    "message_text",
    "messages_from_output",
    "model_run_id",
    "review_event",
    "sse",
]
