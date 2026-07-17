from __future__ import annotations

from routedeck_core.app import Feature
from routedeck_core.contracts.application import Capability, Node
from routedeck_core.contracts.navigation import (
    DeepLinkPolicy,
    NavigationPolicy,
    NodeKind,
    RecoveryPolicy,
    Route,
    Transition,
)
from routedeck_core.contracts.surfaces import (
    PrivateFormBinding,
    Surface,
    SurfaceAffordance,
    SurfaceLifecycle,
    SurfaceSlots,
)
from routedeck_core.contracts.projection import FrozenJsonObject

from ...identifiers import MedusaOutcomeType
from ..orders.declarations import (
    ORDER_CONFIRMATION_REF,
    ORDER_PROVIDER,
    RECONCILE_ORDER,
    RECONCILE_ORDER_AFFORDANCE,
)
from .declarations import (
    CHECKOUT_DELIVERY_REF,
    CHECKOUT_FACTS_PROVIDER,
    CHECKOUT_READY_GUARD,
    CHECKOUT_PAYMENT_REF,
    CHECKOUT_REVIEW_REF,
    CHECKOUT_START,
    CONTACT_VALID_GUARD,
    PAYMENT_PROVIDERS_PROVIDER,
    PAYMENT_VALID_GUARD,
    PLACE_ORDER,
    PROTECTED_CHECKOUT_INPUT_POLICY,
    REVIEW_CURRENT_GUARD,
    SAVE_CONTACT,
    SELECT_PAYMENT,
    SELECT_SHIPPING,
    SHIPPING_OPTIONS_PROVIDER,
    SHIPPING_VALID_GUARD,
    START_CHECKOUT_AFFORDANCE,
)
from .schemas import (
    CONTACT_FORM_SCHEMA,
    ORDER_REVIEW_SCHEMA,
    PAYMENT_METHOD_SCHEMA,
    RECOVERY_SCHEMA,
    REVIEW_PENDING_SCHEMA,
    SHIPPING_OPTIONS_SCHEMA,
)
from .models import CONTACT_FIELD_NAMES

CHECKOUT_FRAME = Surface(
    id="checkout.frame",
    component="checkout.frame",
    lifecycle=SurfaceLifecycle.STABLE,
)
CHECKOUT_PRIVATE_FORM_BINDING = PrivateFormBinding(
    form_id_prop="form_handle",
    allowed_field_names=CONTACT_FIELD_NAMES,
)
CONTACT_FORM = Surface(
    id="checkout.contact_form",
    component="checkout.contact_form",
    lifecycle=SurfaceLifecycle.STABLE,
    affordances=(
        SurfaceAffordance(
            id="save_contact", event="submit", operation=SAVE_CONTACT.ref
        ),
    ),
    private_form_binding=CHECKOUT_PRIVATE_FORM_BINDING,
    public_props_schema=FrozenJsonObject(CONTACT_FORM_SCHEMA),
)
SHIPPING_OPTIONS = Surface(
    id="checkout.shipping_options",
    component="checkout.shipping_options",
    lifecycle=SurfaceLifecycle.STABLE,
    affordances=(
        SurfaceAffordance(
            id="select_shipping", event="select", operation=SELECT_SHIPPING.ref
        ),
    ),
    public_props_schema=FrozenJsonObject(SHIPPING_OPTIONS_SCHEMA),
)
PAYMENT_METHOD = Surface(
    id="checkout.payment_method",
    component="checkout.payment_method",
    lifecycle=SurfaceLifecycle.STABLE,
    affordances=(
        SurfaceAffordance(
            id="select_payment", event="select", operation=SELECT_PAYMENT.ref
        ),
    ),
    public_props_schema=FrozenJsonObject(PAYMENT_METHOD_SCHEMA),
)
ORDER_REVIEW = Surface(
    id="checkout.order_review",
    component="checkout.order_review",
    lifecycle=SurfaceLifecycle.STABLE,
    affordances=(
        SurfaceAffordance(
            id="propose_order", event="submit", operation=PLACE_ORDER.ref
        ),
    ),
    private_form_binding=CHECKOUT_PRIVATE_FORM_BINDING,
    public_props_schema=FrozenJsonObject(ORDER_REVIEW_SCHEMA),
)
CHECKOUT_REVIEW = Surface(
    id="checkout.review",
    component="checkout.review",
    lifecycle=SurfaceLifecycle.STABLE,
    public_props_schema=FrozenJsonObject(REVIEW_PENDING_SCHEMA),
)
CHECKOUT_STATUS = Surface(
    id="checkout.status",
    component="checkout.status",
    lifecycle=SurfaceLifecycle.STABLE,
)
CHECKOUT_ERROR = Surface(
    id="checkout.error",
    component="checkout.error",
    lifecycle=SurfaceLifecycle.STABLE,
)
CHECKOUT_RECOVERY = Surface(
    id="checkout.recovery",
    component="checkout.recovery",
    lifecycle=SurfaceLifecycle.STABLE,
    affordances=(RECONCILE_ORDER_AFFORDANCE,),
    public_props_schema=FrozenJsonObject(RECOVERY_SCHEMA),
)
CHECKOUT_DIAGNOSTIC = Surface(
    id="checkout.diagnostic",
    component="checkout.diagnostic",
)

