from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import routedeck_core
import routedeck_fastapi
import routedeck_langgraph
import routedeck_sqlite
from routedeck_core.app import (
    ApplicationSpec,
    BoundRouteDeckApp,
    CompiledRouteDeckApp,
    ContextProvider,
    FeatureBindings,
    Guard,
    OperationHandler,
    bind_app,
    compile_app,
)
from routedeck_core.contracts.application import CapabilitySpec
from routedeck_core.contracts.navigation import TransitionSpec
from routedeck_core.contracts.operations import (
    GuardRef,
    OperationDisposition,
    OperationRef,
    OperationRequest,
    OperationSource,
    ProviderRef,
)
from routedeck_core.contracts.retention import RouteDeckRetentionPolicy
from routedeck_core.ports import (
    Clock,
    RegisteredOperationExecutor,
    RouteDeckNotifier,
    RouteDeckSessionStore,
)
from routedeck_core.navigation import RouteDeckNavigationRunner
from routedeck_core.supervision import RouteDeckOperationRunner
from routedeck_core.state.session import navgraph_version, require_compatible_session

if TYPE_CHECKING:
    from .session import BuyerMarket

from .features.cart import (
    ADD_ITEM_AFFORDANCE,
    BUYER_MARKET_PROVIDER,
    CART_ADD_ITEM,
    CART_CAPABILITY,
    CART_CREATE,
    CART_CREATED_OUTCOME,
    CART_CREATE_UNKNOWN_RECOVERY,
    CART_EXISTS_GUARD,
    CART_MUTATION_UNKNOWN_RECOVERY,
    CART_NODE,
    CART_OPEN,
    CART_STATE_PROVIDER,
    CART_SUMMARY,
    CREATE_CART_AFFORDANCE,
    CreateCartHandler,
    FEATURE_SPEC as CART_FEATURE,
    OPEN_CART_AFFORDANCE,
)
from .request_ids import initial_cart_request_id
from .features.cart.feature import (
    CART_ABSENT_GUARD,
    CART_BINDING_PROVIDER,
    CART_ITEMS_PROVIDER,
    CART_REMOVE_ITEM,
    CART_UPDATE_ITEM,
)
from .features.cart.guards import CartAbsentGuard, CartExistsGuard
from .features.cart.handlers import (
    AddCartItemHandler,
    OpenCartHandler,
    RemoveCartItemHandler,
    UpdateCartItemHandler,
)
from .features.cart.providers import (
    BuyerMarketProvider,
    CartBindingProvider,
    CartItemsProvider,
    CartStateProvider,
)
from .medusa.client.protocol import MedusaStoreClient
from .features.catalog import (
    BUYER_HOME_NODE,
    CATALOG_BROWSE_NODE,
    CATALOG_LIST,
    CATALOG_PRODUCTS_PROVIDER,
    CATALOG_PRODUCT_PROVIDER,
    CATALOG_PRODUCT_NODE,
    CATALOG_SEARCH,
    CATALOG_VARIANTS_PROVIDER,
    CatalogProvider,
    CatalogRouteKeyValidator,
    CONTINUE_SHOPPING,
    CONTINUE_SHOPPING_AFFORDANCE,
    CurrentCatalogProductProvider,
    FEATURE_SPEC as CATALOG_FEATURE,
    ListCatalogHandler,
    OPEN_PRODUCT,
    OPEN_PRODUCT_BY_ROUTE,
    OpenProductHandler,
    OpenProductByRouteHandler,
    PRODUCT_DETAIL,
    PRODUCT_GRID,
    PUBLIC_PRODUCT_GUARD,
    PublicProductGuard,
    SELECT_VARIANT,
    SearchCatalogHandler,
    SelectVariantHandler,
    VARIANT_ALLOWED_GUARD,
    VariantAllowedGuard,
)
from .features.checkout import (
    CHECKOUT_CAPABILITY,
    CHECKOUT_FACTS_PROVIDER,
    CHECKOUT_READY_GUARD,
    CHECKOUT_START,
    CONTACT_VALID_GUARD,
    CONTACT_NODE,
    CheckoutFactsProvider,
    CheckoutPrivateFormReader,
    CheckoutReadyGuard,
    ContactValidGuard,
    EncryptedCheckoutPrivateFormReader,
    FEATURE_SPEC as CHECKOUT_FEATURE,
    PLACE_ORDER,
    PAYMENT_PROVIDERS_PROVIDER,
    PAYMENT_VALID_GUARD,
    PaymentProvidersProvider,
    PaymentValidGuard,
    REVIEW_NODE,
    REVIEW_CURRENT_GUARD,
    ReviewCurrentGuard,
    SAVE_CONTACT,
    SELECT_SHIPPING,
    SELECT_PAYMENT,
    SHIPPING_OPTIONS_PROVIDER,
    SHIPPING_VALID_GUARD,
    SaveContactHandler,
    SelectShippingHandler,
    SelectPaymentHandler,
    ShippingOptionsProvider,
    ShippingValidGuard,
    START_CHECKOUT_AFFORDANCE,
    StartCheckoutHandler,
)
from .features.orders import (
    BoundOrderProvider,
    CONFIRMATION_NODE,
    FEATURE_SPEC as ORDERS_FEATURE,
    ORDER_CONFIRMATION,
    ORDER_PROVIDER,
    ORDERS_CAPABILITY,
    OrdersContinueShoppingHandler,
    PlaceOrderHandler,
    RECONCILE_ORDER,
    RECONCILE_ORDER_AFFORDANCE,
    ReconcileOrderHandler,
)
from .features.checkout.feature import CHECKOUT_RECOVERY


