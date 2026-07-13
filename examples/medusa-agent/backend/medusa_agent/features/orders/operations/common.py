from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import SecretStr

from routedeck_core.contracts.effects import (
    EntityBindingEffect,
    EntityKindEffects,
    ExactRouteParameter,
    PublicSurfaceEffect,
    SessionEffects,
)
from routedeck_core.contracts.failures import (
    FailureKind,
    FailureSafeDetails,
    RouteDeckFailure,
)
from routedeck_core.contracts.operations import DeliveryPhase, OperationOutcome
from routedeck_core.contracts.projection import (
    FrozenJson,
    PublicEntityHandle,
    PublicValue,
)
from routedeck_core.ports.executor import ExecutionContext

from ....medusa.client.models import (
    MedusaClientFailure,
    MedusaClientFailureKind,
    Order,
)
from ...checkout.feature import CHECKOUT_FACTS_PROVIDER, CHECKOUT_RECOVERY
from ...checkout.models import CheckoutFactsContext, CheckoutFactsState
from ..feature import ORDER_CONFIRMATION, RECONCILE_ORDER
from ..models import OrderConfirmationProjection

_FAILURE_KINDS = {
    MedusaClientFailureKind.TRANSPORT: FailureKind.TRANSPORT,
    MedusaClientFailureKind.PROVIDER_PROTOCOL: FailureKind.PROVIDER_PROTOCOL,
    MedusaClientFailureKind.BUSINESS: FailureKind.BUSINESS,
}


def reviewed_cart(context: ExecutionContext):
    values = context.provider_values.to_dict().get(CHECKOUT_FACTS_PROVIDER.id)
    if not isinstance(values, dict):
        raise RuntimeError("place order requires authoritative checkout facts")
    facts = CheckoutFactsContext.from_provider_values(values)
    if facts.state is not CheckoutFactsState.READY or facts.cart is None:
        raise RuntimeError("place order requires a ready checkout cart")
    return facts.cart


def recovery_effects(
    *,
    private_order_id: str,
    order_ref: str,
    expected_fingerprint: str,
    contact_form_handle: str,
    correlation_id: str,
) -> SessionEffects:
    recovery_values = {
        "state": "external_outcome_unknown",
        "message": "The order was submitted but its confirmation must be verified.",
        "correlation_id": correlation_id,
        "order_ref": order_ref,
    }
    return SessionEffects(
        replace_entities=(
            EntityKindEffects(
                entity_kind="order",
                bindings=(
                    EntityBindingEffect(
                        public=PublicEntityHandle(
                            entity_kind="order",
                            handle=order_ref,
                            values=(
                                PublicValue(
                                    name="verification_fingerprint",
                                    value=FrozenJson(expected_fingerprint),
                                ),
                                PublicValue(
                                    name="contact_form_handle",
                                    value=FrozenJson(contact_form_handle),
                                ),
                            ),
                        ),
                        private_id=SecretStr(private_order_id),
                        allowed_operation_ids=(RECONCILE_ORDER.id,),
                    ),
                ),
            ),
        ),
        surface_updates=(
            PublicSurfaceEffect(
                surface_id=CHECKOUT_RECOVERY.id,
                values=public_values(recovery_values),
            ),
        ),
    )


def confirmation_effects(
    *,
    order: Order,
    confirmation_handle: str,
    expected_fingerprint: str,
    contact_form_handle: str,
    projection: OrderConfirmationProjection,
) -> SessionEffects:
    return SessionEffects(
        replace_entities=(
            EntityKindEffects(entity_kind="cart"),
            EntityKindEffects(entity_kind="line_item"),
            EntityKindEffects(entity_kind="shipping_option"),
            EntityKindEffects(entity_kind="payment_provider"),
            EntityKindEffects(
                entity_kind="order",
                bindings=(
                    EntityBindingEffect(
                        public=PublicEntityHandle(
                            entity_kind="order",
                            handle=confirmation_handle,
                            values=(
                                PublicValue(
                                    name="verification_fingerprint",
                                    value=FrozenJson(expected_fingerprint),
                                ),
                            ),
                        ),
                        private_id=SecretStr(order.id.get_secret_value()),
                    ),
                ),
            ),
        ),
        surface_updates=(
            PublicSurfaceEffect(
                surface_id=ORDER_CONFIRMATION.id,
                values=public_values(
                    projection.model_dump(mode="json", exclude_none=True)
                ),
            ),
        ),
        remove_private_form_ids=(contact_form_handle,),
        route_params=(
            ExactRouteParameter(
                name="confirmation_handle",
                value=confirmation_handle,
            ),
        ),
        complete_session=True,
    )


def business_failure(
    *,
    context: ExecutionContext,
    operation_id: str,
    code: str,
    message: str,
) -> OperationOutcome:
    return OperationOutcome(
        delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
        failure=RouteDeckFailure(
            kind=FailureKind.BUSINESS,
            code=code,
            phase="complete_cart",
            correlation_id=context.attempt_id,
            operation_id=operation_id,
            request_id=context.request_id,
            public_message=message,
            safe_details=FailureSafeDetails(
                provider="medusa",
                provider_code=code,
                delivery_phase=DeliveryPhase.RESPONSE_RECEIVED.value,
            ),
        ),
    )


def unknown_failure(
    *,
    context: ExecutionContext,
    operation_id: str,
    delivery_phase: DeliveryPhase,
    provider_failure: MedusaClientFailure,
    effects: SessionEffects,
) -> OperationOutcome:
    return OperationOutcome(
        delivery_phase=delivery_phase,
        effects=effects,
        failure=RouteDeckFailure(
            kind=FailureKind.EXTERNAL_OUTCOME_UNKNOWN,
            code=provider_failure.code,
            phase="order_verification",
            correlation_id=context.attempt_id,
            operation_id=operation_id,
            request_id=context.request_id,
            public_message="The external outcome is uncertain; do not submit again.",
            safe_details=FailureSafeDetails(
                provider="medusa",
                provider_code=provider_failure.code,
                delivery_phase=delivery_phase.value,
            ),
        ),
    )


def client_failure(
    *,
    context: ExecutionContext,
    operation_id: str,
    delivery_phase: DeliveryPhase,
    failure: MedusaClientFailure,
) -> OperationOutcome:
    return OperationOutcome(
        delivery_phase=delivery_phase,
        failure=RouteDeckFailure(
            kind=_FAILURE_KINDS[failure.kind],
            code=failure.code,
            phase="order_reconciliation",
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


def public_values(values: Mapping[str, Any]) -> tuple[PublicValue, ...]:
    return tuple(
        PublicValue(name=name, value=FrozenJson(value))
        for name, value in values.items()
    )
