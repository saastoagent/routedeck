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
from routedeck_core.contracts.surfaces import (
    Surface,
    SurfaceAffordance,
    SurfaceLifecycle,
    SurfaceSlots,
)

from ...identifiers import MedusaOutcomeType
from ..checkout.declarations import (
    CHECKOUT_FACTS_PROVIDER,
    CHECKOUT_READY_GUARD,
    CHECKOUT_START,
    CHECKOUT_CONTACT_REF,
    START_CHECKOUT_AFFORDANCE,
)
from .declarations import (
    ADD_ITEM_AFFORDANCE,
    BUYER_MARKET_PROVIDER,
    CART_ABSENT_GUARD,
    CART_ADD_ITEM,
    CART_BINDING_PROVIDER,
    CART_CAPABILITY,
    CART_CREATE,
    CART_CREATE_UNKNOWN_RECOVERY,
    CART_EXISTS_GUARD,
    CART_ITEMS_PROVIDER,
    CART_MUTATION_UNKNOWN_RECOVERY,
    CART_OPEN,
    CART_REMOVE_ITEM,
    CART_STATE_PROVIDER,
    CART_SUMMARY_REF,
    CART_UPDATE_ITEM,
    CREATE_CART_AFFORDANCE,
    OPEN_CART_AFFORDANCE,
    VIEW_CART_ACTION,
)

CART_FRAME = Surface(
    id="cart.frame",
    component="cart.frame",
    lifecycle=SurfaceLifecycle.STABLE,
)
CART_SUMMARY = Surface(
    id="cart.summary",
    component="cart.summary",
    lifecycle=SurfaceLifecycle.STABLE,
    affordances=(
        SurfaceAffordance(
            id="update_item", event="change", operation=CART_UPDATE_ITEM.ref
        ),
        SurfaceAffordance(
            id="remove_item", event="remove", operation=CART_REMOVE_ITEM.ref
        ),
        START_CHECKOUT_AFFORDANCE,
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
CART_STATUS = Surface(
    id="cart.status",
    component="cart.status",
    lifecycle=SurfaceLifecycle.STABLE,
)
CART_ERROR = Surface(
    id="cart.error",
    component="cart.error",
    lifecycle=SurfaceLifecycle.STABLE,
)
CART_DIAGNOSTIC = Surface(
    id="cart.diagnostic",
    component="cart.diagnostic",
)
CHECKOUT_ENTRY_CAPABILITY = Capability(
    id="cart.checkout",
    title="Start checkout",
    operations=(CHECKOUT_START.ref,),
    surfaces=(CART_SUMMARY.ref,),
)

CART_NODE = Node(
    id="cart.summary",
    title="Cart",
    kind=NodeKind.WORKFLOW,
    route=Route(template="/cart", deep_link_policy=DeepLinkPolicy.SESSION_BOUND),
    context_providers=(
        BUYER_MARKET_PROVIDER,
        CART_STATE_PROVIDER,
        CHECKOUT_FACTS_PROVIDER,
    ),
    entity_providers=(CART_BINDING_PROVIDER, CART_ITEMS_PROVIDER),
    guards=(CART_EXISTS_GUARD, CHECKOUT_READY_GUARD),
    operations=(CART_OPEN, CART_UPDATE_ITEM, CART_REMOVE_ITEM, CHECKOUT_START),
    outgoing=(
        Transition(
            operation=CART_OPEN.ref,
            outcome=MedusaOutcomeType.OPENED,
            target=CART_SUMMARY_REF,
        ),
        Transition(
            operation=CART_UPDATE_ITEM.ref,
            outcome=MedusaOutcomeType.UPDATED,
            target=CART_SUMMARY_REF,
        ),
        Transition(
            operation=CART_REMOVE_ITEM.ref,
            outcome=MedusaOutcomeType.REMOVED,
            target=CART_SUMMARY_REF,
        ),
        Transition(
            operation=CHECKOUT_START.ref,
            outcome=MedusaOutcomeType.STARTED,
            target=CHECKOUT_CONTACT_REF,
        ),
    ),
    capabilities=(CART_CAPABILITY, CHECKOUT_ENTRY_CAPABILITY),
    surfaces=SurfaceSlots(
        active=CART_SUMMARY,
        frame=(CART_FRAME,),
        detail=(CART_SUMMARY,),
        status=(CART_STATUS,),
        error=(CART_ERROR,),
        diagnostic=(CART_DIAGNOSTIC,),
    ),
    recovery=RecoveryPolicy(
        directives=("refresh_cart", CART_MUTATION_UNKNOWN_RECOVERY),
        failure_surface=CART_ERROR.ref,
    ),
)

FEATURE = Feature(
    namespace="cart",
    nodes=(CART_NODE,),
)


__all__ = [
    "ADD_ITEM_AFFORDANCE",
    "BUYER_MARKET_PROVIDER",
    "CART_ADD_ITEM",
    "CART_ABSENT_GUARD",
    "CART_BINDING_PROVIDER",
    "CART_CAPABILITY",
    "CART_CREATE",
    "CART_CREATE_UNKNOWN_RECOVERY",
    "CART_EXISTS_GUARD",
    "CART_NODE",
    "CART_OPEN",
    "CART_STATE_PROVIDER",
    "CART_SUMMARY",
    "CART_MUTATION_UNKNOWN_RECOVERY",
    "CREATE_CART_AFFORDANCE",
    "FEATURE",
    "OPEN_CART_AFFORDANCE",
    "VIEW_CART_ACTION",
]
