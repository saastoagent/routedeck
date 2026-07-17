from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest
from pydantic import SecretStr

from medusa_agent.composition import compile_medusa_app
from routedeck_core.app import BoundApplication, FeatureBindings
from routedeck_core.contracts.events import RouteDeckEvent
from routedeck_core.contracts.mutations import MutationCommit, MutationRecord
from routedeck_core.contracts.session import RouteDeckSession, SessionSnapshot
from routedeck_core.navigation import (
    NavigationIntent,
    NavigationIntentKind,
    NavigationRequest,
    NavigationTransactionError,
    RouteDeckNavigationRunner,
)
from routedeck_core.navigation.engine import NavigationEngine
from routedeck_core.state.leases import TurnClaim, TurnLease
from routedeck_testing.factories import session_factory


@dataclass(frozen=True)
class CatalogValidator:
    def is_valid(self, key: str, value: str) -> bool:
        return key == "product_handle" and value == "t-shirt"


@dataclass(frozen=True)
class FixedClock:
    def now(self) -> datetime:
        return datetime(2029, 1, 1, tzinfo=UTC)


@dataclass
class RecordingStore:
    state: RouteDeckSession
    lease: TurnLease | None = None
    claim: TurnClaim | None = None
    events: list[RouteDeckEvent] = field(default_factory=list)
    mutations: dict[str, MutationRecord] = field(default_factory=dict)

    async def load(self, session_id: str) -> SessionSnapshot:
        assert session_id == self.state.session_id
        return SessionSnapshot(state=self.state)

    async def find_attempt(self, session_id: str, request_id: str):
        del session_id, request_id
        return None

    async def find_mutation(
        self,
        session_id: str,
        request_id: str,
    ) -> MutationRecord | None:
        assert session_id == self.state.session_id
        return self.mutations.get(request_id)

    async def acquire_turn(self, claim: TurnClaim) -> TurnLease:
        assert self.lease is None
        assert claim.session_id == self.state.session_id
        assert claim.expected_session_version == self.state.session_version
        self.lease = TurnLease(
            capability=SecretStr(f"lease:{claim.request_id}"),
            fencing_token=1,
            session_id=claim.session_id,
            request_id=claim.request_id,
        )
        self.claim = claim
        return self.lease

    async def commit_state(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
        mutation: MutationCommit,
    ) -> SessionSnapshot:
        assert lease == self.lease
        assert expected_session_version == self.state.session_version
        self.state = next_state
        self.events.extend(events)
        assert self.claim is not None
        self.mutations[lease.request_id] = MutationRecord(
            **mutation.model_dump(mode="python"),
            session_id=lease.session_id,
            request_id=lease.request_id,
            request_fingerprint=self.claim.request_fingerprint,
            committed_session_version=next_state.session_version,
            committed_projection_version=next_state.projection_version,
            committed_event_cursor=next_state.event_cursor,
        )
        return SessionSnapshot(state=next_state)

    async def release_turn(self, lease: TurnLease) -> None:
        assert lease == self.lease
        self.lease = None
        self.claim = None


@dataclass
class UnexpectedEntryRunner:
    calls: int = 0

    async def run(self, *args, **kwargs):
        del args, kwargs
        self.calls += 1
        raise AssertionError("history restore must not execute a route entry")


@dataclass
class RecordingNotifier:
    events: list[RouteDeckEvent] = field(default_factory=list)

    async def notify(
        self,
        session_id: str,
        events: Sequence[RouteDeckEvent],
    ) -> None:
        assert session_id
        self.events.extend(events)


def _runner(session: RouteDeckSession):
    app = compile_medusa_app()
    store = RecordingStore(session)
    operations = UnexpectedEntryRunner()
    runner = RouteDeckNavigationRunner(
        app=BoundApplication(
            app=app,
            bindings=FeatureBindings(handlers={}, providers={}, guards={}),
        ),
        store=store,  # type: ignore[arg-type]
        operation_runner=operations,  # type: ignore[arg-type]
        clock=FixedClock(),
        notifier=RecordingNotifier(),
        id_factory=lambda kind: f"{kind}-1",
        public_key_validator_factory=lambda _session: CatalogValidator(),
    )
    return runner, store, operations


def _product_timeline(*, return_home: bool) -> RouteDeckSession:
    app = compile_medusa_app()
    engine = NavigationEngine(app)
    home = session_factory(app=app, node_id="buyer.home")
    product = engine.open(
        home,
        node_id="catalog.product",
        route_params={"product_handle": "t-shirt"},
        public_key_validator=CatalogValidator(),
    )
    if not return_home:
        return product
    return engine.open(
        product,
        node_id="buyer.home",
        public_key_validator=CatalogValidator(),
    )


@pytest.mark.asyncio
async def test_restore_entry_route_preserves_the_original_timeline() -> None:
    session = _product_timeline(return_home=True)
    product_entry_id = session.back_stack[-1].entry_id
    runner, store, operations = _runner(session)

    restored = await runner.navigate(
        NavigationRequest(
            session_id=session.session_id,
            request_id="restore-product-entry",
            expected_session_version=session.session_version,
            intent=NavigationIntent(
                kind=NavigationIntentKind.RESTORE_HISTORY_ENTRY,
                path="/products/t-shirt",
                history_entry_id=product_entry_id,
            ),
        )
    )

    assert operations.calls == 0
    assert tuple(item.entry_id for item in restored.state.back_stack) == (1,)
    assert restored.state.current.entry_id == 2
    assert tuple(item.entry_id for item in restored.state.forward_stack) == (3,)
    assert restored.state.next_history_entry_id == 4
    assert store.state == restored.state


@pytest.mark.asyncio
async def test_restore_same_path_with_another_entry_id_fails() -> None:
    session = _product_timeline(return_home=False)
    runner, store, operations = _runner(session)

    with pytest.raises(NavigationTransactionError) as raised:
        await runner.navigate(
            NavigationRequest(
                session_id=session.session_id,
                request_id="mismatched-product-entry",
                expected_session_version=session.session_version,
                intent=NavigationIntent(
                    kind=NavigationIntentKind.RESTORE_HISTORY_ENTRY,
                    path="/products/t-shirt",
                    history_entry_id=1,
                ),
            )
        )

    assert raised.value.code == "history_path_mismatch"
    assert operations.calls == 0
    assert store.state == session


@pytest.mark.asyncio
async def test_navigation_retry_replays_before_the_stale_version_check() -> None:
    session = _product_timeline(return_home=True)
    runner, store, _operations = _runner(session)
    request = NavigationRequest(
        session_id=session.session_id,
        request_id="back-once",
        expected_session_version=session.session_version,
        intent=NavigationIntent(kind=NavigationIntentKind.BACK),
    )

    first = await runner.navigate(request)
    replay = await runner.navigate(request)

    assert replay == first
    assert len(store.events) == 1
