from __future__ import annotations

import hashlib
import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import timedelta
from enum import StrEnum
from typing import Protocol, runtime_checkable

from .app import BoundApplication, CompiledApplication
from .conversation_runs import ConversationRunCoordinator
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


class SessionProvisioningErrorCode(StrEnum):
    SESSION_IDENTITY_MISMATCH = "session_identity_mismatch"
    SESSION_INITIALIZER_INVALID = "session_initializer_invalid"


class SessionProvisioningError(RuntimeError):
    def __init__(self, code: SessionProvisioningErrorCode) -> None:
        super().__init__(code.value)
        self.code = code


_SESSION_PROVISIONING_FINGERPRINT = hashlib.sha256(
    b"routedeck.session-creation.v1"
).hexdigest()


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
    conversation_runs: ConversationRunCoordinator = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "conversation_runs",
            ConversationRunCoordinator(
                app=self.services.app,
                store=self.services.store,
                runner=self.services.runner,
                agent_driver=self.agent_driver,
                id_factory=self.services.id_factory,
            ),
        )

    async def close(self) -> None:
        await self.conversation_runs.close()
        await self.lifecycle.close()

    async def ensure_declared_entry_run(
        self, snapshot: SessionSnapshot
    ):
        return await self.conversation_runs.ensure_declared_entry_run(snapshot)

    async def provision_session(
        self,
        *,
        session_id: str,
        request_id: str,
    ) -> SessionSnapshot:
        """Create or replay one durable session and return its current snapshot."""

        created = self.session_factory(self.services.app.app, session_id)
        if inspect.isawaitable(created):
            created = await created
        if (
            not isinstance(created, RouteDeckSession)
            or created.session_id != session_id
        ):
            raise SessionProvisioningError(
                SessionProvisioningErrorCode.SESSION_IDENTITY_MISMATCH
            )
        snapshot = await self.services.store.create_for_request(
            created,
            request_id,
            _SESSION_PROVISIONING_FINGERPRINT,
        )
        initialized = self.session_initializer(self.services, snapshot)
        if inspect.isawaitable(initialized):
            initialized = await initialized
        if (
            not isinstance(initialized, SessionSnapshot)
            or initialized.session_id != snapshot.session_id
            or initialized.session_version < snapshot.session_version
        ):
            raise SessionProvisioningError(
                SessionProvisioningErrorCode.SESSION_INITIALIZER_INVALID
            )
        await self.ensure_declared_entry_run(initialized)
        return await self.services.store.load(initialized.session_id)


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
    "SessionProvisioningError",
    "SessionProvisioningErrorCode",
    "SessionFactory",
    "SessionInitializer",
    "build_routedeck_runtime",
]
