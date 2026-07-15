from __future__ import annotations

import secrets

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from routedeck_core.contracts.failures import FailureKind

from ..contracts import RouteDeckHttpProblem, SessionCreateRequest
from ..responses import PRIVATE_CACHE_CONTROL, exception_response, public_projection
from ..security import RouteDeckMutationPolicy
from ..session_http import (
    authenticated_snapshot,
    initialize_session,
    make_session,
    project,
    resolve_dependencies,
    session_creation_fingerprint,
    set_guest_cookie,
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
            session = await make_session(dependencies.session_factory, session_id)
            if session.session_id != session_id:
                raise RouteDeckHttpProblem(
                    500,
                    "session_identity_mismatch",
                    "The session could not be created.",
                    FailureKind.INTERNAL,
                    "session_creation",
                )
            snapshot = await dependencies.store.create_for_request(
                session,
                body.request_id,
                session_creation_fingerprint(),
            )
            session_id = snapshot.session_id
            try:
                snapshot = await initialize_session(
                    dependencies.session_initializer,
                    snapshot,
                )
            except Exception as error:
                return exception_response(error)
            projection = project(dependencies, snapshot)
            response = JSONResponse(
                status_code=201,
                content={"projection": public_projection(projection)},
                headers={"Cache-Control": PRIVATE_CACHE_CONTROL},
            )
            set_guest_cookie(response, session_id, dependencies.cookie)
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
