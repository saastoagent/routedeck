from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from routedeck_core.contracts.conversation import (
    ConversationRole,
    FinalizedConversationTurn,
)
from routedeck_core.contracts.failures import FailureKind
from routedeck_core.contracts.mutations import MutationKind
from routedeck_core.ports import (
    AssistantInitiatedTrigger,
    RouteDeckConversationTrigger,
    UserMessageTrigger,
)
from routedeck_core.state.session import require_current_session

from ..contracts import AssistantTurnRequest, ChatStreamRequest
from ..conversation_projection import public_conversation
from ..conversation_replay import (
    conversation_fingerprint,
    conversation_replay_frames,
    conversation_stream_headers,
)
from ..conversation_stream import ConversationTurnRequest, stream_agent_turn
from ..dependencies import RouteDeckDependencies, RouteDeckDependencyUnavailable
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
                content={"turns": public_conversation(snapshot)},
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

    return router


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
    fingerprint = conversation_fingerprint(trigger)
    recorded = await dependencies.store.find_mutation(session_id, request_id)
    if recorded is not None:
        if (
            recorded.kind is not MutationKind.CHAT
            or recorded.request_fingerprint != fingerprint
        ):
            return _conversation_conflict_response(
                code="request_id_reused",
                public_message="This request ID was already used for another mutation.",
            )
        replay_snapshot = await dependencies.store.load(session_id)
        require_current_session(dependencies.app, replay_snapshot.state)
        return StreamingResponse(
            iter(conversation_replay_frames(recorded, replay_snapshot)),
            media_type="text/event-stream",
            headers=conversation_stream_headers(),
        )
    snapshot = await dependencies.store.load(session_id)
    require_current_session(dependencies.app, snapshot.state)
    if snapshot.session_version != expected_session_version:
        return _conversation_conflict_response(
            code="version_conflict",
            public_message="The session changed before this conversation turn began.",
        )
    return StreamingResponse(
        stream_agent_turn(
            dependencies=dependencies,
            session_id=session_id,
            request=ConversationTurnRequest(
                request_id=request_id,
                expected_session_version=expected_session_version,
                trigger=trigger,
            ),
            initial_snapshot=snapshot,
        ),
        media_type="text/event-stream",
        headers=conversation_stream_headers(),
    )


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
