from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from enum import StrEnum
from typing import Any, TypeAlias

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from routedeck_core.contracts.operations import DeliveryPhase

from ...medusa.client.models import (
    Cart,
    CheckoutAddress,
    CheckoutContact,
    MedusaClientFailureKind,
)


class _CheckoutContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class BillingChoice(StrEnum):
    SAME_AS_SHIPPING = "same_as_shipping"
    SEPARATE = "separate"


DEFAULT_BILLING_CHOICE = BillingChoice.SAME_AS_SHIPPING
CONTACT_FIELD_NAMES = (
    "email",
    "shipping_address",
    "billing_choice",
    "billing_address",
)


def validate_country_code(value: str) -> str:
    if (
        len(value) != 2
        or not value.isascii()
        or not value.isalpha()
        or value != value.lower()
    ):
        raise ValueError("country_code must be two lowercase ASCII letters")
    return value


class ContactAddress(_CheckoutContract):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    address_1: str = Field(min_length=1, max_length=200)
    address_2: str | None = Field(default=None, max_length=200)
    company: str | None = Field(default=None, max_length=120)
    postal_code: str = Field(min_length=1, max_length=32)
    city: str = Field(min_length=1, max_length=120)
    country_code: str = Field(min_length=2, max_length=2)
    province: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, min_length=1, max_length=32)

    @field_validator("country_code")
    @classmethod
    def _country_code(cls, value: str) -> str:
        return validate_country_code(value)

    def to_medusa(self) -> CheckoutAddress:
        return CheckoutAddress(**self.model_dump(mode="python"))


class PrivateContactDraft(_CheckoutContract):
    email: EmailStr = Field(max_length=254)
    shipping_address: ContactAddress
    billing_choice: BillingChoice
    billing_address: ContactAddress | None = None

    @model_validator(mode="after")
    def _billing_address_contract(self) -> PrivateContactDraft:
        if self.billing_choice is BillingChoice.SEPARATE:
            if self.billing_address is None:
                raise ValueError("separate billing requires a billing address")
        elif self.billing_address is not None:
            raise ValueError("same-as-shipping must not include a billing address")
        return self

    def to_medusa(self) -> CheckoutContact:
        billing = (
            self.shipping_address
            if self.billing_choice is BillingChoice.SAME_AS_SHIPPING
            else self.billing_address
        )
        if billing is None:
            raise RuntimeError("validated contact draft has no billing address")
        return CheckoutContact(
            email=self.email,
            shipping_address=self.shipping_address.to_medusa(),
            billing_address=billing.to_medusa(),
        )


class LoadedContactDraft(_CheckoutContract):
    form_handle: str = Field(min_length=1)
    revision: int = Field(ge=1)
    contact: PrivateContactDraft


class CheckoutFactsState(StrEnum):
    MISSING = "missing"
    READY = "ready"
    REFRESH_FAILED = "refresh_failed"


class CheckoutLineFacts(_CheckoutContract):
    private_variant_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    variant_title: str | None = None
    quantity: int = Field(ge=1)
    unit_amount: int
    total: int


class CheckoutShippingFacts(_CheckoutContract):
    private_option_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    amount: int


class CheckoutCartFacts(_CheckoutContract):
    private_cart_id: str = Field(min_length=1)
    private_region_id: str = Field(min_length=1)
    public_cart_handle: str = Field(min_length=1)
    currency_code: str = Field(min_length=3, max_length=3)
    items: tuple[CheckoutLineFacts, ...] = ()
    item_count: int = Field(ge=0)
    subtotal: int
    shipping_total: int
    tax_total: int
    discount_total: int
    total: int
    contact_saved: bool
    billing_complete: bool
    contact_fingerprint: str = Field(min_length=64, max_length=64)
    contact_form_handle: str | None = Field(default=None, min_length=1)
    shipping_selected: bool
    shipping: CheckoutShippingFacts | None = None
    payment_provider_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _complete_checkout_facts(self) -> CheckoutCartFacts:
        if self.item_count != sum(item.quantity for item in self.items):
            raise ValueError("checkout item_count must match line quantities")
        if self.shipping_selected != (self.shipping is not None):
            raise ValueError("checkout shipping selection facts are inconsistent")
        if len(self.payment_provider_ids) != len(set(self.payment_provider_ids)):
            raise ValueError("checkout payment provider IDs must be unique")
        return self


