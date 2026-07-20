from __future__ import annotations

import hashlib
import json

from pydantic import SecretStr

from medusa_agent import contact_identity
from medusa_agent.contact_identity import contact_fingerprint
from medusa_agent.medusa.client.models import Cart, Order, StoreAddress


def test_cart_and_order_share_one_canonical_contact_fingerprint() -> None:
    shipping = _address(first_name="Zoë", city="München")
    billing = _address(first_name="Raghav", city="Bengaluru")
    cart = _cart(
        email="zoë@example.test",
        shipping_address=shipping,
        billing_address=billing,
    )
    order = _order(
        email=cart.email,
        shipping_address=shipping,
        billing_address=billing,
    )

    cart_fingerprint = contact_fingerprint(cart)
    order_fingerprint = contact_fingerprint(order)

    assert cart_fingerprint == order_fingerprint
    assert len(cart_fingerprint) == 64
    payload = {
        "email": "zoë@example.test",
        "shipping_address": shipping.model_dump(mode="json"),
        "billing_address": billing.model_dump(mode="json"),
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    assert cart_fingerprint == hashlib.sha256(encoded).hexdigest()


def test_none_addresses_have_a_stable_cross_resource_fingerprint() -> None:
    cart = _cart(email=None, shipping_address=None, billing_address=None)
    order = _order(email=None, shipping_address=None, billing_address=None)

    assert contact_fingerprint(cart) == contact_fingerprint(order)
    assert len(contact_fingerprint(cart)) == 64


def test_one_contact_field_change_changes_the_fingerprint() -> None:
    original = _cart(
        email="buyer@example.test",
        shipping_address=_address(city="London"),
        billing_address=_address(city="London"),
    )
    changed = _order(
        email="buyer@example.test",
        shipping_address=_address(city="Leeds"),
        billing_address=_address(city="London"),
    )

    assert contact_fingerprint(original) != contact_fingerprint(changed)


def test_contact_serialization_options_are_explicit_and_canonical(monkeypatch) -> None:
    captured: dict[str, object] = {}
    real_dumps = json.dumps

    def capture_dumps(value, **options):
        captured.update(options)
        return real_dumps(value, **options)

    monkeypatch.setattr(contact_identity.json, "dumps", capture_dumps)

    contact_fingerprint(
        _cart(
            email="buyer@example.test",
            shipping_address=None,
            billing_address=None,
        )
    )

    assert captured == {
        "ensure_ascii": False,
        "allow_nan": False,
        "sort_keys": True,
        "separators": (",", ":"),
    }


def _address(
    *,
    first_name: str = "Buyer",
    city: str = "London",
) -> StoreAddress:
    return StoreAddress(
        first_name=first_name,
        last_name="Example",
        address_1="1 Market Street",
        postal_code="SW1A 1AA",
        city=city,
        country_code="gb",
    )


def _cart(
    *,
    email: str | None,
    shipping_address: StoreAddress | None,
    billing_address: StoreAddress | None,
) -> Cart:
    return Cart(
        id=SecretStr("cart-1"),
        currency_code="gbp",
        region_id=SecretStr("region-1"),
        email=email,
        item_subtotal=0,
        shipping_address=shipping_address,
        billing_address=billing_address,
    )


def _order(
    *,
    email: str | None,
    shipping_address: StoreAddress | None,
    billing_address: StoreAddress | None,
) -> Order:
    return Order(
        id=SecretStr("order-1"),
        status="pending",
        display_id=1,
        currency_code="gbp",
        email=email,
        total=0,
        subtotal=0,
        item_subtotal=0,
        tax_total=0,
        discount_total=0,
        shipping_total=0,
        shipping_address=shipping_address,
        billing_address=billing_address,
    )
