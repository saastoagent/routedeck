from __future__ import annotations

from fastapi import APIRouter, Request

from .dependencies import (
    RouteDeckDependencies,
    RouteDeckSessionSelector,
    SseSettings,
)
from .routes.contract import create_contract_routes
from .routes.conversation import create_conversation_routes
from .routes.events import create_event_routes
from .routes.inspection import create_inspection_routes
from .routes.operations import create_operation_routes
from .routes.private_forms import create_private_form_routes
from .routes.sessions import create_session_routes
from .runtime import RuntimeProvider, dependencies_from_runtime, resolve_runtime
from .security import RouteDeckMutationPolicy, SameOriginMutationPolicy


def create_routedeck_router_from_runtime_provider(
    provider: RuntimeProvider,
    *,
    session_selector: RouteDeckSessionSelector,
    sse: SseSettings | None = None,
    mutation_policy: RouteDeckMutationPolicy | None = None,
) -> APIRouter:
    """Derive every RouteDeck HTTP plane from one runtime provider."""

    async def provide_dependencies(request: Request) -> RouteDeckDependencies:
        runtime = await resolve_runtime(provider, request)
        return dependencies_from_runtime(
            runtime,
            session_selector=session_selector,
            sse=sse,
        )

    router = APIRouter(prefix="/api/routedeck", tags=["routedeck"])
    request_policy = mutation_policy or SameOriginMutationPolicy()
    router.include_router(create_contract_routes(provide_dependencies))
    router.include_router(
        create_session_routes(provide_dependencies, request_policy)
    )
    router.include_router(
        create_operation_routes(provide_dependencies, request_policy)
    )
    router.include_router(
        create_conversation_routes(provide_dependencies, request_policy)
    )
    router.include_router(create_event_routes(provide_dependencies))
    router.include_router(
        create_private_form_routes(provide_dependencies, request_policy)
    )
    router.include_router(create_inspection_routes(provide_dependencies))
    return router


__all__ = ["create_routedeck_router_from_runtime_provider"]
