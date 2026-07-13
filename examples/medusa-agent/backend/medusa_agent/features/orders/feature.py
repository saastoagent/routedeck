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
    EntityInputSpec,
    EntityProviderSpec,
    OperationSpec,
    SafetyClass,
)
from routedeck_core.contracts.projection import FrozenJsonObject
from routedeck_core.contracts.surfaces import (
    SurfaceAffordanceSpec,
    SurfaceLifecycle,
    SurfaceSlotsSpec,
    SurfaceSpec,
)

from ...identifiers import MedusaOperationType

from .models import ORDER_CONFIRMATION_SCHEMA, ORDER_RECOVERY_PROVIDER_SCHEMA


ORDER_PROVIDER = EntityProviderSpec(
    id="orders.confirmed_order",
    entity_kind="order",
    description="Independently verified order facts for the completion result.",
    output_schema=FrozenJsonObject(ORDER_RECOVERY_PROVIDER_SCHEMA),
)
RECONCILE_ORDER = OperationSpec(
    id=MedusaOperationType.ORDERS_RECONCILE,
    title="Verify submitted order",
    description="Re-read an already submitted order without completing the cart again.",
    input_schema=FrozenJsonObject(
        {
            "type": "object",
            "required": ["order_ref"],
            "properties": {"order_ref": {"type": "string", "minLength": 1}},
            "additionalProperties": False,
        }
    ),
    entity_inputs=(EntityInputSpec(argument_name="order_ref", entity_kind="order"),),
    safety_class=SafetyClass.READ_EXTERNAL,
    outcomes=("verified",),
    provider_refs=(ORDER_PROVIDER.ref,),
)
RECONCILE_ORDER_AFFORDANCE = SurfaceAffordanceSpec(
    id="reconcile_order",
    event="retry",
    operation=RECONCILE_ORDER.ref,
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
    public_props_schema=FrozenJsonObject(ORDER_CONFIRMATION_SCHEMA),
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


__all__ = [
    "CONFIRMATION_NODE",
    "FEATURE_SPEC",
    "ORDER_CONFIRMATION",
    "ORDER_PROVIDER",
    "ORDERS_CAPABILITY",
    "RECONCILE_ORDER",
    "RECONCILE_ORDER_AFFORDANCE",
]
