from __future__ import annotations

import secrets

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..contracts import SessionCreateRequest
from ..responses import PRIVATE_CACHE_CONTROL, exception_response, public_projection
from ..security import RouteDeckMutationPolicy
from ..session_http import (
    authenticated_snapshot,
    project,
    resolve_dependencies,
    validated_body,
)
from . import DependencyProvider


def create_session_routes(
    provider: DependencyProvider,
    mutation_policy: RouteDeckMutationPolicy,
) -> APIRouter:
    router = APIRouter()

    @router.post("/sessions", status_code=201)
    async def create_session(request: Request):
        try:
            dependencies = await resolve_dependencies(provider, request)
            body = await validated_body(
                request,
                SessionCreateRequest,
                mutation_policy,
            )
            session_id = secrets.token_urlsafe(32)
            snapshot = await dependencies.session_provisioner(
                session_id=session_id,
                request_id=body.request_id,
            )
            projection = project(dependencies, snapshot)
            response = JSONResponse(
                status_code=201,
                content={"projection": public_projection(projection)},
                headers={"Cache-Control": PRIVATE_CACHE_CONTROL},
            )
            await dependencies.session_selector.attach_created_session(
                request,
                response,
                snapshot.session_id,
            )
            return response
        except Exception as error:
            return exception_response(error)

    @router.get("/session")
    async def get_session(request: Request):
        try:
            dependencies = await resolve_dependencies(provider, request)
            snapshot = await authenticated_snapshot(request, dependencies)
            projection = project(dependencies, snapshot)
            return JSONResponse(
                content={"projection": public_projection(projection)},
                headers={"Cache-Control": PRIVATE_CACHE_CONTROL},
            )
        except Exception as error:
            return exception_response(error)

    return router


__all__ = ["create_session_routes"]
