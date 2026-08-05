from __future__ import annotations

from routedeck_core.contracts.agent import AgentPolicy
from routedeck_core.contracts.navigation import (
    NodeRef,
)
from routedeck_core.contracts.operations import (
    ContextProvider,
    EntityInput,
    EntityProvider,
    Guard,
    OperationRef,
    Operation,
    OperationSource,
    ReviewPolicy,
    SafetyClass,
)
from routedeck_core.contracts.projection import FrozenJsonObject
from routedeck_core.contracts.surfaces import (
    SurfaceAffordance,
)

from ...identifiers import MedusaAgentPolicyType, MedusaOperationType, MedusaOutcomeType

from .schemas import (
    CHECKOUT_FACTS_PROVIDER_SCHEMA,
    CHECKOUT_STARTED_SCHEMA,
    CONTACT_SAVED_SCHEMA,
    PAYMENT_PROVIDER_SCHEMA,
    PAYMENT_SELECTED_SCHEMA,
    SHIPPING_PROVIDER_SCHEMA,
    SHIPPING_SELECTED_SCHEMA,
)


PROTECTED_CHECKOUT_INPUT_POLICY = AgentPolicy(
    id=MedusaAgentPolicyType.PROTECTED_CHECKOUT_INPUT,
    instruction=(
        "Protected checkout input is surface-only. When the current node is "
        "checkout.contact or contact input is required, stop the chat handoff. "
        "Direct the buyer to the rendered protected contact form and wait for "
        "that surface to complete. "
        "Do not enumerate, request, restate, accept, or summarize email, phone, "
        "shipping, or billing values in chat. If the buyer volunteers those "
        "values, do not repeat them; direct the buyer back to the protected form. "
        "Never infer private Medusa Store identifiers."
    ),
)


CHECKOUT_FACTS_PROVIDER = ContextProvider(
    id="checkout.facts",
    description="Authoritative cart, address, delivery, payment, and totals facts.",
    output_schema=FrozenJsonObject(CHECKOUT_FACTS_PROVIDER_SCHEMA),
)
SHIPPING_OPTIONS_PROVIDER = EntityProvider(
    id="checkout.shipping_options",
    entity_kind="shipping_option",
    description="Shipping options available for the current cart.",
    output_schema=FrozenJsonObject(SHIPPING_PROVIDER_SCHEMA),
)
PAYMENT_PROVIDERS_PROVIDER = EntityProvider(
    id="checkout.payment_providers",
    entity_kind="payment_provider",
    description="Configured payment providers available for the current checkout.",
    output_schema=FrozenJsonObject(PAYMENT_PROVIDER_SCHEMA),
)

CHECKOUT_READY_GUARD = Guard(
    id="checkout.cart_ready",
    description="Requires a real non-empty cart that can enter checkout.",
)
CONTACT_VALID_GUARD = Guard(
    id="checkout.contact_valid",
    description="Requires valid guest contact and address input.",
)
SHIPPING_VALID_GUARD = Guard(
    id="checkout.shipping_valid",
    description="Requires a shipping option from the current authoritative allowlist.",
)
PAYMENT_VALID_GUARD = Guard(
    id="checkout.payment_valid",
    description="Requires the configured payment provider from the current allowlist.",
)
REVIEW_CURRENT_GUARD = Guard(
    id="checkout.review_current",
    description="Requires refreshed checkout facts to match the reviewed proposal.",
)