class CheckoutFactsContext(_CheckoutContract):
    state: CheckoutFactsState
    cart: CheckoutCartFacts | None = None
    delivery_phase: DeliveryPhase | None = None
    failure_kind: MedusaClientFailureKind | None = None
    failure_code: str | None = Field(default=None, min_length=1)
    public_message: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _state_payload(self) -> CheckoutFactsContext:
        failure_values = (
            self.delivery_phase,
            self.failure_kind,
            self.failure_code,
            self.public_message,
        )
        if self.state is CheckoutFactsState.READY:
            if self.cart is None or any(value is not None for value in failure_values):
                raise ValueError("ready checkout facts require one cart")
        elif self.state is CheckoutFactsState.REFRESH_FAILED:
            if self.cart is not None or any(value is None for value in failure_values):
                raise ValueError("failed checkout facts require failure evidence")
        elif self.cart is not None or any(
            value is not None for value in failure_values
        ):
            raise ValueError("missing checkout facts cannot contain cart or failure")
        return self

    def to_provider_values(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)

    @classmethod
    def from_provider_values(cls, values: Mapping[str, Any]) -> CheckoutFactsContext:
        return cls.model_validate(dict(values))


class ShippingProviderState(StrEnum):
    READY = "ready"
    EMPTY = "empty"
    REFRESH_FAILED = "refresh_failed"


class ShippingOptionProjection(_CheckoutContract):
    shipping_option_ref: str = Field(min_length=1)
    label: str = Field(min_length=1)
    amount: int = Field(ge=0)
    currency_code: str = Field(min_length=3, max_length=3)


class ShippingOptionBinding(_CheckoutContract):
    public_handle: str = Field(min_length=1)
    private_id: str = Field(min_length=1)


class ShippingOptionsProjection(_CheckoutContract):
    state: ShippingProviderState
    options: tuple[ShippingOptionProjection, ...] = ()
    message: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _public_state(self) -> ShippingOptionsProjection:
        if self.state is ShippingProviderState.READY:
            if not self.options or self.message is not None:
                raise ValueError("ready shipping projection requires options only")
        elif self.options or self.message is None:
            raise ValueError("unavailable shipping projection requires a message only")
        return self


class ShippingOptionsContext(_CheckoutContract):
    state: ShippingProviderState
    projection: ShippingOptionsProjection
    bindings: tuple[ShippingOptionBinding, ...] = ()
    delivery_phase: DeliveryPhase | None = None
    failure_kind: MedusaClientFailureKind | None = None
    failure_code: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _context_state(self) -> ShippingOptionsContext:
        failure_values = (self.delivery_phase, self.failure_kind, self.failure_code)
        if self.projection.state is not self.state:
            raise ValueError("shipping provider and projection states must match")
        if self.state is ShippingProviderState.READY:
            if any(value is not None for value in failure_values):
                raise ValueError("ready shipping context cannot contain failure")
            if tuple(item.public_handle for item in self.bindings) != tuple(
                item.shipping_option_ref for item in self.projection.options
            ):
                raise ValueError("shipping bindings must match projected options")
            if len({item.private_id for item in self.bindings}) != len(self.bindings):
                raise ValueError("shipping option IDs must be unique")
        elif self.bindings:
            raise ValueError("unavailable shipping context cannot contain bindings")
        elif self.state is ShippingProviderState.REFRESH_FAILED:
            if any(value is None for value in failure_values):
                raise ValueError("failed shipping context requires failure evidence")
        elif any(value is not None for value in failure_values):
            raise ValueError("empty shipping context cannot contain failure")
        return self

    def to_provider_values(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)

    @classmethod
    def from_provider_values(cls, values: Mapping[str, Any]) -> ShippingOptionsContext:
        return cls.model_validate(dict(values))


