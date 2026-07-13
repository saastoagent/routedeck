from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

import routedeck_sqlalchemy
from routedeck_core.app import (
    BoundRouteDeckApp,
    ContextProvider,
    Guard,
    OperationHandler,
)
from routedeck_core.contracts.operations import (
    GuardRef,
    OperationDisposition,
    OperationRef,
    OperationRequest,
    OperationSource,
    ProviderRef,
)
from routedeck_core.contracts.retention import RouteDeckRetentionPolicy
from routedeck_core.navigation import RouteDeckNavigationRunner
from routedeck_core.ports import (
    Clock,
    RegisteredOperationExecutor,
    RouteDeckNotifier,
    RouteDeckSessionStore,
)
from routedeck_core.state.session import navgraph_version, require_compatible_session
from routedeck_core.supervision import RouteDeckOperationRunner

from .bindings import bind_medusa_app
from .composition import compile_medusa_app_spec
from .features.cart import CART_CREATE, CART_CREATED_OUTCOME
from .features.catalog import CatalogRouteKeyValidator
from .features.checkout import (
    CheckoutPrivateFormReader,
    EncryptedCheckoutPrivateFormReader,
)
from .medusa.client.protocol import MedusaStoreClient
from .request_ids import initial_cart_request_id

if TYPE_CHECKING:
    from .session import BuyerMarket


@dataclass(frozen=True)
class MedusaRuntime:
    """The product composition result; RouteDeck remains the runtime owner."""

    app: BoundRouteDeckApp
    runner: RouteDeckOperationRunner
    navigation: RouteDeckNavigationRunner
    store: RouteDeckSessionStore
    default_session_id: str
    initial_market: BuyerMarket

    async def create_session(self, *, session_id: str | None = None):
        """Create the buyer session, then journal its one real cart creation."""

        from .session import create_medusa_session

        state = create_medusa_session(
            session_id=session_id or self.default_session_id,
            market=self.initial_market,
        )
        created = await self.store.create(state)
        return await self.initialize_session(created)

    async def initialize_session(self, created_snapshot):
        """Run the product-owned startup exactly once for a created session."""

        state = created_snapshot.state
        result = await self.runner.run(
            OperationRequest(
                session_id=state.session_id,
                request_id=initial_cart_request_id(state.session_id),
                expected_session_version=created_snapshot.session_version,
                operation_id=CART_CREATE.id,
                source=OperationSource.SYSTEM,
            )
        )
        if result.disposition is OperationDisposition.COMPLETED:
            if result.outcome != CART_CREATED_OUTCOME:
                raise RuntimeError(
                    "Medusa session initialization returned an undeclared outcome."
                )
        else:
            raise RuntimeError(
                "Medusa session initialization did not prove cart creation."
            )
        return await self.store.load(state.session_id)

    async def load_session(self, session_id: str | None = None):
        snapshot = await self.store.load(session_id or self.default_session_id)
        require_compatible_session(self.app.app, snapshot.state)
        return snapshot

    async def close(self) -> None:
        close = getattr(self.store, "close", None)
        if close is None or not callable(close):
            raise RuntimeError("configured RouteDeck store has no close boundary")
        await close()


def build_medusa_runtime(
    *,
    client: MedusaStoreClient,
    private_forms: CheckoutPrivateFormReader,
    configured_payment_provider_id: str,
    handlers: Mapping[OperationRef, OperationHandler],
    providers: Mapping[ProviderRef, ContextProvider],
    guards: Mapping[GuardRef, Guard],
    store: RouteDeckSessionStore,
    clock: Clock,
    notifier: RouteDeckNotifier,
    id_factory: Callable[[str], str],
    review_ttl: timedelta,
    default_session_id: str,
    initial_market: BuyerMarket,
) -> MedusaRuntime:
    """Build the Medusa consumer on the generic supervised runner."""

    app = bind_medusa_app(
        client=client,
        private_forms=private_forms,
        configured_payment_provider_id=configured_payment_provider_id,
        buyer_country_code=initial_market.country_code,
        handlers=handlers,
        providers=providers,
        guards=guards,
    )
    runner = RouteDeckOperationRunner(
        app=app,
        store=store,
        executor=RegisteredOperationExecutor(),
        clock=clock,
        notifier=notifier,
        id_factory=id_factory,
        review_ttl=review_ttl,
        resume_capability_ttl=timedelta(hours=24),
        default_session_id=default_session_id,
    )
    navigation = RouteDeckNavigationRunner(
        app=app,
        store=store,
        operation_runner=runner,
        clock=clock,
        notifier=notifier,
        id_factory=id_factory,
        public_key_validator_factory=CatalogRouteKeyValidator.from_session,
    )
    return MedusaRuntime(
        app=app,
        runner=runner,
        navigation=navigation,
        store=store,
        default_session_id=default_session_id,
        initial_market=initial_market,
    )


async def open_persistent_medusa_runtime(
    *,
    database_url: str,
    encryption_key: str | bytes,
    instance_id: str,
    client: MedusaStoreClient,
    configured_payment_provider_id: str,
    handlers: Mapping[OperationRef, OperationHandler],
    providers: Mapping[ProviderRef, ContextProvider],
    guards: Mapping[GuardRef, Guard],
    clock: Clock,
    notifier: RouteDeckNotifier,
    id_factory: Callable[[str], str],
    review_ttl: timedelta,
    default_session_id: str,
    market: BuyerMarket,
    retention_policy: RouteDeckRetentionPolicy | None = None,
    busy_timeout: timedelta = timedelta(seconds=5),
    worker_count: int = 1,
) -> MedusaRuntime:
    """Open the durable RouteDeck authority used by the Medusa product."""

    compiled = compile_medusa_app_spec()
    codec = routedeck_sqlalchemy.FernetSensitiveCodec(encryption_key)
    store = await routedeck_sqlalchemy.SqlAlchemySessionStore.open(
        database_url,
        instance_id=instance_id,
        codec=codec,
        clock=clock,
        retention_policy=retention_policy,
        busy_timeout=busy_timeout,
        worker_count=worker_count,
        expected_navgraph_version=navgraph_version(compiled),
    )
    try:
        return build_medusa_runtime(
            client=client,
            private_forms=EncryptedCheckoutPrivateFormReader(store, codec),
            configured_payment_provider_id=configured_payment_provider_id,
            handlers=handlers,
            providers=providers,
            guards=guards,
            store=store,
            clock=clock,
            notifier=notifier,
            id_factory=id_factory,
            review_ttl=review_ttl,
            default_session_id=default_session_id,
            initial_market=market,
        )
    except BaseException:
        await store.close()
        raise


__all__ = [
    "MedusaRuntime",
    "build_medusa_runtime",
    "open_persistent_medusa_runtime",
]
