from __future__ import annotations

from dataclasses import dataclass

from routedeck_core.contracts.failures import (
    FailureKind,
    FailureSafeDetails,
    RouteDeckFailure,
)
from routedeck_core.supervision.guards import GuardDecision, GuardInvocationContext

from ...medusa.client.models import MedusaClientFailureKind
from .feature import (
    CHECKOUT_FACTS_PROVIDER,
    PAYMENT_PROVIDERS_PROVIDER,
    SHIPPING_OPTIONS_PROVIDER,
)
from .models import (
    CheckoutFactsContext,
    CheckoutFactsState,
    PaymentProviderContext,
    PaymentProviderState,
    ShippingOptionsContext,
    ShippingProviderState,
)


_FAILURE_KINDS = {
    MedusaClientFailureKind.TRANSPORT: FailureKind.TRANSPORT,
    MedusaClientFailureKind.PROVIDER_PROTOCOL: FailureKind.PROVIDER_PROTOCOL,
    MedusaClientFailureKind.BUSINESS: FailureKind.BUSINESS,
}


class CheckoutReadyGuard:
    async def __call__(self, context: GuardInvocationContext) -> GuardDecision:
        facts = _checkout_facts(context)
        if facts.state is CheckoutFactsState.MISSING:
            return GuardDecision.blocked(
                _failure(
                    context,
                    kind=FailureKind.GUARD,
                    code="cart_required",
                    message="Add an item to a cart before starting checkout.",
                )
            )
        if facts.state is CheckoutFactsState.REFRESH_FAILED:
            return GuardDecision.blocked(_facts_failure(context, facts))
        cart = facts.cart
        if cart is None:
            raise TypeError("ready checkout facts are missing the cart")
        if cart.item_count == 0:
            return GuardDecision.blocked(
                _failure(
                    context,
                    kind=FailureKind.BUSINESS,
                    code="cart_empty",
                    message="Add at least one item before starting checkout.",
                )
            )
        return GuardDecision.allowed_result()


class ContactValidGuard:
    async def __call__(self, context: GuardInvocationContext) -> GuardDecision:
        form_handle = context.request.arguments.to_dict().get("form_handle")
        if not isinstance(form_handle, str) or not form_handle:
            return GuardDecision.needs_input(
                _failure(
                    context,
                    kind=FailureKind.GUARD,
                    code="private_form_required",
                    message="Complete the contact form before continuing.",
                )
            )
        drafts = tuple(
            draft
            for draft in context.session.private_state.drafts
            if draft.form_id == form_handle
        )
        if len(drafts) != 1:
            return GuardDecision.needs_input(
                _failure(
                    context,
                    kind=FailureKind.GUARD,
                    code="private_form_not_found",
                    message="Complete the contact form before continuing.",
                )
            )
        if not drafts[0].complete:
            return GuardDecision.needs_input(
                _failure(
                    context,
                    kind=FailureKind.GUARD,
                    code="private_form_incomplete",
                    message="Complete every required contact field before continuing.",
                )
            )
        return GuardDecision.allowed_result()


