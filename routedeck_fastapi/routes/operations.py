from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from routedeck_core.contracts.operations import OperationRequest, OperationSource
from routedeck_core.contracts.projection import FrozenJsonObject
from routedeck_core.navigation.transactions import NavigationRequest

from ..contracts import (
    DispatchRequest,
    NavigationRequestBody,
    ReviewRequest,
    RouteDeckHttpProblem,
)
from ..dependencies import RouteDeckDependencyUnavailable
from ..responses import (
    PRIVATE_CACHE_CONTROL,
    exception_response,
    operation_response,
    public_projection,
)
from ..security import RouteDeckMutationPolicy
from ..session_http import (
    guest_session_id,
    project,
    resolve_dependencies,
    validated_body,
)
from . import DependencyProvider


def create_operation_routes(
    provider: DependencyProvider,
    mutation_policy: RouteDeckMutationPolicy,
) -> APIRouter:
    router = APIRouter()

    @router.post("/dispatch")
    async def dispatch(request: Request):
        try:
            dependencies = await resolve_dependencies(provider, request)
            session_id = guest_session_id(request, dependencies.cookie)
            body = await validated_body(request, DispatchRequest, mutation_policy)
            try:
                operation_request = OperationRequest(
                    session_id=session_id,
                    request_id=body.request_id,
                    expected_session_version=body.expected_session_version,
                    operation_id=body.operation_id,
                    source=OperationSource.SURFACE,
                    arguments=FrozenJsonObject(body.arguments),
                )
            except (TypeError, ValueError, ValidationError) as error:
                raise RouteDeckHttpProblem(
                    400,
                    "invalid_request",
                    "The request is invalid.",
                ) from error
            result = await dependencies.runner.run(operation_request)
            return operation_response(result)
        except Exception as error:
            return exception_response(error)

    @router.post("/navigation")
    async def navigate(request: Request):
        try:
            dependencies = await resolve_dependencies(provider, request)
            if dependencies.navigation is None:
                raise RouteDeckDependencyUnavailable(
                    "RouteDeck navigation transactions are not configured"
                )
            session_id = guest_session_id(request, dependencies.cookie)
            body = await validated_body(
                request,
                NavigationRequestBody,
                mutation_policy,
            )
            snapshot = await dependencies.navigation.navigate(
                NavigationRequest(
                    session_id=session_id,
                    request_id=body.request_id,
                    expected_session_version=body.expected_session_version,
                    intent=body.intent,
                )
            )
            projection = project(dependencies, snapshot)
            return JSONResponse(
                content={"projection": public_projection(projection)},
                headers={"Cache-Control": PRIVATE_CACHE_CONTROL},
            )
        except Exception as error:
            return exception_response(error)

    @router.post("/reviews/{review_id}/accept")
    async def accept_review(review_id: str, request: Request):
        return await _review_response(
            provider=provider,
            request=request,
            review_id=review_id,
            accept=True,
            mutation_policy=mutation_policy,
        )

    @router.post("/reviews/{review_id}/reject")
    async def reject_review(review_id: str, request: Request):
        return await _review_response(
            provider=provider,
            request=request,
            review_id=review_id,
            accept=False,
            mutation_policy=mutation_policy,
        )

    return router


async def _review_response(
    *,
    provider: DependencyProvider,
    request: Request,
    review_id: str,
    accept: bool,
    mutation_policy: RouteDeckMutationPolicy,
):
    try:
        dependencies = await resolve_dependencies(provider, request)
        session_id = guest_session_id(request, dependencies.cookie)
        body = await validated_body(request, ReviewRequest, mutation_policy)
        method = (
            dependencies.runner.accept_review
            if accept
            else dependencies.runner.reject_review
        )
        result = await method(
            review_id,
            request_id=body.request_id,
            expected_session_version=body.expected_session_version,
            session_id=session_id,
        )
        return operation_response(result)
    except Exception as error:
        return exception_response(error)


__all__ = ["create_operation_routes"]
