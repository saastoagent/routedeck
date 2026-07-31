from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import cast

from fastapi import Request

from routedeck_core.runtime import RouteDeckRuntime

from .dependencies import (
    EventWakeupNotifier,
    RouteDeckDependencies,
    RouteDeckDependencyUnavailable,
    RouteDeckSessionSelector,
    SseSettings,
)


RuntimeProvider = Callable[
    [Request],
    RouteDeckRuntime | Awaitable[RouteDeckRuntime],
]


def dependencies_from_runtime(
    runtime: RouteDeckRuntime,
    *,
    session_selector: RouteDeckSessionSelector,
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

    return RouteDeckDependencies(
        app=services.app.app,
        runner=services.runner,
        store=services.store,
        notifier=cast(EventWakeupNotifier, services.notifier),
        projector=services.projector,
        private_form_codec=runtime.private_form_codec,
        session_provisioner=runtime.provision_session,
        agent_driver=runtime.agent_driver,
        navigation=services.navigation,
        session_selector=session_selector,
        conversation_runs=runtime.conversation_runs,
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
