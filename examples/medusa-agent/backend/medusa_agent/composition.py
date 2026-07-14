from __future__ import annotations

import routedeck_core
import routedeck_fastapi
import routedeck_langgraph
import routedeck_sqlalchemy
from routedeck_core.app import (
    ApplicationSpec,
    CompiledRouteDeckApp,
    compile_app,
)
from routedeck_core.contracts.application import CapabilitySpec
from routedeck_core.contracts.navigation import TransitionSpec

from .features.cart import (
    ADD_ITEM_AFFORDANCE,
    BUYER_MARKET_PROVIDER,
    CART_ADD_ITEM,
    CART_CAPABILITY,
    CART_CREATE,
    CART_CREATE_UNKNOWN_RECOVERY,
    CART_EXISTS_GUARD,
    CART_MUTATION_UNKNOWN_RECOVERY,
    CART_NODE,
    CART_OPEN,
    CART_STATE_PROVIDER,
    CART_SUMMARY,
    CREATE_CART_AFFORDANCE,
    FEATURE_SPEC as CART_FEATURE,
    OPEN_CART_AFFORDANCE,
    VIEW_CART_ACTION,
)
from .features.cart.feature import (
    CART_ABSENT_GUARD,
    CART_BINDING_PROVIDER,
    CART_ITEMS_PROVIDER,
)
from .features.catalog import (
    BUYER_HOME_NODE,
    CATALOG_BROWSE_NODE,
    CATALOG_LIST,
    CATALOG_PRODUCTS_PROVIDER,
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
from .features.checkout.feature import CHECKOUT_RECOVERY
from .features.orders import (
    CONFIRMATION_NODE,
    FEATURE_SPEC as ORDERS_FEATURE,
    ORDER_CONFIRMATION,
    ORDER_PROVIDER,
    ORDERS_CAPABILITY,
    RECONCILE_ORDER,
    RECONCILE_ORDER_AFFORDANCE,
)
from .identifiers import MedusaOutcomeType


_FRAMEWORK_PACKAGES = (
    routedeck_core,
    routedeck_fastapi,
    routedeck_langgraph,
    routedeck_sqlalchemy,
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
        "entity_providers": (
            *CATALOG_BROWSE_NODE.entity_providers,
            CART_BINDING_PROVIDER,
        ),
        "guards": (*CATALOG_BROWSE_NODE.guards, CART_EXISTS_GUARD),
        "operations": (*CATALOG_BROWSE_NODE.operations, CART_OPEN),
        "capabilities": (*CATALOG_BROWSE_NODE.capabilities, CART_CAPABILITY),
        "suggested_actions": (
            *CATALOG_BROWSE_NODE.suggested_actions,
            VIEW_CART_ACTION,
        ),
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
        "suggested_actions": (
            *CATALOG_PRODUCT_NODE.suggested_actions,
            VIEW_CART_ACTION,
        ),
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
            outcome=MedusaOutcomeType.CREATED,
            target=_COMPOSED_BUYER_HOME_NODE.ref,
        ),
        TransitionSpec(
            source=_COMPOSED_BUYER_HOME_NODE.ref,
            operation=CATALOG_LIST.ref,
            outcome=MedusaOutcomeType.LISTED,
            target=_COMPOSED_CATALOG_BROWSE_NODE.ref,
        ),
        TransitionSpec(
            source=_COMPOSED_CATALOG_BROWSE_NODE.ref,
            operation=CART_OPEN.ref,
            outcome=MedusaOutcomeType.OPENED,
            target=_COMPOSED_CART_NODE.ref,
        ),
        TransitionSpec(
            source=_COMPOSED_CATALOG_PRODUCT_NODE.ref,
            operation=CART_OPEN.ref,
            outcome=MedusaOutcomeType.OPENED,
            target=_COMPOSED_CART_NODE.ref,
        ),
        TransitionSpec(
            source=_COMPOSED_CATALOG_PRODUCT_NODE.ref,
            operation=CART_CREATE.ref,
            outcome=MedusaOutcomeType.CREATED,
            target=_COMPOSED_CATALOG_PRODUCT_NODE.ref,
        ),
        TransitionSpec(
            source=_COMPOSED_CATALOG_PRODUCT_NODE.ref,
            operation=CART_ADD_ITEM.ref,
            outcome=MedusaOutcomeType.ADDED,
            target=_COMPOSED_CATALOG_PRODUCT_NODE.ref,
        ),
        TransitionSpec(
            source=_COMPOSED_CART_NODE.ref,
            operation=CHECKOUT_START.ref,
            outcome=MedusaOutcomeType.STARTED,
            target=CONTACT_NODE.ref,
        ),
        TransitionSpec(
            source=REVIEW_NODE.ref,
            operation=PLACE_ORDER.ref,
            outcome=MedusaOutcomeType.ORDER_CREATED,
            target=_COMPOSED_CONFIRMATION_NODE.ref,
        ),
        TransitionSpec(
            source=_COMPOSED_REVIEW_NODE.ref,
            operation=RECONCILE_ORDER.ref,
            outcome=MedusaOutcomeType.VERIFIED,
            target=_COMPOSED_CONFIRMATION_NODE.ref,
        ),
        TransitionSpec(
            source=_COMPOSED_CONFIRMATION_NODE.ref,
            operation=CONTINUE_SHOPPING.ref,
            outcome=MedusaOutcomeType.CONTINUED,
            target=_COMPOSED_CATALOG_BROWSE_NODE.ref,
        ),
    ),
)


def framework_packages() -> tuple[str, ...]:
    """Return the public RouteDeck packages wired by this composition root."""

    return tuple(package.__name__ for package in _FRAMEWORK_PACKAGES)


def compile_medusa_app_spec() -> CompiledRouteDeckApp:
    return compile_app(MEDUSA_APP_SPEC)


__all__ = [
    "MEDUSA_APP_SPEC",
    "compile_medusa_app_spec",
    "framework_packages",
]