class ShippingValidGuard:
    async def __call__(self, context: GuardInvocationContext) -> GuardDecision:
        facts = _checkout_facts(context)
        if facts.state is not CheckoutFactsState.READY or facts.cart is None:
            if facts.state is CheckoutFactsState.REFRESH_FAILED:
                return GuardDecision.blocked(_facts_failure(context, facts))
            return GuardDecision.blocked(
                _failure(
                    context,
                    kind=FailureKind.GUARD,
                    code="cart_required",
                    message="A cart is required before selecting delivery.",
                )
            )
        if not facts.cart.contact_saved:
            return GuardDecision.blocked(
                _failure(
                    context,
                    kind=FailureKind.GUARD,
                    code="contact_required",
                    message="Save contact and address details before selecting delivery.",
                )
            )
        values = context.provider_values.to_dict().get(SHIPPING_OPTIONS_PROVIDER.id)
        if not isinstance(values, dict):
            raise TypeError("shipping guard requires typed provider values")
        shipping = ShippingOptionsContext.from_provider_values(values)
        if shipping.state is ShippingProviderState.EMPTY:
            return GuardDecision.blocked(
                _failure(
                    context,
                    kind=FailureKind.BUSINESS,
                    code="shipping_options_empty",
                    message=shipping.projection.message
                    or "No delivery options are available.",
                )
            )
        if shipping.state is ShippingProviderState.REFRESH_FAILED:
            if (
                shipping.failure_kind is None
                or shipping.failure_code is None
                or shipping.delivery_phase is None
            ):
                raise TypeError("failed shipping refresh is missing typed evidence")
            return GuardDecision.blocked(
                _failure(
                    context,
                    kind=_FAILURE_KINDS[shipping.failure_kind],
                    code=shipping.failure_code,
                    message=shipping.projection.message
                    or "Delivery options are unavailable.",
                    safe_details=FailureSafeDetails(
                        provider="medusa",
                        provider_code=shipping.failure_code,
                        delivery_phase=shipping.delivery_phase.value,
                    ),
                )
            )
        resolved = tuple(
            entity
            for entity in context.resolved_entities
            if entity.argument_name == "shipping_option_ref"
            and entity.entity_kind == "shipping_option"
        )
        current_ids = {binding.private_id for binding in shipping.bindings}
        if (
            len(resolved) != 1
            or resolved[0].private_id.get_secret_value() not in current_ids
        ):
            return GuardDecision.blocked(
                _failure(
                    context,
                    kind=FailureKind.GUARD,
                    code="shipping_option_not_current",
                    message="That delivery option is no longer available.",
                )
            )
        return GuardDecision.allowed_result()


@dataclass(frozen=True)
class PaymentValidGuard:
    configured_provider_id: str

    def __post_init__(self) -> None:
        if not self.configured_provider_id:
            raise ValueError("configured payment provider ID must be non-empty")

    async def __call__(self, context: GuardInvocationContext) -> GuardDecision:
        facts = _checkout_facts(context)
        if facts.state is not CheckoutFactsState.READY or facts.cart is None:
            if facts.state is CheckoutFactsState.REFRESH_FAILED:
                return GuardDecision.blocked(_facts_failure(context, facts))
            return GuardDecision.blocked(
                _failure(
                    context,
                    kind=FailureKind.GUARD,
                    code="cart_required",
                    message="A cart is required before selecting payment.",
                )
            )
        cart = facts.cart
        if (
            not cart.items
            or not cart.contact_saved
            or not cart.billing_complete
            or cart.contact_form_handle is None
            or not cart.shipping_selected
            or cart.shipping is None
        ):
            return GuardDecision.blocked(
                _failure(
                    context,
                    kind=FailureKind.GUARD,
                    code="checkout_incomplete",
                    message="Complete contact and delivery before selecting payment.",
                )
            )
        payment = _payment_context(context)
        unavailable = _payment_unavailable_failure(context, payment)
        if unavailable is not None:
            return GuardDecision.blocked(unavailable)
        if payment.state is not PaymentProviderState.READY:
            raise TypeError("payment guard requires a ready typed provider")
        resolved = tuple(
            entity
            for entity in context.resolved_entities
            if entity.argument_name == "payment_provider_ref"
            and entity.entity_kind == "payment_provider"
        )
        if (
            len(payment.bindings) != 1
            or payment.bindings[0].private_id != self.configured_provider_id
            or len(resolved) != 1
            or resolved[0].private_id.get_secret_value() != self.configured_provider_id
        ):
            return GuardDecision.blocked(
                _failure(
                    context,
                    kind=FailureKind.GUARD,
                    code="payment_provider_not_current",
                    message="That payment method is no longer available.",
                )
            )
        return GuardDecision.allowed_result()