class PaymentProviderState(StrEnum):
    READY = "ready"
    MISSING = "missing"
    REFRESH_FAILED = "refresh_failed"


class PaymentProviderProjection(_CheckoutContract):
    payment_provider_ref: str = Field(min_length=1)
    label: str = Field(min_length=1)


class PaymentProviderBinding(_CheckoutContract):
    public_handle: str = Field(min_length=1)
    private_id: str = Field(min_length=1)


class PaymentMethodProjection(_CheckoutContract):
    state: PaymentProviderState
    providers: tuple[PaymentProviderProjection, ...] = ()
    message: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _public_state(self) -> PaymentMethodProjection:
        if self.state is PaymentProviderState.READY:
            if len(self.providers) != 1 or self.message is not None:
                raise ValueError("ready payment projection requires one provider")
        elif self.providers or self.message is None:
            raise ValueError("unavailable payment projection requires a message")
        return self


class PaymentProviderContext(_CheckoutContract):
    state: PaymentProviderState
    projection: PaymentMethodProjection
    bindings: tuple[PaymentProviderBinding, ...] = ()
    delivery_phase: DeliveryPhase | None = None
    failure_kind: MedusaClientFailureKind | None = None
    failure_code: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _context_state(self) -> PaymentProviderContext:
        failure_values = (self.delivery_phase, self.failure_kind, self.failure_code)
        if self.projection.state is not self.state:
            raise ValueError("payment provider and projection states must match")
        if self.state is PaymentProviderState.READY:
            if any(value is not None for value in failure_values):
                raise ValueError("ready payment context cannot contain failure")
            if len(self.bindings) != 1:
                raise ValueError("ready payment context requires one binding")
            if (
                self.bindings[0].public_handle
                != self.projection.providers[0].payment_provider_ref
            ):
                raise ValueError("payment binding must match public provider")
        elif self.bindings:
            raise ValueError("unavailable payment context cannot contain bindings")
        elif self.state is PaymentProviderState.REFRESH_FAILED:
            if any(value is None for value in failure_values):
                raise ValueError("failed payment context requires failure evidence")
        elif any(value is not None for value in failure_values):
            raise ValueError("missing payment context cannot contain failure")
        return self

    def to_provider_values(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)

    @classmethod
    def from_provider_values(cls, values: Mapping[str, Any]) -> PaymentProviderContext:
        return cls.model_validate(dict(values))


class ReviewLineProjection(_CheckoutContract):
    title: str = Field(min_length=1)
    variant_title: str | None = None
    quantity: int = Field(ge=1)
    unit_amount: int
    total: int


class OrderReviewProjection(_CheckoutContract):
    form_handle: str = Field(min_length=1)
    items: tuple[ReviewLineProjection, ...] = Field(min_length=1)
    currency_code: str = Field(min_length=3, max_length=3)
    subtotal: int
    shipping_total: int
    tax_total: int
    discount_total: int
    total: int
    shipping_label: str = Field(min_length=1)
    payment_label: str = Field(min_length=1)
    contact_complete: bool
    billing_complete: bool


EntityHandleFactory: TypeAlias = Callable[[], str]


