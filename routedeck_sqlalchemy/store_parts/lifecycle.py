from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Protocol, TypeVar

from sqlalchemy.orm import Session

from routedeck_core.contracts.retention import RouteDeckRetentionPolicy
from routedeck_core.ports.clock import Clock
from routedeck_core.ports.codec import SensitiveCodec
from routedeck_core.runtime_defaults import UtcClock

from ..database import DatabaseRuntime, open_database
from ..lease import (
    ApplicationLease,
    RouteDeckWorkerConfigurationError,
    acquire_application_lease,
)
from ..runtime import SqlAlchemyStoreRuntime, aware_utc


T = TypeVar("T")


class _LifecycleManagedStore(Protocol):
    _lifecycle: _StoreLifecycle

    async def _recover_abandoned_turns(self) -> None: ...

    async def cleanup_expired(self) -> int: ...

    async def close(self) -> None: ...


StoreT = TypeVar("StoreT", bound=_LifecycleManagedStore)


class _StoreLifecycle:
    def __init__(self, runtime: SqlAlchemyStoreRuntime) -> None:
        self.runtime = runtime

    @classmethod
    async def open_store(
        cls,
        store_factory: Callable[..., StoreT],
        database_url: str,
        *,
        instance_id: str,
        codec: SensitiveCodec,
        clock: Clock | None = None,
        retention_policy: RouteDeckRetentionPolicy | None = None,
        busy_timeout: timedelta = timedelta(seconds=5),
        worker_count: int = 1,
        lease_ttl: timedelta = timedelta(seconds=30),
        expected_navgraph_version: str | None = None,
    ) -> StoreT:
        if worker_count != 1:
            raise RouteDeckWorkerConfigurationError(
                "RouteDeck SQLAlchemy persistence supports one application worker"
            )
        if not isinstance(codec, SensitiveCodec):
            raise TypeError("SqlAlchemySessionStore requires a SensitiveCodec")
        if lease_ttl <= timedelta(seconds=3):
            raise ValueError("lease_ttl must be greater than three seconds")
        effective_clock = clock or UtcClock()
        effective_retention = (
            retention_policy or RouteDeckRetentionPolicy.standalone_default()
        )
        now = aware_utc(effective_clock.now())

        def initialize() -> tuple[DatabaseRuntime, ApplicationLease]:
            database = open_database(database_url, busy_timeout=busy_timeout)
            try:
                with database.session_factory() as session, session.begin():
                    lease = acquire_application_lease(
                        session,
                        instance_id=instance_id,
                        now=now,
                        ttl=lease_ttl,
                    )
                return database, lease
            except BaseException:
                database.dispose()
                raise

        database, lease = await asyncio.to_thread(initialize)
        store = store_factory(
            database=database,
            instance_lease=lease,
            instance_lease_ttl=lease_ttl,
            codec=codec,
            clock=effective_clock,
            retention_policy=effective_retention,
            expected_navgraph_version=expected_navgraph_version,
        )
        try:
            await store._recover_abandoned_turns()
            if effective_retention.cleanup_on_startup:
                await store.cleanup_expired()
            store._lifecycle.start(
                instance_id=instance_id,
                cleanup_interval=effective_retention.cleanup_interval,
                cleanup=store.cleanup_expired,
            )
            return store
        except BaseException:
            await store.close()
            raise

    @property
    def dialect_name(self) -> str:
        return self.runtime.database.dialect_name

    @property
    def database_url(self) -> str:
        return self.runtime.database.database_url

    def ensure_open(self) -> None:
        self.runtime.ensure_open()

    def start(
        self,
        *,
        instance_id: str,
        cleanup_interval: timedelta,
        cleanup: Callable[[], Awaitable[int]],
    ) -> None:
        self.runtime.start(
            instance_id=instance_id,
            cleanup_interval=cleanup_interval,
            cleanup=cleanup,
        )

    async def close(self) -> None:
        await self.runtime.close()

    async def write(
        self,
        operation: Callable[[Session, datetime], T],
    ) -> T:
        return await self.runtime.write(operation)

    async def read(
        self,
        operation: Callable[[Session, datetime], T],
    ) -> T:
        return await self.runtime.write(operation)
