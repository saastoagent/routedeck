from __future__ import annotations

import routedeck_core
import routedeck_fastapi
import routedeck_langgraph
import routedeck_sqlite
from routedeck_core.app import ApplicationSpec, CompiledRouteDeckApp, compile_app
from routedeck_core.contracts.navigation import TransitionSpec

from .features.cart import (
    ADD_ITEM_AFFORDANCE,
    BUYER_MARKET_PROVIDER,
    CART_ADD_ITEM,
    CART_CAPABILITY,
    CART_CREATE,
    CART_EXISTS_GUARD,
    CART_NODE,
    CART_OPEN,
    CART_STATE_PROVIDER,
    CART_SUMMARY,
    CREATE_CART_AFFORDANCE,
    FEATURE_SPEC as CART_FEATURE,
    OPEN_CART_AFFORDANCE,
)
from .features.catalog import (
    BUYER_HOME_NODE,
    CATALOG_BROWSE_NODE,
    CATALOG_LIST,
    CATALOG_PRODUCT_NODE,
    CONTINUE_SHOPPING,
    CONTINUE_SHOPPING_AFFORDANCE,
    FEATURE_SPEC as CATALOG_FEATURE,
    PRODUCT_DETAIL,
    PRODUCT_GRID,
)
from .features.checkout import (
    CHECKOUT_CAPABILITY,
    CHECKOUT_FACTS_PROVIDER,
    CHECKOUT_READY_GUARD,
    CHECKOUT_START,
    CONTACT_NODE,
    FEATURE_SPEC as CHECKOUT_FEATURE,
    PLACE_ORDER,
    REVIEW_NODE,
    START_CHECKOUT_AFFORDANCE,
)
from .features.orders import (
    CONFIRMATION_NODE,
    FEATURE_SPEC as ORDERS_FEATURE,
    ORDER_CONFIRMATION,
    ORDERS_CAPABILITY,
)


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
        "guards": (*CATALOG_PRODUCT_NODE.guards, CART_EXISTS_GUARD),
        "operations": (
            *CATALOG_PRODUCT_NODE.operations,
            CART_CREATE,
            CART_ADD_ITEM,
            CART_OPEN,
        ),
        "capabilities": (*CATALOG_PRODUCT_NODE.capabilities, CART_CAPABILITY),
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
            BUYER_HOME_NODE,
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
        CHECKOUT_FEATURE,
        _COMPOSED_ORDERS_FEATURE,
    ),
    transitions=(
        TransitionSpec(
            source=BUYER_HOME_NODE.ref,
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
            outcome="created",
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


__all__ = ["MEDUSA_APP_SPEC", "compile_medusa_app_spec", "framework_packages"]
