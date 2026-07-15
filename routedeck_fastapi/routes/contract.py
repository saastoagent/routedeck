from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..responses import exception_response
from ..session_http import resolve_dependencies
from . import DependencyProvider


def create_contract_routes(provider: DependencyProvider) -> APIRouter:
    router = APIRouter()

    @router.get("/contract")
    async def get_frontend_contract(request: Request):
        try:
            dependencies = await resolve_dependencies(provider, request)
            return JSONResponse(
                content={
                    "frontend_contract": dependencies.app.frontend_contract.model_dump(
                        mode="json"
                    )
                },
                headers={"Cache-Control": "no-cache"},
            )
        except Exception as error:
            return exception_response(error, cache_control="no-cache")

    return router


__all__ = ["create_contract_routes"]
