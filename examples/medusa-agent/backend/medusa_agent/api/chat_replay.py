from __future__ import annotations

import hashlib
import inspect
import json

from fastapi import Request
from fastapi.responses import JSONResponse

from routedeck_core.contracts.conversation import (
    ConversationRole,
    ConversationTurnStatus,
)
from routedeck_core.contracts.mutations import MutationRecord, MutationStatus
from routedeck_core.contracts.session import SessionSnapshot
from routedeck_core.ports import SessionStoreError, SessionStoreErrorCode
from routedeck_fastapi import RouteDeckDependencies, RouteDeckDependencyUnavailable

from .chat_contract import (
    ChatDependencyProvider,
    ChatStreamRequest,
    MedusaChatDependencies,
)
from .chat_events import ChatStreamFailure, sse
from .conversation import public_conversation


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
            raise ChatStreamFailure(
                "chat_replay_invalid",
                "The saved buyer-agent turn could not be replayed.",
            )
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
        if set(result) != {"expires_at", "operation_id", "review_id"} or any(
            not isinstance(value, str) or not value for value in result.values()
        ):
            raise ChatStreamFailure(
                "chat_replay_invalid",
                "The saved buyer-agent turn could not be replayed.",
            )
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
        if set(result) != {"code", "message"} or any(
            not isinstance(value, str) or not value for value in result.values()
        ):
            raise ChatStreamFailure(
                "chat_replay_invalid",
                "The saved buyer-agent turn could not be replayed.",
            )
        return (
            start,
            history,
            sse("chat_error", result),
            sse(
                "stream_end",
                {"request_id": record.request_id, "status": "turn_interrupted"},
            ),
        )
    raise ChatStreamFailure(
        "chat_replay_invalid",
        "The saved buyer-agent turn could not be replayed.",
    )


def chat_stream_headers() -> dict[str, str]:
    return {
        "Cache-Control": "private, no-store, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }


def guest_session_id(
    request: Request,
    dependencies: RouteDeckDependencies,
) -> str:
    session_id = request.cookies.get(dependencies.cookie.name)
    if not session_id or len(session_id) > 512:
        raise SessionStoreError(SessionStoreErrorCode.SESSION_NOT_FOUND)
    return session_id


async def resolve_dependencies(
    provider: ChatDependencyProvider,
    request: Request,
) -> MedusaChatDependencies:
    value = provider(request)
    if inspect.isawaitable(value):
        value = await value
    if not isinstance(value, MedusaChatDependencies):
        raise RouteDeckDependencyUnavailable("Medusa chat is not configured")
    return value


def problem_response(status: int, *, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"failure": {"code": code, "message": message}},
        headers={"Cache-Control": "no-store"},
    )


__all__ = [
    "chat_fingerprint",
    "chat_replay_frames",
    "chat_stream_headers",
    "guest_session_id",
    "problem_response",
    "resolve_dependencies",
]
