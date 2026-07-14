from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from routedeck_core.contracts.mutations import MutationKind
from routedeck_core.state.session import require_current_session

from .contracts import ChatStreamRequest
from .conversation_dependencies import (
    ConversationDependencyProvider,
    RouteDeckConversationDependencies,
    resolve_conversation_dependencies,
)
from .conversation_projection import PublicConversationTurn, public_conversation
from .conversation_replay import (
    chat_fingerprint,
    chat_replay_frames,
    chat_stream_headers,
)
from .conversation_stream import stream_agent_chat
from .dependencies import RouteDeckDependencyUnavailable
from .responses import exception_response
from .security import RouteDeckMutationPolicy, SameOriginMutationPolicy
from .session_http import guest_session_id, validated_body


def create_routedeck_conversation_router(
    provider: ConversationDependencyProvider,
    *,
    mutation_policy: RouteDeckMutationPolicy | None = None,
) -> APIRouter:
    """Mount RouteDeck-owned conversation projection and turn streaming."""

    router = APIRouter(prefix="/api/routedeck", tags=["routedeck-conversation"])
    request_policy = mutation_policy or SameOriginMutationPolicy()

    @router.get("/conversation")
    async def get_conversation(request: Request):
        try:
            dependencies = await resolve_conversation_dependencies(provider, request)
            session_id = guest_session_id(request, dependencies.routedeck.cookie)
            snapshot = await dependencies.routedeck.store.load(session_id)
            require_current_session(dependencies.routedeck.app, snapshot.state)
            return JSONResponse(
                content={"turns": public_conversation(snapshot)},
                headers={"Cache-Control": "private, no-store"},
            )
        except Exception as error:
            return exception_response(error)

    @router.post("/chat")
    async def chat(request: Request):
        try:
            dependencies = await resolve_conversation_dependencies(provider, request)
            if dependencies.agent is None:
                raise RouteDeckDependencyUnavailable(
                    "RouteDeck conversation agent is not configured"
                )
            body = await validated_body(request, ChatStreamRequest, request_policy)
            routedeck = dependencies.routedeck
            session_id = guest_session_id(request, routedeck.cookie)
            fingerprint = chat_fingerprint(body)
            recorded = await routedeck.store.find_mutation(
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
                replay_snapshot = await routedeck.store.load(session_id)
                require_current_session(routedeck.app, replay_snapshot.state)
                return StreamingResponse(
                    iter(chat_replay_frames(recorded, replay_snapshot)),
                    media_type="text/event-stream",
                    headers=chat_stream_headers(),
                )
            snapshot = await routedeck.store.load(session_id)
            require_current_session(routedeck.app, snapshot.state)
            if snapshot.session_version != body.expected_session_version:
                return _problem_response(
                    409,
                    code="version_conflict",
                    message="The session changed before this chat turn began.",
                )
        except Exception as error:
            return exception_response(error)

        return StreamingResponse(
            stream_agent_chat(
                dependencies=dependencies,
                session_id=session_id,
                request=body,
                initial_snapshot=snapshot,
            ),
            media_type="text/event-stream",
            headers=chat_stream_headers(),
        )

    return router


def _problem_response(status: int, *, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"failure": {"code": code, "message": message}},
        headers={"Cache-Control": "private, no-store"},
    )


__all__ = [
    "ChatStreamRequest",
    "ConversationDependencyProvider",
    "PublicConversationTurn",
    "RouteDeckConversationDependencies",
    "create_routedeck_conversation_router",
    "public_conversation",
    "stream_agent_chat",
]
