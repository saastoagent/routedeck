from __future__ import annotations

from collections.abc import Mapping

from routedeck_core.contracts.operations import DeliveryPhase

from ..models import (
    Cart,
    CartCompletionRejected,
    CartCompletionUnknown,
    CompleteCartResult,
    CompletionError,
    MedusaClientFailure,
    Order,
    OrderPlaced,
    OrderResult,
)
from ..transport import protocol_failure
from ..wire import parse_resource, require_identifier, required_body
from .base import MedusaResourceClient


_CARTS = "/store/carts"
_ORDERS = "/store/orders"
_ORDER_FIELDS = (
    "id,status,display_id,currency_code,region_id,email,total,subtotal,item_subtotal,tax_total,"
    "discount_total,shipping_total,*items,+items.total,*shipping_methods,"
    "+shipping_methods.name,*shipping_address,*billing_address,*payment_collections,"
    "*payment_collections.payment_sessions"
)


class OrdersResource:
    def __init__(self, base: MedusaResourceClient) -> None:
        self._base = base

    async def complete_cart(self, cart_id: str) -> CompleteCartResult:
        require_identifier(cart_id, "cart_id")
        outcome = await self._base.request(
            "POST",
            f"{_CARTS}/{cart_id}/complete",
            params={"fields": _ORDER_FIELDS},
        )
        if outcome.failure is not None:
            return await self._record_complete_cart(
                CartCompletionUnknown(
                    delivery_phase=outcome.delivery_phase,
                    failure=outcome.failure,
                )
            )
        body = required_body(outcome.body)
        response_type = body.get("type")
        if response_type == "order":
            parsed = parse_resource(body, "order", Order, "order_schema_invalid")
            if isinstance(parsed, MedusaClientFailure):
                return await self._record_complete_cart(
                    CartCompletionUnknown(
                        delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                        failure=parsed,
                    )
                )
            return await self._record_complete_cart(OrderPlaced(order=parsed))
        if response_type == "cart":
            parsed = parse_resource(body, "cart", Cart, "cart_schema_invalid")
            error = body.get("error")
            error_type = error.get("type") if isinstance(error, Mapping) else None
            if isinstance(parsed, MedusaClientFailure) or not isinstance(
                error_type, str
            ):
                return await self._record_complete_cart(
                    CartCompletionUnknown(
                        delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                        failure=(
                            parsed
                            if isinstance(parsed, MedusaClientFailure)
                            else protocol_failure("completion_error_schema_invalid")
                        ),
                    )
                )
            return await self._record_complete_cart(
                CartCompletionRejected(
                    cart=parsed,
                    error=CompletionError(
                        code=error_type,
                        public_message="The cart could not be completed.",
                    ),
                )
            )
        return await self._record_complete_cart(
            CartCompletionUnknown(
                delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                failure=protocol_failure("completion_discriminator_invalid"),
            )
        )

    async def get_order(self, order_id: str) -> OrderResult:
        require_identifier(order_id, "order_id")
        outcome = await self._base.request(
            "GET",
            f"{_ORDERS}/{order_id}",
            params={"fields": _ORDER_FIELDS},
        )
        if outcome.failure is not None:
            return await self._record_get_order(
                order_id,
                OrderResult.failed(
                    delivery_phase=outcome.delivery_phase,
                    failure=outcome.failure,
                ),
            )
        parsed = parse_resource(outcome.body, "order", Order, "order_schema_invalid")
        if isinstance(parsed, MedusaClientFailure):
            return await self._record_get_order(
                order_id,
                OrderResult.failed(
                    delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                    failure=parsed,
                ),
            )
        return await self._record_get_order(
            order_id,
            OrderResult.succeeded(parsed),
        )

    async def _record_complete_cart(
        self,
        result: CompleteCartResult,
    ) -> CompleteCartResult:
        return await self._base.record_complete_cart(
            self._base.evidence(
                operation="complete_cart",
                method="POST",
                path_template=f"{_CARTS}/{{cart_id}}/complete",
            ),
            result,
        )

    async def _record_get_order(
        self,
        order_id: str,
        result: OrderResult,
    ) -> OrderResult:
        return await self._base.record_get_order(
            self._base.evidence(
                operation="get_order",
                method="GET",
                path_template=f"{_ORDERS}/{{order_id}}",
            ),
            order_id,
            result,
        )


__all__ = ["OrdersResource"]
