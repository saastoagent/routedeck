from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from medusa_agent.api import MedusaAgentReadinessProbe, health_router
from medusa_agent.runtime import (
    LiveMedusaApplication,
    open_live_medusa_application,
)
from routedeck_core import RouteDeckRuntime
from routedeck_fastapi import (
    RouteDeckDependencyUnavailable,
    SameOriginMutationPolicy,
    create_routedeck_router_from_runtime_provider,
)


_DEFAULT_BROWSER_ORIGINS = (
    "http://127.0.0.1:5198",
    "http://localhost:5198",
)


async def _routedeck_runtime(request: Request) -> RouteDeckRuntime:
    runtime = getattr(request.app.state, "routedeck_runtime", None)
    if not isinstance(runtime, RouteDeckRuntime):
        raise RouteDeckDependencyUnavailable("RouteDeck runtime is not configured")
    return runtime


def create_medusa_app(
    *,
    runtime: RouteDeckRuntime | None = None,
    readiness: MedusaAgentReadinessProbe | None = None,
    live_runtime_factory: (
        Callable[[], Awaitable[LiveMedusaApplication]] | None
    ) = None,
    browser_origins: Sequence[str] = _DEFAULT_BROWSER_ORIGINS,
) -> FastAPI:
    """Compose product APIs with the generic RouteDeck transport exactly once."""

    if live_runtime_factory is not None and (
        runtime is not None or readiness is not None
    ):
        raise ValueError(
            "Live runtime composition cannot be combined with injected ports"
        )
    application = FastAPI(
        title="Medusa Agent",
        lifespan=(
            None
            if live_runtime_factory is None
            else _live_lifespan(live_runtime_factory)
        ),
    )
    application.state.routedeck_runtime = runtime
    application.state.medusa_readiness = readiness
    trusted_browser_origins = frozenset(browser_origins)
    mutation_policy = SameOriginMutationPolicy(trusted_origins=trusted_browser_origins)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(trusted_browser_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(
        create_routedeck_router_from_runtime_provider(
            _routedeck_runtime,
            mutation_policy=mutation_policy,
        )
    )
    application.include_router(health_router)
    return application


def _live_lifespan(
    factory: Callable[[], Awaitable[LiveMedusaApplication]],
):
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        live = await factory()
        try:
            application.state.routedeck_runtime = live.runtime
            application.state.medusa_readiness = live.readiness
            application.state.medusa_live_runtime = live
            yield
        finally:
            application.state.routedeck_runtime = None
            application.state.medusa_readiness = None
            application.state.medusa_live_runtime = None
            await live.close()

    return lifespan


app = create_medusa_app(live_runtime_factory=open_live_medusa_application)


__all__ = ["app", "create_medusa_app"]
