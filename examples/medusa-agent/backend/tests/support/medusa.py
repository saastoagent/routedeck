from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pydantic import SecretStr

from medusa_agent.medusa.client.models import (
    Cart,
    CartResult,
    CheckoutContact,
    CompleteCartResult,
    CreateCartRequest,
    CreateCartResult,
    MedusaCart,
    OrderResult,
    PaymentProvidersResult,
    ProductPageResult,
    ProductQuery,
    ProductResult,
    RegionsResult,
    ShippingOptionsResult,
)

if TYPE_CHECKING:
    from medusa_agent.session import BuyerMarket


def buyer_market() -> BuyerMarket:
    from medusa_agent.session import BuyerMarket

    return BuyerMarket(
        region_handle="private-region-sentinel",
        country_code="zx",
        currency_code="qzx",
        sales_channel_handle="private-channel-sentinel",
    )


def cart() -> MedusaCart:
    return MedusaCart(
        id=SecretStr("private-cart-sentinel"),
        currency_code="qzx",
    )


@dataclass
class RecordingMedusaStoreClient:
    """Explicit test client that rejects every undeclared Store operation."""

    create_cart_result: CreateCartResult
    calls: list[str] = field(default_factory=list)
    create_cart_requests: list[CreateCartRequest] = field(default_factory=list)

    async def create_cart(self, request: CreateCartRequest) -> CreateCartResult:
        self.calls.append("create_cart")
        self.create_cart_requests.append(request)
        return self.create_cart_result

    async def list_regions(self) -> RegionsResult:
        raise AssertionError("list_regions was not selected for this test")

    async def list_products(self, query: ProductQuery) -> ProductPageResult:
        raise AssertionError("list_products was not selected for this test")

    async def get_product(self, handle: str, region_id: str) -> ProductResult:
        raise AssertionError("get_product was not selected for this test")

    async def get_cart(self, cart_id: str) -> CartResult:
        raise AssertionError("get_cart was not selected for this test")

    async def add_line_item(
        self, cart_id: str, variant_id: str, quantity: int
    ) -> CartResult:
        raise AssertionError("add_line_item was not selected for this test")

    async def update_line_item(
        self, cart_id: str, line_id: str, quantity: int
    ) -> CartResult:
        raise AssertionError("update_line_item was not selected for this test")

    async def remove_line_item(self, cart_id: str, line_id: str) -> CartResult:
        raise AssertionError("remove_line_item was not selected for this test")

    async def set_checkout_contact(
        self, cart_id: str, contact: CheckoutContact
    ) -> CartResult:
        raise AssertionError("set_checkout_contact was not selected for this test")

    async def list_shipping_options(self, cart_id: str) -> ShippingOptionsResult:
        raise AssertionError("list_shipping_options was not selected for this test")

    async def set_shipping_option(self, cart_id: str, option_id: str) -> CartResult:
        raise AssertionError("set_shipping_option was not selected for this test")

    async def list_payment_providers(self, region_id: str) -> PaymentProvidersResult:
        raise AssertionError("list_payment_providers was not selected for this test")

    async def initialize_payment(self, cart: Cart, provider_id: str) -> CartResult:
        raise AssertionError("initialize_payment was not selected for this test")

    async def complete_cart(self, cart_id: str) -> CompleteCartResult:
        raise AssertionError("complete_cart was not selected for this test")

    async def get_order(self, order_id: str) -> OrderResult:
        raise AssertionError("get_order was not selected for this test")

    @property
    def created_cart(self) -> MedusaCart:
        if self.create_cart_result.cart is None:
            raise AssertionError("recording client has no successful cart result")
        return self.create_cart_result.cart


__all__ = ["RecordingMedusaStoreClient", "buyer_market", "cart"]
