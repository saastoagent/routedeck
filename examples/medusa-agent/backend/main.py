from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from medusa_agent.api import MedusaAgentReadinessProbe, health_router
from medusa_agent.config import Settings
from medusa_agent.runtime import (
    LiveMedusaApplication,
    open_live_medusa_application,
)
from routedeck_core import RouteDeckRuntime
from routedeck_fastapi import (
    GuestCookieSessionSelector,
    GuestCookieSettings,
    RouteDeckDependencyUnavailable,
    RouteDeckSessionSelector,
    SameOriginMutationPolicy,
    create_routedeck_router_from_runtime_provider,
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
    browser_origins: Sequence[str],
    session_selector: RouteDeckSessionSelector,
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
            session_selector=session_selector,
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


def create_live_app() -> FastAPI:
    settings = Settings.from_env()

    async def open_configured_runtime() -> LiveMedusaApplication:
        return await open_live_medusa_application(settings)

    return create_medusa_app(
        live_runtime_factory=open_configured_runtime,
        browser_origins=tuple(
            str(origin).rstrip("/") for origin in settings.routedeck_browser_origins
        ),
        session_selector=GuestCookieSessionSelector(
            GuestCookieSettings(
                name=settings.routedeck_guest_cookie_name,
                secure=settings.routedeck_guest_cookie_secure,
                path=settings.routedeck_guest_cookie_path,
            )
        ),
    )


__all__ = ["create_live_app", "create_medusa_app"]
