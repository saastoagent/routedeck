from __future__ import annotations

from typing import TypeVar

import pytest

from medusa_agent.config import Settings
from medusa_agent.medusa.client import (
    CheckoutAddress,
    CheckoutContact,
    CreateCartRequest,
    DeliveryResult,
    HttpMedusaStoreClient,
    ProductQuery,
)


T = TypeVar("T")


def _value(result: DeliveryResult[T]) -> T:
    assert result.failure is None
    assert result.delivery_phase.value == "response_received"
    assert result.value is not None
    return result.value


@pytest.mark.asyncio
async def test_real_store_catalog_cart_shipping_and_system_payment_provider() -> None:
    settings = Settings.from_env()
    client = HttpMedusaStoreClient(settings)

    regions = _value(await client.list_regions())
    region = next(
        candidate
        for candidate in regions
        if candidate.id.get_secret_value() == settings.medusa_region_id
    )
    assert region.countries

    page = _value(
        await client.list_products(ProductQuery(region_id=settings.medusa_region_id))
    )
    assert page.products
    product = page.products[0]
    assert product.variants
    detail = _value(await client.get_product(product.handle, settings.medusa_region_id))
    assert detail.handle == product.handle

    created = await client.create_cart(
        CreateCartRequest(
            region_id=settings.medusa_region_id,
            country_code=region.countries[0].iso_2,
            sales_channel_id=settings.medusa_sales_channel_id,
        )
    )
    assert created.failure is None
    assert created.cart is not None
    cart = _value(await client.get_cart(created.cart.id.get_secret_value()))

    variant_id = product.variants[0].id.get_secret_value()
    cart = _value(
        await client.add_line_item(
            cart.id.get_secret_value(),
            variant_id,
            1,
        )
    )
    country_code = region.countries[0].iso_2.lower()
    cart = _value(
        await client.set_checkout_contact(
            cart.id.get_secret_value(),
            CheckoutContact(
                email="routedeck-real-smoke@example.invalid",
                shipping_address=CheckoutAddress(
                    first_name="RouteDeck",
                    last_name="Smoke",
                    address_1="1 Demo Street",
                    postal_code="1000",
                    city="Copenhagen",
                    country_code=country_code,
                ),
                billing_address=CheckoutAddress(
                    first_name="RouteDeck",
                    last_name="Smoke",
                    address_1="1 Demo Street",
                    postal_code="1000",
                    city="Copenhagen",
                    country_code=country_code,
                ),
            ),
        )
    )
    shipping_options = _value(
        await client.list_shipping_options(cart.id.get_secret_value())
    )
    assert shipping_options
    cart = _value(
        await client.set_shipping_option(
            cart.id.get_secret_value(),
            shipping_options[0].id.get_secret_value(),
        )
    )
    assert cart.shipping_methods
    assert cart.item_subtotal > 0
    assert cart.subtotal >= cart.item_subtotal

    assert settings.medusa_payment_provider_id == "pp_system_default"
    providers = _value(await client.list_payment_providers(settings.medusa_region_id))
    assert settings.medusa_payment_provider_id in {
        provider.id for provider in providers if provider.is_enabled
    }
