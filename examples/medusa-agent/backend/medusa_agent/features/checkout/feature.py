from __future__ import annotations

from routedeck_core.app import FeatureSpec
from routedeck_core.contracts.agent import AgentPolicySpec
from routedeck_core.contracts.application import CapabilitySpec, NodeSpec
from routedeck_core.contracts.navigation import (
    DeepLinkPolicy,
    NavigationPolicySpec,
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
    OperationRef,
    OperationSpec,
    ReviewPolicy,
    SafetyClass,
)
from routedeck_core.contracts.projection import FrozenJsonObject
from routedeck_core.contracts.surfaces import (
    PrivateFormBindingSpec,
    SurfaceAffordanceSpec,
    SurfaceLifecycle,
    SurfaceSlotsSpec,
    SurfaceSpec,
)

from ...identifiers import MedusaAgentPolicyType, MedusaOperationType, MedusaOutcomeType

from .models import CONTACT_FIELD_NAMES
from .schemas import (
    CHECKOUT_FACTS_PROVIDER_SCHEMA,
    CHECKOUT_STARTED_SCHEMA,
    CONTACT_FORM_SCHEMA,
    CONTACT_SAVED_SCHEMA,
    ORDER_REVIEW_SCHEMA,
    PAYMENT_METHOD_SCHEMA,
    PAYMENT_PROVIDER_SCHEMA,
    PAYMENT_SELECTED_SCHEMA,
    RECOVERY_SCHEMA,
    REVIEW_PENDING_SCHEMA,
    SHIPPING_OPTIONS_SCHEMA,
    SHIPPING_PROVIDER_SCHEMA,
    SHIPPING_SELECTED_SCHEMA,
)


