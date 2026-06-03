from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
ROUTEDECK_ROOT = BACKEND_ROOT.parents[2]
for path in (BACKEND_ROOT, ROUTEDECK_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


from core.config import Settings
from services.medusa_store import MedusaStoreClient


@pytest.mark.asyncio
async def test_list_products_uses_publishable_key_and_normalizes_public_fields():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["x-publishable-api-key"] == "pk_test"
        assert request.url.path == "/store/products"
        return httpx.Response(
            200,
            json={
                "products": [
                    {
                        "id": "prod_1",
                        "title": "Medusa T-Shirt",
                        "description": "Soft cotton shirt",
                        "thumbnail": "https://example.test/shirt.png",
                        "variants": [
                            {"id": "variant_1", "title": "M", "options": [{"value": "M"}]},
                        ],
                    }
                ]
            },
        )

    client = MedusaStoreClient(
        Settings(medusa_backend_url="http://medusa.test", medusa_publishable_api_key="pk_test"),
        transport=httpx.MockTransport(handler),
    )

    products = await client.list_products(limit=12)

    assert len(requests) == 1
    assert products[0].id == "prod_1"
    assert products[0].title == "Medusa T-Shirt"
    assert products[0].description == "Soft cotton shirt"
    assert products[0].variants[0].id == "variant_1"
    assert products[0].variants[0].options == ["M"]


@pytest.mark.asyncio
async def test_get_product_uses_product_id_path_and_normalizes_variants():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/store/products/prod_1"
        return httpx.Response(
            200,
            json={
                "product": {
                    "id": "prod_1",
                    "title": "Medusa Hoodie",
                    "variants": [{"id": "variant_2", "title": "L", "options": []}],
                }
            },
        )

    client = MedusaStoreClient(
        Settings(medusa_backend_url="http://medusa.test", medusa_publishable_api_key="pk_test"),
        transport=httpx.MockTransport(handler),
    )

    product = await client.get_product("prod_1")

    assert product.id == "prod_1"
    assert product.title == "Medusa Hoodie"
    assert product.variants[0].id == "variant_2"


@pytest.mark.asyncio
async def test_create_cart_and_add_line_item_call_store_api():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path, request.content))
        if request.url.path == "/store/regions":
            return httpx.Response(200, json={"regions": [{"id": "reg_1", "currency_code": "usd"}]})
        if request.url.path == "/store/carts":
            return httpx.Response(200, json={"cart": {"id": "cart_1", "items": []}})
        if request.url.path == "/store/carts/cart_1/line-items":
            return httpx.Response(
                200,
                json={"cart": {"id": "cart_1", "items": [{"id": "li_1", "quantity": 2, "title": "Medusa T-Shirt"}]}},
            )
        return httpx.Response(404)

    client = MedusaStoreClient(
        Settings(medusa_backend_url="http://medusa.test", medusa_publishable_api_key="pk_test"),
        transport=httpx.MockTransport(handler),
    )

    region = await client.first_region()
    cart = await client.create_cart(region_id=region.id)
    updated = await client.add_line_item(cart_id=cart.id, variant_id="variant_1", quantity=2)

    assert region.id == "reg_1"
    assert cart.id == "cart_1"
    assert updated.items[0].quantity == 2
    assert ("POST", "/store/carts/cart_1/line-items", b'{"variant_id":"variant_1","quantity":2}') in calls


@pytest.mark.asyncio
async def test_store_client_requires_publishable_key_before_live_store_calls():
    from services.medusa_store import MedusaStoreConfigurationError

    client = MedusaStoreClient(Settings(medusa_backend_url="http://medusa.test"))

    with pytest.raises(MedusaStoreConfigurationError, match="MEDUSA_PUBLISHABLE_API_KEY"):
        await client.list_products()


def test_opaque_refs_hide_private_medusa_ids():
    from services.commerce_refs import OpaqueRefStore

    refs = OpaqueRefStore(prefix="product")
    public_ref = refs.remember("prod_123")

    assert public_ref.startswith("product_")
    assert "prod_123" not in public_ref
    assert refs.resolve(public_ref) == "prod_123"
    assert refs.remember("prod_123") == public_ref


def test_commerce_state_tracks_selection_and_cart_without_private_ids_in_snapshot():
    from services.commerce_state import CommerceStateStore

    store = CommerceStateStore()
    state = store.for_session("session-1")
    state.selected_product_ref = "product_opaque"
    state.selected_variant_ref = "variant_opaque"
    state.cart_ref = "cart_opaque"

    snapshot = state.public_snapshot()

    assert snapshot["selected_product_ref"] == "product_opaque"
    assert snapshot["selected_variant_ref"] == "variant_opaque"
    assert snapshot["cart_ref"] == "cart_opaque"
    assert "prod_" not in str(snapshot)
    assert "variant_private" not in str(snapshot)
