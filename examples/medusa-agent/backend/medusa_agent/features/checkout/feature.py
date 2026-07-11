from __future__ import annotations

from routedeck_core.app import FeatureSpec
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
    GuardSpec,
    OperationSpec,
    ReviewPolicy,
    SafetyClass,
)
from routedeck_core.contracts.surfaces import (
    SurfaceAffordanceSpec,
    SurfaceLifecycle,
    SurfaceSlotsSpec,
    SurfaceSpec,
)


CHECKOUT_FACTS_PROVIDER = ContextProviderSpec(
    id="checkout.facts",
    description="Authoritative cart, address, delivery, payment, and totals facts.",
)
SHIPPING_OPTIONS_PROVIDER = ContextProviderSpec(
    id="checkout.shipping_options",
    description="Shipping options available for the current cart.",
)
PAYMENT_PROVIDERS_PROVIDER = ContextProviderSpec(
    id="checkout.payment_providers",
    description="Configured payment providers available for the current checkout.",
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
    id="checkout.start",
    title="Start checkout",
    description="Enter guest checkout with the current cart.",
    safety_class=SafetyClass.NAVIGATION,
    outcomes=("started",),
    provider_refs=(CHECKOUT_FACTS_PROVIDER.ref,),
    guard_refs=(CHECKOUT_READY_GUARD.ref,),
)
START_CHECKOUT_AFFORDANCE = SurfaceAffordanceSpec(
    id="start_checkout",
    event="submit",
    operation=CHECKOUT_START.ref,
)
SAVE_CONTACT = OperationSpec(
    id="checkout.save_contact",
    title="Save guest contact",
    description="Validate and save guest contact and address values.",
    input_schema={
        "type": "object",
        "required": ["contact"],
        "properties": {"contact": {"type": "object", "sensitive": True}},
    },
    safety_class=SafetyClass.WRITE_EXTERNAL,
    outcomes=("saved",),
    provider_refs=(CHECKOUT_FACTS_PROVIDER.ref,),
    guard_refs=(CONTACT_VALID_GUARD.ref,),
)
SELECT_SHIPPING = OperationSpec(
    id="checkout.select_shipping",
    title="Select delivery",
    description="Select an offered shipping option for the current cart.",
    input_schema={
        "type": "object",
        "required": ["shipping_option_ref"],
        "properties": {"shipping_option_ref": {"type": "string"}},
    },
    safety_class=SafetyClass.WRITE_EXTERNAL,
    outcomes=("selected",),
    provider_refs=(SHIPPING_OPTIONS_PROVIDER.ref,),
    guard_refs=(SHIPPING_VALID_GUARD.ref,),
)
SELECT_PAYMENT = OperationSpec(
    id="checkout.select_payment",
    title="Select payment",
    description="Select and initialize the configured payment provider.",
    input_schema={
        "type": "object",
        "required": ["payment_provider_ref"],
        "properties": {"payment_provider_ref": {"type": "string"}},
    },
    safety_class=SafetyClass.WRITE_EXTERNAL,
    outcomes=("selected",),
    provider_refs=(PAYMENT_PROVIDERS_PROVIDER.ref,),
    guard_refs=(PAYMENT_VALID_GUARD.ref,),
)
PLACE_ORDER = OperationSpec(
    id="checkout.place_order",
    title="Place order",
    description="Complete the reviewed cart exactly once.",
    safety_class=SafetyClass.WRITE_EXTERNAL,
    review_policy=ReviewPolicy.REQUIRED,
    outcomes=("order_created", "checkout_failed", "external_outcome_unknown"),
    provider_refs=(CHECKOUT_FACTS_PROVIDER.ref,),
    guard_refs=(REVIEW_CURRENT_GUARD.ref,),
)

CHECKOUT_FRAME = SurfaceSpec(
    id="checkout.frame",
    component="checkout.frame",
    lifecycle=SurfaceLifecycle.STABLE,
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
)
CHECKOUT_REVIEW = SurfaceSpec(
    id="checkout.review",
    component="checkout.review",
    lifecycle=SurfaceLifecycle.STABLE,
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
    guards=(CONTACT_VALID_GUARD,),
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
        directives=("retry_contact",), failure_surface=CHECKOUT_ERROR.ref
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
    context_providers=(CHECKOUT_FACTS_PROVIDER, SHIPPING_OPTIONS_PROVIDER),
    guards=(SHIPPING_VALID_GUARD,),
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
        directives=("refresh_shipping_options",),
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
    context_providers=(CHECKOUT_FACTS_PROVIDER, PAYMENT_PROVIDERS_PROVIDER),
    guards=(PAYMENT_VALID_GUARD,),
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
        directives=("refresh_payment_providers",),
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
    nodes=(CONTACT_NODE, DELIVERY_NODE, PAYMENT_NODE, REVIEW_NODE),
    transitions=(
        TransitionSpec(
            source=CONTACT_NODE.ref,
            operation=SAVE_CONTACT.ref,
            outcome="saved",
            target=DELIVERY_NODE.ref,
        ),
        TransitionSpec(
            source=DELIVERY_NODE.ref,
            operation=SELECT_SHIPPING.ref,
            outcome="selected",
            target=PAYMENT_NODE.ref,
        ),
        TransitionSpec(
            source=PAYMENT_NODE.ref,
            operation=SELECT_PAYMENT.ref,
            outcome="selected",
            target=REVIEW_NODE.ref,
        ),
        TransitionSpec(
            source=REVIEW_NODE.ref,
            operation=PLACE_ORDER.ref,
            outcome="checkout_failed",
            target=REVIEW_NODE.ref,
        ),
        TransitionSpec(
            source=REVIEW_NODE.ref,
            operation=PLACE_ORDER.ref,
            outcome="external_outcome_unknown",
            target=REVIEW_NODE.ref,
        ),
    ),
)


__all__ = [
    "CHECKOUT_CAPABILITY",
    "CHECKOUT_FACTS_PROVIDER",
    "CHECKOUT_READY_GUARD",
    "CHECKOUT_START",
    "CONTACT_NODE",
    "FEATURE_SPEC",
    "PLACE_ORDER",
    "REVIEW_NODE",
    "START_CHECKOUT_AFFORDANCE",
]
