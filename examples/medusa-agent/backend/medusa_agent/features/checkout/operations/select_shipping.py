from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from routedeck_core.contracts.effects import (
    EntityKindEffects,
    PublicSurfaceEffect,
    SessionEffects,
)
from routedeck_core.contracts.operations import OperationOutcome
from routedeck_core.contracts.projection import FrozenJsonObject
from routedeck_core.handles import new_opaque_handle
from routedeck_core.ports.executor import ExecutionContext

from ....identifiers import MedusaOutcomeType
from ....medusa.client.models import CartResult
from ....medusa.client.protocol import MedusaStoreClient
from ..feature import PAYMENT_METHOD, SELECT_PAYMENT, SELECT_SHIPPING
from ..models import EntityHandleFactory
from ..providers import load_payment_provider
from .common import (
    operation_failure,
    protocol_failure,
    public_values,
    require_current_cart,
    require_current_shipping,
    require_exact_arguments,
    require_string,
)
from .delivery_effects import payment_binding_effects, shipping_binding_effect


@dataclass(frozen=True)
class SelectShippingHandler:
    client: MedusaStoreClient
    configured_provider_id: str
    new_entity_handle: EntityHandleFactory = new_opaque_handle

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
            expected=("shipping_option_ref",),
            operation_id=SELECT_SHIPPING.id,
        )
        selected_ref = require_string(arguments, "shipping_option_ref")
        current = require_current_cart(context)
        shipping = require_current_shipping(context)
        private_option_id = context.private_entity_id("shipping_option_ref")
        binding = next(
            item for item in shipping.bindings if item.private_id == private_option_id
        )
        if binding.public_handle != selected_ref:
            raise RuntimeError(
                "resolved shipping option does not match its public handle"
            )
        projected = next(
            item
            for item in shipping.projection.options
            if item.shipping_option_ref == selected_ref
        )

        result = await self.client.set_shipping_option(
            current.private_cart_id,
            private_option_id,
        )
        if not isinstance(result, CartResult):
            raise TypeError(
                "MedusaStoreClient.set_shipping_option must return CartResult"
            )
        if result.failure is not None:
            return operation_failure(
                context=context,
                operation_id=SELECT_SHIPPING.id,
                delivery_phase=result.delivery_phase,
                failure=result.failure,
            )
        cart = result.value
        if cart is None:
            raise TypeError("Successful CartResult is missing its cart")
        if cart.id.get_secret_value() != current.private_cart_id:
            return protocol_failure(
                context=context,
                operation_id=SELECT_SHIPPING.id,
                code="cart_identity_mismatch",
                message="The store returned a different checkout cart.",
            )
        selected_ids = {
            method.shipping_option_id.get_secret_value()
            for method in cart.shipping_methods
        }
        if private_option_id not in selected_ids:
            return protocol_failure(
                context=context,
                operation_id=SELECT_SHIPPING.id,
                code="shipping_not_selected",
                message="The store did not confirm the delivery selection.",
            )

        payment = await load_payment_provider(
            self.client,
            cart.region_id.get_secret_value(),
            self.configured_provider_id,
            new_entity_handle=self.new_entity_handle,
        )

        return OperationOutcome(
            outcome=MedusaOutcomeType.SELECTED,
            delivery_phase=result.delivery_phase,
            observation=FrozenJsonObject(projected.model_dump(mode="json")),
            effects=SessionEffects(
                replace_entities=(
                    EntityKindEffects(
                        entity_kind="shipping_option",
                        bindings=(
                            shipping_binding_effect(
                                binding,
                                projected,
                                allowed_operation_ids=(),
                            ),
                        ),
                    ),
                    EntityKindEffects(
                        entity_kind="payment_provider",
                        bindings=payment_binding_effects(
                            payment,
                            allowed_operation_ids=(SELECT_PAYMENT.id,),
                        ),
                    ),
                ),
                surface_updates=(
                    PublicSurfaceEffect(
                        surface_id=PAYMENT_METHOD.id,
                        values=public_values(
                            payment.projection.model_dump(
                                mode="json",
                                exclude_none=True,
                            )
                        ),
                    ),
                ),
            ),
        )


__all__ = ["SelectShippingHandler"]
