from __future__ import annotations

import httpx

from ...config import Settings
from .evidence import MedusaStoreEvidenceSink, StoreCallEvidence
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
from .resources.base import MedusaResourceClient
from .resources.cart import CartResource
from .resources.catalog import CatalogResource
from .resources.checkout import CheckoutResource
from .resources.orders import OrdersResource
from .transport import (
    TransportFailureEvidence,
    classify_transport_failure,
)


class HttpMedusaStoreClient:
    """Canonical Store client facade over typed Medusa resources."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        evidence_sink: MedusaStoreEvidenceSink | None = None,
    ) -> None:
        base = MedusaResourceClient(
            settings,
            transport=transport,
            evidence_sink=evidence_sink,
        )
        cart = CartResource(base)
        self._catalog = CatalogResource(base)
        self._cart = cart
        self._checkout = CheckoutResource(base, cart)
        self._orders = OrdersResource(base)

    async def list_regions(self) -> RegionsResult:
        return await self._catalog.list_regions()

    async def list_products(self, query: ProductQuery) -> ProductPageResult:
        return await self._catalog.list_products(query)

    async def get_product(self, handle: str, region_id: str) -> ProductResult:
        return await self._catalog.get_product(handle, region_id)

    async def create_cart(self, request: CreateCartRequest) -> CreateCartResult:
        return await self._cart.create_cart(request)

    async def get_cart(self, cart_id: str) -> CartResult:
        return await self._cart.get_cart(cart_id)

    async def add_line_item(
        self,
        cart_id: str,
        variant_id: str,
        quantity: int,
    ) -> CartResult:
        return await self._cart.add_line_item(cart_id, variant_id, quantity)

    async def update_line_item(
        self,
        cart_id: str,
        line_id: str,
        quantity: int,
    ) -> CartResult:
        return await self._cart.update_line_item(cart_id, line_id, quantity)

    async def remove_line_item(self, cart_id: str, line_id: str) -> CartResult:
        return await self._cart.remove_line_item(cart_id, line_id)

    async def set_checkout_contact(
        self,
        cart_id: str,
        contact: CheckoutContact,
    ) -> CartResult:
        return await self._checkout.set_checkout_contact(cart_id, contact)

    async def list_shipping_options(
        self,
        cart_id: str,
    ) -> ShippingOptionsResult:
        return await self._checkout.list_shipping_options(cart_id)

    async def set_shipping_option(
        self,
        cart_id: str,
        option_id: str,
    ) -> CartResult:
        return await self._checkout.set_shipping_option(cart_id, option_id)

    async def list_payment_providers(
        self,
        region_id: str,
    ) -> PaymentProvidersResult:
        return await self._checkout.list_payment_providers(region_id)

    async def initialize_payment(
        self,
        cart: Cart,
        provider_id: str,
    ) -> CartResult:
        return await self._checkout.initialize_payment(cart, provider_id)

    async def complete_cart(self, cart_id: str) -> CompleteCartResult:
        return await self._orders.complete_cart(cart_id)

    async def get_order(self, order_id: str) -> OrderResult:
        return await self._orders.get_order(order_id)


__all__ = [
    "HttpMedusaStoreClient",
    "MedusaStoreEvidenceSink",
    "StoreCallEvidence",
    "TransportFailureEvidence",
    "classify_transport_failure",
]
