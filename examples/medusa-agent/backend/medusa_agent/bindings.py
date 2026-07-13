from __future__ import annotations

from collections.abc import Mapping

from routedeck_core.app import (
    BoundRouteDeckApp,
    ContextProvider,
    FeatureBindings,
    Guard,
    OperationHandler,
    bind_app,
)
from routedeck_core.contracts.operations import GuardRef, OperationRef, ProviderRef

from .composition import compile_medusa_app_spec
from .features.cart import (
    BUYER_MARKET_PROVIDER,
    CART_ADD_ITEM,
    CART_CREATE,
    CART_EXISTS_GUARD,
    CART_OPEN,
    CART_STATE_PROVIDER,
    CreateCartHandler,
)
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
from .features.catalog import (
    CATALOG_LIST,
    CATALOG_PRODUCTS_PROVIDER,
    CATALOG_PRODUCT_PROVIDER,
    CATALOG_SEARCH,
    CATALOG_VARIANTS_PROVIDER,
    CONTINUE_SHOPPING,
    CurrentCatalogProductProvider,
    ListCatalogHandler,
    OPEN_PRODUCT,
    OPEN_PRODUCT_BY_ROUTE,
    OpenProductByRouteHandler,
    OpenProductHandler,
    PUBLIC_PRODUCT_GUARD,
    PublicProductGuard,
    SELECT_VARIANT,
    SearchCatalogHandler,
    SelectVariantHandler,
    VARIANT_ALLOWED_GUARD,
    VariantAllowedGuard,
    CatalogProvider,
)
from .features.checkout import (
    CHECKOUT_FACTS_PROVIDER,
    CHECKOUT_READY_GUARD,
    CHECKOUT_START,
    CONTACT_VALID_GUARD,
    CheckoutFactsProvider,
    CheckoutPrivateFormReader,
    CheckoutReadyGuard,
    ContactValidGuard,
    PAYMENT_PROVIDERS_PROVIDER,
    PAYMENT_VALID_GUARD,
    PLACE_ORDER,
    PaymentProvidersProvider,
    PaymentValidGuard,
    REVIEW_CURRENT_GUARD,
    ReviewCurrentGuard,
    SAVE_CONTACT,
    SELECT_PAYMENT,
    SELECT_SHIPPING,
    SHIPPING_OPTIONS_PROVIDER,
    SHIPPING_VALID_GUARD,
    SaveContactHandler,
    SelectPaymentHandler,
    SelectShippingHandler,
    ShippingOptionsProvider,
    ShippingValidGuard,
    StartCheckoutHandler,
)
from .features.orders import (
    BoundOrderProvider,
    ORDER_PROVIDER,
    OrdersContinueShoppingHandler,
    PlaceOrderHandler,
    RECONCILE_ORDER,
    ReconcileOrderHandler,
)
from .medusa.client.protocol import MedusaStoreClient


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
    """Bind each Medusa business vertical to the compiled RouteDeck graph."""

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
    catalog_guard_refs = {PUBLIC_PRODUCT_GUARD.ref, VARIANT_ALLOWED_GUARD.ref}
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
            PAYMENT_VALID_GUARD.ref: PaymentValidGuard(
                configured_payment_provider_id
            ),
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


__all__ = ["bind_medusa_app"]