_FRAMEWORK_PACKAGES = (
    routedeck_core,
    routedeck_fastapi,
    routedeck_langgraph,
    routedeck_sqlite,
)


_COMPOSED_PRODUCT_GRID = PRODUCT_GRID.model_copy(
    update={
        "affordances": (*PRODUCT_GRID.affordances, OPEN_CART_AFFORDANCE),
    }
)
_COMPOSED_BUYER_HOME_NODE = BUYER_HOME_NODE.model_copy(
    update={
        "context_providers": (
            *BUYER_HOME_NODE.context_providers,
            BUYER_MARKET_PROVIDER,
        ),
        "entity_providers": (
            *BUYER_HOME_NODE.entity_providers,
            CART_BINDING_PROVIDER,
        ),
        "guards": (*BUYER_HOME_NODE.guards, CART_ABSENT_GUARD),
        "operations": (*BUYER_HOME_NODE.operations, CART_CREATE),
        "capabilities": (*BUYER_HOME_NODE.capabilities, CART_CAPABILITY),
        "recovery": BUYER_HOME_NODE.recovery.model_copy(
            update={
                "directives": (
                    *BUYER_HOME_NODE.recovery.directives,
                    CART_CREATE_UNKNOWN_RECOVERY,
                )
            }
        ),
    }
)
_COMPOSED_PRODUCT_DETAIL = PRODUCT_DETAIL.model_copy(
    update={
        "affordances": (
            *PRODUCT_DETAIL.affordances,
            CREATE_CART_AFFORDANCE,
            ADD_ITEM_AFFORDANCE,
            OPEN_CART_AFFORDANCE,
        ),
    }
)
_COMPOSED_CATALOG_BROWSE_NODE = CATALOG_BROWSE_NODE.model_copy(
    update={
        "context_providers": (
            *CATALOG_BROWSE_NODE.context_providers,
            CART_STATE_PROVIDER,
        ),
        "guards": (*CATALOG_BROWSE_NODE.guards, CART_EXISTS_GUARD),
        "operations": (*CATALOG_BROWSE_NODE.operations, CART_OPEN),
        "capabilities": (*CATALOG_BROWSE_NODE.capabilities, CART_CAPABILITY),
        "surfaces": CATALOG_BROWSE_NODE.surfaces.model_copy(
            update={
                "active": _COMPOSED_PRODUCT_GRID,
                "peer": (_COMPOSED_PRODUCT_GRID,),
            }
        ),
    }
)
_COMPOSED_CATALOG_PRODUCT_NODE = CATALOG_PRODUCT_NODE.model_copy(
    update={
        "context_providers": (
            BUYER_MARKET_PROVIDER,
            CART_STATE_PROVIDER,
        ),
        "entity_providers": (
            *CATALOG_PRODUCT_NODE.entity_providers,
            CART_BINDING_PROVIDER,
            CART_ITEMS_PROVIDER,
        ),
        "guards": (
            *CATALOG_PRODUCT_NODE.guards,
            CART_ABSENT_GUARD,
            CART_EXISTS_GUARD,
        ),
        "operations": (
            *CATALOG_PRODUCT_NODE.operations,
            CART_CREATE,
            CART_ADD_ITEM,
            CART_OPEN,
        ),
        "capabilities": (*CATALOG_PRODUCT_NODE.capabilities, CART_CAPABILITY),
        "recovery": CATALOG_PRODUCT_NODE.recovery.model_copy(
            update={
                "directives": (
                    *CATALOG_PRODUCT_NODE.recovery.directives,
                    CART_CREATE_UNKNOWN_RECOVERY,
                    CART_MUTATION_UNKNOWN_RECOVERY,
                )
            }
        ),
        "surfaces": CATALOG_PRODUCT_NODE.surfaces.model_copy(
            update={
                "active": _COMPOSED_PRODUCT_DETAIL,
                "detail": (_COMPOSED_PRODUCT_DETAIL,),
            }
        ),
    }
)
_COMPOSED_CATALOG_FEATURE = CATALOG_FEATURE.model_copy(
    update={
        "nodes": (
            _COMPOSED_BUYER_HOME_NODE,
            _COMPOSED_CATALOG_BROWSE_NODE,
            _COMPOSED_CATALOG_PRODUCT_NODE,
        )
    }
)

