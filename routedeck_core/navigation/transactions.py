from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..app import BoundRouteDeckApp
from ..contracts.events import (
    CanonicalRouteDeckEvent,
    PublicEventPayload,
    RouteDeckEventType,
)
from ..contracts.navigation import DeepLinkPolicy
from ..contracts.mutations import MutationCommit, MutationKind, MutationStatus
from ..contracts.operations import (
    OperationDisposition,
    OperationRequest,
    OperationSource,
)
from ..contracts.projection import FrozenJsonObject
from ..contracts.session import Location, RouteDeckSession, SessionSnapshot
from ..ports import Clock, RouteDeckNotifier, RouteDeckSessionStore
from ..ports.notifier import notify_event_wakeup
from ..state.leases import TurnClaim, TurnOwnerKind
from ..state.aggregate import RouteDeckSessionAggregate
from ..supervision import RouteDeckOperationRunner, RouteEntryInvocation
from ..supervision.outcomes import canonical_json_fingerprint
from ..validation import RouteDeckValidationError
from .deep_links import DeepLinkEngine
from .engine import NavigationEngine
from .routes import PublicRouteKeyValidator, StructuralRouteMatch


class NavigationIntentKind(StrEnum):
    OPEN_PATH = "open_path"
    BACK = "back"
    FORWARD = "forward"
    CANCEL = "cancel"
    RESTORE_HISTORY_ENTRY = "restore_history_entry"


class NavigationIntent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: NavigationIntentKind
    path: str | None = None
    history_entry_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _exact_shape(self) -> NavigationIntent:
        if self.kind is NavigationIntentKind.OPEN_PATH:
            if self.path is None or self.history_entry_id is not None:
                raise ValueError("open_path requires path only")
        elif self.kind is NavigationIntentKind.RESTORE_HISTORY_ENTRY:
            if self.path is None or self.history_entry_id is None:
                raise ValueError("restore_history_entry requires path and entry ID")
        elif self.path is not None or self.history_entry_id is not None:
            raise ValueError(f"{self.kind.value} accepts no navigation bindings")
        return self


class NavigationRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    session_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    expected_session_version: int = Field(ge=0)
    intent: NavigationIntent


class NavigationTransactionError(RouteDeckValidationError):
    def __init__(self, code: str, public_message: str) -> None:
        super().__init__(code)
        self.code = code
        self.public_message = public_message


PublicKeyValidatorFactory = Callable[[RouteDeckSession], PublicRouteKeyValidator | None]
IdFactory = Callable[[str], str]


