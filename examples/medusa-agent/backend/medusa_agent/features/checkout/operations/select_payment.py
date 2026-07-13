from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from routedeck_core.contracts.effects import (
    EntityKindEffects,
    PublicSurfaceEffect,
    SessionEffects,
)
from routedeck_core.contracts.operations import DeliveryPhase, OperationOutcome
from routedeck_core.contracts.projection import FrozenJsonObject
from routedeck_core.ports.executor import ExecutionContext

from ....medusa.client.models import CartResult
from ....medusa.client.protocol import MedusaStoreClient
from ..feature import ORDER_REVIEW, SELECT_PAYMENT
from ..models import order_review_projection, project_checkout_cart
from .common import (
    operation_failure,
    prewrite_business_failure,
    protocol_failure,
    public_values,
    require_current_cart,
    require_current_payment,
    require_exact_arguments,
    require_string,
)


@dataclass(frozen=True)
class SelectPaymentHandler:
    client: MedusaStoreClient
    configured_provider_id: str

    def __post_init__(self) -> None:
        if not self.configured_provider_id:
            raise ValueError("configured payment provider ID must be non-empty")

    async def __call__(
        self,
        arguments: Mapping[str, Any],
        context: ExecutionContext,
    ) -> OperationOutcome:
        require_exact_arguments(
            arguments,
            expected=("payment_provider_ref",),
            operation_id=SELECT_PAYMENT.id,
        )
        selected_ref = require_string(arguments, "payment_provider_ref")
        current = require_current_cart(context)
        payment = require_current_payment(context)
        private_provider_id = context.private_entity_id("payment_provider_ref")
        if private_provider_id != self.configured_provider_id:
            raise RuntimeError(
                "resolved payment provider is not the configured provider"
            )
        binding = payment.bindings[0]
        projection = payment.projection.providers[0]
        if (
            binding.public_handle != selected_ref
            or binding.private_id != private_provider_id
            or projection.payment_provider_ref != selected_ref
        ):
            raise RuntimeError(
                "resolved payment provider does not match its projection"
            )

        cart_result = await self.client.get_cart(current.private_cart_id)
        if not isinstance(cart_result, CartResult):
            raise TypeError("MedusaStoreClient.get_cart must return CartResult")
        if cart_result.failure is not None:
            return operation_failure(
                context=context,
                operation_id=SELECT_PAYMENT.id,
                delivery_phase=DeliveryPhase.NOT_SENT,
                failure=cart_result.failure,
            )
        cart = cart_result.value
        if cart is None:
            raise TypeError("Successful CartResult is missing its cart")
        if cart.id.get_secret_value() != current.private_cart_id:
            return prewrite_business_failure(
                context=context,
                operation_id=SELECT_PAYMENT.id,
                code="cart_identity_mismatch",
                message="The checkout cart changed before payment selection.",
            )
        refreshed_before_write = project_checkout_cart(
            cart,
            public_cart_handle=current.public_cart_handle,
            contact_form_handle=current.contact_form_handle,
        )
        if refreshed_before_write != current:
            return prewrite_business_failure(
                context=context,
                operation_id=SELECT_PAYMENT.id,
                code="checkout_changed",
                message="The checkout changed. Review the latest totals and try again.",
            )

        result = await self.client.initialize_payment(
            cart,
            self.configured_provider_id,
        )
        if not isinstance(result, CartResult):
            raise TypeError(
                "MedusaStoreClient.initialize_payment must return CartResult"
            )
        if result.failure is not None:
            return operation_failure(
                context=context,
                operation_id=SELECT_PAYMENT.id,
                delivery_phase=result.delivery_phase,
                failure=result.failure,
            )
        initialized = result.value
        if initialized is None:
            raise TypeError("Successful CartResult is missing its cart")
        if initialized.id.get_secret_value() != current.private_cart_id:
            return protocol_failure(
                context=context,
                operation_id=SELECT_PAYMENT.id,
                code="cart_identity_mismatch",
                message="The store returned a different checkout cart.",
            )
        refreshed = project_checkout_cart(
            initialized,
            public_cart_handle=current.public_cart_handle,
            contact_form_handle=current.contact_form_handle,
        )
        if refreshed.payment_provider_ids != (self.configured_provider_id,):
            return protocol_failure(
                context=context,
                operation_id=SELECT_PAYMENT.id,
                code="payment_not_initialized",
                message="The store did not confirm the configured payment method.",
            )
        review = order_review_projection(
            refreshed,
            payment_label=projection.label,
        )
        return OperationOutcome(
            outcome="selected",
            delivery_phase=result.delivery_phase,
            observation=FrozenJsonObject(projection.model_dump(mode="json")),
            effects=SessionEffects(
                replace_entities=(
                    EntityKindEffects(entity_kind="shipping_option"),
                    EntityKindEffects(entity_kind="payment_provider"),
                ),
                surface_updates=(
                    PublicSurfaceEffect(
                        surface_id=ORDER_REVIEW.id,
                        values=public_values(review.model_dump(mode="json")),
                    ),
                ),
            ),
        )


__all__ = ["SelectPaymentHandler"]
