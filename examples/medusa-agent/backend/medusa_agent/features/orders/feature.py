from __future__ import annotations

from routedeck_core.app import Feature
from routedeck_core.contracts.application import Capability, Node
from routedeck_core.contracts.navigation import (
    DeepLinkPolicy,
    NodeKind,
    RecoveryPolicy,
    Route,
    Transition,
)
from routedeck_core.contracts.projection import FrozenJsonObject
from routedeck_core.contracts.surfaces import Surface, SurfaceLifecycle, SurfaceSlots

from ...identifiers import MedusaOutcomeType
from ..catalog.declarations import (
    CATALOG_BROWSE_REF,
    CATALOG_PRODUCTS_PROVIDER,
    CONTINUE_SHOPPING,
    CONTINUE_SHOPPING_AFFORDANCE,
)
from .declarations import (
    ORDER_PROVIDER,
    RECONCILE_ORDER,
    RECONCILE_ORDER_AFFORDANCE,
)
from .models import ORDER_CONFIRMATION_SCHEMA

ORDERS_FRAME = Surface(
    id="orders.frame",
    component="orders.frame",
    lifecycle=SurfaceLifecycle.STABLE,
)
ORDER_CONFIRMATION = Surface(
    id="orders.confirmation",
    component="orders.confirmation",
    lifecycle=SurfaceLifecycle.STABLE,
    affordances=(CONTINUE_SHOPPING_AFFORDANCE,),
    public_props_schema=FrozenJsonObject(ORDER_CONFIRMATION_SCHEMA),
)
ORDERS_STATUS = Surface(
    id="orders.status",
    component="orders.status",
    lifecycle=SurfaceLifecycle.STABLE,
)
ORDERS_ERROR = Surface(
    id="orders.error",
    component="orders.error",
    lifecycle=SurfaceLifecycle.STABLE,
)
ORDERS_DIAGNOSTIC = Surface(
    id="orders.diagnostic",
    component="orders.diagnostic",
)
ORDERS_CAPABILITY = Capability(
    id="orders.confirmation",
    title="Order confirmation",
    operations=(CONTINUE_SHOPPING.ref,),
    surfaces=(
        ORDER_CONFIRMATION.ref,
        ORDERS_STATUS.ref,
        ORDERS_ERROR.ref,
        ORDERS_DIAGNOSTIC.ref,
    ),
)

CONFIRMATION_NODE = Node(
    id="orders.confirmation",
    title="Order confirmed",
    kind=NodeKind.TRANSIENT,
    route=Route(
        template="/orders/{confirmation_handle}/confirmation",
        deep_link_policy=DeepLinkPolicy.SESSION_BOUND,
    ),
    entity_providers=(ORDER_PROVIDER, CATALOG_PRODUCTS_PROVIDER),
    operations=(CONTINUE_SHOPPING,),
    outgoing=(
        Transition(
            operation=CONTINUE_SHOPPING.ref,
            outcome=MedusaOutcomeType.CONTINUED,
            target=CATALOG_BROWSE_REF,
        ),
    ),
    capabilities=(ORDERS_CAPABILITY,),
    surfaces=SurfaceSlots(
        active=ORDER_CONFIRMATION,
        frame=(ORDERS_FRAME,),
        status=(ORDERS_STATUS,),
        error=(ORDERS_ERROR,),
        diagnostic=(ORDERS_DIAGNOSTIC,),
    ),
    recovery=RecoveryPolicy(
        directives=("verify_order",), failure_surface=ORDERS_ERROR.ref
    ),
)

FEATURE = Feature(
    namespace="orders",
    nodes=(CONFIRMATION_NODE,),
)


__all__ = [
    "CONFIRMATION_NODE",
    "FEATURE",
    "ORDER_CONFIRMATION",
    "ORDER_PROVIDER",
    "ORDERS_CAPABILITY",
    "RECONCILE_ORDER",
    "RECONCILE_ORDER_AFFORDANCE",
]
