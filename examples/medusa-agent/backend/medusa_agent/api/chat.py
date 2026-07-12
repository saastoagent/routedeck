from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import logging
import secrets
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from pydantic import BaseModel, ConfigDict, Field, field_validator

from routedeck_core.contracts.conversation import (
    ConversationRole,
    ConversationTurnStatus,
    FinalizedConversationTurn,
)
from routedeck_core.contracts.failures import FailureKind, RouteDeckFailure
from routedeck_core.contracts.mutations import (
    MutationKind,
    MutationRecord,
    MutationStatus,
)
from routedeck_core.contracts.session import SessionSnapshot
from routedeck_core.ports import SessionStoreError, SessionStoreErrorCode
from routedeck_core.state.leases import TurnClaim, TurnLease, TurnOwnerKind
from routedeck_core.state.session import require_compatible_session
from routedeck_fastapi import RouteDeckDependencies, RouteDeckDependencyUnavailable
from routedeck_langgraph import (
    RouteDeckInvocationContext,
    extract_conversation_turns,
)

from .conversation import public_conversation


_LOGGER = logging.getLogger(__name__)


class _ChatRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChatStreamRequest(_ChatRequestModel):
    request_id: str = Field(min_length=1, max_length=256)
    expected_session_version: int = Field(ge=0)
    message: str = Field(min_length=1, max_length=16_000)

    @field_validator("request_id", "message")
    @classmethod
    def _not_whitespace(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must contain non-whitespace text")
        return value


class AgentEventStream(Protocol):
    def astream_events(
        self,
        input: Mapping[str, Any],
        config: Mapping[str, Any] | None = None,
        *,
        version: str = "v2",
        **kwargs: Any,
    ) -> AsyncIterator[Mapping[str, Any]]: ...


@dataclass(frozen=True)
class MedusaChatDependencies:
    routedeck: RouteDeckDependencies
    agent: AgentEventStream

    def __post_init__(self) -> None:
        if not callable(getattr(self.agent, "astream_events", None)):
            raise TypeError("Medusa chat agent must expose astream_events")


ChatDependencyProvider = Callable[
    [Request],
    MedusaChatDependencies | Awaitable[MedusaChatDependencies],
]


class _ChatStreamFailure(RuntimeError):
    def __init__(self, code: str, public_message: str) -> None:
        super().__init__(code)
        self.code = code
        self.public_message = public_message


@dataclass(frozen=True)
class _CompletedModelRun:
    output: AIMessage
    chunks: tuple[str, ...]


def create_medusa_chat_router(provider: ChatDependencyProvider) -> APIRouter:
    """Create the product-owned assistant stream, separate from RouteDeck SSE."""

    router = APIRouter(prefix="/api/medusa-agent", tags=["medusa-agent-chat"])

    @router.post("/chat")
    async def chat(body: ChatStreamRequest, request: Request):
        try:
            dependencies = await _resolve_dependencies(provider, request)
            session_id = _guest_session_id(request, dependencies.routedeck)
            fingerprint = _chat_fingerprint(body)
            recorded = await dependencies.routedeck.store.find_mutation(
                session_id,
                body.request_id,
            )
            if recorded is not None:
                if (
                    recorded.kind is not MutationKind.CHAT
                    or recorded.request_fingerprint != fingerprint
                ):
                    return _problem_response(
                        409,
                        code="request_id_reused",
                        message="This request ID was already used for another mutation.",
                    )
                replay_snapshot = await dependencies.routedeck.store.load(session_id)
                require_compatible_session(
                    dependencies.routedeck.app,
                    replay_snapshot.state,
                )
                return StreamingResponse(
                    iter(
                        _chat_replay_frames(
                            recorded,
                            replay_snapshot,
                        )
                    ),
                    media_type="text/event-stream",
                    headers=_chat_stream_headers(),
                )
            snapshot = await dependencies.routedeck.store.load(session_id)
            require_compatible_session(
                dependencies.routedeck.app,
                snapshot.state,
            )
            if snapshot.session_version != body.expected_session_version:
                return _problem_response(
                    409,
                    code="version_conflict",
                    message="The session changed before this chat turn began.",
                )
        except _ChatStreamFailure as error:
            return _problem_response(
                500,
                code=error.code,
                message=error.public_message,
            )
        except RouteDeckDependencyUnavailable:
            return _problem_response(
                503,
                code="dependency_unavailable",
                message="The Medusa buyer agent is unavailable.",
            )
        except SessionStoreError as error:
            status = (
                404
                if error.code is SessionStoreErrorCode.SESSION_NOT_FOUND
                else (
                    410 if error.code is SessionStoreErrorCode.SESSION_EXPIRED else 409
                )
            )
            return _problem_response(
                status,
                code=error.code.value,
                message="The RouteDeck session could not be loaded.",
            )

        return StreamingResponse(
            stream_agent_chat(
                dependencies=dependencies,
                session_id=session_id,
                request=body,
                initial_snapshot=snapshot,
            ),
            media_type="text/event-stream",
            headers=_chat_stream_headers(),
        )

    return router


async def stream_agent_chat(
    *,
    dependencies: MedusaChatDependencies,
    session_id: str,
    request: ChatStreamRequest,
    initial_snapshot: SessionSnapshot | None = None,
) -> AsyncIterator[str]:
    """Run one durable parent turn and emit only product chat SSE frames."""

    runner = dependencies.routedeck.runner
    snapshot = initial_snapshot or await dependencies.routedeck.store.load(session_id)
    turn: TurnLease | None = None
    turn_active = False
    finalized = False
    user_turn = FinalizedConversationTurn(
        turn_id=runner.id_factory("turn"),
        role=ConversationRole.USER,
        content=request.message,
        request_id=request.request_id,
    )
    try:
        turn = await runner.begin_turn(
            TurnClaim(
                session_id=session_id,
                expected_session_version=request.expected_session_version,
                request_id=request.request_id,
                request_fingerprint=_chat_fingerprint(request),
                owner_kind=TurnOwnerKind.CHAT,
            )
        )
        turn_active = True
        yield _sse(
            "stream_start",
            {
                "request_id": request.request_id,
                "session_version": snapshot.session_version,
            },
        )
        yield _sse(
            "conversation_snapshot",
            {"turns": public_conversation(snapshot)},
        )
        yield _sse(
            "user_message",
            {
                "content": request.message,
                "request_id": request.request_id,
                "turn_id": user_turn.turn_id,
            },
        )

        invocation_context: RouteDeckInvocationContext = {
            "session_id": session_id,
            "request_id_prefix": request.request_id,
            "turn": turn,
            "review_turns": (user_turn,),
        }
        final_messages: tuple[BaseMessage, ...] | None = None
        model_chunks: dict[str, list[str]] = {}
        completed_model_runs: list[_CompletedModelRun] = []
        event_stream = dependencies.agent.astream_events(
            {"messages": [HumanMessage(content=request.message, id=user_turn.turn_id)]},
            version="v2",
            context=invocation_context,
        )
        async for event in event_stream:
            event_name = event.get("event")
            data = event.get("data")
            if not isinstance(data, Mapping):
                data = {}

            if event_name == "on_chat_model_end":
                output = data.get("output")
                if isinstance(output, AIMessage) and len(output.tool_calls) > 1:
                    raise _ChatStreamFailure(
                        "parallel_tool_calls_rejected",
                        "The buyer agent attempted parallel tool calls.",
                    )
                if isinstance(output, AIMessage):
                    run_id = _model_run_id(event)
                    completed_model_runs.append(
                        _CompletedModelRun(
                            output=output,
                            chunks=tuple(model_chunks.pop(run_id, ())),
                        )
                    )

            if event_name == "on_chat_model_stream":
                chunk_text = _message_text(data.get("chunk"))
                if chunk_text:
                    model_chunks.setdefault(_model_run_id(event), []).append(chunk_text)

            event_output = data.get("output")
            candidate = _messages_from_output(event_output)
            review = _review_event(event_output)
            if review is None and candidate is not None:
                review = next(
                    (
                        payload
                        for message in candidate
                        if (payload := _review_event(message)) is not None
                    ),
                    None,
                )
            if review is not None:
                turn_active = False
                await _close_event_stream(event_stream)
                yield _sse("review_required", review)
                yield _sse(
                    "stream_end",
                    {
                        "request_id": request.request_id,
                        "status": "requires_review",
                    },
                )
                return

            if event_name == "on_chain_end" and candidate is not None:
                final_messages = candidate

        if final_messages is None:
            raise _ChatStreamFailure(
                "agent_result_missing",
                "The buyer agent did not return a final response.",
            )

        review = next(
            (
                payload
                for message in final_messages
                if (payload := _review_event(message)) is not None
            ),
            None,
        )
        if review is not None:
            turn_active = False
            yield _sse("review_required", review)
            yield _sse(
                "stream_end",
                {"request_id": request.request_id, "status": "requires_review"},
            )
            return

        assistant_message = _final_assistant_message(final_messages)
        assistant_text = (
            _message_text(assistant_message) if assistant_message is not None else ""
        )
        if assistant_message is None or not assistant_text:
            raise _ChatStreamFailure(
                "assistant_response_empty",
                "The buyer agent returned an empty response.",
            )
        extracted = extract_conversation_turns(
            final_messages,
            current_user_turn=user_turn,
            id_factory=runner.id_factory,
        )
        if (
            not extracted.turns
            or extracted.turns[-1].role is not ConversationRole.ASSISTANT
            or extracted.turns[-1].content != assistant_text
        ):
            raise _ChatStreamFailure(
                "agent_history_invalid",
                "The buyer agent returned invalid conversation history.",
            )
        assistant_turn = extracted.turns[-1]
        current = await dependencies.routedeck.store.load(session_id)
        completed = await runner.complete_turn(
            turn,
            expected_session_version=current.session_version,
            turns=extracted.turns,
        )
        finalized = True
        turn_active = False
        for chunk in _final_assistant_chunks(assistant_message, completed_model_runs):
            yield _sse(
                "assistant_delta",
                {
                    "content": chunk,
                    "request_id": request.request_id,
                },
            )
        yield _sse(
            "assistant_end",
            {
                "request_id": request.request_id,
                "session_version": completed.session_version,
                "projection_version": completed.projection_version,
                "turn_id": assistant_turn.turn_id,
            },
        )
        yield _sse(
            "stream_end",
            {"request_id": request.request_id, "status": "completed"},
        )
    except asyncio.CancelledError:
        if turn is not None and turn_active and not finalized:
            await asyncio.shield(
                _interrupt_turn(
                    dependencies=dependencies,
                    turn=turn,
                    request_id=request.request_id,
                )
            )
        raise
    except Exception as error:
        interruption_persistence_failed = False
        if turn is not None and turn_active and not finalized:
            try:
                await _interrupt_turn(
                    dependencies=dependencies,
                    turn=turn,
                    request_id=request.request_id,
                )
            except Exception as interrupt_error:
                _log_chat_failure(
                    "medusa_chat_interrupt_failed",
                    request_id=request.request_id,
                    error=interrupt_error,
                )
                interruption_persistence_failed = True
        _log_chat_failure(
            "medusa_chat_stream_failed",
            request_id=request.request_id,
            error=error,
        )
        if interruption_persistence_failed:
            yield _sse(
                "stream_end",
                {"request_id": request.request_id, "status": "outcome_unknown"},
            )
            return
        code = error.code if isinstance(error, _ChatStreamFailure) else "agent_error"
        message = (
            error.public_message
            if isinstance(error, _ChatStreamFailure)
            else "The buyer agent could not complete this turn."
        )
        yield _sse("chat_error", {"code": code, "message": message})
        yield _sse(
            "stream_end",
            {"request_id": request.request_id, "status": "turn_interrupted"},
        )


async def _interrupt_turn(
    *,
    dependencies: MedusaChatDependencies,
    turn: TurnLease,
    request_id: str,
) -> None:
    current = await dependencies.routedeck.store.load(turn.session_id)
    await dependencies.routedeck.runner.interrupt_turn(
        turn,
        expected_session_version=current.session_version,
        failure=RouteDeckFailure(
            kind=FailureKind.INTERNAL,
            code="turn_interrupted",
            phase="agent_stream",
            correlation_id=secrets.token_urlsafe(12),
            request_id=request_id,
            public_message="The buyer-agent turn was interrupted.",
        ),
    )


def _final_assistant_message(messages: Sequence[BaseMessage]) -> AIMessage | None:
    for message in reversed(messages):
        if isinstance(message, AIMessage) and not message.tool_calls:
            return message
    return None


def _final_assistant_chunks(
    assistant: AIMessage,
    completed_runs: Sequence[_CompletedModelRun],
) -> tuple[str, ...]:
    assistant_text = _message_text(assistant)
    for run in completed_runs:
        if run.output.tool_calls or _message_text(run.output) != assistant_text:
            continue
        if run.chunks and "".join(run.chunks) == assistant_text:
            return run.chunks
    return (assistant_text,)


def _model_run_id(event: Mapping[str, Any]) -> str:
    run_id = event.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise _ChatStreamFailure(
            "agent_stream_contract_invalid",
            "The buyer agent returned an invalid streaming event.",
        )
    return run_id


def _message_text(message: object) -> str:
    if isinstance(message, BaseMessage):
        return message.text
    return ""


def _messages_from_output(output: object) -> tuple[BaseMessage, ...] | None:
    if not isinstance(output, Mapping):
        return None
    messages = output.get("messages")
    if not isinstance(messages, (list, tuple)) or any(
        not isinstance(message, BaseMessage) for message in messages
    ):
        return None
    return tuple(messages)


def _review_event(value: object) -> dict[str, Any] | None:
    if not isinstance(value, ToolMessage) or not isinstance(value.artifact, Mapping):
        return None
    if value.artifact.get("disposition") != "requires_review":
        return None
    review = value.artifact.get("review")
    operation_id = value.artifact.get("operation_id")
    if not isinstance(review, Mapping) or not isinstance(operation_id, str):
        raise _ChatStreamFailure(
            "review_result_invalid",
            "The buyer agent returned an invalid review result.",
        )
    review_id = review.get("id")
    expires_at = review.get("expires_at")
    if not isinstance(review_id, str) or not isinstance(expires_at, str):
        raise _ChatStreamFailure(
            "review_result_invalid",
            "The buyer agent returned an invalid review result.",
        )
    return {
        "expires_at": expires_at,
        "operation_id": operation_id,
        "review_id": review_id,
        "status": "requires_review",
    }


def _chat_fingerprint(request: ChatStreamRequest) -> str:
    canonical = json.dumps(
        {"message": request.message},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _chat_replay_frames(
    record: MutationRecord,
    snapshot: SessionSnapshot,
) -> tuple[str, ...]:
    start = _sse(
        "stream_start",
        {
            "request_id": record.request_id,
            "session_version": snapshot.session_version,
        },
    )
    history = _sse(
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
            raise _ChatStreamFailure(
                "chat_replay_invalid",
                "The saved buyer-agent turn could not be replayed.",
            )
        return (
            start,
            history,
            _sse(
                "assistant_end",
                {
                    "request_id": record.request_id,
                    "session_version": snapshot.session_version,
                    "projection_version": snapshot.projection_version,
                    "turn_id": assistant.turn_id,
                },
            ),
            _sse(
                "stream_end",
                {"request_id": record.request_id, "status": "completed"},
            ),
        )
    result = record.result.to_dict()
    if record.status is MutationStatus.REQUIRES_REVIEW:
        if set(result) != {"expires_at", "operation_id", "review_id"} or any(
            not isinstance(value, str) or not value for value in result.values()
        ):
            raise _ChatStreamFailure(
                "chat_replay_invalid",
                "The saved buyer-agent turn could not be replayed.",
            )
        return (
            start,
            history,
            _sse("review_required", {**result, "status": "requires_review"}),
            _sse(
                "stream_end",
                {"request_id": record.request_id, "status": "requires_review"},
            ),
        )
    if record.status is MutationStatus.TURN_INTERRUPTED:
        if set(result) != {"code", "message"} or any(
            not isinstance(value, str) or not value for value in result.values()
        ):
            raise _ChatStreamFailure(
                "chat_replay_invalid",
                "The saved buyer-agent turn could not be replayed.",
            )
        return (
            start,
            history,
            _sse("chat_error", result),
            _sse(
                "stream_end",
                {"request_id": record.request_id, "status": "turn_interrupted"},
            ),
        )
    raise _ChatStreamFailure(
        "chat_replay_invalid",
        "The saved buyer-agent turn could not be replayed.",
    )


def _chat_stream_headers() -> dict[str, str]:
    return {
        "Cache-Control": "private, no-store, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }


def _log_chat_failure(
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


def _guest_session_id(request: Request, dependencies: RouteDeckDependencies) -> str:
    session_id = request.cookies.get(dependencies.cookie.name)
    if not session_id:
        raise SessionStoreError(SessionStoreErrorCode.SESSION_NOT_FOUND)
    if len(session_id) > 512:
        raise SessionStoreError(SessionStoreErrorCode.SESSION_NOT_FOUND)
    return session_id


async def _resolve_dependencies(
    provider: ChatDependencyProvider,
    request: Request,
) -> MedusaChatDependencies:
    value = provider(request)
    if inspect.isawaitable(value):
        value = await value
    if not isinstance(value, MedusaChatDependencies):
        raise RouteDeckDependencyUnavailable("Medusa chat is not configured")
    return value


async def _close_event_stream(stream: object) -> None:
    close = getattr(stream, "aclose", None)
    if close is not None and callable(close):
        await close()


def _sse(event: str, data: Mapping[str, Any]) -> str:
    payload = json.dumps(
        dict(data),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return f"event: {event}\ndata: {payload}\n\n"


def _problem_response(status: int, *, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"failure": {"code": code, "message": message}},
        headers={"Cache-Control": "no-store"},
    )


__all__ = [
    "AgentEventStream",
    "ChatStreamRequest",
    "MedusaChatDependencies",
    "create_medusa_chat_router",
    "stream_agent_chat",
]
