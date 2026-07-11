from __future__ import annotations

import routedeck_core
import routedeck_fastapi
import routedeck_langgraph
import routedeck_sqlite
from routedeck_core.app import ApplicationSpec, CompiledRouteDeckApp, compile_app
from routedeck_core.contracts.navigation import TransitionSpec

from .features.cart.feature import CART_NODE, CART_OPEN, FEATURE_SPEC as CART_FEATURE
from .features.catalog.feature import (
    BUYER_HOME_NODE,
    CATALOG_BROWSE_NODE,
    CATALOG_LIST,
    CATALOG_PRODUCT_NODE,
    FEATURE_SPEC as CATALOG_FEATURE,
)
from .features.checkout.feature import (
    CHECKOUT_START,
    CONTACT_NODE,
    FEATURE_SPEC as CHECKOUT_FEATURE,
    PLACE_ORDER,
    REVIEW_NODE,
)
from .features.orders.feature import (
    CONFIRMATION_NODE,
    CONTINUE_SHOPPING,
    FEATURE_SPEC as ORDERS_FEATURE,
)


_FRAMEWORK_PACKAGES = (
    routedeck_core,
    routedeck_fastapi,
    routedeck_langgraph,
    routedeck_sqlite,
)


MEDUSA_APP_SPEC = ApplicationSpec(
    name="medusa-buyer",
    entry_node=BUYER_HOME_NODE.ref,
    features=(
        CATALOG_FEATURE,
        CART_FEATURE,
        CHECKOUT_FEATURE,
        ORDERS_FEATURE,
    ),
    transitions=(
        TransitionSpec(
            source=BUYER_HOME_NODE.ref,
            operation=CATALOG_LIST.ref,
            outcome="listed",
            target=CATALOG_BROWSE_NODE.ref,
        ),
        TransitionSpec(
            source=CATALOG_BROWSE_NODE.ref,
            operation=CART_OPEN.ref,
            outcome="opened",
            target=CART_NODE.ref,
        ),
        TransitionSpec(
            source=CATALOG_PRODUCT_NODE.ref,
            operation=CART_OPEN.ref,
            outcome="opened",
            target=CART_NODE.ref,
        ),
        TransitionSpec(
            source=CART_NODE.ref,
            operation=CHECKOUT_START.ref,
            outcome="started",
            target=CONTACT_NODE.ref,
        ),
        TransitionSpec(
            source=REVIEW_NODE.ref,
            operation=PLACE_ORDER.ref,
            outcome="order_created",
            target=CONFIRMATION_NODE.ref,
        ),
        TransitionSpec(
            source=CONFIRMATION_NODE.ref,
            operation=CONTINUE_SHOPPING.ref,
            outcome="continued",
            target=CATALOG_BROWSE_NODE.ref,
        ),
    ),
)


def framework_packages() -> tuple[str, ...]:
    """Return the public RouteDeck packages wired by this composition root."""

    return tuple(package.__name__ for package in _FRAMEWORK_PACKAGES)


def compile_medusa_app_spec() -> CompiledRouteDeckApp:
    return compile_app(MEDUSA_APP_SPEC)


__all__ = ["MEDUSA_APP_SPEC", "compile_medusa_app_spec", "framework_packages"]
