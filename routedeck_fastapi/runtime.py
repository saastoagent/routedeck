from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable

from fastapi import Request

from routedeck_core.contracts.session import RouteDeckSession, SessionSnapshot
from routedeck_core.runtime import RouteDeckRuntime

from .dependencies import (
    EventWakeupNotifier,
    GuestCookieSettings,
    RouteDeckDependencies,
    RouteDeckDependencyUnavailable,
    SseSettings,
)


RuntimeProvider = Callable[
    [Request],
    RouteDeckRuntime | Awaitable[RouteDeckRuntime],
]


def dependencies_from_runtime(
    runtime: RouteDeckRuntime,
    *,
    cookie: GuestCookieSettings | None = None,
    sse: SseSettings | None = None,
) -> RouteDeckDependencies:
    """Derive every FastAPI dependency from one framework-owned runtime."""

    services = runtime.services
    effective_sse = sse or SseSettings()
    if effective_sse.follow and not isinstance(
        services.notifier,
        EventWakeupNotifier,
    ):
        raise TypeError(
            "RouteDeck followed SSE requires a cursor-aware runtime notifier"
        )

    def make_session(
        session_id: str,
    ) -> RouteDeckSession | Awaitable[RouteDeckSession]:
        return runtime.session_factory(services.app.app, session_id)

    def initialize_session(
        snapshot: SessionSnapshot,
    ) -> SessionSnapshot | Awaitable[SessionSnapshot]:
        return runtime.session_initializer(services, snapshot)

    return RouteDeckDependencies(
        app=services.app.app,
        runner=services.runner,
        store=services.store,
        notifier=services.notifier,
        projector=services.projector,
        private_form_codec=runtime.private_form_codec,
        session_factory=make_session,
        agent_driver=runtime.agent_driver,
        navigation=services.navigation,
        session_initializer=initialize_session,
        cookie=cookie or GuestCookieSettings(),
        sse=effective_sse,
    )


async def resolve_runtime(
    provider: RuntimeProvider,
    request: Request,
) -> RouteDeckRuntime:
    runtime = provider(request)
    if inspect.isawaitable(runtime):
        runtime = await runtime
    if not isinstance(runtime, RouteDeckRuntime):
        raise RouteDeckDependencyUnavailable(
            "RouteDeck runtime is not configured"
        )
    return runtime


__all__ = ["RuntimeProvider", "dependencies_from_runtime"]
