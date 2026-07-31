from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from routedeck_core.contracts.conversation import (
    ConversationRole,
    FinalizedConversationTurn,
)
from routedeck_core.contracts.failures import FailureKind
from routedeck_core.ports import (
    AssistantInitiatedTrigger,
    RouteDeckConversationTrigger,
    UserMessageTrigger,
)
from routedeck_core.state.session import require_current_session

from ..contracts import (
    AssistantTurnRequest,
    ChatStreamRequest,
    ConversationRunStartRequest,
    RouteDeckHttpProblem,
)
from ..conversation_projection import public_conversation, public_conversation_envelope
from ..conversation_replay import (
    conversation_stream_headers,
    sse,
)
from ..conversation_runs import (
    ConversationRunNotFound,
    encode_run_event,
    public_conversation_run_envelope,
    require_conversation_runs,
)
from ..dependencies import RouteDeckDependencies, RouteDeckDependencyUnavailable
from ..inspection import event_cursor
from ..responses import exception_response, transport_failure
from ..security import RouteDeckMutationPolicy
from ..session_http import selected_session_id, resolve_dependencies, validated_body
from . import DependencyProvider


def create_conversation_routes(
    provider: DependencyProvider,
    mutation_policy: RouteDeckMutationPolicy,
) -> APIRouter:
    router = APIRouter()

    @router.get("/conversation")
    async def get_conversation(request: Request):
        try:
            dependencies = await resolve_dependencies(provider, request)
            session_id = await selected_session_id(
                request,
                dependencies.session_selector,
            )
            snapshot = await dependencies.store.load(session_id)
            require_current_session(dependencies.app, snapshot.state)
            return JSONResponse(
                content=public_conversation_envelope(snapshot),
                headers={"Cache-Control": "private, no-store"},
            )
        except Exception as error:
            return exception_response(error)

    @router.post("/chat")
    async def chat(request: Request):
        try:
            dependencies = await resolve_dependencies(provider, request)
            _require_agent_driver(dependencies)
            body = await validated_body(
                request,
                ChatStreamRequest,
                mutation_policy,
            )
            trigger = UserMessageTrigger(
                message=body.message,
                user_turn=FinalizedConversationTurn(
                    turn_id=dependencies.runner.id_factory("turn"),
                    role=ConversationRole.USER,
                    content=body.message,
                    request_id=body.request_id,
                ),
            )
            return await _conversation_turn_response(
                dependencies=dependencies,
                request=request,
                request_id=body.request_id,
                expected_session_version=body.expected_session_version,
                trigger=trigger,
            )
        except Exception as error:
            return exception_response(error)

    @router.post("/conversation/assistant-turn")
    async def assistant_turn(request: Request):
        try:
            dependencies = await resolve_dependencies(provider, request)
            _require_agent_driver(dependencies)
            body = await validated_body(
                request,
                AssistantTurnRequest,
                mutation_policy,
            )
            return await _conversation_turn_response(
                dependencies=dependencies,
                request=request,
                request_id=body.request_id,
                expected_session_version=body.expected_session_version,
                trigger=AssistantInitiatedTrigger(),
            )
        except Exception as error:
            return exception_response(error)

    @router.post("/conversation/runs")
    async def start_conversation_run(request: Request):
        try:
            dependencies = await resolve_dependencies(provider, request)
            body = await validated_body(
                request,
                ConversationRunStartRequest,
                mutation_policy,
            )
            session_id = await selected_session_id(
                request,
                dependencies.session_selector,
            )
            trigger: RouteDeckConversationTrigger
            if body.trigger == "user_message":
                assert body.message is not None
                trigger = UserMessageTrigger(
                    message=body.message,
                    user_turn=FinalizedConversationTurn(
                        turn_id=dependencies.runner.id_factory("turn"),
                        role=ConversationRole.USER,
                        content=body.message,
                        request_id=body.request_id,
                    ),
                )
            else:
                trigger = AssistantInitiatedTrigger()
            run = await require_conversation_runs(dependencies).start_or_attach(
                session_id=session_id,
                request_id=body.request_id,
                expected_session_version=body.expected_session_version,
                trigger=trigger,
            )
            return JSONResponse(
                status_code=200 if run.terminal else 202,
                content=public_conversation_run_envelope(run),
                headers={"Cache-Control": "private, no-store"},
            )
        except ConversationRunNotFound:
            return _run_not_found_response()
        except Exception as error:
            return exception_response(error)

    @router.get("/conversation/runs/{request_id}")
    async def get_conversation_run(request_id: str, request: Request):
        try:
            dependencies = await resolve_dependencies(provider, request)
            session_id = await selected_session_id(
                request,
                dependencies.session_selector,
            )
            run = await require_conversation_runs(dependencies).get(
                session_id, request_id
            )
            return JSONResponse(
                content=public_conversation_run_envelope(run),
                headers={"Cache-Control": "private, no-store"},
            )
        except ConversationRunNotFound:
            return _run_not_found_response()
        except Exception as error:
            return exception_response(error)

    @router.get("/conversation/runs/{request_id}/events")
    async def get_conversation_run_events(request_id: str, request: Request):
        try:
            dependencies = await resolve_dependencies(provider, request)
            session_id = await selected_session_id(
                request,
                dependencies.session_selector,
            )
            after = event_cursor(request)
            coordinator = require_conversation_runs(dependencies)
            run = await coordinator.get(session_id, request_id)
            if after > run.cursor:
                return _conversation_conflict_response(
                    code="conversation_run_cursor_invalid",
                    public_message=(
                        "The conversation run cursor is ahead of the server."
                    ),
                )
            return StreamingResponse(
                _run_event_stream(
                    coordinator.events(
                        session_id,
                        request_id,
                        after,
                        dependencies.sse.heartbeat_interval.total_seconds(),
                    )
                ),
                media_type="text/event-stream",
                headers=conversation_stream_headers(),
            )
        except Exception as error:
            return exception_response(error)

    return router