_COMPOSED_CART_SUMMARY = CART_SUMMARY.model_copy(
    update={
        "affordances": (*CART_SUMMARY.affordances, START_CHECKOUT_AFFORDANCE),
    }
)
_COMPOSED_CART_NODE = CART_NODE.model_copy(
    update={
        "context_providers": (*CART_NODE.context_providers, CHECKOUT_FACTS_PROVIDER),
        "guards": (*CART_NODE.guards, CHECKOUT_READY_GUARD),
        "operations": (*CART_NODE.operations, CHECKOUT_START),
        "capabilities": (*CART_NODE.capabilities, CHECKOUT_CAPABILITY),
        "surfaces": CART_NODE.surfaces.model_copy(
            update={
                "active": _COMPOSED_CART_SUMMARY,
                "detail": (_COMPOSED_CART_SUMMARY,),
            }
        ),
    }
)
_COMPOSED_CART_FEATURE = CART_FEATURE.model_copy(
    update={"nodes": (_COMPOSED_CART_NODE,)}
)

_COMPOSED_CHECKOUT_RECOVERY = CHECKOUT_RECOVERY.model_copy(
    update={
        "affordances": (
            *CHECKOUT_RECOVERY.affordances,
            RECONCILE_ORDER_AFFORDANCE,
        )
    }
)
_ORDER_RECOVERY_CAPABILITY = CapabilitySpec(
    id="orders.recovery",
    title="Order recovery",
    operations=(RECONCILE_ORDER.ref,),
    surfaces=(CHECKOUT_RECOVERY.ref,),
)
_COMPOSED_REVIEW_NODE = REVIEW_NODE.model_copy(
    update={
        "entity_providers": (*REVIEW_NODE.entity_providers, ORDER_PROVIDER),
        "operations": (*REVIEW_NODE.operations, RECONCILE_ORDER),
        "capabilities": (*REVIEW_NODE.capabilities, _ORDER_RECOVERY_CAPABILITY),
        "surfaces": REVIEW_NODE.surfaces.model_copy(
            update={
                "diagnostic": tuple(
                    _COMPOSED_CHECKOUT_RECOVERY
                    if surface.id == CHECKOUT_RECOVERY.id
                    else surface
                    for surface in REVIEW_NODE.surfaces.diagnostic
                )
            }
        ),
    }
)
_COMPOSED_CHECKOUT_FEATURE = CHECKOUT_FEATURE.model_copy(
    update={
        "nodes": tuple(
            _COMPOSED_REVIEW_NODE if node.id == REVIEW_NODE.id else node
            for node in CHECKOUT_FEATURE.nodes
        )
    }
)

