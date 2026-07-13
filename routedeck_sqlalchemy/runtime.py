from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from typing import TypeVar

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from routedeck_core.ports.clock import Clock
from routedeck_core.ports.session_store import SessionStoreError, SessionStoreErrorCode

from .database import DatabaseRuntime
from .lease import (
    ApplicationLease,
    RouteDeckInstanceLeaseLost,
    assert_application_lease,
    heartbeat_application_lease,
    release_application_lease,
)


T = TypeVar("T")


class SqlAlchemyStoreRuntime:
    """Own database serialization, application lease, and maintenance tasks."""

    def __init__(
        self,
        *,
        database: DatabaseRuntime,
        application_lease: ApplicationLease,
        lease_ttl: timedelta,
        clock: Clock,
    ) -> None:
        self.database = database
        self.application_lease = application_lease
        self._lease_ttl = lease_ttl
        self._clock = clock
        self._lock = asyncio.Lock()
        self._closed = False
        self._background_failure: BaseException | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._cleanup_task: asyncio.Task[None] | None = None

    def start(
        self,
        *,
        instance_id: str,
        cleanup_interval: timedelta,
        cleanup: Callable[[], Awaitable[int]],
    ) -> None:
        self.ensure_open()
        if self._heartbeat_task is not None or self._cleanup_task is not None:
            raise RuntimeError("RouteDeck SQLAlchemy maintenance already started")
        self._heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(),
            name=f"routedeck-sqlalchemy-heartbeat:{instance_id}",
        )
        self._cleanup_task = asyncio.create_task(
            self._cleanup_loop(cleanup_interval, cleanup),
            name=f"routedeck-sqlalchemy-cleanup:{instance_id}",
        )

    async def close(self) -> None:
        if self._closed:
            return
        tasks = tuple(
            task
            for task in (self._heartbeat_task, self._cleanup_task)
            if task is not None
        )
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        failure: BaseException | None = None
        now = aware_utc(self._clock.now())

        def release() -> None:
            with self.database.session_factory() as database, database.begin():
                release_application_lease(
                    database,
                    self.application_lease,
                    now=now,
                )

        async with self._lock:
            try:
                await asyncio.to_thread(release)
            except RouteDeckInstanceLeaseLost as error:
                failure = error
            await asyncio.to_thread(self.database.dispose)
            self._closed = True
        if failure is not None:
            raise failure

    async def write(
        self,
        operation: Callable[[Session, datetime], T],
    ) -> T:
        self.ensure_open()
        now = aware_utc(self._clock.now())

        def run() -> T:
            with self.database.session_factory() as database, database.begin():
                assert_application_lease(database, self.application_lease, now=now)
                return operation(database, now)

        try:
            async with self._lock:
                return await asyncio.to_thread(run)
        except (SessionStoreError, RouteDeckInstanceLeaseLost):
            raise
        except SQLAlchemyError as error:
            raise SessionStoreError(
                SessionStoreErrorCode.PERSISTENCE_FAILURE
            ) from error

    def ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("SqlAlchemySessionStore is closed")
        if self._background_failure is not None:
            raise RouteDeckInstanceLeaseLost(
                "RouteDeck SQLAlchemy background maintenance failed"
            ) from self._background_failure

    async def _heartbeat_loop(self) -> None:
        interval = self._lease_ttl.total_seconds() / 3
        try:
            while True:
                await asyncio.sleep(interval)
                now = aware_utc(self._clock.now())

                def heartbeat() -> None:
                    with self.database.session_factory() as database, database.begin():
                        self.application_lease = heartbeat_application_lease(
                            database,
                            self.application_lease,
                            now=now,
                            ttl=self._lease_ttl,
                        )

                async with self._lock:
                    await asyncio.to_thread(heartbeat)
        except asyncio.CancelledError:
            raise
        except BaseException as error:
            self._background_failure = error

    async def _cleanup_loop(
        self,
        interval: timedelta,
        cleanup: Callable[[], Awaitable[int]],
    ) -> None:
        try:
            while True:
                await asyncio.sleep(interval.total_seconds())
                await cleanup()
        except asyncio.CancelledError:
            raise
        except BaseException as error:
            self._background_failure = error


def aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("RouteDeck clocks must return timezone-aware timestamps")
    return value.astimezone(timezone.utc)


__all__ = ["SqlAlchemyStoreRuntime", "aware_utc"]
