from __future__ import annotations

import asyncio
import secrets
from collections.abc import AsyncIterator, Mapping

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from routedeck_core.contracts.conversation import (
    ConversationRole,
    FinalizedConversationTurn,
)
from routedeck_core.contracts.failures import FailureKind, RouteDeckFailure
from routedeck_core.contracts.mutations import MutationKind
from routedeck_core.contracts.session import SessionSnapshot
from routedeck_core.ports import SessionStoreError, SessionStoreErrorCode
from routedeck_core.state.leases import TurnClaim, TurnLease, TurnOwnerKind
from routedeck_core.state.session import require_compatible_session
from routedeck_fastapi import RouteDeckDependencyUnavailable
from routedeck_langgraph import (
    RouteDeckInvocationContext,
    extract_conversation_turns,
)

from ..turn_policy import TURN_POLICY_EVENT_TAG

from .chat_contract import (
    AgentEventStream,
    ChatDependencyProvider,
    ChatStreamRequest,
    MedusaChatDependencies,
)
from .chat_events import (
    ChatStreamFailure as _ChatStreamFailure,
    CompletedModelRun as _CompletedModelRun,
    close_event_stream as _close_event_stream,
    final_assistant_message as _final_assistant_message,
    final_assistant_was_streamed as _final_assistant_was_streamed,
    log_chat_failure as _log_chat_failure,
    message_text as _message_text,
    messages_from_output as _messages_from_output,
    model_run_id as _model_run_id,
    review_event as _review_event,
    sse as _sse,
)
from .chat_replay import (
    chat_fingerprint as _chat_fingerprint,
    chat_replay_frames as _chat_replay_frames,
    chat_stream_headers as _chat_stream_headers,
    guest_session_id as _guest_session_id,
    problem_response as _problem_response,
    resolve_dependencies as _resolve_dependencies,
)
from .conversation import public_conversation


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
    snapshot = (
        initial_snapshot
        if initial_snapshot is not None
        else await dependencies.routedeck.store.load(session_id)
    )
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
        exposed_model_runs: set[str] = set()
        tool_calling_model_runs: set[str] = set()
        completed_model_runs: list[_CompletedModelRun] = []
        event_stream = dependencies.agent.astream_events(
            {"messages": [HumanMessage(content=request.message, id=user_turn.turn_id)]},
            version="v2",
            context=invocation_context,
        )
        async for event in event_stream:
            if _is_internal_turn_policy_event(event):
                continue
            event_name = event.get("event")
            data = event.get("data")
            if not isinstance(data, Mapping):
                raise _ChatStreamFailure(
                    "agent_stream_contract_invalid",
                    "The buyer agent returned an invalid streaming event.",
                )

            if event_name == "on_chat_model_end":
                output = data.get("output")
                if isinstance(output, AIMessage) and len(output.tool_calls) > 1:
                    raise _ChatStreamFailure(
                        "parallel_tool_calls_rejected",
                        "The buyer agent attempted parallel tool calls.",
                    )
                if isinstance(output, AIMessage):
                    run_id = _model_run_id(event)
                    if output.tool_calls and run_id in exposed_model_runs:
                        exposed_model_runs.remove(run_id)
                        yield _sse(
                            "assistant_reset",
                            {"request_id": request.request_id},
                        )
                    completed_model_runs.append(
                        _CompletedModelRun(
                            output=output,
                            chunks=tuple(model_chunks.pop(run_id, ())),
                        )
                    )

            if event_name == "on_chat_model_stream":
                chunk = data.get("chunk")
                run_id = _model_run_id(event)
                if getattr(chunk, "tool_call_chunks", ()):
                    tool_calling_model_runs.add(run_id)
                    if run_id in exposed_model_runs:
                        exposed_model_runs.remove(run_id)
                        yield _sse(
                            "assistant_reset",
                            {"request_id": request.request_id},
                        )
                chunk_text = _message_text(chunk)
                if chunk_text:
                    model_chunks.setdefault(run_id, []).append(chunk_text)
                    if run_id not in tool_calling_model_runs:
                        exposed_model_runs.add(run_id)
                        yield _sse(
                            "assistant_delta",
                            {
                                "content": chunk_text,
                                "request_id": request.request_id,
                            },
                        )

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
        if not _final_assistant_was_streamed(
            assistant_message,
            completed_model_runs,
        ):
            raise _ChatStreamFailure(
                "assistant_stream_missing",
                "The buyer agent did not stream its final response.",
            )
        current = await dependencies.routedeck.store.load(session_id)
        completed = await runner.complete_turn(
            turn,
            expected_session_version=current.session_version,
            turns=extracted.turns,
        )
        finalized = True
        turn_active = False
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


def _is_internal_turn_policy_event(event: Mapping[str, object]) -> bool:
    tags = event.get("tags")
    return isinstance(tags, (list, tuple)) and TURN_POLICY_EVENT_TAG in tags


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


__all__ = [
    "AgentEventStream",
    "ChatStreamRequest",
    "MedusaChatDependencies",
    "create_medusa_chat_router",
    "stream_agent_chat",
]
