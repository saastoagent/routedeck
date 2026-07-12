from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import (
    Cart,
    CartResult,
    CheckoutContact,
    CompleteCartResult,
    CreateCartRequest,
    CreateCartResult,
    OrderResult,
    PaymentProvidersResult,
    ProductPageResult,
    ProductQuery,
    ProductResult,
    RegionsResult,
    ShippingOptionsResult,
)


@runtime_checkable
class MedusaStoreClient(Protocol):
    """Typed business port; every call preserves external delivery evidence."""

    async def list_regions(self) -> RegionsResult: ...

    async def list_products(self, query: ProductQuery) -> ProductPageResult: ...

    async def get_product(self, handle: str, region_id: str) -> ProductResult: ...

    async def create_cart(self, request: CreateCartRequest) -> CreateCartResult: ...

    async def get_cart(self, cart_id: str) -> CartResult: ...

    async def add_line_item(
        self, cart_id: str, variant_id: str, quantity: int
    ) -> CartResult: ...

    async def update_line_item(
        self, cart_id: str, line_id: str, quantity: int
    ) -> CartResult: ...

    async def remove_line_item(self, cart_id: str, line_id: str) -> CartResult: ...

    async def set_checkout_contact(
        self, cart_id: str, contact: CheckoutContact
    ) -> CartResult: ...

    async def list_shipping_options(self, cart_id: str) -> ShippingOptionsResult: ...

    async def set_shipping_option(self, cart_id: str, option_id: str) -> CartResult: ...

    async def list_payment_providers(
        self, region_id: str
    ) -> PaymentProvidersResult: ...

    async def initialize_payment(self, cart: Cart, provider_id: str) -> CartResult: ...

    async def complete_cart(self, cart_id: str) -> CompleteCartResult: ...

    async def get_order(self, order_id: str) -> OrderResult: ...


__all__ = ["MedusaStoreClient"]
