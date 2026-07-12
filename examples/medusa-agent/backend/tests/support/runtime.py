from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import SecretStr

from medusa_agent.composition import build_medusa_runtime, compile_medusa_app_spec
from medusa_agent.features.cart import (
    BUYER_MARKET_PROVIDER,
    CART_ADD_ITEM,
    CART_CREATE,
    CART_EXISTS_GUARD,
    CART_OPEN,
    CART_STATE_PROVIDER,
)
from medusa_agent.features.cart.feature import (
    CART_ABSENT_GUARD,
    CART_BINDING_PROVIDER,
    CART_ITEMS_PROVIDER,
    CART_REMOVE_ITEM,
    CART_UPDATE_ITEM,
)
from medusa_agent.features.catalog import (
    CATALOG_LIST,
    CATALOG_PRODUCTS_PROVIDER,
    CATALOG_PRODUCT_PROVIDER,
    CATALOG_SEARCH,
    CATALOG_VARIANTS_PROVIDER,
    CONTINUE_SHOPPING,
    OPEN_PRODUCT,
    OPEN_PRODUCT_BY_ROUTE,
    PUBLIC_PRODUCT_GUARD,
    SELECT_VARIANT,
    VARIANT_ALLOWED_GUARD,
)
from medusa_agent.features.checkout import (
    CHECKOUT_FACTS_PROVIDER,
    CHECKOUT_READY_GUARD,
    CHECKOUT_START,
    CONTACT_VALID_GUARD,
    SAVE_CONTACT,
    SELECT_SHIPPING,
    SHIPPING_OPTIONS_PROVIDER,
    SHIPPING_VALID_GUARD,
)
from medusa_agent.medusa.client.protocol import MedusaStoreClient
from medusa_agent.session import BuyerMarket, create_medusa_session
from routedeck_core.app import ContextProvider, Guard, OperationHandler
from routedeck_core.contracts.conversation import FinalizedConversationTurn
from routedeck_core.contracts.events import CanonicalRouteDeckEvent, EventPage
from routedeck_core.contracts.failures import RouteDeckFailure
from routedeck_core.contracts.mutations import MutationCommit, MutationRecord
from routedeck_core.contracts.operations import (
    GuardRef,
    OperationOutcome,
    OperationRequest,
    OperationSource,
    OperationRef,
    ProviderRef,
)
from routedeck_core.contracts.projection import FrozenJsonObject
from routedeck_core.contracts.session import (
    JournaledExecutionResult,
    Location,
    LocationParameter,
    PendingReview,
    RouteDeckSession,
    SessionSnapshot,
    StoredOperationAttempt,
)
from routedeck_core.ports.executor import ExecutionContext
from routedeck_core.navigation import RouteDeckNavigationRunner
from routedeck_core.state.leases import ExecutionClaim, TurnClaim, TurnLease
from routedeck_core.supervision.guards import (
    GuardDecision,
    GuardInvocationContext,
    ProviderInvocationContext,
    ProviderResult,
)
from routedeck_core.supervision import RouteDeckOperationRunner


@dataclass
class RecordingNotifier:
    notifications: list[tuple[str, tuple[CanonicalRouteDeckEvent, ...]]] = field(
        default_factory=list
    )

    async def notify(
        self,
        session_id: str,
        events: Sequence[CanonicalRouteDeckEvent],
    ) -> None:
        self.notifications.append((session_id, tuple(events)))


@dataclass(frozen=True)
class FixedClock:
    current: datetime = datetime(2029, 1, 1, tzinfo=UTC)

    def now(self) -> datetime:
        return self.current


@dataclass
class SequentialIds:
    counters: Counter[str] = field(default_factory=Counter)

    def __call__(self, kind: str) -> str:
        self.counters[kind] += 1
        return f"{kind}-{self.counters[kind]}"