@dataclass(frozen=True)
class ReviewCurrentGuard:
    configured_provider_id: str

    def __post_init__(self) -> None:
        if not self.configured_provider_id:
            raise ValueError("configured payment provider ID must be non-empty")

    async def __call__(self, context: GuardInvocationContext) -> GuardDecision:
        facts = _checkout_facts(context)
        if facts.state is not CheckoutFactsState.READY or facts.cart is None:
            if facts.state is CheckoutFactsState.REFRESH_FAILED:
                return GuardDecision.blocked(_facts_failure(context, facts))
            return GuardDecision.blocked(
                _failure(
                    context,
                    kind=FailureKind.GUARD,
                    code="cart_required",
                    message="The checkout cart is unavailable.",
                )
            )
        cart = facts.cart
        if (
            not cart.items
            or not cart.contact_saved
            or not cart.billing_complete
            or cart.contact_form_handle is None
            or cart.shipping is None
            or cart.payment_provider_ids != (self.configured_provider_id,)
        ):
            return GuardDecision.blocked(
                _failure(
                    context,
                    kind=FailureKind.GUARD,
                    code="review_incomplete",
                    message="Refresh the checkout before placing the order.",
                )
            )
        return GuardDecision.allowed_result()


def _checkout_facts(context: GuardInvocationContext) -> CheckoutFactsContext:
    values = context.provider_values.to_dict().get(CHECKOUT_FACTS_PROVIDER.id)
    if not isinstance(values, dict):
        raise TypeError("checkout guard requires typed cart facts")
    return CheckoutFactsContext.from_provider_values(values)


def _payment_context(context: GuardInvocationContext) -> PaymentProviderContext:
    values = context.provider_values.to_dict().get(PAYMENT_PROVIDERS_PROVIDER.id)
    if not isinstance(values, dict):
        raise TypeError("payment guard requires typed provider values")
    return PaymentProviderContext.from_provider_values(values)


def _payment_unavailable_failure(
    context: GuardInvocationContext,
    payment: PaymentProviderContext,
) -> RouteDeckFailure | None:
    if payment.state is PaymentProviderState.MISSING:
        return _failure(
            context,
            kind=FailureKind.BUSINESS,
            code="payment_provider_unavailable",
            message=payment.projection.message
            or "The configured payment method is unavailable.",
        )
    if payment.state is PaymentProviderState.REFRESH_FAILED:
        if (
            payment.failure_kind is None
            or payment.failure_code is None
            or payment.delivery_phase is None
        ):
            raise TypeError("failed payment refresh is missing typed evidence")
        return _failure(
            context,
            kind=_FAILURE_KINDS[payment.failure_kind],
            code=payment.failure_code,
            message=payment.projection.message
            or "The payment method could not be verified.",
            safe_details=FailureSafeDetails(
                provider="medusa",
                provider_code=payment.failure_code,
                delivery_phase=payment.delivery_phase.value,
            ),
        )
    return None


def _facts_failure(
    context: GuardInvocationContext,
    facts: CheckoutFactsContext,
) -> RouteDeckFailure:
    if (
        facts.failure_kind is None
        or facts.failure_code is None
        or facts.public_message is None
        or facts.delivery_phase is None
    ):
        raise TypeError("failed checkout facts are missing typed evidence")
    return _failure(
        context,
        kind=_FAILURE_KINDS[facts.failure_kind],
        code=facts.failure_code,
        message=facts.public_message,
        safe_details=FailureSafeDetails(
            provider="medusa",
            provider_code=facts.failure_code,
            delivery_phase=facts.delivery_phase.value,
        ),
    )


def _failure(
    context: GuardInvocationContext,
    *,
    kind: FailureKind,
    code: str,
    message: str,
    safe_details: FailureSafeDetails | None = None,
) -> RouteDeckFailure:
    return RouteDeckFailure(
        kind=kind,
        code=code,
        phase="guard",
        correlation_id=context.attempt_id,
        operation_id=context.request.operation_id,
        request_id=context.request.request_id,
        public_message=message,
        safe_details=safe_details or FailureSafeDetails(),
    )


__all__ = [
    "CheckoutReadyGuard",
    "ContactValidGuard",
    "PaymentValidGuard",
    "ReviewCurrentGuard",
    "ShippingValidGuard",
]
