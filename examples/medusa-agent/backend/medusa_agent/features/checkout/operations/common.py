from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from routedeck_core.contracts.failures import (
    FailureKind,
    FailureSafeDetails,
    RouteDeckFailure,
)
from routedeck_core.contracts.operations import DeliveryPhase, OperationOutcome
from routedeck_core.contracts.projection import FrozenJson, PublicValue
from routedeck_core.ports.executor import ExecutionContext

from ....medusa.client.models import (
    MedusaClientFailure,
    MedusaClientFailureKind,
)
from ..feature import (
    CHECKOUT_FACTS_PROVIDER,
    PAYMENT_PROVIDERS_PROVIDER,
    SAVE_CONTACT,
    SHIPPING_OPTIONS_PROVIDER,
)
from ..models import (
    BillingChoice,
    CheckoutFactsContext,
    CheckoutFactsState,
    PaymentProviderContext,
    PaymentProviderState,
    PrivateContactDraft,
    ShippingOptionsContext,
    ShippingProviderState,
)
from ..providers import PrivateContactDraftError


MEDUSA_FAILURE_KIND_MAP = {
    MedusaClientFailureKind.TRANSPORT: FailureKind.TRANSPORT,
    MedusaClientFailureKind.PROVIDER_PROTOCOL: FailureKind.PROVIDER_PROTOCOL,
    MedusaClientFailureKind.BUSINESS: FailureKind.BUSINESS,
}


def require_current_cart(context: ExecutionContext):
    values = context.provider_values.to_dict().get(CHECKOUT_FACTS_PROVIDER.id)
    if not isinstance(values, dict):
        raise RuntimeError("checkout operation requires typed cart facts")
    facts = CheckoutFactsContext.from_provider_values(values)
    if facts.state is not CheckoutFactsState.READY or facts.cart is None:
        raise RuntimeError("checkout operation requires an authoritative cart")
    return facts.cart


def require_current_shipping(context: ExecutionContext) -> ShippingOptionsContext:
    values = context.provider_values.to_dict().get(SHIPPING_OPTIONS_PROVIDER.id)
    if not isinstance(values, dict):
        raise RuntimeError("delivery operation requires typed options")
    shipping = ShippingOptionsContext.from_provider_values(values)
    if shipping.state is not ShippingProviderState.READY:
        raise RuntimeError("delivery operation requires current options")
    return shipping


def require_current_payment(context: ExecutionContext) -> PaymentProviderContext:
    values = context.provider_values.to_dict().get(PAYMENT_PROVIDERS_PROVIDER.id)
    if not isinstance(values, dict):
        raise RuntimeError("payment operation requires typed provider values")
    payment = PaymentProviderContext.from_provider_values(values)
    if payment.state is not PaymentProviderState.READY:
        raise RuntimeError("payment operation requires the configured provider")
    return payment


def private_form_failure(
    context: ExecutionContext,
    error: PrivateContactDraftError,
) -> OperationOutcome:
    return OperationOutcome(
        delivery_phase=DeliveryPhase.NOT_SENT,
        failure=RouteDeckFailure(
            kind=FailureKind.BUSINESS,
            code=error.code,
            phase="private_form_validation",
            correlation_id=context.attempt_id,
            operation_id=SAVE_CONTACT.id,
            request_id=context.request_id,
            public_message=error.public_message,
            safe_details=FailureSafeDetails(delivery_phase="not_sent"),
        ),
    )


def contact_country_failure(
    contact: PrivateContactDraft,
    buyer_country_code: str,
) -> PrivateContactDraftError | None:
    addresses = [contact.shipping_address]
    if contact.billing_choice is BillingChoice.SEPARATE:
        if contact.billing_address is None:
            raise RuntimeError("validated separate billing contact has no address")
        addresses.append(contact.billing_address)
    if any(address.country_code != buyer_country_code for address in addresses):
        return PrivateContactDraftError(
            "contact_country_not_allowed",
            "Choose the configured buyer country for shipping and billing.",
        )
    return None


def operation_failure(
    *,
    context: ExecutionContext,
    operation_id: str,
    delivery_phase: DeliveryPhase,
    failure: MedusaClientFailure,
) -> OperationOutcome:
    return OperationOutcome(
        delivery_phase=delivery_phase,
        failure=RouteDeckFailure(
            kind=MEDUSA_FAILURE_KIND_MAP[failure.kind],
            code=failure.code,
            phase="execute",
            correlation_id=context.attempt_id,
            operation_id=operation_id,
            request_id=context.request_id,
            public_message=failure.public_message,
            safe_details=FailureSafeDetails(
                provider="medusa",
                provider_code=failure.code,
                delivery_phase=delivery_phase.value,
            ),
        ),
    )


def protocol_failure(
    *,
    context: ExecutionContext,
    operation_id: str,
    code: str,
    message: str,
) -> OperationOutcome:
    return operation_failure(
        context=context,
        operation_id=operation_id,
        delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
        failure=MedusaClientFailure(
            kind=MedusaClientFailureKind.PROVIDER_PROTOCOL,
            code=code,
            public_message=message,
        ),
    )


def prewrite_business_failure(
    *,
    context: ExecutionContext,
    operation_id: str,
    code: str,
    message: str,
) -> OperationOutcome:
    return operation_failure(
        context=context,
        operation_id=operation_id,
        delivery_phase=DeliveryPhase.NOT_SENT,
        failure=MedusaClientFailure(
            kind=MedusaClientFailureKind.BUSINESS,
            code=code,
            public_message=message,
        ),
    )


def require_exact_arguments(
    arguments: Mapping[str, Any],
    *,
    expected: tuple[str, ...],
    operation_id: str,
) -> None:
    if set(arguments) != set(expected):
        raise ValueError(
            f"{operation_id} requires exactly these arguments: {expected!r}"
        )


def require_string(arguments: Mapping[str, Any], name: str) -> str:
    value = arguments.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def public_values(values: Mapping[str, Any]) -> tuple[PublicValue, ...]:
    return tuple(
        PublicValue(name=name, value=FrozenJson(value))
        for name, value in values.items()
    )


__all__ = [
    "contact_country_failure",
    "operation_failure",
    "prewrite_business_failure",
    "private_form_failure",
    "protocol_failure",
    "public_values",
    "require_current_cart",
    "require_current_payment",
    "require_current_shipping",
    "require_exact_arguments",
    "require_string",
]
