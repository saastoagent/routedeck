from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..inspection import inspection
from ..responses import PRIVATE_CACHE_CONTROL, exception_response
from ..session_http import authenticated_snapshot, project, resolve_dependencies
from . import DependencyProvider


def create_inspection_routes(provider: DependencyProvider) -> APIRouter:
    router = APIRouter()

    @router.get("/inspect")
    async def inspect_session(request: Request):
        try:
            dependencies = await resolve_dependencies(provider, request)
            snapshot = await authenticated_snapshot(request, dependencies)
            projection = project(dependencies, snapshot)
            return JSONResponse(
                content=inspection(dependencies, snapshot, projection),
                headers={"Cache-Control": PRIVATE_CACHE_CONTROL},
            )
        except Exception as error:
            return exception_response(error)

    return router


__all__ = ["create_inspection_routes"]