PROTECTED_CHECKOUT_INPUT_POLICY = AgentPolicySpec(
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


CHECKOUT_FACTS_PROVIDER = ContextProviderSpec(
    id="checkout.facts",
    description="Authoritative cart, address, delivery, payment, and totals facts.",
    output_schema=FrozenJsonObject(CHECKOUT_FACTS_PROVIDER_SCHEMA),
)
SHIPPING_OPTIONS_PROVIDER = EntityProviderSpec(
    id="checkout.shipping_options",
    entity_kind="shipping_option",
    description="Shipping options available for the current cart.",
    output_schema=FrozenJsonObject(SHIPPING_PROVIDER_SCHEMA),
)
PAYMENT_PROVIDERS_PROVIDER = EntityProviderSpec(
    id="checkout.payment_providers",
    entity_kind="payment_provider",
    description="Configured payment providers available for the current checkout.",
    output_schema=FrozenJsonObject(PAYMENT_PROVIDER_SCHEMA),
)

CHECKOUT_READY_GUARD = GuardSpec(
    id="checkout.cart_ready",
    description="Requires a real non-empty cart that can enter checkout.",
)
CONTACT_VALID_GUARD = GuardSpec(
    id="checkout.contact_valid",
    description="Requires valid guest contact and address input.",
)
SHIPPING_VALID_GUARD = GuardSpec(
    id="checkout.shipping_valid",
    description="Requires a shipping option from the current authoritative allowlist.",
)
PAYMENT_VALID_GUARD = GuardSpec(
    id="checkout.payment_valid",
    description="Requires the configured payment provider from the current allowlist.",
)
REVIEW_CURRENT_GUARD = GuardSpec(
    id="checkout.review_current",
    description="Requires refreshed checkout facts to match the reviewed proposal.",
)

CHECKOUT_START = OperationSpec(
    id=MedusaOperationType.CHECKOUT_START,
    title="Start checkout",
    description="Enter guest checkout with the current cart.",
    input_schema=FrozenJsonObject(
        {"type": "object", "properties": {}, "additionalProperties": False}
    ),
    safety_class=SafetyClass.NAVIGATION,
    outcomes=(MedusaOutcomeType.STARTED,),
    outcome_schemas=FrozenJsonObject({"started": CHECKOUT_STARTED_SCHEMA}),
    provider_refs=(CHECKOUT_FACTS_PROVIDER.ref,),
    guard_refs=(CHECKOUT_READY_GUARD.ref,),
)
START_CHECKOUT_AFFORDANCE = SurfaceAffordanceSpec(
    id="start_checkout",
    event="submit",
    operation=CHECKOUT_START.ref,
)
SAVE_CONTACT = OperationSpec(
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
    unknown_recovery_directive="reconcile_unknown_contact",
    outcomes=(MedusaOutcomeType.SAVED,),
    outcome_schemas=FrozenJsonObject({"saved": CONTACT_SAVED_SCHEMA}),
    provider_refs=(CHECKOUT_FACTS_PROVIDER.ref,),
    guard_refs=(CHECKOUT_READY_GUARD.ref, CONTACT_VALID_GUARD.ref),
)
SELECT_SHIPPING = OperationSpec(
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
        EntityInputSpec(
            argument_name="shipping_option_ref",
            entity_kind="shipping_option",
        ),
    ),
    safety_class=SafetyClass.WRITE_EXTERNAL,
    unknown_recovery_directive="reconcile_unknown_shipping_selection",
    outcomes=(MedusaOutcomeType.SELECTED,),
    outcome_schemas=FrozenJsonObject({"selected": SHIPPING_SELECTED_SCHEMA}),
    provider_refs=(CHECKOUT_FACTS_PROVIDER.ref, SHIPPING_OPTIONS_PROVIDER.ref),
    guard_refs=(CHECKOUT_READY_GUARD.ref, SHIPPING_VALID_GUARD.ref),
)
SELECT_PAYMENT = OperationSpec(
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
        EntityInputSpec(
            argument_name="payment_provider_ref",
            entity_kind="payment_provider",
        ),
    ),
    safety_class=SafetyClass.WRITE_EXTERNAL,
    unknown_recovery_directive="reconcile_unknown_payment_selection",
    outcomes=(MedusaOutcomeType.SELECTED,),
    outcome_schemas=FrozenJsonObject({"selected": PAYMENT_SELECTED_SCHEMA}),
    provider_refs=(CHECKOUT_FACTS_PROVIDER.ref, PAYMENT_PROVIDERS_PROVIDER.ref),
    guard_refs=(CHECKOUT_READY_GUARD.ref, PAYMENT_VALID_GUARD.ref),
)
PLACE_ORDER = OperationSpec(
    id=MedusaOperationType.CHECKOUT_PLACE_ORDER,
    title="Place order",
    description="Complete the reviewed cart exactly once.",
    safety_class=SafetyClass.WRITE_EXTERNAL,
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

CHECKOUT_FRAME = SurfaceSpec(
    id="checkout.frame",
    component="checkout.frame",
    lifecycle=SurfaceLifecycle.STABLE,
)
CHECKOUT_PRIVATE_FORM_BINDING = PrivateFormBindingSpec(
    form_id_prop="form_handle",
    allowed_field_names=CONTACT_FIELD_NAMES,
)
CONTACT_FORM = SurfaceSpec(
    id="checkout.contact_form",
    component="checkout.contact_form",
    lifecycle=SurfaceLifecycle.STABLE,
    affordances=(
        SurfaceAffordanceSpec(
            id="save_contact", event="submit", operation=SAVE_CONTACT.ref
        ),
    ),
    private_form_binding=CHECKOUT_PRIVATE_FORM_BINDING,
    public_props_schema=FrozenJsonObject(CONTACT_FORM_SCHEMA),
)
SHIPPING_OPTIONS = SurfaceSpec(
    id="checkout.shipping_options",
    component="checkout.shipping_options",
    lifecycle=SurfaceLifecycle.STABLE,
    affordances=(
        SurfaceAffordanceSpec(
            id="select_shipping", event="select", operation=SELECT_SHIPPING.ref
        ),
    ),
    public_props_schema=FrozenJsonObject(SHIPPING_OPTIONS_SCHEMA),
)
PAYMENT_METHOD = SurfaceSpec(
    id="checkout.payment_method",
    component="checkout.payment_method",
    lifecycle=SurfaceLifecycle.STABLE,
    affordances=(
        SurfaceAffordanceSpec(
            id="select_payment", event="select", operation=SELECT_PAYMENT.ref
        ),
    ),
    public_props_schema=FrozenJsonObject(PAYMENT_METHOD_SCHEMA),
)
ORDER_REVIEW = SurfaceSpec(
    id="checkout.order_review",
    component="checkout.order_review",
    lifecycle=SurfaceLifecycle.STABLE,
    affordances=(
        SurfaceAffordanceSpec(
            id="propose_order", event="submit", operation=PLACE_ORDER.ref
        ),
    ),
    private_form_binding=CHECKOUT_PRIVATE_FORM_BINDING,
    public_props_schema=FrozenJsonObject(ORDER_REVIEW_SCHEMA),
)
CHECKOUT_REVIEW = SurfaceSpec(
    id="checkout.review",
    component="checkout.review",
    lifecycle=SurfaceLifecycle.STABLE,
    public_props_schema=FrozenJsonObject(REVIEW_PENDING_SCHEMA),
)
CHECKOUT_STATUS = SurfaceSpec(
    id="checkout.status",
    component="checkout.status",
    lifecycle=SurfaceLifecycle.STABLE,
)
CHECKOUT_ERROR = SurfaceSpec(
    id="checkout.error",
    component="checkout.error",
    lifecycle=SurfaceLifecycle.STABLE,
)
CHECKOUT_RECOVERY = SurfaceSpec(
    id="checkout.recovery",
    component="checkout.recovery",
    lifecycle=SurfaceLifecycle.STABLE,
    public_props_schema=FrozenJsonObject(RECOVERY_SCHEMA),
)
CHECKOUT_DIAGNOSTIC = SurfaceSpec(
    id="checkout.diagnostic",
    component="checkout.diagnostic",
)

CHECKOUT_CAPABILITY = CapabilitySpec(
    id="checkout.guest",
    title="Guest checkout",
    operations=(
        CHECKOUT_START.ref,
        SAVE_CONTACT.ref,
        SELECT_SHIPPING.ref,
        SELECT_PAYMENT.ref,
        PLACE_ORDER.ref,
    ),
    surfaces=(
        CONTACT_FORM.ref,
        SHIPPING_OPTIONS.ref,
        PAYMENT_METHOD.ref,
        ORDER_REVIEW.ref,
        CHECKOUT_REVIEW.ref,
        CHECKOUT_STATUS.ref,
        CHECKOUT_ERROR.ref,
        CHECKOUT_RECOVERY.ref,
    ),
)

CONTACT_NODE = NodeSpec(
    id="checkout.contact",
    title="Contact",
    kind=NodeKind.WORKFLOW,
    route=RouteSpec(
        template="/checkout/contact",
        deep_link_policy=DeepLinkPolicy.SESSION_BOUND,
    ),
    context_providers=(CHECKOUT_FACTS_PROVIDER,),
    guards=(CHECKOUT_READY_GUARD, CONTACT_VALID_GUARD),
    operations=(SAVE_CONTACT,),
    capabilities=(CHECKOUT_CAPABILITY,),
    surfaces=SurfaceSlotsSpec(
        active=CONTACT_FORM,
        frame=(CHECKOUT_FRAME,),
        form=(CONTACT_FORM,),
        status=(CHECKOUT_STATUS,),
        error=(CHECKOUT_ERROR,),
        diagnostic=(CHECKOUT_DIAGNOSTIC,),
    ),
    navigation=NavigationPolicySpec(),
    recovery=RecoveryPolicySpec(
        directives=("retry_contact", "reconcile_unknown_contact"),
        failure_surface=CHECKOUT_ERROR.ref,
    ),
)
DELIVERY_NODE = NodeSpec(
    id="checkout.delivery",
    title="Delivery",
    kind=NodeKind.WORKFLOW,
    route=RouteSpec(
        template="/checkout/delivery",
        deep_link_policy=DeepLinkPolicy.SESSION_BOUND,
    ),
    context_providers=(CHECKOUT_FACTS_PROVIDER,),
    entity_providers=(SHIPPING_OPTIONS_PROVIDER,),
    guards=(CHECKOUT_READY_GUARD, SHIPPING_VALID_GUARD),
    operations=(SELECT_SHIPPING,),
    capabilities=(CHECKOUT_CAPABILITY,),
    surfaces=SurfaceSlotsSpec(
        active=SHIPPING_OPTIONS,
        frame=(CHECKOUT_FRAME,),
        detail=(SHIPPING_OPTIONS,),
        status=(CHECKOUT_STATUS,),
        error=(CHECKOUT_ERROR,),
        diagnostic=(CHECKOUT_DIAGNOSTIC,),
    ),
    recovery=RecoveryPolicySpec(
        directives=(
            "refresh_shipping_options",
            "reconcile_unknown_shipping_selection",
        ),
        failure_surface=CHECKOUT_ERROR.ref,
    ),
)
PAYMENT_NODE = NodeSpec(
    id="checkout.payment",
    title="Payment",
    kind=NodeKind.WORKFLOW,
    route=RouteSpec(
        template="/checkout/payment",
        deep_link_policy=DeepLinkPolicy.SESSION_BOUND,
    ),
    context_providers=(CHECKOUT_FACTS_PROVIDER,),
    entity_providers=(SHIPPING_OPTIONS_PROVIDER, PAYMENT_PROVIDERS_PROVIDER),
    guards=(CHECKOUT_READY_GUARD, PAYMENT_VALID_GUARD),
    operations=(SELECT_PAYMENT,),
    capabilities=(CHECKOUT_CAPABILITY,),
    surfaces=SurfaceSlotsSpec(
        active=PAYMENT_METHOD,
        frame=(CHECKOUT_FRAME,),
        detail=(PAYMENT_METHOD,),
        status=(CHECKOUT_STATUS,),
        error=(CHECKOUT_ERROR,),
        diagnostic=(CHECKOUT_DIAGNOSTIC,),
    ),
    recovery=RecoveryPolicySpec(
        directives=(
            "refresh_payment_providers",
            "reconcile_unknown_payment_selection",
        ),
        failure_surface=CHECKOUT_ERROR.ref,
    ),
)
REVIEW_NODE = NodeSpec(
    id="checkout.review",
    title="Review",
    kind=NodeKind.WORKFLOW,
    route=RouteSpec(
        template="/checkout/review",
        deep_link_policy=DeepLinkPolicy.SESSION_BOUND,
    ),
    context_providers=(CHECKOUT_FACTS_PROVIDER,),
    guards=(REVIEW_CURRENT_GUARD,),
    operations=(PLACE_ORDER,),
    capabilities=(CHECKOUT_CAPABILITY,),
    surfaces=SurfaceSlotsSpec(
        active=ORDER_REVIEW,
        frame=(CHECKOUT_FRAME,),
        review=(CHECKOUT_REVIEW,),
        status=(CHECKOUT_STATUS,),
        error=(CHECKOUT_ERROR,),
        diagnostic=(CHECKOUT_DIAGNOSTIC, CHECKOUT_RECOVERY),
    ),
    recovery=RecoveryPolicySpec(
        directives=("refresh_review", "reconcile_unknown_order"),
        failure_surface=CHECKOUT_RECOVERY.ref,
    ),
)

FEATURE_SPEC = FeatureSpec(
    namespace="checkout",
    agent_policies=(PROTECTED_CHECKOUT_INPUT_POLICY,),
    policy_refs=(PROTECTED_CHECKOUT_INPUT_POLICY.ref,),
    nodes=(CONTACT_NODE, DELIVERY_NODE, PAYMENT_NODE, REVIEW_NODE),
    transitions=(
        TransitionSpec(
            source=CONTACT_NODE.ref,
            operation=SAVE_CONTACT.ref,
            outcome=MedusaOutcomeType.SAVED,
            target=DELIVERY_NODE.ref,
        ),
        TransitionSpec(
            source=DELIVERY_NODE.ref,
            operation=SELECT_SHIPPING.ref,
            outcome=MedusaOutcomeType.SELECTED,
            target=PAYMENT_NODE.ref,
        ),
        TransitionSpec(
            source=PAYMENT_NODE.ref,
            operation=SELECT_PAYMENT.ref,
            outcome=MedusaOutcomeType.SELECTED,
            target=REVIEW_NODE.ref,
        ),
        TransitionSpec(
            source=REVIEW_NODE.ref,
            operation=PLACE_ORDER.ref,
            outcome=MedusaOutcomeType.CHECKOUT_FAILED,
            target=REVIEW_NODE.ref,
        ),
    ),
)


__all__ = [
    "CHECKOUT_CAPABILITY",
    "CHECKOUT_FACTS_PROVIDER",
    "CHECKOUT_READY_GUARD",
    "CHECKOUT_START",
    "CONTACT_FORM",
    "CONTACT_NODE",
    "CONTACT_VALID_GUARD",
    "DELIVERY_NODE",
    "FEATURE_SPEC",
    "PLACE_ORDER",
    "PAYMENT_METHOD",
    "PAYMENT_PROVIDERS_PROVIDER",
    "PAYMENT_VALID_GUARD",
    "PROTECTED_CHECKOUT_INPUT_POLICY",
    "SAVE_CONTACT",
    "SELECT_SHIPPING",
    "SELECT_PAYMENT",
    "SHIPPING_OPTIONS",
    "SHIPPING_OPTIONS_PROVIDER",
    "SHIPPING_VALID_GUARD",
    "REVIEW_CURRENT_GUARD",
    "REVIEW_NODE",
    "CHECKOUT_RECOVERY",
    "CHECKOUT_REVIEW",
    "ORDER_REVIEW",
    "START_CHECKOUT_AFFORDANCE",
]
