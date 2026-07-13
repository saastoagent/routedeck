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
    EntityInputSpec,
    EntityProviderSpec,
    GuardSpec,
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

CART_CREATED_OUTCOME = "created"
CART_CREATE_UNKNOWN_RECOVERY = "reconcile_unknown_cart_creation"
CART_MUTATION_UNKNOWN_RECOVERY = "reconcile_unknown_cart"

BUYER_MARKET_PROVIDER = ContextProviderSpec(
    id="cart.buyer_market",
    description="Typed buyer market, region, currency, and sales-channel configuration.",
    output_schema=FrozenJsonObject(
        {
            "type": "object",
            "properties": {
                "region_id": {"type": "string", "minLength": 1},
                "country_code": {
                    "type": "string",
                    "minLength": 2,
                    "maxLength": 2,
                },
                "sales_channel_id": {"type": "string", "minLength": 1},
                "currency_code": {
                    "type": "string",
                    "minLength": 3,
                    "maxLength": 3,
                },
            },
            "required": [
                "region_id",
                "country_code",
                "currency_code",
                "sales_channel_id",
            ],
            "additionalProperties": False,
        }
    ),
)
CART_STATE_PROVIDER = ContextProviderSpec(
    id="cart.current",
    description="Authoritative current-cart quantities, prices, and totals.",
    output_schema=FrozenJsonObject(
        {
            "type": "object",
            "required": ["state"],
            "properties": {
                "state": {
                    "type": "string",
                    "enum": ["missing", "ready", "refresh_failed"],
                },
                "cart": {"type": "object"},
                "delivery_phase": {
                    "type": "string",
                    "enum": ["not_sent", "possibly_sent", "response_received"],
                },
                "failure_kind": {
                    "type": "string",
                    "enum": ["transport", "provider_protocol", "business"],
                },
                "failure_code": {"type": "string", "minLength": 1},
                "public_message": {"type": "string", "minLength": 1},
            },
            "additionalProperties": False,
        }
    ),
)
CART_ITEMS_PROVIDER = EntityProviderSpec(
    id="cart.items",
    entity_kind="line_item",
    description="Opaque line-item bindings observed for the current cart.",
    output_schema=FrozenJsonObject(
        {
            "type": "object",
            "required": ["items"],
            "properties": {"items": {"type": "array"}},
            "additionalProperties": False,
        }
    ),
)
CART_BINDING_PROVIDER = EntityProviderSpec(
    id="cart.binding",
    entity_kind="cart",
    description="The one opaque current-cart binding for this buyer session.",
    output_schema=FrozenJsonObject(
        {
            "type": "object",
            "required": ["cart_ref"],
            "properties": {
                "cart_ref": {"type": ["string", "null"]},
            },
            "additionalProperties": False,
        }
    ),
)
CART_EXISTS_GUARD = GuardSpec(
    id="cart.exists",
    description="Requires the current session to hold one real cart binding.",
)
CART_ABSENT_GUARD = GuardSpec(
    id="cart.absent",
    description="Prevents duplicate cart creation, including uncertain writes.",
)

