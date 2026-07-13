from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from medusa_agent.api import MedusaAgentReadinessProbe, health_router
from medusa_agent.api.chat import (
    AgentEventStream,
    MedusaChatDependencies,
    create_medusa_chat_router,
)
from medusa_agent.api.conversation import create_medusa_conversation_router
from medusa_agent.api.entry import (
    MedusaEntryDependencies,
    create_medusa_entry_router,
)
from medusa_agent.runtime import (
    LiveMedusaApplication,
    open_live_medusa_application,
)
from routedeck_fastapi import (
    RouteDeckDependencies,
    RouteDeckDependencyUnavailable,
    SameOriginMutationPolicy,
    create_routedeck_router_from_provider,
)


_DEFAULT_BROWSER_ORIGINS = (
    "http://127.0.0.1:5198",
    "http://localhost:5198",
)


async def _routedeck_dependencies(request: Request) -> RouteDeckDependencies:
    dependencies = getattr(request.app.state, "routedeck_dependencies", None)
    if not isinstance(dependencies, RouteDeckDependencies):
        raise RouteDeckDependencyUnavailable("RouteDeck runtime is not configured")
    return dependencies


async def _chat_dependencies(request: Request) -> MedusaChatDependencies:
    routedeck = await _routedeck_dependencies(request)
    agent = getattr(request.app.state, "medusa_chat_agent", None)
    if agent is None or not callable(getattr(agent, "astream_events", None)):
        raise RouteDeckDependencyUnavailable("Medusa chat agent is not configured")
    return MedusaChatDependencies(routedeck=routedeck, agent=agent)


async def _entry_dependencies(request: Request) -> MedusaEntryDependencies:
    routedeck = await _routedeck_dependencies(request)
    agent = getattr(request.app.state, "medusa_entry_agent", None)
    if agent is None or not callable(getattr(agent, "ainvoke", None)):
        raise RouteDeckDependencyUnavailable("Medusa entry agent is not configured")
    return MedusaEntryDependencies(routedeck=routedeck, agent=agent)


def create_medusa_app(
    *,
    routedeck: RouteDeckDependencies | None = None,
    agent: AgentEventStream | None = None,
    entry_agent: object | None = None,
    readiness: MedusaAgentReadinessProbe | None = None,
    live_runtime_factory: (
        Callable[[], Awaitable[LiveMedusaApplication]] | None
    ) = None,
    browser_origins: Sequence[str] = _DEFAULT_BROWSER_ORIGINS,
) -> FastAPI:
    """Compose product APIs with the generic RouteDeck transport exactly once."""

    if live_runtime_factory is not None and (
        routedeck is not None
        or agent is not None
        or entry_agent is not None
        or readiness is not None
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
    application.state.routedeck_dependencies = routedeck
    application.state.medusa_chat_agent = agent
    application.state.medusa_entry_agent = entry_agent
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
        create_routedeck_router_from_provider(
            _routedeck_dependencies,
            mutation_policy=mutation_policy,
        )
    )
    application.include_router(create_medusa_chat_router(_chat_dependencies))
    application.include_router(create_medusa_entry_router(_entry_dependencies))
    application.include_router(
        create_medusa_conversation_router(_routedeck_dependencies)
    )
    application.include_router(health_router)
    return application


def _live_lifespan(
    factory: Callable[[], Awaitable[LiveMedusaApplication]],
):
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        live = await factory()
        application.state.routedeck_dependencies = live.routedeck
        application.state.medusa_chat_agent = live.agent
        application.state.medusa_entry_agent = live.entry_agent
        application.state.medusa_readiness = live.readiness
        application.state.medusa_live_runtime = live
        try:
            yield
        finally:
            application.state.routedeck_dependencies = None
            application.state.medusa_chat_agent = None
            application.state.medusa_entry_agent = None
            application.state.medusa_readiness = None
            application.state.medusa_live_runtime = None
            await live.close()

    return lifespan


app = create_medusa_app(live_runtime_factory=open_live_medusa_application)


__all__ = ["app", "create_medusa_app"]
