from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol, runtime_checkable

from .app import BoundApplication, CompiledApplication
from .contracts.session import RouteDeckSession, SessionSnapshot
from .navigation import RouteDeckNavigationRunner
from .navigation.transactions import PublicKeyValidatorFactory
from .ports import (
    Clock,
    RegisteredOperationExecutor,
    RouteDeckAgentDriver,
    RouteDeckAgentDriverFactory,
    RouteDeckNotifier,
    RouteDeckSessionStore,
    SensitiveCodec,
)
from .projection import ConfiguredSessionProjector
from .supervision import RouteDeckOperationRunner


SessionFactory = Callable[
    [CompiledApplication, str],
    RouteDeckSession | Awaitable[RouteDeckSession],
]
SessionInitializer = Callable[
    ["RouteDeckRuntimeServices", SessionSnapshot],
    SessionSnapshot | Awaitable[SessionSnapshot],
]


@runtime_checkable
class RouteDeckRuntimeLifecycle(Protocol):
    async def close(self) -> None: ...


@dataclass(frozen=True)
class RouteDeckRuntimeServices:
    app: BoundApplication
    store: RouteDeckSessionStore
    clock: Clock
    notifier: RouteDeckNotifier
    id_factory: Callable[[str], str]
    runner: RouteDeckOperationRunner
    navigation: RouteDeckNavigationRunner
    projector: ConfiguredSessionProjector


@dataclass(frozen=True)
class RouteDeckRuntime:
    services: RouteDeckRuntimeServices
    private_form_codec: SensitiveCodec
    session_factory: SessionFactory
    session_initializer: SessionInitializer
    agent_driver: RouteDeckAgentDriver | None
    lifecycle: RouteDeckRuntimeLifecycle

    async def close(self) -> None:
        await self.lifecycle.close()


def build_routedeck_runtime(
    *,
    app: BoundApplication,
    store: RouteDeckSessionStore,
    private_form_codec: SensitiveCodec,
    session_factory: SessionFactory,
    session_initializer: SessionInitializer,
    public_key_validator_factory: PublicKeyValidatorFactory,
    agent_driver_factory: RouteDeckAgentDriverFactory | None,
    lifecycle: RouteDeckRuntimeLifecycle,
    clock: Clock,
    notifier: RouteDeckNotifier,
    id_factory: Callable[[str], str],
    review_ttl: timedelta,
    resume_capability_ttl: timedelta,
) -> RouteDeckRuntime:
    """Construct one immutable, product-neutral RouteDeck runtime."""

    if not isinstance(private_form_codec, SensitiveCodec):
        raise TypeError("RouteDeck runtime requires a SensitiveCodec")
    if not isinstance(lifecycle, RouteDeckRuntimeLifecycle):
        raise TypeError("RouteDeck runtime requires an explicit lifecycle")
    runner = RouteDeckOperationRunner(
        app=app,
        store=store,
        executor=RegisteredOperationExecutor(),
        clock=clock,
        notifier=notifier,
        id_factory=id_factory,
        review_ttl=review_ttl,
        resume_capability_ttl=resume_capability_ttl,
    )
    navigation = RouteDeckNavigationRunner(
        app=app,
        store=store,
        operation_runner=runner,
        clock=clock,
        notifier=notifier,
        id_factory=id_factory,
        public_key_validator_factory=public_key_validator_factory,
    )
    services = RouteDeckRuntimeServices(
        app=app,
        store=store,
        clock=clock,
        notifier=notifier,
        id_factory=id_factory,
        runner=runner,
        navigation=navigation,
        projector=ConfiguredSessionProjector(
            app=app.app,
            clock=clock,
            public_key_validator_factory=public_key_validator_factory,
        ),
    )
    agent_driver = (
        None
        if agent_driver_factory is None
        else agent_driver_factory.create(services)
    )
    if agent_driver is not None and not isinstance(agent_driver, RouteDeckAgentDriver):
        raise TypeError("RouteDeck agent-driver factory returned an invalid driver")
    return RouteDeckRuntime(
        services=services,
        private_form_codec=private_form_codec,
        session_factory=session_factory,
        session_initializer=session_initializer,
        agent_driver=agent_driver,
        lifecycle=lifecycle,
    )


__all__ = [
    "PublicKeyValidatorFactory",
    "RouteDeckRuntime",
    "RouteDeckRuntimeLifecycle",
    "RouteDeckRuntimeServices",
    "SessionFactory",
    "SessionInitializer",
    "build_routedeck_runtime",
]