CART_CREATE = OperationSpec(
    id=MedusaOperationType.CART_CREATE,
    title="Create cart",
    description="Create one journaled cart for the current guest session.",
    input_schema=FrozenJsonObject(
        {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        }
    ),
    safety_class=SafetyClass.WRITE_EXTERNAL,
    unknown_recovery_directive=CART_CREATE_UNKNOWN_RECOVERY,
    outcomes=(CART_CREATED_OUTCOME,),
    outcome_schemas=FrozenJsonObject(
        {
            CART_CREATED_OUTCOME: {
                "type": "object",
                "properties": {
                    "cart_id": {"type": "string", "minLength": 1},
                    "currency_code": {
                        "type": "string",
                        "minLength": 3,
                        "maxLength": 3,
                    },
                },
                "required": ["cart_id", "currency_code"],
                "additionalProperties": False,
            }
        }
    ),
    provider_refs=(BUYER_MARKET_PROVIDER.ref,),
    guard_refs=(CART_ABSENT_GUARD.ref,),
)
CART_ADD_ITEM = OperationSpec(
    id=MedusaOperationType.CART_ADD_ITEM,
    title="Add item",
    description="Add a validated variant and quantity to the current cart.",
    input_schema=FrozenJsonObject(
        {
            "type": "object",
            "required": ["variant_ref", "quantity"],
            "properties": {
                "variant_ref": {"type": "string"},
                "quantity": {"type": "integer", "minimum": 1},
            },
            "additionalProperties": False,
        }
    ),
    entity_inputs=(
        EntityInputSpec(argument_name="variant_ref", entity_kind="variant"),
    ),
    safety_class=SafetyClass.WRITE_EXTERNAL,
    unknown_recovery_directive=CART_MUTATION_UNKNOWN_RECOVERY,
    outcomes=("added",),
    provider_refs=(CART_STATE_PROVIDER.ref,),
    guard_refs=(CART_EXISTS_GUARD.ref,),
)
CART_OPEN = OperationSpec(
    id=MedusaOperationType.CART_OPEN,
    title="Open cart",
    description="Navigate to the current cart summary.",
    safety_class=SafetyClass.NAVIGATION,
    outcomes=("opened",),
    provider_refs=(CART_STATE_PROVIDER.ref,),
    guard_refs=(CART_EXISTS_GUARD.ref,),
)
CART_UPDATE_ITEM = OperationSpec(
    id=MedusaOperationType.CART_UPDATE_ITEM,
    title="Update quantity",
    description="Update one allowlisted line-item quantity.",
    input_schema=FrozenJsonObject(
        {
            "type": "object",
            "required": ["line_item_ref", "quantity"],
            "properties": {
                "line_item_ref": {"type": "string"},
                "quantity": {"type": "integer", "minimum": 1},
            },
            "additionalProperties": False,
        }
    ),
    entity_inputs=(
        EntityInputSpec(argument_name="line_item_ref", entity_kind="line_item"),
    ),
    safety_class=SafetyClass.WRITE_EXTERNAL,
    unknown_recovery_directive=CART_MUTATION_UNKNOWN_RECOVERY,
    outcomes=("updated",),
    provider_refs=(CART_STATE_PROVIDER.ref,),
    guard_refs=(CART_EXISTS_GUARD.ref,),
)
CART_REMOVE_ITEM = OperationSpec(
    id=MedusaOperationType.CART_REMOVE_ITEM,
    title="Remove item",
    description="Remove one allowlisted line item from the current cart.",
    input_schema=FrozenJsonObject(
        {
            "type": "object",
            "required": ["line_item_ref"],
            "properties": {"line_item_ref": {"type": "string"}},
            "additionalProperties": False,
        }
    ),
    entity_inputs=(
        EntityInputSpec(argument_name="line_item_ref", entity_kind="line_item"),
    ),
    safety_class=SafetyClass.WRITE_EXTERNAL,
    unknown_recovery_directive=CART_MUTATION_UNKNOWN_RECOVERY,
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
    public_props_schema=FrozenJsonObject(
        {
            "type": "object",
            "required": [
                "cart_ref",
                "currency_code",
                "items",
                "subtotal",
                "shipping_total",
                "tax_total",
                "discount_total",
                "total",
            ],
            "properties": {
                "cart_ref": {"type": "string", "minLength": 1},
                "currency_code": {
                    "type": "string",
                    "minLength": 3,
                    "maxLength": 3,
                },
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": [
                            "line_item_ref",
                            "title",
                            "selected_options",
                            "quantity",
                            "unit_price",
                        ],
                        "properties": {
                            "line_item_ref": {"type": "string", "minLength": 1},
                            "title": {"type": "string", "minLength": 1},
                            "product_title": {"type": "string"},
                            "variant_title": {"type": "string"},
                            "selected_options": {
                                "type": "array",
                                "items": {"type": "string", "minLength": 1},
                            },
                            "quantity": {"type": "integer", "minimum": 1},
                            "unit_price": {"type": "integer"},
                            "line_total": {"type": "integer"},
                        },
                        "additionalProperties": False,
                    },
                },
                "subtotal": {"type": "integer"},
                "shipping_total": {"type": "integer"},
                "tax_total": {"type": "integer"},
                "discount_total": {"type": "integer"},
                "total": {"type": "integer"},
            },
            "additionalProperties": False,
        }
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
    route=RouteSpec(template="/cart", deep_link_policy=DeepLinkPolicy.SESSION_BOUND),
    context_providers=(BUYER_MARKET_PROVIDER, CART_STATE_PROVIDER),
    entity_providers=(CART_BINDING_PROVIDER, CART_ITEMS_PROVIDER),
    guards=(CART_EXISTS_GUARD,),
    operations=(CART_OPEN, CART_UPDATE_ITEM, CART_REMOVE_ITEM),
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
        directives=("refresh_cart", CART_MUTATION_UNKNOWN_RECOVERY),
        failure_surface=CART_ERROR.ref,
    ),
)

FEATURE_SPEC = FeatureSpec(
    namespace="cart",
    nodes=(CART_NODE,),
    transitions=(
        TransitionSpec(
            source=CART_NODE.ref,
            operation=CART_OPEN.ref,
            outcome="opened",
            target=CART_NODE.ref,
        ),
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
    "CART_ABSENT_GUARD",
    "CART_BINDING_PROVIDER",
    "CART_CAPABILITY",
    "CART_CREATE",
    "CART_CREATED_OUTCOME",
    "CART_CREATE_UNKNOWN_RECOVERY",
    "CART_EXISTS_GUARD",
    "CART_NODE",
    "CART_OPEN",
    "CART_STATE_PROVIDER",
    "CART_SUMMARY",
    "CART_MUTATION_UNKNOWN_RECOVERY",
    "CREATE_CART_AFFORDANCE",
    "FEATURE_SPEC",
    "OPEN_CART_AFFORDANCE",
]
