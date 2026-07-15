from __future__ import annotations

from routedeck_core.contracts.operations import DeliveryPhase

from ..errors import MedusaClientContractError
from ..models import (
    Cart,
    CartResult,
    CreateCartRequest,
    CreateCartResult,
    MedusaClientFailure,
)
from ..wire import cart_result, parse_resource, require_identifier
from .base import MedusaResourceClient


_CARTS = "/store/carts"
_CART_FIELDS = (
    "id,currency_code,region_id,sales_channel_id,email,total,subtotal,item_subtotal,tax_total,"
    "discount_total,shipping_total,*items,+items.total,*shipping_methods,"
    "+shipping_methods.name,*shipping_address,*billing_address,*payment_collection,"
    "*payment_collection.payment_sessions"
)


class CartResource:
    def __init__(self, base: MedusaResourceClient) -> None:
        self._base = base

    async def create_cart(self, request: CreateCartRequest) -> CreateCartResult:
        outcome = await self._base.request(
            "POST",
            _CARTS,
            params={"fields": _CART_FIELDS},
            json_body={
                "region_id": request.region_id,
                "sales_channel_id": request.sales_channel_id,
            },
        )
        if outcome.failure is not None:
            return CreateCartResult.failed(
                delivery_phase=outcome.delivery_phase,
                failure=outcome.failure,
            )
        cart = parse_resource(outcome.body, "cart", Cart, "cart_schema_invalid")
        if isinstance(cart, MedusaClientFailure):
            return CreateCartResult.failed(
                delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                failure=cart,
            )
        return CreateCartResult.succeeded(cart)

    async def get_cart(self, cart_id: str) -> CartResult:
        require_identifier(cart_id, "cart_id")
        outcome = await self._base.request(
            "GET",
            f"{_CARTS}/{cart_id}",
            params={"fields": _CART_FIELDS},
        )
        return cart_result(outcome, key="cart")

    async def add_line_item(
        self,
        cart_id: str,
        variant_id: str,
        quantity: int,
    ) -> CartResult:
        require_identifier(cart_id, "cart_id")
        require_identifier(variant_id, "variant_id")
        if quantity < 1:
            raise MedusaClientContractError("quantity must be positive")
        outcome = await self._base.request(
            "POST",
            f"{_CARTS}/{cart_id}/line-items",
            params={"fields": _CART_FIELDS},
            json_body={"variant_id": variant_id, "quantity": quantity},
        )
        return cart_result(outcome, key="cart")

    async def update_line_item(
        self,
        cart_id: str,
        line_id: str,
        quantity: int,
    ) -> CartResult:
        require_identifier(cart_id, "cart_id")
        require_identifier(line_id, "line_id")
        if quantity < 0:
            raise MedusaClientContractError("quantity cannot be negative")
        outcome = await self._base.request(
            "POST",
            f"{_CARTS}/{cart_id}/line-items/{line_id}",
            params={"fields": _CART_FIELDS},
            json_body={"quantity": quantity},
        )
        return cart_result(outcome, key="cart")

    async def remove_line_item(self, cart_id: str, line_id: str) -> CartResult:
        require_identifier(cart_id, "cart_id")
        require_identifier(line_id, "line_id")
        outcome = await self._base.request(
            "DELETE",
            f"{_CARTS}/{cart_id}/line-items/{line_id}",
            params={"fields": _CART_FIELDS},
        )
        return cart_result(outcome, key="parent")


__all__ = ["CartResource"]