@dataclass(frozen=True)
class RouteDeckNavigationRunner:
    """Own exact route entry, canonical history, and persisted navigation writes."""

    app: BoundRouteDeckApp
    store: RouteDeckSessionStore
    operation_runner: RouteDeckOperationRunner
    clock: Clock
    notifier: RouteDeckNotifier
    id_factory: IdFactory
    public_key_validator_factory: PublicKeyValidatorFactory

    async def navigate(self, request: NavigationRequest) -> SessionSnapshot:
        fingerprint = canonical_json_fingerprint(
            "routedeck.navigation-request.v1",
            request.model_dump(mode="json"),
        )
        recorded = await self.store.find_mutation(
            request.session_id,
            request.request_id,
        )
        if recorded is not None:
            if (
                recorded.kind is not MutationKind.NAVIGATION
                or recorded.request_fingerprint != fingerprint
            ):
                raise NavigationTransactionError(
                    "request_id_reused",
                    "This request ID was already used for another mutation.",
                )
            return await self.store.load(request.session_id)
        structural = self._structural_match(request.intent)
        stored_operation = await self.store.find_attempt(
            request.session_id,
            request.request_id,
        )
        if stored_operation is not None:
            if (
                structural is not None
                and self._node(structural.node_id).entry is not None
            ):
                return await self._run_entry(request, structural)
            raise NavigationTransactionError(
                "request_id_reused",
                "This request ID was already used for another operation.",
            )
        initial = await self.store.load(request.session_id)
        if initial.session_version != request.expected_session_version:
            raise NavigationTransactionError(
                "version_conflict",
                "The session changed before navigation was applied.",
            )
        if structural is not None and self._same_location(initial.state, structural):
            exact_current_restore = (
                request.intent.kind is NavigationIntentKind.RESTORE_HISTORY_ENTRY
                and initial.state.current.entry_id == request.intent.history_entry_id
            )
            if (
                request.intent.kind is not NavigationIntentKind.RESTORE_HISTORY_ENTRY
                or exact_current_restore
            ):
                self._authorize_path(
                    initial.state,
                    request.intent.path or "",
                    structural,
                )
                return await self._commit_navigation_noop(
                    request,
                    initial,
                    fingerprint,
                )
        if (
            structural is not None
            and request.intent.kind is NavigationIntentKind.OPEN_PATH
        ):
            node = self._node(structural.node_id)
            if node.entry is not None:
                return await self._run_entry(request, structural)
        return await self._commit_navigation(request, structural, fingerprint)

    def _structural_match(
        self, intent: NavigationIntent
    ) -> StructuralRouteMatch | None:
        if intent.kind not in {
            NavigationIntentKind.OPEN_PATH,
            NavigationIntentKind.RESTORE_HISTORY_ENTRY,
        }:
            return None
        if intent.path is None:
            raise NavigationTransactionError(
                "invalid_navigation", "A path is required."
            )
        match = self.app.app.routes.match(intent.path)
        self._require_canonical_path(intent.path, match)
        return match

    async def _run_entry(
        self,
        request: NavigationRequest,
        match: StructuralRouteMatch,
    ) -> SessionSnapshot:
        node = self._node(match.node_id)
        entry = node.entry
        if entry is None:
            raise RuntimeError("Route entry disappeared after structural matching")
        route_params = dict(match.params)
        arguments = {
            binding.argument: route_params[binding.parameter]
            for binding in entry.bindings
        }
        result = await self.operation_runner.run(
            OperationRequest(
                session_id=request.session_id,
                request_id=request.request_id,
                expected_session_version=request.expected_session_version,
                operation_id=entry.operation.id,
                source=OperationSource.ROUTE,
                arguments=FrozenJsonObject(arguments),
            ),
            route_entry=RouteEntryInvocation(
                location=Location(
                    node_id=match.node_id,
                    route_params=match.route_params,
                )
            ),
        )
        if (
            result.disposition is not OperationDisposition.COMPLETED
            or result.outcome != entry.outcome
        ):
            failure = result.failure
            raise NavigationTransactionError(
                failure.code if failure is not None else "route_entry_failed",
                (
                    failure.public_message
                    if failure is not None
                    else "The requested route could not be opened."
                ),
            )
        return await self.store.load(request.session_id)

    async def _commit_navigation(
        self,
        request: NavigationRequest,
        structural: StructuralRouteMatch | None,
        fingerprint: str,
    ) -> SessionSnapshot:
        lease = await self.store.acquire_turn(
            TurnClaim(
                session_id=request.session_id,
                expected_session_version=request.expected_session_version,
                request_id=request.request_id,
                request_fingerprint=fingerprint,
                owner_kind=TurnOwnerKind.NAVIGATION,
            )
        )
        try:
            snapshot = await self.store.load(request.session_id)
            if snapshot.session_version != request.expected_session_version:
                raise NavigationTransactionError(
                    "version_conflict",
                    "The session changed before navigation was applied.",
                )
            next_state = self._apply_intent(snapshot.state, request.intent, structural)
            if next_state is snapshot.state or next_state == snapshot.state:
                return await self.store.commit_state(
                    lease,
                    snapshot.session_version,
                    snapshot.state,
                    (),
                    self._navigation_commit(),
                )
            next_state = (
                RouteDeckSessionAggregate(next_state)
                .record_public_events(1)
                .commit()
            )
            event = CanonicalRouteDeckEvent(
                event_id=self.id_factory("event"),
                cursor=next_state.event_cursor,
                event_type=RouteDeckEventType.NAVIGATION_CHANGED,
                session_id=next_state.session_id,
                session_version=next_state.session_version,
                projection_version=next_state.projection_version,
                created_at=self.clock.now(),
                payload=PublicEventPayload(
                    node_id=next_state.current.node_id,
                    request_id=request.request_id,
                    status_code=next_state.public_state.status_code,
                ),
            )
            saved = await self.store.commit_state(
                lease,
                snapshot.session_version,
                next_state,
                (event,),
                self._navigation_commit(),
            )
            await notify_event_wakeup(self.notifier, saved.session_id, (event,))
            return saved
        finally:
            await self.store.release_turn(lease)

    async def _commit_navigation_noop(
        self,
        request: NavigationRequest,
        snapshot: SessionSnapshot,
        fingerprint: str,
    ) -> SessionSnapshot:
        lease = await self.store.acquire_turn(
            TurnClaim(
                session_id=request.session_id,
                expected_session_version=request.expected_session_version,
                request_id=request.request_id,
                request_fingerprint=fingerprint,
                owner_kind=TurnOwnerKind.NAVIGATION,
            )
        )
        try:
            return await self.store.commit_state(
                lease,
                snapshot.session_version,
                snapshot.state,
                (),
                self._navigation_commit(),
            )
        finally:
            await self.store.release_turn(lease)

    @staticmethod
    def _navigation_commit() -> MutationCommit:
        return MutationCommit(
            kind=MutationKind.NAVIGATION,
            status=MutationStatus.COMPLETED,
        )

    def _apply_intent(
        self,
        session: RouteDeckSession,
        intent: NavigationIntent,
        structural: StructuralRouteMatch | None,
    ) -> RouteDeckSession:
        validator = self.public_key_validator_factory(session)
        engine = NavigationEngine(self.app.app)
        now = self.clock.now()
        if intent.kind is NavigationIntentKind.OPEN_PATH:
            if structural is None or intent.path is None:
                raise RuntimeError("Open navigation is missing its structural route")
            self._authorize_path(session, intent.path, structural)
            return engine.open(
                session,
                node_id=structural.node_id,
                route_params=structural.params,
                public_key_validator=validator,
                resume_handle=structural.resume_handle,
                now=now,
            )
        if intent.kind is NavigationIntentKind.BACK:
            return engine.back(session, public_key_validator=validator, now=now)
        if intent.kind is NavigationIntentKind.FORWARD:
            return engine.forward(session, public_key_validator=validator, now=now)
        if intent.kind is NavigationIntentKind.CANCEL:
            return engine.cancel(session, public_key_validator=validator, now=now)
        if intent.kind is NavigationIntentKind.RESTORE_HISTORY_ENTRY:
            if (
                structural is None
                or intent.path is None
                or intent.history_entry_id is None
            ):
                raise RuntimeError("History restore is missing exact bindings")
            self._authorize_path(session, intent.path, structural)
            restored = engine.restore_history_entry(
                session,
                intent.history_entry_id,
                public_key_validator=validator,
                now=now,
            )
            if not self._same_location(restored, structural):
                raise NavigationTransactionError(
                    "history_path_mismatch",
                    "The browser history path does not match its RouteDeck entry.",
                )
            return restored
        raise RuntimeError(f"Unsupported navigation intent: {intent.kind.value}")

    def _authorize_path(
        self,
        session: RouteDeckSession,
        path: str,
        structural: StructuralRouteMatch,
    ) -> None:
        node = self._node(structural.node_id)
        if (
            node.entry is not None
            and node.route.deep_link_policy is DeepLinkPolicy.SHAREABLE
        ):
            return
        DeepLinkEngine(self.app.app).open(
            path,
            session=session,
            now=self.clock.now(),
            public_key_validator=self.public_key_validator_factory(session),
        )

    def _require_canonical_path(self, path: str, match: StructuralRouteMatch) -> None:
        params: dict[str, str] = dict(match.params)
        if match.resume_handle is not None:
            params["resume_handle"] = match.resume_handle
        canonical = self.app.app.routes.encode(match.node_id, params)
        if path != canonical:
            raise NavigationTransactionError(
                "route_not_canonical",
                "The requested route is not canonical.",
            )

    @staticmethod
    def _same_location(session: RouteDeckSession, match: StructuralRouteMatch) -> bool:
        return (
            session.current.node_id == match.node_id
            and session.current.route_params == match.route_params
        )

    def _node(self, node_id: str):
        node = next(
            (
                candidate
                for candidate in self.app.app.spec.nodes
                if candidate.id == node_id
            ),
            None,
        )
        if node is None:
            raise NavigationTransactionError(
                "route_not_found", "The requested route is unavailable."
            )
        return node


__all__ = [
    "NavigationIntent",
    "NavigationIntentKind",
    "NavigationRequest",
    "NavigationTransactionError",
    "RouteDeckNavigationRunner",
]
