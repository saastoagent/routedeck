from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ...contact_identity import contact_fingerprint
from ...medusa.client.models import Order
from ..checkout.models import CheckoutCartFacts, ReviewLineProjection


class _OrderContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class OrderVerificationLine(_OrderContract):
    private_variant_id: str = Field(min_length=1)
    quantity: int = Field(ge=1)
    unit_amount: int
    total: int


class OrderVerificationPayload(_OrderContract):
    private_region_id: str = Field(min_length=1)
    currency_code: str = Field(min_length=3, max_length=3)
    items: tuple[OrderVerificationLine, ...] = Field(min_length=1)
    subtotal: int
    shipping_total: int
    tax_total: int
    discount_total: int
    total: int
    contact_fingerprint: str = Field(min_length=64, max_length=64)
    private_shipping_option_id: str = Field(min_length=1)
    shipping_label: str = Field(min_length=1)
    shipping_amount: int
    payment_provider_ids: tuple[str, ...] = Field(min_length=1)


class OrderRecoveryContext(_OrderContract):
    order_ref: str = Field(min_length=1)
    verification_fingerprint: str = Field(min_length=64, max_length=64)
    contact_form_handle: str = Field(min_length=1)

    def to_provider_values(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_provider_values(cls, values: Mapping[str, Any]) -> OrderRecoveryContext:
        return cls.model_validate(dict(values))


class OrderConfirmationProjection(_OrderContract):
    confirmation_handle: str = Field(min_length=1)
    display_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    items: tuple[ReviewLineProjection, ...] = Field(min_length=1)
    currency_code: str = Field(min_length=3, max_length=3)
    subtotal: int
    shipping_total: int
    tax_total: int
    discount_total: int
    total: int
    shipping_label: str = Field(min_length=1)
    payment_label: str = Field(min_length=1)


def expected_order_payload(
    cart: CheckoutCartFacts,
    *,
    configured_provider_id: str,
) -> OrderVerificationPayload:
    if cart.shipping is None or not cart.items:
        raise ValueError("reviewed checkout is incomplete")
    if cart.payment_provider_ids != (configured_provider_id,):
        raise ValueError("reviewed checkout does not use the configured provider")
    return OrderVerificationPayload(
        private_region_id=cart.private_region_id,
        currency_code=cart.currency_code,
        items=tuple(
            sorted(
                (
                    OrderVerificationLine(
                        private_variant_id=item.private_variant_id,
                        quantity=item.quantity,
                        unit_amount=item.unit_amount,
                        total=item.total,
                    )
                    for item in cart.items
                ),
                key=lambda item: (
                    item.private_variant_id,
                    item.quantity,
                    item.unit_amount,
                    item.total,
                ),
            )
        ),
        subtotal=cart.subtotal,
        shipping_total=cart.shipping_total,
        tax_total=cart.tax_total,
        discount_total=cart.discount_total,
        total=cart.total,
        contact_fingerprint=cart.contact_fingerprint,
        private_shipping_option_id=cart.shipping.private_option_id,
        shipping_label=cart.shipping.label,
        shipping_amount=cart.shipping.amount,
        payment_provider_ids=cart.payment_provider_ids,
    )


def actual_order_payload(order: Order) -> OrderVerificationPayload | None:
    if order.region_id is None or len(order.shipping_methods) != 1:
        return None
    lines: list[OrderVerificationLine] = []
    for item in order.items:
        if item.variant_id is None or item.total is None:
            return None
        lines.append(
            OrderVerificationLine(
                private_variant_id=item.variant_id.get_secret_value(),
                quantity=item.quantity,
                unit_amount=item.unit_price,
                total=item.total,
            )
        )
    if not lines:
        return None
    shipping = order.shipping_methods[0]
    if shipping.name is None:
        return None
    payment_provider_ids = tuple(
        sorted(
            {
                session.provider_id
                for collection in order.payment_collections
                for session in collection.payment_sessions
            }
        )
    )
    if not payment_provider_ids:
        return None
    return OrderVerificationPayload(
        private_region_id=order.region_id.get_secret_value(),
        currency_code=order.currency_code,
        items=tuple(
            sorted(
                lines,
                key=lambda item: (
                    item.private_variant_id,
                    item.quantity,
                    item.unit_amount,
                    item.total,
                ),
            )
        ),
        subtotal=order.item_subtotal,
        shipping_total=order.shipping_total,
        tax_total=order.tax_total,
        discount_total=order.discount_total,
        total=order.total,
        contact_fingerprint=contact_fingerprint(order),
        private_shipping_option_id=shipping.shipping_option_id.get_secret_value(),
        shipping_label=shipping.name,
        shipping_amount=shipping.amount,
        payment_provider_ids=payment_provider_ids,
    )


def verification_fingerprint(payload: OrderVerificationPayload) -> str:
    encoded = json.dumps(
        payload.model_dump(mode="json"),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def order_matches_fingerprint(order: Order, expected_fingerprint: str) -> bool:
    actual = actual_order_payload(order)
    return (
        actual is not None and verification_fingerprint(actual) == expected_fingerprint
    )


def confirmation_projection(
    order: Order,
    reviewed_cart: CheckoutCartFacts,
    *,
    confirmation_handle: str,
) -> OrderConfirmationProjection:
    if reviewed_cart.shipping is None:
        raise ValueError("reviewed checkout has no shipping selection")
    return OrderConfirmationProjection(
        confirmation_handle=confirmation_handle,
        display_id=str(order.display_id),
        status=order.status,
        items=tuple(
            ReviewLineProjection(
                title=item.title,
                variant_title=item.variant_title,
                quantity=item.quantity,
                unit_amount=item.unit_amount,
                total=item.total,
            )
            for item in reviewed_cart.items
        ),
        currency_code=order.currency_code,
        subtotal=order.item_subtotal,
        shipping_total=order.shipping_total,
        tax_total=order.tax_total,
        discount_total=order.discount_total,
        total=order.total,
        shipping_label=reviewed_cart.shipping.label,
        payment_label="System / manual demo payment",
    )


def confirmation_projection_from_order(
    order: Order,
    *,
    confirmation_handle: str,
) -> OrderConfirmationProjection:
    if len(order.shipping_methods) != 1 or order.shipping_methods[0].name is None:
        raise ValueError("verified order has no exact shipping method")
    lines: list[ReviewLineProjection] = []
    for item in order.items:
        if item.total is None:
            raise ValueError("verified order line has no authoritative total")
        lines.append(
            ReviewLineProjection(
                title=item.title,
                quantity=item.quantity,
                unit_amount=item.unit_price,
                total=item.total,
            )
        )
    return OrderConfirmationProjection(
        confirmation_handle=confirmation_handle,
        display_id=str(order.display_id),
        status=order.status,
        items=tuple(lines),
        currency_code=order.currency_code,
        subtotal=order.item_subtotal,
        shipping_total=order.shipping_total,
        tax_total=order.tax_total,
        discount_total=order.discount_total,
        total=order.total,
        shipping_label=order.shipping_methods[0].name,
        payment_label="System / manual demo payment",
    )


ORDER_RECOVERY_PROVIDER_SCHEMA = {
    "type": "object",
    "properties": {
        "order_ref": {"type": "string", "minLength": 1},
        "verification_fingerprint": {
            "type": "string",
            "minLength": 64,
            "maxLength": 64,
        },
        "contact_form_handle": {"type": "string", "minLength": 1},
    },
    "required": [
        "order_ref",
        "verification_fingerprint",
        "contact_form_handle",
    ],
    "additionalProperties": False,
}

ORDER_CONFIRMATION_SCHEMA = {
    "type": "object",
    "properties": {
        "confirmation_handle": {"type": "string", "minLength": 1},
        "display_id": {"type": "string", "minLength": 1},
        "status": {"type": "string", "minLength": 1},
        "items": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "minLength": 1},
                    "variant_title": {"type": "string"},
                    "quantity": {"type": "integer", "minimum": 1},
                    "unit_amount": {"type": "integer"},
                    "total": {"type": "integer"},
                },
                "required": ["title", "quantity", "unit_amount", "total"],
                "additionalProperties": False,
            },
        },
        "currency_code": {"type": "string", "minLength": 3, "maxLength": 3},
        "subtotal": {"type": "integer"},
        "shipping_total": {"type": "integer"},
        "tax_total": {"type": "integer"},
        "discount_total": {"type": "integer"},
        "total": {"type": "integer"},
        "shipping_label": {"type": "string", "minLength": 1},
        "payment_label": {"type": "string", "minLength": 1},
    },
    "required": [
        "confirmation_handle",
        "display_id",
        "status",
        "items",
        "currency_code",
        "subtotal",
        "shipping_total",
        "tax_total",
        "discount_total",
        "total",
        "shipping_label",
        "payment_label",
    ],
    "additionalProperties": False,
}


__all__ = [
    "ORDER_CONFIRMATION_SCHEMA",
    "ORDER_RECOVERY_PROVIDER_SCHEMA",
    "OrderConfirmationProjection",
    "OrderRecoveryContext",
    "OrderVerificationPayload",
    "actual_order_payload",
    "confirmation_projection",
    "confirmation_projection_from_order",
    "expected_order_payload",
    "order_matches_fingerprint",
    "verification_fingerprint",
]
