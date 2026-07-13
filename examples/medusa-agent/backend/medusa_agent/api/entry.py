from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from routedeck_core.ports import SessionStoreError, SessionStoreErrorCode
from routedeck_fastapi import RouteDeckDependencies, RouteDeckDependencyUnavailable

from ..entry_conversation import (
    BuyerEntryAgent,
    EntryConversationError,
    start_home_conversation,
)
from .conversation import public_conversation


class _EntryRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StartBuyerConversationRequest(_EntryRequestModel):
    request_id: str = Field(min_length=1, max_length=256)
    expected_session_version: int = Field(ge=0)


@dataclass(frozen=True)
class MedusaEntryDependencies:
    routedeck: RouteDeckDependencies
    agent: BuyerEntryAgent


EntryDependencyProvider = Callable[
    [Request], MedusaEntryDependencies | Awaitable[MedusaEntryDependencies]
]


def create_medusa_entry_router(provider: EntryDependencyProvider) -> APIRouter:
    """Begin a durable buyer.home conversation through the agent system prompt."""

    router = APIRouter(prefix="/api/medusa-agent", tags=["medusa-agent-entry"])

    @router.post("/conversation/entry")
    async def start_conversation(body: StartBuyerConversationRequest, request: Request):
        try:
            dependencies = await _resolve_dependencies(provider, request)
            session_id = _guest_session_id(request, dependencies.routedeck)
            completed = await start_home_conversation(
                runner=dependencies.routedeck.runner,
                store=dependencies.routedeck.store,
                agent=dependencies.agent,
                session_id=session_id,
                request_id=body.request_id,
                expected_session_version=body.expected_session_version,
            )
            return JSONResponse(
                content={
                    "turns": public_conversation(completed),
                    "session_version": completed.session_version,
                    "projection_version": completed.projection_version,
                },
                headers={"Cache-Control": "private, no-store"},
            )
        except RouteDeckDependencyUnavailable:
            return _problem_response(
                503,
                code="dependency_unavailable",
                message="The Medusa buyer entry agent is unavailable.",
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
        except EntryConversationError:
            return _problem_response(
                500,
                code="entry_conversation_invalid",
                message="The buyer greeting could not be completed.",
            )

    return router


async def _resolve_dependencies(
    provider: EntryDependencyProvider,
    request: Request,
) -> MedusaEntryDependencies:
    value = provider(request)
    if inspect.isawaitable(value):
        value = await value
    if not isinstance(value, MedusaEntryDependencies):
        raise RouteDeckDependencyUnavailable("Medusa entry agent is not configured")
    return value


def _guest_session_id(request: Request, dependencies: RouteDeckDependencies) -> str:
    session_id = request.cookies.get(dependencies.cookie.name)
    if not session_id or len(session_id) > 512:
        raise SessionStoreError(SessionStoreErrorCode.SESSION_NOT_FOUND)
    return session_id


def _problem_response(status: int, *, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"failure": {"code": code, "message": message}},
        headers={"Cache-Control": "private, no-store"},
    )


__all__ = [
    "MedusaEntryDependencies",
    "StartBuyerConversationRequest",
    "create_medusa_entry_router",
]
