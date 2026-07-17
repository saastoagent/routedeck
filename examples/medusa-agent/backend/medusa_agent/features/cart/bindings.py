from __future__ import annotations

from routedeck_core.app import FeatureBindings

from ...medusa.client.protocol import MedusaStoreClient
from .declarations import (
    BUYER_MARKET_PROVIDER,
    CART_ABSENT_GUARD,
    CART_ADD_ITEM,
    CART_BINDING_PROVIDER,
    CART_CREATE,
    CART_EXISTS_GUARD,
    CART_ITEMS_PROVIDER,
    CART_OPEN,
    CART_REMOVE_ITEM,
    CART_STATE_PROVIDER,
    CART_UPDATE_ITEM,
)
from .guards import CartAbsentGuard, CartExistsGuard
from .operations import (
    AddCartItemHandler,
    CreateCartHandler,
    OpenCartHandler,
    RemoveCartItemHandler,
    UpdateCartItemHandler,
)
from .providers import (
    BuyerMarketProvider,
    CartBindingProvider,
    CartItemsProvider,
    CartStateProvider,
)


def create_cart_bindings(client: MedusaStoreClient) -> FeatureBindings:
    """Bind the cart feature to its Medusa dependency."""

    return FeatureBindings(
        handlers={
            CART_CREATE.ref: CreateCartHandler(client),
            CART_ADD_ITEM.ref: AddCartItemHandler(client),
            CART_OPEN.ref: OpenCartHandler(),
            CART_UPDATE_ITEM.ref: UpdateCartItemHandler(client),
            CART_REMOVE_ITEM.ref: RemoveCartItemHandler(client),
        },
        providers={
            BUYER_MARKET_PROVIDER.ref: BuyerMarketProvider(),
            CART_STATE_PROVIDER.ref: CartStateProvider(client),
            CART_BINDING_PROVIDER.ref: CartBindingProvider(),
            CART_ITEMS_PROVIDER.ref: CartItemsProvider(),
        },
        guards={
            CART_ABSENT_GUARD.ref: CartAbsentGuard(),
            CART_EXISTS_GUARD.ref: CartExistsGuard(),
        },
    )


__all__ = ["create_cart_bindings"]