def project_checkout_cart(
    cart: Cart,
    *,
    public_cart_handle: str,
    contact_form_handle: str | None = None,
) -> CheckoutCartFacts:
    address = cart.shipping_address
    billing = cart.billing_address
    contact_saved = (
        cart.email is not None
        and address is not None
        and all(
            value
            for value in (
                address.first_name,
                address.last_name,
                address.address_1,
                address.postal_code,
                address.city,
                address.country_code,
            )
        )
    )
    billing_complete = billing is not None and all(
        value
        for value in (
            billing.first_name,
            billing.last_name,
            billing.address_1,
            billing.postal_code,
            billing.city,
            billing.country_code,
        )
    )
    lines: list[CheckoutLineFacts] = []
    for item in cart.items:
        if item.total is None:
            raise ValueError("checkout cart line is missing its authoritative total")
        lines.append(
            CheckoutLineFacts(
                private_variant_id=item.variant_id.get_secret_value(),
                title=item.product_title or item.title,
                variant_title=item.variant_title,
                quantity=item.quantity,
                unit_amount=item.unit_price,
                total=item.total,
            )
        )
    shipping: CheckoutShippingFacts | None = None
    if cart.shipping_methods:
        if len(cart.shipping_methods) != 1:
            raise ValueError("checkout cart requires exactly one shipping method")
        method = cart.shipping_methods[0]
        if method.name is None:
            raise ValueError("checkout shipping method is missing its label")
        shipping = CheckoutShippingFacts(
            private_option_id=method.shipping_option_id.get_secret_value(),
            label=method.name,
            amount=method.amount,
        )
    payment_provider_ids = tuple(
        sorted(
            {
                session.provider_id
                for session in (
                    cart.payment_collection.payment_sessions
                    if cart.payment_collection is not None
                    else ()
                )
            }
        )
    )
    return CheckoutCartFacts(
        private_cart_id=cart.id.get_secret_value(),
        private_region_id=cart.region_id.get_secret_value(),
        public_cart_handle=public_cart_handle,
        currency_code=cart.currency_code,
        items=tuple(lines),
        item_count=sum(item.quantity for item in lines),
        subtotal=cart.item_subtotal,
        shipping_total=cart.shipping_total,
        tax_total=cart.tax_total,
        discount_total=cart.discount_total,
        total=cart.total,
        contact_saved=contact_saved,
        billing_complete=billing_complete,
        contact_fingerprint=_contact_fingerprint(cart),
        contact_form_handle=contact_form_handle,
        shipping_selected=shipping is not None,
        shipping=shipping,
        payment_provider_ids=payment_provider_ids,
    )


def order_review_projection(
    cart: CheckoutCartFacts,
    *,
    payment_label: str,
) -> OrderReviewProjection:
    if (
        cart.contact_form_handle is None
        or cart.shipping is None
        or not cart.contact_saved
        or not cart.billing_complete
    ):
        raise ValueError("checkout cart is incomplete for review")
    return OrderReviewProjection(
        form_handle=cart.contact_form_handle,
        items=tuple(
            ReviewLineProjection(
                title=item.title,
                variant_title=item.variant_title,
                quantity=item.quantity,
                unit_amount=item.unit_amount,
                total=item.total,
            )
            for item in cart.items
        ),
        currency_code=cart.currency_code,
        subtotal=cart.subtotal,
        shipping_total=cart.shipping_total,
        tax_total=cart.tax_total,
        discount_total=cart.discount_total,
        total=cart.total,
        shipping_label=cart.shipping.label,
        payment_label=payment_label,
        contact_complete=cart.contact_saved,
        billing_complete=cart.billing_complete,
    )


def _contact_fingerprint(cart: Cart) -> str:
    payload = {
        "email": cart.email,
        "shipping_address": (
            cart.shipping_address.model_dump(mode="json")
            if cart.shipping_address is not None
            else None
        ),
        "billing_address": (
            cart.billing_address.model_dump(mode="json")
            if cart.billing_address is not None
            else None
        ),
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


CONTACT_FORM_SCHEMA = {
    "type": "object",
    "properties": {
        "form_handle": {"type": "string", "minLength": 1},
        "revision": {"type": "integer", "minimum": 0},
        "complete": {"type": "boolean"},
        "fields": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
        },
        "billing_choices": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": [choice.value for choice in BillingChoice],
            },
        },
        "default_billing_choice": {
            "type": "string",
            "enum": [choice.value for choice in BillingChoice],
        },
        "country_choices": {
            "type": "array",
            "minItems": 1,
            "uniqueItems": True,
            "items": {"type": "string", "minLength": 2, "maxLength": 2},
        },
        "default_country_code": {
            "type": "string",
            "minLength": 2,
            "maxLength": 2,
        },
    },
    "required": [
        "form_handle",
        "revision",
        "complete",
        "fields",
        "billing_choices",
        "default_billing_choice",
        "country_choices",
        "default_country_code",
    ],
    "additionalProperties": False,
}