class ExplicitTestSessionStore:
    """In-memory test port used only by the isolated Medusa contract test."""

    def __init__(self, session: RouteDeckSession) -> None:
        self.session = session
        self.attempts: dict[tuple[str, str], StoredOperationAttempt] = {}
        self.reviews: dict[tuple[str, str], PendingReview] = {}
        self.lease: TurnLease | None = None
        self.claims: dict[str, ExecutionClaim] = {}
        self.child_request_id: str | None = None
        self.fail_next_commit_attempt = False

    async def load(self, session_id: str) -> SessionSnapshot:
        if session_id != self.session.session_id:
            raise KeyError(session_id)
        return SessionSnapshot(state=self.session)

    async def find_mutation(
        self,
        session_id: str,
        request_id: str,
    ) -> MutationRecord | None:
        del session_id, request_id
        return None

    async def find_attempt(
        self,
        session_id: str,
        request_id: str,
    ) -> StoredOperationAttempt | None:
        return self.attempts.get((session_id, request_id))

    async def find_review(
        self,
        session_id: str,
        review_id: str,
    ) -> PendingReview | None:
        return self.reviews.get((session_id, review_id))

    async def acquire_turn(self, claim: TurnClaim) -> TurnLease:
        if self.lease is not None:
            raise AssertionError("test runtime permits one explicit turn")
        self.lease = TurnLease(
            capability=SecretStr(f"lease:{claim.request_id}"),
            fencing_token=1,
            session_id=claim.session_id,
            request_id=claim.request_id,
        )
        return self.lease

    async def claim_child_attempt(
        self,
        lease: TurnLease,
        request_id: str,
        request_fingerprint: str,
    ) -> None:
        del request_fingerprint
        self._require_lease(lease)
        if self.child_request_id is not None:
            raise AssertionError("test runtime permits one child attempt")
        self.child_request_id = request_id

    async def release_child_attempt(
        self,
        lease: TurnLease,
        request_id: str,
    ) -> None:
        self._require_lease(lease)
        if self.child_request_id != request_id:
            raise AssertionError("test child attempt mismatch")
        self.child_request_id = None

    async def claim_execution(
        self,
        lease: TurnLease,
        record: StoredOperationAttempt,
    ) -> ExecutionClaim:
        self._require_lease(lease)
        attempt = record.attempt
        claim = ExecutionClaim(
            capability=SecretStr(f"execution:{attempt.attempt_id}"),
            fencing_token=lease.fencing_token,
            session_id=lease.session_id,
            request_id=attempt.request_id,
            attempt_id=attempt.attempt_id,
        )
        self.claims[claim.attempt_id] = claim
        self.attempts[(claim.session_id, claim.request_id)] = record
        return claim

    async def recover_execution_claim(
        self,
        lease: TurnLease,
        attempt_id: str,
    ) -> ExecutionClaim:
        self._require_lease(lease)
        return self.claims[attempt_id]

    async def record_execution_started(
        self,
        claim: ExecutionClaim,
        record: StoredOperationAttempt,
    ) -> None:
        self._require_claim(claim)
        self.attempts[(claim.session_id, claim.request_id)] = record

    async def record_execution_result(
        self,
        claim: ExecutionClaim,
        result: JournaledExecutionResult,
        record: StoredOperationAttempt,
    ) -> None:
        self._require_claim(claim)
        if record.journaled_result != result:
            raise AssertionError("runner must supply the journaled aggregate")
        self.attempts[(claim.session_id, claim.request_id)] = record

    async def commit_attempt(
        self,
        claim: ExecutionClaim,
        expected_session_version: int,
        next_state: RouteDeckSession,
        events: Sequence[CanonicalRouteDeckEvent],
        record: StoredOperationAttempt,
    ) -> SessionSnapshot:
        self._require_claim(claim)
        if self.fail_next_commit_attempt:
            self.fail_next_commit_attempt = False
            raise RuntimeError("injected test commit failure")
        if self.session.session_version != expected_session_version:
            raise AssertionError("test session version mismatch")
        if record.attempt.attempt_id != claim.attempt_id:
            raise AssertionError("commit must identify the child attempt")
        if len(events) != 1:
            raise AssertionError("test operation must commit one public event")
        self.session = next_state
        self.attempts[(claim.session_id, claim.request_id)] = record
        return SessionSnapshot(state=next_state)

    async def commit_supervision(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        events: Sequence[CanonicalRouteDeckEvent],
        record: StoredOperationAttempt,
    ) -> SessionSnapshot:
        del lease, expected_session_version, next_state, events, record
        raise AssertionError("cart.create reaches an execution claim")

    async def release_turn(self, lease: TurnLease) -> None:
        self._require_lease(lease)
        self.lease = None

    async def create(self, initial: RouteDeckSession) -> SessionSnapshot:
        raise AssertionError("test runtime session is created explicitly")

    async def create_for_request(
        self,
        initial: RouteDeckSession,
        request_id: str,
        request_fingerprint: str,
    ) -> SessionSnapshot:
        del initial, request_id, request_fingerprint
        raise AssertionError("test runtime session is created explicitly")

    async def stage_review(
        self,
        lease: TurnLease,
        expected_session_version: int,
        record: StoredOperationAttempt,
        next_state: RouteDeckSession,
        events: Sequence[CanonicalRouteDeckEvent],
        parent_mutation: MutationCommit | None = None,
    ) -> SessionSnapshot:
        del lease, expected_session_version, record, next_state, events, parent_mutation
        raise AssertionError("cart.create must not stage a review")

    async def commit_state(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        events: Sequence[CanonicalRouteDeckEvent],
        mutation: MutationCommit,
    ) -> SessionSnapshot:
        del lease, expected_session_version, next_state, events, mutation
        raise AssertionError("cart.create commits through commit_attempt")

    async def finalize_turn(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        turns: Sequence[FinalizedConversationTurn],
        events: Sequence[CanonicalRouteDeckEvent],
        mutation: MutationCommit,
    ) -> SessionSnapshot:
        del lease, expected_session_version, next_state, turns, events, mutation
        raise AssertionError("cart.create is not a model turn")

    async def interrupt_turn(
        self,
        lease: TurnLease,
        expected_session_version: int,
        next_state: RouteDeckSession,
        failure: RouteDeckFailure,
        events: Sequence[CanonicalRouteDeckEvent],
        mutation: MutationCommit,
    ) -> SessionSnapshot:
        del lease, expected_session_version, next_state, failure, events, mutation
        raise AssertionError("cart.create is not an interrupted model turn")

    async def mark_external_outcome_unknown(
        self,
        claim: ExecutionClaim,
        expected_session_version: int,
        record: StoredOperationAttempt,
        next_state: RouteDeckSession,
        events: Sequence[CanonicalRouteDeckEvent],
    ) -> SessionSnapshot:
        del claim, expected_session_version, record, next_state, events
        raise AssertionError("typed cart creation must not become ambiguous")

    async def events_after(
        self,
        session_id: str,
        cursor: int,
        limit: int,
    ) -> EventPage:
        del session_id, limit
        return EventPage(events=(), next_cursor=cursor, has_more=False)

    async def load_private_blob(self, session_id: str, form_id: str) -> bytes | None:
        del session_id, form_id
        raise AssertionError("cart.create does not read private form blobs")

    async def save_private_blob(
        self,
        lease: TurnLease,
        expected_session_version: int,
        form_id: str,
        encrypted_value: bytes,
        next_state: RouteDeckSession,
        events: Sequence[CanonicalRouteDeckEvent],
        mutation: MutationCommit,
    ) -> SessionSnapshot:
        del (
            lease,
            expected_session_version,
            form_id,
            encrypted_value,
            next_state,
            events,
            mutation,
        )
        raise AssertionError("cart.create does not write private form blobs")

    def _require_lease(self, lease: TurnLease) -> None:
        if self.lease != lease:
            raise AssertionError("test lease mismatch")

    def _require_claim(self, claim: ExecutionClaim) -> None:
        if self.claims.get(claim.attempt_id) != claim:
            raise AssertionError("test execution claim mismatch")


