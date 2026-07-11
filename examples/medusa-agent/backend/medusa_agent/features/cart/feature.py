from __future__ import annotations

from routedeck_core.app import FeatureSpec
from routedeck_core.contracts.application import CapabilitySpec, NodeSpec
from routedeck_core.contracts.navigation import (
    DeepLinkPolicy,
    NodeKind,
    RecoveryPolicySpec,
    RouteSpec,
    TransitionSpec,
)
from routedeck_core.contracts.operations import (
    ContextProviderSpec,
    EntityProviderSpec,
    GuardSpec,
    OperationSpec,
    SafetyClass,
)
from routedeck_core.contracts.surfaces import (
    SurfaceAffordanceSpec,
    SurfaceLifecycle,
    SurfaceSlotsSpec,
    SurfaceSpec,
)

BUYER_MARKET_PROVIDER = ContextProviderSpec(
    id="cart.buyer_market",
    description="Typed buyer market, region, currency, and sales-channel configuration.",
)
CART_STATE_PROVIDER = ContextProviderSpec(
    id="cart.current",
    description="Authoritative current-cart quantities, prices, and totals.",
)
CART_ITEMS_PROVIDER = EntityProviderSpec(
    id="cart.items",
    entity_kind="line_item",
    description="Opaque line-item bindings observed for the current cart.",
)
CART_EXISTS_GUARD = GuardSpec(
    id="cart.exists",
    description="Requires the current session to hold one real cart binding.",
)

CART_CREATE = OperationSpec(
    id="cart.create",
    title="Create cart",
    description="Create one journaled cart for the current guest session.",
    safety_class=SafetyClass.WRITE_EXTERNAL,
    outcomes=("created",),
    provider_refs=(BUYER_MARKET_PROVIDER.ref,),
)
CART_ADD_ITEM = OperationSpec(
    id="cart.add_item",
    title="Add item",
    description="Add a validated variant and quantity to the current cart.",
    input_schema={
        "type": "object",
        "required": ["variant_ref", "quantity"],
        "properties": {
            "variant_ref": {"type": "string"},
            "quantity": {"type": "integer", "minimum": 1},
        },
    },
    safety_class=SafetyClass.WRITE_EXTERNAL,
    outcomes=("added",),
    provider_refs=(CART_STATE_PROVIDER.ref,),
    guard_refs=(CART_EXISTS_GUARD.ref,),
)
CART_OPEN = OperationSpec(
    id="cart.open",
    title="Open cart",
    description="Navigate to the current cart summary.",
    safety_class=SafetyClass.NAVIGATION,
    outcomes=("opened",),
    guard_refs=(CART_EXISTS_GUARD.ref,),
)
CART_UPDATE_ITEM = OperationSpec(
    id="cart.update_item",
    title="Update quantity",
    description="Update one allowlisted line-item quantity.",
    input_schema={
        "type": "object",
        "required": ["line_item_ref", "quantity"],
        "properties": {
            "line_item_ref": {"type": "string"},
            "quantity": {"type": "integer", "minimum": 1},
        },
    },
    safety_class=SafetyClass.WRITE_EXTERNAL,
    outcomes=("updated",),
    provider_refs=(CART_STATE_PROVIDER.ref,),
    guard_refs=(CART_EXISTS_GUARD.ref,),
)
CART_REMOVE_ITEM = OperationSpec(
    id="cart.remove_item",
    title="Remove item",
    description="Remove one allowlisted line item from the current cart.",
    input_schema={
        "type": "object",
        "required": ["line_item_ref"],
        "properties": {"line_item_ref": {"type": "string"}},
    },
    safety_class=SafetyClass.WRITE_EXTERNAL,
    outcomes=("removed",),
    provider_refs=(CART_STATE_PROVIDER.ref,),
    guard_refs=(CART_EXISTS_GUARD.ref,),
)
OPEN_CART_AFFORDANCE = SurfaceAffordanceSpec(
    id="open_cart",
    event="open",
    operation=CART_OPEN.ref,
)
CREATE_CART_AFFORDANCE = SurfaceAffordanceSpec(
    id="create_cart",
    event="create",
    operation=CART_CREATE.ref,
)
ADD_ITEM_AFFORDANCE = SurfaceAffordanceSpec(
    id="add_item",
    event="add",
    operation=CART_ADD_ITEM.ref,
)