async def _run_event_stream(events):
    async for event in events:
        yield b": heartbeat\n\n" if event is None else encode_run_event(event)


async def _conversation_turn_response(
    *,
    dependencies: RouteDeckDependencies,
    request: Request,
    request_id: str,
    expected_session_version: int,
    trigger: RouteDeckConversationTrigger,
):
    session_id = await selected_session_id(
        request,
        dependencies.session_selector,
    )
    snapshot = await dependencies.store.load(session_id)
    require_current_session(dependencies.app, snapshot.state)
    run = await require_conversation_runs(dependencies).start_or_attach(
        session_id=session_id,
        request_id=request_id,
        expected_session_version=expected_session_version,
        trigger=trigger,
    )
    return StreamingResponse(
        _legacy_run_stream(
            dependencies=dependencies,
            session_id=session_id,
            initial_snapshot=snapshot,
            run=run,
        ),
        media_type="text/event-stream",
        headers=conversation_stream_headers(),
    )


async def _legacy_run_stream(*, dependencies, session_id, initial_snapshot, run):
    yield sse(
        "stream_start",
        {"request_id": run.request_id, "session_version": initial_snapshot.session_version},
    )
    yield sse("conversation_snapshot", {"turns": public_conversation(initial_snapshot)})
    if run.user_message is not None and run.user_turn_id is not None:
        yield sse("user_message", {
            "content": run.user_message,
            "request_id": run.request_id,
            "turn_id": run.user_turn_id,
        })
    previous = ""
    if run.assistant_content:
        yield sse("assistant_delta", {
            "content": run.assistant_content,
            "request_id": run.request_id,
        })
        previous = run.assistant_content
    current = run
    if not current.terminal:
        async for event in require_conversation_runs(dependencies).events(
            session_id,
            run.request_id,
            run.cursor,
            dependencies.sse.heartbeat_interval.total_seconds(),
        ):
            if event is None:
                continue
            if event.assistant_content != previous:
                if event.assistant_content.startswith(previous):
                    delta = event.assistant_content[len(previous):]
                    if delta:
                        yield sse("assistant_delta", {
                            "content": delta,
                            "request_id": run.request_id,
                        })
                else:
                    yield sse("assistant_reset", {"request_id": run.request_id})
                    if event.assistant_content:
                        yield sse("assistant_delta", {
                            "content": event.assistant_content,
                            "request_id": run.request_id,
                        })
                previous = event.assistant_content
            current = event
    if current.stage.value == "interrupted":
        failure = current.failure
        yield sse("chat_error", {
            "code": failure.code if failure is not None else "turn_interrupted",
            "message": failure.message if failure is not None else "The agent turn was interrupted.",
        })
        yield sse("stream_end", {
            "request_id": run.request_id,
            "status": "turn_interrupted",
        })
        return
    if current.review is not None:
        yield sse("review_required", {
            "status": "requires_review",
            "operation_id": current.review.operation_id,
            "review_id": current.review.review_id,
            "expires_at": current.review.expires_at,
        })
        yield sse("stream_end", {
            "request_id": run.request_id,
            "status": "requires_review",
        })
        return
    if current.session_version is None or current.projection_version is None or current.turn_id is None:
        raise RuntimeError("completed conversation run lacks durable completion")
    yield sse("assistant_end", {
        "request_id": run.request_id,
        "session_version": current.session_version,
        "projection_version": current.projection_version,
        "turn_id": current.turn_id,
    })
    yield sse("stream_end", {"request_id": run.request_id, "status": "completed"})


def _run_not_found_response():
    return exception_response(RouteDeckHttpProblem(
        404,
        "conversation_run_not_found",
        "That conversation run is unavailable.",
        phase="conversation_run",
    ))


def _require_agent_driver(dependencies: RouteDeckDependencies) -> None:
    if dependencies.agent_driver is None:
        raise RouteDeckDependencyUnavailable(
            "RouteDeck conversation agent is not configured"
        )


def _conversation_conflict_response(
    *,
    code: str,
    public_message: str,
) -> JSONResponse:
    failure = transport_failure(
        kind=FailureKind.STATE_CONFLICT,
        code=code,
        phase="conversation_turn",
        public_message=public_message,
    )
    return JSONResponse(
        status_code=409,
        content={"failure": failure.model_dump(mode="json")},
        headers={"Cache-Control": "private, no-store"},
    )


__all__ = ["create_conversation_routes"]