@dataclass(frozen=True)
class BuyerMarketProvider:
    market: BuyerMarket

    async def __call__(self, context: ProviderInvocationContext) -> ProviderResult:
        del context
        return ProviderResult(
            values=FrozenJsonObject(
                {
                    "region_id": self.market.region_handle,
                    "country_code": self.market.country_code,
                    "sales_channel_id": self.market.sales_channel_handle,
                }
            )
        )


class UnexpectedHandler:
    async def __call__(
        self,
        arguments: Mapping[str, Any],
        context: ExecutionContext,
    ) -> OperationOutcome:
        del arguments, context
        raise AssertionError("an unselected Medusa operation executed")


class UnexpectedProvider:
    async def __call__(self, context: ProviderInvocationContext) -> ProviderResult:
        del context
        raise AssertionError("an undeclared provider executed")


class UnexpectedGuard:
    async def __call__(self, context: GuardInvocationContext) -> GuardDecision:
        del context
        raise AssertionError("an undeclared guard executed")


class UnexpectedPrivateFormReader:
    async def load_contact(self, session_id: str, form_handle: str):
        del session_id, form_handle
        raise AssertionError("a private checkout form was not selected for this test")


@dataclass(frozen=True)
class TestMedusaRuntime:
    runner: RouteDeckOperationRunner
    navigation: RouteDeckNavigationRunner
    store: ExplicitTestSessionStore
    notifier: RecordingNotifier


