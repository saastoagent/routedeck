from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from routedeck_core.app import BoundApplication, CompiledApplication
from routedeck_core.contracts.retention import RouteDeckRetentionPolicy
from routedeck_core.navigation.transactions import PublicKeyValidatorFactory
from routedeck_core.ports import (
    Clock,
    RouteDeckAgentDriverFactory,
    RouteDeckNotifier,
)
from routedeck_core.runtime import (
    RouteDeckRuntime,
    SessionFactory,
    SessionInitializer,
    build_routedeck_runtime,
)
from routedeck_core.runtime_defaults import (
    InProcessEventNotifier,
    UtcClock,
    _new_runtime_id,
)
from routedeck_core.state.session import navgraph_version

from .codec import FernetSensitiveCodec
from .store import SqlAlchemySessionStore


@dataclass(frozen=True)
class SqlAlchemyRuntimeResources:
    store: SqlAlchemySessionStore
    codec: FernetSensitiveCodec


ApplicationFactory = Callable[[SqlAlchemyRuntimeResources], BoundApplication]


async def open_sqlalchemy_routedeck_runtime(
    *,
    compiled_app: CompiledApplication,
    application_factory: ApplicationFactory,
    session_factory: SessionFactory,
    session_initializer: SessionInitializer,
    public_key_validator_factory: PublicKeyValidatorFactory,
    agent_driver_factory: RouteDeckAgentDriverFactory | None,
    database_url: str,
    encryption_key: str | bytes,
    instance_id: str,
    review_ttl: timedelta,
    resume_capability_ttl: timedelta,
    default_session_id: str,
    retention_policy: RouteDeckRetentionPolicy | None = None,
    busy_timeout: timedelta = timedelta(seconds=5),
    worker_count: int = 1,
    clock: Clock | None = None,
    notifier: RouteDeckNotifier | None = None,
    id_factory: Callable[[str], str] | None = None,
) -> RouteDeckRuntime:
    """Open durable resources and construct one fail-closed RouteDeck runtime."""

    effective_clock = UtcClock() if clock is None else clock
    effective_notifier = (
        InProcessEventNotifier() if notifier is None else notifier
    )
    effective_id_factory = _new_runtime_id if id_factory is None else id_factory
    codec = FernetSensitiveCodec(encryption_key)
    store = await SqlAlchemySessionStore.open(
        database_url,
        instance_id=instance_id,
        codec=codec,
        clock=effective_clock,
        retention_policy=retention_policy,
        busy_timeout=busy_timeout,
        worker_count=worker_count,
        expected_navgraph_version=navgraph_version(compiled_app),
    )
    try:
        resources = SqlAlchemyRuntimeResources(store=store, codec=codec)
        app = application_factory(resources)
        if not isinstance(app, BoundApplication):
            raise TypeError(
                "application_factory must return a BoundApplication"
            )
        if app.app is not compiled_app:
            raise ValueError(
                "application_factory must bind the supplied compiled app instance"
            )
        return build_routedeck_runtime(
            app=app,
            store=store,
            private_form_codec=codec,
            session_factory=session_factory,
            session_initializer=session_initializer,
            public_key_validator_factory=public_key_validator_factory,
            agent_driver_factory=agent_driver_factory,
            lifecycle=store,
            clock=effective_clock,
            notifier=effective_notifier,
            id_factory=effective_id_factory,
            review_ttl=review_ttl,
            resume_capability_ttl=resume_capability_ttl,
            default_session_id=default_session_id,
        )
    except BaseException:
        await store.close()
        raise


__all__ = [
    "ApplicationFactory",
    "SqlAlchemyRuntimeResources",
    "open_sqlalchemy_routedeck_runtime",
]
