from __future__ import annotations

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

from ...contact_identity import contact_fingerprint
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
        contact_fingerprint=contact_fingerprint(cart),
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


__all__ = [
    "BillingChoice",
    "CONTACT_FIELD_NAMES",
    "DEFAULT_BILLING_CHOICE",
    "CheckoutCartFacts",
    "CheckoutLineFacts",
    "CheckoutFactsContext",
    "CheckoutFactsState",
    "CheckoutShippingFacts",
    "ContactAddress",
    "EntityHandleFactory",
    "LoadedContactDraft",
    "OrderReviewProjection",
    "PaymentMethodProjection",
    "PaymentProviderBinding",
    "PaymentProviderContext",
    "PaymentProviderProjection",
    "PaymentProviderState",
    "PrivateContactDraft",
    "ReviewLineProjection",
    "ShippingOptionBinding",
    "ShippingOptionProjection",
    "ShippingOptionsContext",
    "ShippingOptionsProjection",
    "ShippingProviderState",
    "order_review_projection",
    "project_checkout_cart",
    "validate_country_code",
]