def build_test_medusa_runtime(
    *,
    client: MedusaStoreClient,
    market: BuyerMarket,
    initial_location: Location | None = None,
) -> TestMedusaRuntime:
    compiled = compile_medusa_app_spec()
    location = initial_location or Location(
        node_id="catalog.product",
        route_params=(
            LocationParameter(
                name="product_handle",
                value="product-public-1",
            ),
        ),
    )
    base_session = create_medusa_session(session_id="session-1", market=market)
    if location.entry_id is None:
        location = location.model_copy(
            update={"entry_id": base_session.current.entry_id}
        )
    session = base_session.model_copy(update={"current": location})
    store = ExplicitTestSessionStore(session)
    notifier = RecordingNotifier()
    composed_handler_ids = {
        CART_CREATE.id,
        CART_ADD_ITEM.id,
        CART_OPEN.id,
        CART_UPDATE_ITEM.id,
        CART_REMOVE_ITEM.id,
        CATALOG_LIST.id,
        CATALOG_SEARCH.id,
        OPEN_PRODUCT.id,
        OPEN_PRODUCT_BY_ROUTE.id,
        SELECT_VARIANT.id,
        CONTINUE_SHOPPING.id,
        CHECKOUT_START.id,
        SAVE_CONTACT.id,
        SELECT_SHIPPING.id,
        "checkout.select_payment",
        "checkout.place_order",
        "orders.reconcile",
    }
    handlers: dict[OperationRef, OperationHandler] = {
        operation.ref: UnexpectedHandler()
        for operation in compiled.operations.values()
        if operation.id not in composed_handler_ids
    }
    composed_provider_ids = {
        BUYER_MARKET_PROVIDER.id,
        CART_STATE_PROVIDER.id,
        CART_BINDING_PROVIDER.id,
        CART_ITEMS_PROVIDER.id,
        CATALOG_PRODUCTS_PROVIDER.id,
        CATALOG_PRODUCT_PROVIDER.id,
        CATALOG_VARIANTS_PROVIDER.id,
        CHECKOUT_FACTS_PROVIDER.id,
        SHIPPING_OPTIONS_PROVIDER.id,
        "checkout.payment_providers",
        "orders.confirmed_order",
    }
    providers: dict[ProviderRef, ContextProvider] = {
        provider.ref: (
            BuyerMarketProvider(market)
            if provider.id == BUYER_MARKET_PROVIDER.id
            else UnexpectedProvider()
        )
        for provider in compiled.providers.values()
        if provider.id not in composed_provider_ids
    }
    composed_guard_ids = {
        CART_ABSENT_GUARD.id,
        CART_EXISTS_GUARD.id,
        PUBLIC_PRODUCT_GUARD.id,
        VARIANT_ALLOWED_GUARD.id,
        CHECKOUT_READY_GUARD.id,
        CONTACT_VALID_GUARD.id,
        SHIPPING_VALID_GUARD.id,
        "checkout.payment_valid",
        "checkout.review_current",
    }
    guards: dict[GuardRef, Guard] = {
        guard.ref: UnexpectedGuard()
        for guard in compiled.guards.values()
        if guard.id not in composed_guard_ids
    }
    runtime = build_medusa_runtime(
        client=client,
        private_forms=UnexpectedPrivateFormReader(),
        configured_payment_provider_id="pp_system_default",
        handlers=handlers,
        providers=providers,
        guards=guards,
        store=store,
        clock=FixedClock(),
        notifier=notifier,
        id_factory=SequentialIds(),
        review_ttl=timedelta(minutes=10),
        default_session_id=session.session_id,
        initial_market=market,
    )
    return TestMedusaRuntime(
        runner=runtime.runner,
        navigation=runtime.navigation,
        store=store,
        notifier=notifier,
    )


def operation_request(
    *,
    operation_id: str,
    source: OperationSource,
    request_id: str,
) -> OperationRequest:
    return OperationRequest(
        session_id="session-1",
        request_id=request_id,
        expected_session_version=1,
        operation_id=operation_id,
        source=source,
        arguments=FrozenJsonObject({}),
    )


__all__ = ["build_test_medusa_runtime", "operation_request"]