SHIPPING_OPTION_SCHEMA = {
    "type": "object",
    "properties": {
        "shipping_option_ref": {"type": "string", "minLength": 1},
        "label": {"type": "string", "minLength": 1},
        "amount": {"type": "integer", "minimum": 0},
        "currency_code": {"type": "string", "minLength": 3, "maxLength": 3},
    },
    "required": ["shipping_option_ref", "label", "amount", "currency_code"],
    "additionalProperties": False,
}

SHIPPING_OPTIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "state": {
            "type": "string",
            "enum": [state.value for state in ShippingProviderState],
        },
        "options": {"type": "array", "items": SHIPPING_OPTION_SCHEMA},
        "message": {"type": "string", "minLength": 1},
    },
    "required": ["state", "options"],
    "additionalProperties": False,
}

CHECKOUT_STARTED_SCHEMA = CONTACT_FORM_SCHEMA

CONTACT_SAVED_SCHEMA = {
    "type": "object",
    "properties": {
        "form_handle": {"type": "string", "minLength": 1},
        "revision": {"type": "integer", "minimum": 1},
        "contact_saved": {"type": "boolean", "const": True},
        "shipping_state": {
            "type": "string",
            "enum": [state.value for state in ShippingProviderState],
        },
        "shipping_option_count": {"type": "integer", "minimum": 0},
    },
    "required": [
        "form_handle",
        "revision",
        "contact_saved",
        "shipping_state",
        "shipping_option_count",
    ],
    "additionalProperties": False,
}

SHIPPING_SELECTED_SCHEMA = {
    "type": "object",
    "properties": SHIPPING_OPTION_SCHEMA["properties"],
    "required": SHIPPING_OPTION_SCHEMA["required"],
    "additionalProperties": False,
}

CHECKOUT_FACTS_PROVIDER_SCHEMA = {
    "type": "object",
    "properties": {
        "state": {
            "type": "string",
            "enum": [state.value for state in CheckoutFactsState],
        },
        "cart": {
            "type": "object",
            "properties": {
                "private_cart_id": {"type": "string", "minLength": 1},
                "private_region_id": {"type": "string", "minLength": 1},
                "public_cart_handle": {"type": "string", "minLength": 1},
                "currency_code": {"type": "string", "minLength": 3, "maxLength": 3},
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "private_variant_id": {"type": "string", "minLength": 1},
                            "title": {"type": "string", "minLength": 1},
                            "variant_title": {"type": "string"},
                            "quantity": {"type": "integer", "minimum": 1},
                            "unit_amount": {"type": "integer"},
                            "total": {"type": "integer"},
                        },
                        "required": [
                            "private_variant_id",
                            "title",
                            "quantity",
                            "unit_amount",
                            "total",
                        ],
                        "additionalProperties": False,
                    },
                },
                "item_count": {"type": "integer", "minimum": 0},
                "subtotal": {"type": "integer"},
                "shipping_total": {"type": "integer"},
                "tax_total": {"type": "integer"},
                "discount_total": {"type": "integer"},
                "total": {"type": "integer"},
                "contact_saved": {"type": "boolean"},
                "billing_complete": {"type": "boolean"},
                "contact_fingerprint": {
                    "type": "string",
                    "minLength": 64,
                    "maxLength": 64,
                },
                "contact_form_handle": {"type": "string", "minLength": 1},
                "shipping_selected": {"type": "boolean"},
                "shipping": {
                    "type": "object",
                    "properties": {
                        "private_option_id": {"type": "string", "minLength": 1},
                        "label": {"type": "string", "minLength": 1},
                        "amount": {"type": "integer"},
                    },
                    "required": ["private_option_id", "label", "amount"],
                    "additionalProperties": False,
                },
                "payment_provider_ids": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                    "uniqueItems": True,
                },
            },
            "required": [
                "private_cart_id",
                "private_region_id",
                "public_cart_handle",
                "currency_code",
                "items",
                "item_count",
                "subtotal",
                "shipping_total",
                "tax_total",
                "discount_total",
                "total",
                "contact_saved",
                "billing_complete",
                "contact_fingerprint",
                "shipping_selected",
                "payment_provider_ids",
            ],
            "additionalProperties": False,
        },
        "delivery_phase": {
            "type": "string",
            "enum": [phase.value for phase in DeliveryPhase],
        },
        "failure_kind": {
            "type": "string",
            "enum": [kind.value for kind in MedusaClientFailureKind],
        },
        "failure_code": {"type": "string", "minLength": 1},
        "public_message": {"type": "string", "minLength": 1},
    },
    "required": ["state"],
    "additionalProperties": False,
}

