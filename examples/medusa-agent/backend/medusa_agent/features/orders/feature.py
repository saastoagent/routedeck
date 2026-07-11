from __future__ import annotations

from routedeck_core.app import FeatureSpec
from routedeck_core.contracts.application import CapabilitySpec, NodeSpec
from routedeck_core.contracts.navigation import (
    DeepLinkPolicy,
    NodeKind,
    RecoveryPolicySpec,
    RouteSpec,
)
from routedeck_core.contracts.operations import (
    EntityProviderSpec,
    OperationSpec,
    SafetyClass,
)
from routedeck_core.contracts.surfaces import (
    SurfaceAffordanceSpec,
    SurfaceLifecycle,
    SurfaceSlotsSpec,
    SurfaceSpec,
)


ORDER_PROVIDER = EntityProviderSpec(
    id="orders.confirmed_order",
    entity_kind="order",
    description="Independently verified order facts for the completion result.",
)
CONTINUE_SHOPPING = OperationSpec(
    id="catalog.continue_shopping",
    title="Continue shopping",
    description="Return to catalog browsing after confirmation.",
    safety_class=SafetyClass.NAVIGATION,
    outcomes=("continued",),
)

ORDERS_FRAME = SurfaceSpec(
    id="orders.frame",
    component="orders.frame",
    lifecycle=SurfaceLifecycle.STABLE,
)
ORDER_CONFIRMATION = SurfaceSpec(
    id="orders.confirmation",
    component="orders.confirmation",
    lifecycle=SurfaceLifecycle.STABLE,
    affordances=(
        SurfaceAffordanceSpec(
            id="continue_shopping",
            event="open",
            operation=CONTINUE_SHOPPING.ref,
        ),
    ),
)
ORDERS_STATUS = SurfaceSpec(
    id="orders.status",
    component="orders.status",
    lifecycle=SurfaceLifecycle.STABLE,
)
ORDERS_ERROR = SurfaceSpec(
    id="orders.error",
    component="orders.error",
    lifecycle=SurfaceLifecycle.STABLE,
)
ORDERS_DIAGNOSTIC = SurfaceSpec(
    id="orders.diagnostic",
    component="orders.diagnostic",
)
ORDERS_CAPABILITY = CapabilitySpec(
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

CONFIRMATION_NODE = NodeSpec(
    id="orders.confirmation",
    title="Order confirmed",
    kind=NodeKind.TRANSIENT,
    route=RouteSpec(
        template="/orders/{confirmation_handle}/confirmation",
        deep_link_policy=DeepLinkPolicy.SESSION_BOUND,
    ),
    entity_providers=(ORDER_PROVIDER,),
    operations=(CONTINUE_SHOPPING,),
    capabilities=(ORDERS_CAPABILITY,),
    surfaces=SurfaceSlotsSpec(
        active=ORDER_CONFIRMATION,
        frame=(ORDERS_FRAME,),
        status=(ORDERS_STATUS,),
        error=(ORDERS_ERROR,),
        diagnostic=(ORDERS_DIAGNOSTIC,),
    ),
    recovery=RecoveryPolicySpec(
        directives=("verify_order",), failure_surface=ORDERS_ERROR.ref
    ),
)

FEATURE_SPEC = FeatureSpec(
    namespace="orders",
    nodes=(CONFIRMATION_NODE,),
)


__all__ = ["CONFIRMATION_NODE", "CONTINUE_SHOPPING", "FEATURE_SPEC"]