CHECKOUT_CAPABILITY = Capability(
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
ORDER_RECOVERY_CAPABILITY = Capability(
    id="orders.recovery",
    title="Order recovery",
    operations=(RECONCILE_ORDER.ref,),
    surfaces=(CHECKOUT_RECOVERY.ref,),
)

CONTACT_NODE = Node(
    id="checkout.contact",
    title="Contact",
    kind=NodeKind.WORKFLOW,
    route=Route(
        template="/checkout/contact",
        deep_link_policy=DeepLinkPolicy.SESSION_BOUND,
    ),
    context_providers=(CHECKOUT_FACTS_PROVIDER,),
    guards=(CHECKOUT_READY_GUARD, CONTACT_VALID_GUARD),
    operations=(SAVE_CONTACT,),
    outgoing=(
        Transition(
            operation=SAVE_CONTACT.ref,
            outcome=MedusaOutcomeType.SAVED,
            target=CHECKOUT_DELIVERY_REF,
        ),
    ),
    capabilities=(CHECKOUT_CAPABILITY,),
    surfaces=SurfaceSlots(
        active=CONTACT_FORM,
        frame=(CHECKOUT_FRAME,),
        form=(CONTACT_FORM,),
        status=(CHECKOUT_STATUS,),
        error=(CHECKOUT_ERROR,),
        diagnostic=(CHECKOUT_DIAGNOSTIC,),
    ),
    navigation=NavigationPolicy(),
    recovery=RecoveryPolicy(
        directives=("retry_contact", "reconcile_unknown_contact"),
        failure_surface=CHECKOUT_ERROR.ref,
    ),
)
DELIVERY_NODE = Node(
    id="checkout.delivery",
    title="Delivery",
    kind=NodeKind.WORKFLOW,
    route=Route(
        template="/checkout/delivery",
        deep_link_policy=DeepLinkPolicy.SESSION_BOUND,
    ),
    context_providers=(CHECKOUT_FACTS_PROVIDER,),
    entity_providers=(SHIPPING_OPTIONS_PROVIDER,),
    guards=(CHECKOUT_READY_GUARD, SHIPPING_VALID_GUARD),
    operations=(SELECT_SHIPPING,),
    outgoing=(
        Transition(
            operation=SELECT_SHIPPING.ref,
            outcome=MedusaOutcomeType.SELECTED,
            target=CHECKOUT_PAYMENT_REF,
        ),
    ),
    capabilities=(CHECKOUT_CAPABILITY,),
    surfaces=SurfaceSlots(
        active=SHIPPING_OPTIONS,
        frame=(CHECKOUT_FRAME,),
        detail=(SHIPPING_OPTIONS,),
        status=(CHECKOUT_STATUS,),
        error=(CHECKOUT_ERROR,),
        diagnostic=(CHECKOUT_DIAGNOSTIC,),
    ),
    recovery=RecoveryPolicy(
        directives=(
            "refresh_shipping_options",
            "reconcile_unknown_shipping_selection",
        ),
        failure_surface=CHECKOUT_ERROR.ref,
    ),
)
PAYMENT_NODE = Node(
    id="checkout.payment",
    title="Payment",
    kind=NodeKind.WORKFLOW,
    route=Route(
        template="/checkout/payment",
        deep_link_policy=DeepLinkPolicy.SESSION_BOUND,
    ),
    context_providers=(CHECKOUT_FACTS_PROVIDER,),
    entity_providers=(SHIPPING_OPTIONS_PROVIDER, PAYMENT_PROVIDERS_PROVIDER),
    guards=(CHECKOUT_READY_GUARD, PAYMENT_VALID_GUARD),
    operations=(SELECT_PAYMENT,),
    outgoing=(
        Transition(
            operation=SELECT_PAYMENT.ref,
            outcome=MedusaOutcomeType.SELECTED,
            target=CHECKOUT_REVIEW_REF,
        ),
    ),
    capabilities=(CHECKOUT_CAPABILITY,),
    surfaces=SurfaceSlots(
        active=PAYMENT_METHOD,
        frame=(CHECKOUT_FRAME,),
        detail=(PAYMENT_METHOD,),
        status=(CHECKOUT_STATUS,),
        error=(CHECKOUT_ERROR,),
        diagnostic=(CHECKOUT_DIAGNOSTIC,),
    ),
    recovery=RecoveryPolicy(
        directives=(
            "refresh_payment_providers",
            "reconcile_unknown_payment_selection",
        ),
        failure_surface=CHECKOUT_ERROR.ref,
    ),
)
REVIEW_NODE = Node(
    id="checkout.review",
    title="Review",
    kind=NodeKind.WORKFLOW,
    route=Route(
        template="/checkout/review",
        deep_link_policy=DeepLinkPolicy.SESSION_BOUND,
    ),
    context_providers=(CHECKOUT_FACTS_PROVIDER,),
    entity_providers=(ORDER_PROVIDER,),
    guards=(REVIEW_CURRENT_GUARD,),
    operations=(PLACE_ORDER, RECONCILE_ORDER),
    outgoing=(
        Transition(
            operation=PLACE_ORDER.ref,
            outcome=MedusaOutcomeType.CHECKOUT_FAILED,
            target=CHECKOUT_REVIEW_REF,
        ),
        Transition(
            operation=PLACE_ORDER.ref,
            outcome=MedusaOutcomeType.ORDER_CREATED,
            target=ORDER_CONFIRMATION_REF,
        ),
        Transition(
            operation=RECONCILE_ORDER.ref,
            outcome=MedusaOutcomeType.VERIFIED,
            target=ORDER_CONFIRMATION_REF,
        ),
    ),
    capabilities=(CHECKOUT_CAPABILITY, ORDER_RECOVERY_CAPABILITY),
    surfaces=SurfaceSlots(
        active=ORDER_REVIEW,
        frame=(CHECKOUT_FRAME,),
        review=(CHECKOUT_REVIEW,),
        status=(CHECKOUT_STATUS,),
        error=(CHECKOUT_ERROR,),
        diagnostic=(CHECKOUT_DIAGNOSTIC, CHECKOUT_RECOVERY),
    ),
    recovery=RecoveryPolicy(
        directives=("refresh_review", "reconcile_unknown_order"),
        failure_surface=CHECKOUT_RECOVERY.ref,
    ),
)

FEATURE = Feature(
    namespace="checkout",
    agent_policies=(PROTECTED_CHECKOUT_INPUT_POLICY,),
    policy_refs=(PROTECTED_CHECKOUT_INPUT_POLICY.ref,),
    nodes=(CONTACT_NODE, DELIVERY_NODE, PAYMENT_NODE, REVIEW_NODE),
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
    "FEATURE",
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