_COMPOSED_ORDER_CONFIRMATION = ORDER_CONFIRMATION.model_copy(
    update={
        "affordances": (
            *ORDER_CONFIRMATION.affordances,
            CONTINUE_SHOPPING_AFFORDANCE,
        ),
    }
)
_COMPOSED_ORDERS_CAPABILITY = ORDERS_CAPABILITY.model_copy(
    update={"operations": (CONTINUE_SHOPPING.ref,)}
)
_COMPOSED_CONFIRMATION_NODE = CONFIRMATION_NODE.model_copy(
    update={
        "entity_providers": (
            *CONFIRMATION_NODE.entity_providers,
            CATALOG_PRODUCTS_PROVIDER,
        ),
        "operations": (CONTINUE_SHOPPING,),
        "capabilities": (_COMPOSED_ORDERS_CAPABILITY,),
        "surfaces": CONFIRMATION_NODE.surfaces.model_copy(
            update={"active": _COMPOSED_ORDER_CONFIRMATION}
        ),
    }
)
_COMPOSED_ORDERS_FEATURE = ORDERS_FEATURE.model_copy(
    update={"nodes": (_COMPOSED_CONFIRMATION_NODE,)}
)


MEDUSA_APP_SPEC = ApplicationSpec(
    name="medusa-buyer",
    entry_node=BUYER_HOME_NODE.ref,
    features=(
        _COMPOSED_CATALOG_FEATURE,
        _COMPOSED_CART_FEATURE,
        _COMPOSED_CHECKOUT_FEATURE,
        _COMPOSED_ORDERS_FEATURE,
    ),
    transitions=(
        TransitionSpec(
            source=_COMPOSED_BUYER_HOME_NODE.ref,
            operation=CART_CREATE.ref,
            outcome=CART_CREATED_OUTCOME,
            target=_COMPOSED_BUYER_HOME_NODE.ref,
        ),
        TransitionSpec(
            source=_COMPOSED_BUYER_HOME_NODE.ref,
            operation=CATALOG_LIST.ref,
            outcome="listed",
            target=_COMPOSED_CATALOG_BROWSE_NODE.ref,
        ),
        TransitionSpec(
            source=_COMPOSED_CATALOG_BROWSE_NODE.ref,
            operation=CART_OPEN.ref,
            outcome="opened",
            target=_COMPOSED_CART_NODE.ref,
        ),
        TransitionSpec(
            source=_COMPOSED_CATALOG_PRODUCT_NODE.ref,
            operation=CART_OPEN.ref,
            outcome="opened",
            target=_COMPOSED_CART_NODE.ref,
        ),
        TransitionSpec(
            source=_COMPOSED_CATALOG_PRODUCT_NODE.ref,
            operation=CART_CREATE.ref,
            outcome=CART_CREATED_OUTCOME,
            target=_COMPOSED_CATALOG_PRODUCT_NODE.ref,
        ),
        TransitionSpec(
            source=_COMPOSED_CATALOG_PRODUCT_NODE.ref,
            operation=CART_ADD_ITEM.ref,
            outcome="added",
            target=_COMPOSED_CATALOG_PRODUCT_NODE.ref,
        ),
        TransitionSpec(
            source=_COMPOSED_CART_NODE.ref,
            operation=CHECKOUT_START.ref,
            outcome="started",
            target=CONTACT_NODE.ref,
        ),
        TransitionSpec(
            source=REVIEW_NODE.ref,
            operation=PLACE_ORDER.ref,
            outcome="order_created",
            target=_COMPOSED_CONFIRMATION_NODE.ref,
        ),
        TransitionSpec(
            source=_COMPOSED_REVIEW_NODE.ref,
            operation=RECONCILE_ORDER.ref,
            outcome="verified",
            target=_COMPOSED_CONFIRMATION_NODE.ref,
        ),
        TransitionSpec(
            source=_COMPOSED_CONFIRMATION_NODE.ref,
            operation=CONTINUE_SHOPPING.ref,
            outcome="continued",
            target=_COMPOSED_CATALOG_BROWSE_NODE.ref,
        ),
    ),
)