PAYMENT_PROVIDER_PROJECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "payment_provider_ref": {"type": "string", "minLength": 1},
        "label": {"type": "string", "minLength": 1},
    },
    "required": ["payment_provider_ref", "label"],
    "additionalProperties": False,
}

PAYMENT_METHOD_SCHEMA = {
    "type": "object",
    "properties": {
        "state": {
            "type": "string",
            "enum": [state.value for state in PaymentProviderState],
        },
        "providers": {
            "type": "array",
            "items": PAYMENT_PROVIDER_PROJECTION_SCHEMA,
        },
        "message": {"type": "string", "minLength": 1},
    },
    "required": ["state", "providers"],
    "additionalProperties": False,
}

PAYMENT_PROVIDER_SCHEMA = {
    "type": "object",
    "properties": {
        "state": {
            "type": "string",
            "enum": [state.value for state in PaymentProviderState],
        },
        "projection": PAYMENT_METHOD_SCHEMA,
        "bindings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "public_handle": {"type": "string", "minLength": 1},
                    "private_id": {"type": "string", "minLength": 1},
                },
                "required": ["public_handle", "private_id"],
                "additionalProperties": False,
            },
        },
        "delivery_phase": {
            "type": "string",
            "enum": [phase.value for phase in DeliveryPhase],
        },
        "failure_kind": {
            "type": "string",
            "enum": [kind.value for kind in MedusaClientFailureKind],
        },
        "failure_code": {"type": "string", "minLength": 1},
    },
    "required": ["state", "projection", "bindings"],
    "additionalProperties": False,
}

PAYMENT_SELECTED_SCHEMA = {
    "type": "object",
    "properties": PAYMENT_PROVIDER_PROJECTION_SCHEMA["properties"],
    "required": PAYMENT_PROVIDER_PROJECTION_SCHEMA["required"],
    "additionalProperties": False,
}

REVIEW_LINE_SCHEMA = {
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
}

ORDER_REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "form_handle": {"type": "string", "minLength": 1},
        "items": {"type": "array", "minItems": 1, "items": REVIEW_LINE_SCHEMA},
        "currency_code": {"type": "string", "minLength": 3, "maxLength": 3},
        "subtotal": {"type": "integer"},
        "shipping_total": {"type": "integer"},
        "tax_total": {"type": "integer"},
        "discount_total": {"type": "integer"},
        "total": {"type": "integer"},
        "shipping_label": {"type": "string", "minLength": 1},
        "payment_label": {"type": "string", "minLength": 1},
        "contact_complete": {"type": "boolean"},
        "billing_complete": {"type": "boolean"},
    },
    "required": [
        "form_handle",
        "items",
        "currency_code",
        "subtotal",
        "shipping_total",
        "tax_total",
        "discount_total",
        "total",
        "shipping_label",
        "payment_label",
        "contact_complete",
        "billing_complete",
    ],
    "additionalProperties": False,
}

