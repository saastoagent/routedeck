from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from routedeck_core.contracts.effects import SessionEffects
from routedeck_core.contracts.operations import DeliveryPhase, OperationOutcome
from routedeck_core.handles import new_opaque_handle
from routedeck_core.ports.executor import ExecutionContext

from ....identifiers import MedusaOutcomeType
from ....medusa.client.models import (
    CartCompletionRejected,
    CartCompletionUnknown,
    MedusaClientFailure,
    MedusaClientFailureKind,
    OrderPlaced,
    OrderResult,
)
from ....medusa.client.protocol import MedusaStoreClient
from ...checkout.feature import PLACE_ORDER
from ..models import (
    confirmation_projection,
    expected_order_payload,
    order_matches_fingerprint,
    verification_fingerprint,
)
from .common import (
    business_failure,
    confirmation_effects,
    recovery_effects,
    reviewed_cart,
    unknown_failure,
)


@dataclass(frozen=True)
class PlaceOrderHandler:
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
        if arguments:
            raise ValueError(f"{PLACE_ORDER.id} accepts no arguments")
        cart = reviewed_cart(context)
        expected = expected_order_payload(
            cart,
            configured_provider_id=self.configured_provider_id,
        )
        if cart.contact_form_handle is None:
            raise RuntimeError("place order requires a completed private contact form")
        expected_fingerprint = verification_fingerprint(expected)

        completion = await self.client.complete_cart(cart.private_cart_id)
        if isinstance(completion, CartCompletionRejected):
            return business_failure(
                context=context,
                operation_id=PLACE_ORDER.id,
                code=completion.error.code,
                message=completion.error.public_message,
            )
        if isinstance(completion, CartCompletionUnknown):
            return unknown_failure(
                context=context,
                operation_id=PLACE_ORDER.id,
                delivery_phase=completion.delivery_phase,
                provider_failure=completion.failure,
                effects=SessionEffects(),
            )
        if not isinstance(completion, OrderPlaced):
            raise TypeError(
                "MedusaStoreClient.complete_cart returned an invalid result"
            )

        completed_order_id = completion.order.id.get_secret_value()
        verified_result = await self.client.get_order(completed_order_id)
        if not isinstance(verified_result, OrderResult):
            raise TypeError("MedusaStoreClient.get_order must return OrderResult")
        recovery_ref = new_opaque_handle()
        recovery = recovery_effects(
            private_order_id=completed_order_id,
            order_ref=recovery_ref,
            expected_fingerprint=expected_fingerprint,
            contact_form_handle=cart.contact_form_handle,
            correlation_id=context.attempt_id,
        )
        if verified_result.failure is not None:
            return unknown_failure(
                context=context,
                operation_id=PLACE_ORDER.id,
                delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                provider_failure=verified_result.failure,
                effects=recovery,
            )
        verified_order = verified_result.value
        if verified_order is None:
            raise TypeError("Successful OrderResult is missing its order")
        if (
            verified_order.id.get_secret_value() != completed_order_id
            or not order_matches_fingerprint(verified_order, expected_fingerprint)
        ):
            return unknown_failure(
                context=context,
                operation_id=PLACE_ORDER.id,
                delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                provider_failure=MedusaClientFailure(
                    kind=MedusaClientFailureKind.PROVIDER_PROTOCOL,
                    code="order_verification_mismatch",
                    public_message="The completed order could not be verified.",
                ),
                effects=recovery,
            )

        confirmation_handle = new_opaque_handle()
        projection = confirmation_projection(
            verified_order,
            cart,
            confirmation_handle=confirmation_handle,
        )
        return OperationOutcome(
            outcome=MedusaOutcomeType.ORDER_CREATED,
            delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
            effects=confirmation_effects(
                order=verified_order,
                confirmation_handle=confirmation_handle,
                expected_fingerprint=expected_fingerprint,
                contact_form_handle=cart.contact_form_handle,
                projection=projection,
            ),
        )
