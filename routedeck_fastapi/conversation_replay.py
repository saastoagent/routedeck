from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import NoReturn

from routedeck_core.contracts.conversation import (
    ConversationRole,
    ConversationTurnStatus,
)
from routedeck_core.contracts.mutations import MutationRecord, MutationStatus
from routedeck_core.contracts.session import SessionSnapshot
from routedeck_core.ports import RouteDeckAgentStreamError

from .contracts import ChatStreamRequest
from .conversation_projection import public_conversation


def chat_fingerprint(request: ChatStreamRequest) -> str:
    canonical = json.dumps(
        {"message": request.message},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def chat_replay_frames(
    record: MutationRecord,
    snapshot: SessionSnapshot,
) -> tuple[str, ...]:
    start = sse(
        "stream_start",
        {
            "request_id": record.request_id,
            "session_version": snapshot.session_version,
        },
    )
    history = sse(
        "conversation_snapshot",
        {"turns": public_conversation(snapshot)},
    )
    if record.status is MutationStatus.COMPLETED:
        assistant = next(
            (
                turn
                for turn in reversed(snapshot.state.conversation)
                if turn.status is ConversationTurnStatus.FINALIZED
                and turn.role is ConversationRole.ASSISTANT
                and turn.request_id == record.request_id
            ),
            None,
        )
        if assistant is None:
            _invalid_replay()
        return (
            start,
            history,
            sse(
                "assistant_end",
                {
                    "request_id": record.request_id,
                    "session_version": snapshot.session_version,
                    "projection_version": snapshot.projection_version,
                    "turn_id": assistant.turn_id,
                },
            ),
            sse(
                "stream_end",
                {"request_id": record.request_id, "status": "completed"},
            ),
        )
    result = record.result.to_dict()
    if record.status is MutationStatus.REQUIRES_REVIEW:
        _require_replay_result(result, {"expires_at", "operation_id", "review_id"})
        return (
            start,
            history,
            sse("review_required", {**result, "status": "requires_review"}),
            sse(
                "stream_end",
                {"request_id": record.request_id, "status": "requires_review"},
            ),
        )
    if record.status is MutationStatus.TURN_INTERRUPTED:
        _require_replay_result(result, {"code", "message"})
        return (
            start,
            history,
            sse("chat_error", result),
            sse(
                "stream_end",
                {"request_id": record.request_id, "status": "turn_interrupted"},
            ),
        )
    return _invalid_replay()


def chat_stream_headers() -> dict[str, str]:
    return {
        "Cache-Control": "private, no-store, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }


def sse(event: str, data: Mapping[str, object]) -> str:
    payload = json.dumps(
        dict(data),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return f"event: {event}\ndata: {payload}\n\n"


def _require_replay_result(
    result: Mapping[str, object],
    expected_keys: set[str],
) -> None:
    if set(result) != expected_keys or any(
        not isinstance(value, str) or not value for value in result.values()
    ):
        _invalid_replay()


def _invalid_replay() -> NoReturn:
    raise RouteDeckAgentStreamError(
        "chat_replay_invalid",
        "The saved agent turn could not be replayed.",
    )


__all__ = [
    "chat_fingerprint",
    "chat_replay_frames",
    "chat_stream_headers",
    "sse",
]