_REVIEW_PENDING_VALUES_SCHEMA = {
    "type": "object",
    "properties": {
        "state": {"type": "string", "const": "pending"},
        "review_id": {"type": "string", "minLength": 1},
        "expires_at": {"type": "string", "minLength": 1},
    },
    "required": ["state", "review_id", "expires_at"],
    "additionalProperties": False,
}

REVIEW_PENDING_SCHEMA = {
    **_REVIEW_PENDING_VALUES_SCHEMA,
    "required": [],
}

_RECOVERY_VALUES_SCHEMA = {
    "type": "object",
    "properties": {
        "state": {"type": "string", "const": "external_outcome_unknown"},
        "message": {"type": "string", "minLength": 1},
        "correlation_id": {"type": "string", "minLength": 1},
        "order_ref": {"type": "string", "minLength": 1},
    },
    "required": ["state", "message", "correlation_id"],
    "additionalProperties": False,
}

RECOVERY_SCHEMA = {
    **_RECOVERY_VALUES_SCHEMA,
    "required": [],
}

SHIPPING_PROVIDER_SCHEMA = {
    "type": "object",
    "properties": {
        "state": {
            "type": "string",
            "enum": [state.value for state in ShippingProviderState],
        },
        "projection": SHIPPING_OPTIONS_SCHEMA,
        "bindings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "public_handle": {"type": "string", "minLength": 1},
                    "private_id": {"type": "string", "minLength": 1},
                },
                "required": ["public_handle", "private_id"],
                "additionalProperties": False,
            },
        },
        "delivery_phase": {
            "type": "string",
            "enum": [phase.value for phase in DeliveryPhase],
        },
        "failure_kind": {
            "type": "string",
            "enum": [kind.value for kind in MedusaClientFailureKind],
        },
        "failure_code": {"type": "string", "minLength": 1},
    },
    "required": ["state", "projection", "bindings"],
    "additionalProperties": False,
}


__all__ = [
    "BillingChoice",
    "CHECKOUT_FACTS_PROVIDER_SCHEMA",
    "CHECKOUT_STARTED_SCHEMA",
    "CONTACT_FORM_SCHEMA",
    "CONTACT_FIELD_NAMES",
    "CONTACT_SAVED_SCHEMA",
    "DEFAULT_BILLING_CHOICE",
    "CheckoutCartFacts",
    "CheckoutLineFacts",
    "CheckoutFactsContext",
    "CheckoutFactsState",
    "CheckoutShippingFacts",
    "ContactAddress",
    "EntityHandleFactory",
    "LoadedContactDraft",
    "PrivateContactDraft",
    "ORDER_REVIEW_SCHEMA",
    "OrderReviewProjection",
    "PAYMENT_METHOD_SCHEMA",
    "PAYMENT_PROVIDER_SCHEMA",
    "PAYMENT_SELECTED_SCHEMA",
    "PaymentMethodProjection",
    "PaymentProviderBinding",
    "PaymentProviderContext",
    "PaymentProviderProjection",
    "PaymentProviderState",
    "RECOVERY_SCHEMA",
    "REVIEW_LINE_SCHEMA",
    "REVIEW_PENDING_SCHEMA",
    "ReviewLineProjection",
    "SHIPPING_OPTIONS_SCHEMA",
    "SHIPPING_PROVIDER_SCHEMA",
    "SHIPPING_SELECTED_SCHEMA",
    "ShippingOptionBinding",
    "ShippingOptionProjection",
    "ShippingOptionsContext",
    "ShippingOptionsProjection",
    "ShippingProviderState",
    "order_review_projection",
    "project_checkout_cart",
    "validate_country_code",
]