CHECKOUT_START = Operation(
    id=MedusaOperationType.CHECKOUT_START,
    title="Start checkout",
    description="Enter guest checkout with the current cart.",
    input_schema=FrozenJsonObject(
        {"type": "object", "properties": {}, "additionalProperties": False}
    ),
    safety_class=SafetyClass.NAVIGATION,
    allowed_sources=frozenset({OperationSource.AGENT, OperationSource.SURFACE}),
    outcomes=(MedusaOutcomeType.STARTED,),
    outcome_schemas=FrozenJsonObject({"started": CHECKOUT_STARTED_SCHEMA}),
    provider_refs=(CHECKOUT_FACTS_PROVIDER.ref,),
    guard_refs=(CHECKOUT_READY_GUARD.ref,),
)
START_CHECKOUT_AFFORDANCE = SurfaceAffordance(
    id="start_checkout",
    event="submit",
    operation=CHECKOUT_START.ref,
)
SAVE_CONTACT = Operation(
    id=MedusaOperationType.CHECKOUT_SAVE_CONTACT,
    title="Save guest contact",
    description="Validate and save guest contact and address values.",
    input_schema=FrozenJsonObject(
        {
            "type": "object",
            "required": ["form_handle"],
            "properties": {"form_handle": {"type": "string", "minLength": 1}},
            "additionalProperties": False,
        }
    ),
    safety_class=SafetyClass.WRITE_EXTERNAL,
    allowed_sources=frozenset({OperationSource.AGENT, OperationSource.SURFACE}),
    unknown_recovery_directive="reconcile_unknown_contact",
    outcomes=(MedusaOutcomeType.SAVED,),
    outcome_schemas=FrozenJsonObject({"saved": CONTACT_SAVED_SCHEMA}),
    provider_refs=(CHECKOUT_FACTS_PROVIDER.ref,),
    guard_refs=(CHECKOUT_READY_GUARD.ref, CONTACT_VALID_GUARD.ref),
)
SELECT_SHIPPING = Operation(
    id=MedusaOperationType.CHECKOUT_SELECT_SHIPPING,
    title="Select delivery",
    description="Select an offered shipping option for the current cart.",
    input_schema=FrozenJsonObject(
        {
            "type": "object",
            "required": ["shipping_option_ref"],
            "properties": {"shipping_option_ref": {"type": "string"}},
            "additionalProperties": False,
        }
    ),
    entity_inputs=(
        EntityInput(
            argument_name="shipping_option_ref",
            entity_kind="shipping_option",
        ),
    ),
    safety_class=SafetyClass.WRITE_EXTERNAL,
    allowed_sources=frozenset({OperationSource.AGENT, OperationSource.SURFACE}),
    unknown_recovery_directive="reconcile_unknown_shipping_selection",
    outcomes=(MedusaOutcomeType.SELECTED,),
    outcome_schemas=FrozenJsonObject({"selected": SHIPPING_SELECTED_SCHEMA}),
    provider_refs=(CHECKOUT_FACTS_PROVIDER.ref, SHIPPING_OPTIONS_PROVIDER.ref),
    guard_refs=(CHECKOUT_READY_GUARD.ref, SHIPPING_VALID_GUARD.ref),
)
SELECT_PAYMENT = Operation(
    id=MedusaOperationType.CHECKOUT_SELECT_PAYMENT,
    title="Select payment",
    description="Select and initialize the configured payment provider.",
    input_schema=FrozenJsonObject(
        {
            "type": "object",
            "required": ["payment_provider_ref"],
            "properties": {"payment_provider_ref": {"type": "string"}},
            "additionalProperties": False,
        }
    ),
    entity_inputs=(
        EntityInput(
            argument_name="payment_provider_ref",
            entity_kind="payment_provider",
        ),
    ),
    safety_class=SafetyClass.WRITE_EXTERNAL,
    allowed_sources=frozenset({OperationSource.AGENT, OperationSource.SURFACE}),
    unknown_recovery_directive="reconcile_unknown_payment_selection",
    outcomes=(MedusaOutcomeType.SELECTED,),
    outcome_schemas=FrozenJsonObject({"selected": PAYMENT_SELECTED_SCHEMA}),
    provider_refs=(CHECKOUT_FACTS_PROVIDER.ref, PAYMENT_PROVIDERS_PROVIDER.ref),
    guard_refs=(CHECKOUT_READY_GUARD.ref, PAYMENT_VALID_GUARD.ref),
)
PLACE_ORDER = Operation(
    id=MedusaOperationType.CHECKOUT_PLACE_ORDER,
    title="Place order",
    description="Complete the reviewed cart exactly once.",
    safety_class=SafetyClass.WRITE_EXTERNAL,
    allowed_sources=frozenset({OperationSource.AGENT, OperationSource.SURFACE}),
    review_policy=ReviewPolicy.REQUIRED,
    unknown_recovery_directive="reconcile_unknown_order",
    unknown_recovery_operation_refs=(
        OperationRef(id=MedusaOperationType.ORDERS_RECONCILE),
    ),
    outcomes=(MedusaOutcomeType.ORDER_CREATED, MedusaOutcomeType.CHECKOUT_FAILED),
    provider_refs=(CHECKOUT_FACTS_PROVIDER.ref,),
    guard_refs=(REVIEW_CURRENT_GUARD.ref,),
    public_metadata=FrozenJsonObject({"review_surface_id": "checkout.review"}),
)

CHECKOUT_CONTACT_REF = NodeRef(id="checkout.contact")
CHECKOUT_DELIVERY_REF = NodeRef(id="checkout.delivery")
CHECKOUT_PAYMENT_REF = NodeRef(id="checkout.payment")
CHECKOUT_REVIEW_REF = NodeRef(id="checkout.review")
