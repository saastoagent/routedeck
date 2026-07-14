from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from routedeck_core.contracts.conversation import (
    ConversationRole,
    ConversationTurnStatus,
)
from routedeck_core.contracts.session import SessionSnapshot
from routedeck_core.ports import SessionStoreError, SessionStoreErrorCode
from routedeck_core.state.session import require_current_session
from routedeck_core.validation import RouteDeckValidationError
from routedeck_fastapi import RouteDeckDependencies, RouteDeckDependencyUnavailable


class PublicConversationTurn(BaseModel):
    """The existing buyer-visible conversation turn contract."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    turn_id: str
    request_id: str | None
    role: Literal["user", "assistant"]
    content: str


ConversationDependencyProvider = Callable[
    [Request],
    RouteDeckDependencies | Awaitable[RouteDeckDependencies],
]


def create_medusa_conversation_router(
    provider: ConversationDependencyProvider,
) -> APIRouter:
    """Expose a read-only public projection of RouteDeck-owned conversation state."""

    router = APIRouter(prefix="/api/medusa-agent", tags=["medusa-agent-conversation"])

    @router.get("/conversation")
    async def get_conversation(request: Request):
        try:
            dependencies = await _resolve_dependencies(provider, request)
            session_id = _guest_session_id(request, dependencies)
            snapshot = await dependencies.store.load(session_id)
            require_current_session(dependencies.app, snapshot.state)
            return JSONResponse(
                content={"turns": public_conversation(snapshot)},
                headers={"Cache-Control": "private, no-store"},
            )
        except RouteDeckDependencyUnavailable:
            return _problem_response(
                503,
                code="dependency_unavailable",
                message="The Medusa buyer conversation is unavailable.",
            )
        except SessionStoreError as error:
            status = {
                SessionStoreErrorCode.SESSION_NOT_FOUND: 404,
                SessionStoreErrorCode.SESSION_EXPIRED: 410,
            }.get(error.code, 409)
            return _problem_response(
                status,
                code=error.code.value,
                message="The RouteDeck session could not be loaded.",
            )
        except RouteDeckValidationError:
            return _problem_response(
                409,
                code="session_upgrade_required",
                message="This buyer session requires an application upgrade.",
            )
        except Exception:
            return _problem_response(
                500,
                code="conversation_projection_failed",
                message="The buyer conversation could not be restored.",
            )

    return router


def public_conversation(snapshot: SessionSnapshot) -> list[dict[str, object]]:
    """Project only finalized buyer-visible turns from canonical RouteDeck state."""

    return [
        PublicConversationTurn(
            turn_id=turn.turn_id,
            request_id=turn.request_id,
            role=("user" if turn.role is ConversationRole.USER else "assistant"),
            content=turn.content,
        ).model_dump(mode="json")
        for turn in snapshot.state.conversation
        if turn.status is ConversationTurnStatus.FINALIZED
        and turn.role in {ConversationRole.USER, ConversationRole.ASSISTANT}
    ]


def _guest_session_id(
    request: Request,
    dependencies: RouteDeckDependencies,
) -> str:
    session_id = request.cookies.get(dependencies.cookie.name)
    if not session_id or len(session_id) > 512:
        raise SessionStoreError(SessionStoreErrorCode.SESSION_NOT_FOUND)
    return session_id


async def _resolve_dependencies(
    provider: ConversationDependencyProvider,
    request: Request,
) -> RouteDeckDependencies:
    value = provider(request)
    if inspect.isawaitable(value):
        value = await value
    if not isinstance(value, RouteDeckDependencies):
        raise RouteDeckDependencyUnavailable("RouteDeck runtime is not configured")
    return value


def _problem_response(status: int, *, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"failure": {"code": code, "message": message}},
        headers={"Cache-Control": "private, no-store"},
    )


__all__ = [
    "PublicConversationTurn",
    "create_medusa_conversation_router",
    "public_conversation",
]