def framework_packages() -> tuple[str, ...]:
    """Return the public RouteDeck packages wired by this composition root."""

    return tuple(package.__name__ for package in _FRAMEWORK_PACKAGES)


def compile_medusa_app_spec() -> CompiledRouteDeckApp:
    return compile_app(MEDUSA_APP_SPEC)


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


def bind_medusa_app(
    *,
    client: MedusaStoreClient,
    private_forms: CheckoutPrivateFormReader,
    configured_payment_provider_id: str,
    buyer_country_code: str,
    handlers: Mapping[OperationRef, OperationHandler],
    providers: Mapping[ProviderRef, ContextProvider],
    guards: Mapping[GuardRef, Guard],
) -> BoundRouteDeckApp:
    """Bind the real catalog, cart, contact, and shipping verticals once."""

    cart_handler_refs = {
        CART_CREATE.ref,
        CART_ADD_ITEM.ref,
        CART_OPEN.ref,
        CART_UPDATE_ITEM.ref,
        CART_REMOVE_ITEM.ref,
    }
    cart_provider_refs = {
        BUYER_MARKET_PROVIDER.ref,
        CART_STATE_PROVIDER.ref,
        CART_BINDING_PROVIDER.ref,
        CART_ITEMS_PROVIDER.ref,
    }
    cart_guard_refs = {CART_ABSENT_GUARD.ref, CART_EXISTS_GUARD.ref}
    if cart_handler_refs.intersection(handlers):
        raise ValueError("cart handlers are bound by the Medusa composition root")
    if cart_provider_refs.intersection(providers):
        raise ValueError("cart providers are bound by the Medusa composition root")
    if cart_guard_refs.intersection(guards):
        raise ValueError("cart guards are bound by the Medusa composition root")
    catalog_handler_refs = {
        CATALOG_LIST.ref,
        CATALOG_SEARCH.ref,
        OPEN_PRODUCT.ref,
        OPEN_PRODUCT_BY_ROUTE.ref,
        SELECT_VARIANT.ref,
        CONTINUE_SHOPPING.ref,
    }
    catalog_provider_refs = {
        CATALOG_PRODUCTS_PROVIDER.ref,
        CATALOG_PRODUCT_PROVIDER.ref,
        CATALOG_VARIANTS_PROVIDER.ref,
    }
    catalog_guard_refs = {
        PUBLIC_PRODUCT_GUARD.ref,
        VARIANT_ALLOWED_GUARD.ref,
    }
    if catalog_handler_refs.intersection(handlers):
        raise ValueError("catalog handlers are bound by the Medusa composition root")
    if catalog_provider_refs.intersection(providers):
        raise ValueError("catalog providers are bound by the Medusa composition root")
    if catalog_guard_refs.intersection(guards):
        raise ValueError("catalog guards are bound by the Medusa composition root")
    checkout_handler_refs = {
        CHECKOUT_START.ref,
        SAVE_CONTACT.ref,
        SELECT_SHIPPING.ref,
        SELECT_PAYMENT.ref,
        PLACE_ORDER.ref,
        RECONCILE_ORDER.ref,
    }
    checkout_provider_refs = {
        CHECKOUT_FACTS_PROVIDER.ref,
        SHIPPING_OPTIONS_PROVIDER.ref,
        PAYMENT_PROVIDERS_PROVIDER.ref,
        ORDER_PROVIDER.ref,
    }
    checkout_guard_refs = {
        CHECKOUT_READY_GUARD.ref,
        CONTACT_VALID_GUARD.ref,
        SHIPPING_VALID_GUARD.ref,
        PAYMENT_VALID_GUARD.ref,
        REVIEW_CURRENT_GUARD.ref,
    }
    if checkout_handler_refs.intersection(handlers):
        raise ValueError("checkout handlers are bound by the Medusa composition root")
    if checkout_provider_refs.intersection(providers):
        raise ValueError("checkout providers are bound by the Medusa composition root")
    if checkout_guard_refs.intersection(guards):
        raise ValueError("checkout guards are bound by the Medusa composition root")

    all_handlers = dict(handlers)
    all_handlers.update(
        {
            CART_CREATE.ref: CreateCartHandler(client),
            CART_ADD_ITEM.ref: AddCartItemHandler(client),
            CART_OPEN.ref: OpenCartHandler(),
            CART_UPDATE_ITEM.ref: UpdateCartItemHandler(client),
            CART_REMOVE_ITEM.ref: RemoveCartItemHandler(client),
            CATALOG_LIST.ref: ListCatalogHandler(),
            CATALOG_SEARCH.ref: SearchCatalogHandler(),
            OPEN_PRODUCT.ref: OpenProductHandler(),
            OPEN_PRODUCT_BY_ROUTE.ref: OpenProductByRouteHandler(),
            SELECT_VARIANT.ref: SelectVariantHandler(),
            CONTINUE_SHOPPING.ref: OrdersContinueShoppingHandler(),
            CHECKOUT_START.ref: StartCheckoutHandler(
                buyer_country_code=buyer_country_code
            ),
            SAVE_CONTACT.ref: SaveContactHandler(
                client,
                private_forms,
                buyer_country_code=buyer_country_code,
            ),
            SELECT_SHIPPING.ref: SelectShippingHandler(
                client,
                configured_payment_provider_id,
            ),
            SELECT_PAYMENT.ref: SelectPaymentHandler(
                client,
                configured_payment_provider_id,
            ),
            PLACE_ORDER.ref: PlaceOrderHandler(
                client,
                configured_payment_provider_id,
            ),
            RECONCILE_ORDER.ref: ReconcileOrderHandler(client),
        }
    )
    catalog_provider = CatalogProvider(client)
    all_providers = dict(providers)
    all_providers.update(
        {
            BUYER_MARKET_PROVIDER.ref: BuyerMarketProvider(),
            CART_STATE_PROVIDER.ref: CartStateProvider(client),
            CART_BINDING_PROVIDER.ref: CartBindingProvider(),
            CART_ITEMS_PROVIDER.ref: CartItemsProvider(),
            CATALOG_PRODUCTS_PROVIDER.ref: catalog_provider,
            CATALOG_PRODUCT_PROVIDER.ref: catalog_provider,
            CATALOG_VARIANTS_PROVIDER.ref: CurrentCatalogProductProvider(),
            CHECKOUT_FACTS_PROVIDER.ref: CheckoutFactsProvider(client),
            SHIPPING_OPTIONS_PROVIDER.ref: ShippingOptionsProvider(client),
            PAYMENT_PROVIDERS_PROVIDER.ref: PaymentProvidersProvider(
                client,
                configured_payment_provider_id,
            ),
            ORDER_PROVIDER.ref: BoundOrderProvider(),
        }
    )
    all_guards = dict(guards)
    all_guards.update(
        {
            CART_ABSENT_GUARD.ref: CartAbsentGuard(),
            CART_EXISTS_GUARD.ref: CartExistsGuard(),
            PUBLIC_PRODUCT_GUARD.ref: PublicProductGuard(),
            VARIANT_ALLOWED_GUARD.ref: VariantAllowedGuard(),
            CHECKOUT_READY_GUARD.ref: CheckoutReadyGuard(),
            CONTACT_VALID_GUARD.ref: ContactValidGuard(),
            SHIPPING_VALID_GUARD.ref: ShippingValidGuard(),
            PAYMENT_VALID_GUARD.ref: PaymentValidGuard(configured_payment_provider_id),
            REVIEW_CURRENT_GUARD.ref: ReviewCurrentGuard(
                configured_payment_provider_id
            ),
        }
    )
    return bind_app(
        compile_medusa_app_spec(),
        FeatureBindings(
            handlers=all_handlers,
            providers=all_providers,
            guards=all_guards,
        ),
    )


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
    """Build the Medusa consumer on the one generic supervised runner."""

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
    database_path: str | Path,
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
    """Open the one durable RouteDeck authority used by the Medusa product."""

    compiled = compile_medusa_app_spec()
    codec = routedeck_sqlite.FernetSensitiveCodec(encryption_key)
    store = await routedeck_sqlite.SqliteSessionStore.open(
        database_path,
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
    "MEDUSA_APP_SPEC",
    "MedusaRuntime",
    "bind_medusa_app",
    "build_medusa_runtime",
    "compile_medusa_app_spec",
    "framework_packages",
    "open_persistent_medusa_runtime",
]