CART_FRAME = SurfaceSpec(
    id="cart.frame",
    component="cart.frame",
    lifecycle=SurfaceLifecycle.STABLE,
)
CART_SUMMARY = SurfaceSpec(
    id="cart.summary",
    component="cart.summary",
    lifecycle=SurfaceLifecycle.STABLE,
    affordances=(
        SurfaceAffordanceSpec(
            id="update_item", event="change", operation=CART_UPDATE_ITEM.ref
        ),
        SurfaceAffordanceSpec(
            id="remove_item", event="remove", operation=CART_REMOVE_ITEM.ref
        ),
    ),
)
CART_STATUS = SurfaceSpec(
    id="cart.status",
    component="cart.status",
    lifecycle=SurfaceLifecycle.STABLE,
)
CART_ERROR = SurfaceSpec(
    id="cart.error",
    component="cart.error",
    lifecycle=SurfaceLifecycle.STABLE,
)
CART_DIAGNOSTIC = SurfaceSpec(
    id="cart.diagnostic",
    component="cart.diagnostic",
)

CART_CAPABILITY = CapabilitySpec(
    id="cart.manage",
    title="Manage cart",
    operations=(
        CART_CREATE.ref,
        CART_ADD_ITEM.ref,
        CART_OPEN.ref,
        CART_UPDATE_ITEM.ref,
        CART_REMOVE_ITEM.ref,
    ),
    surfaces=(
        CART_SUMMARY.ref,
        CART_STATUS.ref,
        CART_ERROR.ref,
        CART_DIAGNOSTIC.ref,
    ),
)

CART_NODE = NodeSpec(
    id="cart.summary",
    title="Cart",
    kind=NodeKind.WORKFLOW,
    route=RouteSpec(
        template="/cart", deep_link_policy=DeepLinkPolicy.SESSION_BOUND
    ),
    context_providers=(BUYER_MARKET_PROVIDER, CART_STATE_PROVIDER),
    entity_providers=(CART_ITEMS_PROVIDER,),
    guards=(CART_EXISTS_GUARD,),
    operations=(CART_UPDATE_ITEM, CART_REMOVE_ITEM),
    capabilities=(CART_CAPABILITY,),
    surfaces=SurfaceSlotsSpec(
        active=CART_SUMMARY,
        frame=(CART_FRAME,),
        detail=(CART_SUMMARY,),
        status=(CART_STATUS,),
        error=(CART_ERROR,),
        diagnostic=(CART_DIAGNOSTIC,),
    ),
    recovery=RecoveryPolicySpec(
        directives=("refresh_cart",), failure_surface=CART_ERROR.ref
    ),
)

FEATURE_SPEC = FeatureSpec(
    namespace="cart",
    nodes=(CART_NODE,),
    transitions=(
        TransitionSpec(
            source=CART_NODE.ref,
            operation=CART_UPDATE_ITEM.ref,
            outcome="updated",
            target=CART_NODE.ref,
        ),
        TransitionSpec(
            source=CART_NODE.ref,
            operation=CART_REMOVE_ITEM.ref,
            outcome="removed",
            target=CART_NODE.ref,
        ),
    ),
)


__all__ = [
    "ADD_ITEM_AFFORDANCE",
    "BUYER_MARKET_PROVIDER",
    "CART_ADD_ITEM",
    "CART_CAPABILITY",
    "CART_CREATE",
    "CART_EXISTS_GUARD",
    "CART_NODE",
    "CART_OPEN",
    "CART_STATE_PROVIDER",
    "CART_SUMMARY",
    "CREATE_CART_AFFORDANCE",
    "FEATURE_SPEC",
    "OPEN_CART_AFFORDANCE",
]
