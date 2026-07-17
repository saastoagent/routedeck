"""Select Medusa features; RouteDeck owns graph composition and validation."""

from __future__ import annotations

from routedeck_core.app import Application, CompiledApplication, compile_app

from .features.cart.feature import FEATURE as CART_FEATURE
from .features.catalog.feature import BUYER_HOME_NODE, FEATURE as CATALOG_FEATURE
from .features.checkout.feature import FEATURE as CHECKOUT_FEATURE
from .features.orders.feature import FEATURE as ORDERS_FEATURE


MEDUSA_APP = Application(
    name="medusa-buyer",
    entry_node=BUYER_HOME_NODE.ref,
    features=(
        CATALOG_FEATURE,
        CART_FEATURE,
        CHECKOUT_FEATURE,
        ORDERS_FEATURE,
    ),
)


def compile_medusa_app() -> CompiledApplication:
    return compile_app(MEDUSA_APP)


__all__ = ["MEDUSA_APP", "compile_medusa_app"]
