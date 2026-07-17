from __future__ import annotations

from routedeck_core.contracts.application import Capability
from routedeck_core.contracts.navigation import (
    NodeRef,
)
from routedeck_core.contracts.operations import (
    ContextProvider,
    EntityInput,
    EntityProvider,
    Guard,
    Operation,
    SafetyClass,
)
from routedeck_core.contracts.projection import FrozenJsonObject
from routedeck_core.contracts.suggestions import (
    SuggestedAction,
    SuggestedActionVisibility,
)
from routedeck_core.contracts.surfaces import (
    SurfaceRef,
    SurfaceAffordance,
)

from ...identifiers import (
    MedusaOperationType,
    MedusaOutcomeType,
    MedusaSuggestedActionType,
)

CART_CREATE_UNKNOWN_RECOVERY = "reconcile_unknown_cart_creation"
CART_MUTATION_UNKNOWN_RECOVERY = "reconcile_unknown_cart"

BUYER_MARKET_PROVIDER = ContextProvider(
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
CART_STATE_PROVIDER = ContextProvider(
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
CART_ITEMS_PROVIDER = EntityProvider(
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
CART_BINDING_PROVIDER = EntityProvider(
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
CART_EXISTS_GUARD = Guard(
    id="cart.exists",
    description="Requires the current session to hold one real cart binding.",
)
CART_ABSENT_GUARD = Guard(
    id="cart.absent",
    description="Prevents duplicate cart creation, including uncertain writes.",
)

CART_CREATE = Operation(
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
    outcomes=(MedusaOutcomeType.CREATED,),
    outcome_schemas=FrozenJsonObject(
        {
            MedusaOutcomeType.CREATED: {
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
CART_ADD_ITEM = Operation(
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
        EntityInput(argument_name="variant_ref", entity_kind="variant"),
    ),
    safety_class=SafetyClass.WRITE_EXTERNAL,
    unknown_recovery_directive=CART_MUTATION_UNKNOWN_RECOVERY,
    outcomes=(MedusaOutcomeType.ADDED,),
    provider_refs=(CART_STATE_PROVIDER.ref,),
    guard_refs=(CART_EXISTS_GUARD.ref,),
)
CART_OPEN = Operation(
    id=MedusaOperationType.CART_OPEN,
    title="Open cart",
    description="Navigate to the current cart summary.",
    safety_class=SafetyClass.NAVIGATION,
    outcomes=(MedusaOutcomeType.OPENED,),
    provider_refs=(CART_STATE_PROVIDER.ref,),
    guard_refs=(CART_EXISTS_GUARD.ref,),
)
CART_UPDATE_ITEM = Operation(
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
        EntityInput(argument_name="line_item_ref", entity_kind="line_item"),
    ),
    safety_class=SafetyClass.WRITE_EXTERNAL,
    unknown_recovery_directive=CART_MUTATION_UNKNOWN_RECOVERY,
    outcomes=(MedusaOutcomeType.UPDATED,),
    provider_refs=(CART_STATE_PROVIDER.ref,),
    guard_refs=(CART_EXISTS_GUARD.ref,),
)
CART_REMOVE_ITEM = Operation(
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
        EntityInput(argument_name="line_item_ref", entity_kind="line_item"),
    ),
    safety_class=SafetyClass.WRITE_EXTERNAL,
    unknown_recovery_directive=CART_MUTATION_UNKNOWN_RECOVERY,
    outcomes=(MedusaOutcomeType.REMOVED,),
    provider_refs=(CART_STATE_PROVIDER.ref,),
    guard_refs=(CART_EXISTS_GUARD.ref,),
)
OPEN_CART_AFFORDANCE = SurfaceAffordance(
    id="open_cart",
    event="open",
    operation=CART_OPEN.ref,
)
VIEW_CART_ACTION = SuggestedAction(
    id=MedusaSuggestedActionType.VIEW_CART,
    operation_id=CART_OPEN.id,
    label="View cart",
    visibility=SuggestedActionVisibility(required_entity_kinds=("cart",)),
)
CREATE_CART_AFFORDANCE = SurfaceAffordance(
    id="create_cart",
    event="create",
    operation=CART_CREATE.ref,
)
ADD_ITEM_AFFORDANCE = SurfaceAffordance(
    id="add_item",
    event="add",
    operation=CART_ADD_ITEM.ref,
)

CART_SUMMARY_REF = NodeRef(id="cart.summary")
CART_CAPABILITY = Capability(
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
        SurfaceRef(id="cart.summary"),
        SurfaceRef(id="cart.status"),
        SurfaceRef(id="cart.error"),
        SurfaceRef(id="cart.diagnostic"),
    ),
)
