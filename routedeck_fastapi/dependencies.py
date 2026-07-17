from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Protocol, runtime_checkable

from routedeck_core.app import CompiledApplication
from routedeck_core.contracts.events import RouteDeckEvent
from routedeck_core.contracts.projection import PublicProjection
from routedeck_core.contracts.session import RouteDeckSession, SessionSnapshot
from routedeck_core.ports import (
    RouteDeckAgentDriver,
    RouteDeckSessionStore,
    SensitiveCodec,
)
from routedeck_core.navigation.transactions import RouteDeckNavigationRunner
from routedeck_core.supervision import RouteDeckOperationRunner


@runtime_checkable
class SessionProjector(Protocol):
    def project(self, session: RouteDeckSession) -> PublicProjection: ...


@runtime_checkable
class EventWakeupNotifier(Protocol):
    """Notifier used by writers and cursor-aware SSE followers."""

    async def notify(
        self,
        session_id: str,
        events: Sequence[RouteDeckEvent],
    ) -> None: ...

    async def wait_for_events(
        self,
        session_id: str,
        after_cursor: int,
        timeout: timedelta,
    ) -> bool:
        """Return true when an event newer than ``after_cursor`` is known."""


SessionFactory = Callable[
    [str],
    RouteDeckSession | Awaitable[RouteDeckSession],
]
SessionInitializer = Callable[
    [SessionSnapshot],
    SessionSnapshot | Awaitable[SessionSnapshot],
]


@dataclass(frozen=True)
class GuestCookieSettings:
    name: str = "routedeck_guest"
    secure: bool = False
    path: str = "/"

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("guest cookie name must be non-empty")
        if not self.path.startswith("/"):
            raise ValueError("guest cookie path must be absolute")


@dataclass(frozen=True)
class SseSettings:
    replay_batch_size: int = 100
    heartbeat_interval: timedelta = timedelta(seconds=15)
    follow: bool = True

    def __post_init__(self) -> None:
        if self.replay_batch_size < 1:
            raise ValueError("SSE replay batch size must be positive")
        if self.heartbeat_interval <= timedelta(0):
            raise ValueError("SSE heartbeat interval must be positive")


class RouteDeckDependencyUnavailable(RuntimeError):
    """Raised when an application mounted the router before binding runtime ports."""


@dataclass(frozen=True)
class RouteDeckDependencies:
    app: CompiledApplication
    runner: RouteDeckOperationRunner
    store: RouteDeckSessionStore
    notifier: EventWakeupNotifier
    projector: SessionProjector
    private_form_codec: SensitiveCodec
    session_factory: SessionFactory
    agent_driver: RouteDeckAgentDriver | None = None
    navigation: RouteDeckNavigationRunner | None = None
    session_initializer: SessionInitializer | None = None
    cookie: GuestCookieSettings = field(default_factory=GuestCookieSettings)
    sse: SseSettings = field(default_factory=SseSettings)

    def __post_init__(self) -> None:
        if self.agent_driver is not None and not isinstance(
            self.agent_driver,
            RouteDeckAgentDriver,
        ):
            raise TypeError("RouteDeck conversation requires an agent driver")
        if self.sse.follow and not isinstance(self.notifier, EventWakeupNotifier):
            raise TypeError(
                "followed SSE requires a notifier with wait_for_events support"
            )


__all__ = [
    "EventWakeupNotifier",
    "GuestCookieSettings",
    "RouteDeckDependencies",
    "RouteDeckDependencyUnavailable",
    "SessionFactory",
    "SessionInitializer",
    "SessionProjector",
    "SseSettings",
]
