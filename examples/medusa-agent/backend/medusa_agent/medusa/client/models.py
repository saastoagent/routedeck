from __future__ import annotations

from enum import StrEnum
from typing import Any, Generic, Self, TypeAlias, TypeVar

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from routedeck_core.contracts.operations import DeliveryPhase


class _StrictContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class _StoreResource(BaseModel):
    # Store responses may add fields outside the explicit client projection.
    # Required and typed fields below still fail on missing or invalid values.
    model_config = ConfigDict(frozen=True, extra="ignore")


class MedusaClientFailureKind(StrEnum):
    TRANSPORT = "transport"
    PROVIDER_PROTOCOL = "provider_protocol"
    BUSINESS = "business"


class MedusaClientFailure(_StrictContract):
    """Sanitized failure; raw response and exception text never cross the port."""

    kind: MedusaClientFailureKind
    code: str = Field(min_length=1)
    public_message: str = Field(min_length=1)


T = TypeVar("T")


class DeliveryResult(_StrictContract, Generic[T]):
    delivery_phase: DeliveryPhase
    value: T | None = None
    failure: MedusaClientFailure | None = None

    @model_validator(mode="after")
    def _value_or_failure(self) -> DeliveryResult[T]:
        if (self.value is None) == (self.failure is None):
            raise ValueError("DeliveryResult requires a value or failure, not both")
        if (
            self.value is not None
            and self.delivery_phase is not DeliveryPhase.RESPONSE_RECEIVED
        ):
            raise ValueError("successful results require response_received")
        return self

    @classmethod
    def succeeded(cls, value: T) -> Self:
        return cls(delivery_phase=DeliveryPhase.RESPONSE_RECEIVED, value=value)

    @classmethod
    def failed(
        cls,
        *,
        delivery_phase: DeliveryPhase,
        failure: MedusaClientFailure,
    ) -> Self:
        return cls(delivery_phase=delivery_phase, failure=failure)


class CreateCartRequest(_StrictContract):
    """Business input; ``country_code`` is context, not a Store body field."""

    region_id: str = Field(min_length=1)
    country_code: str = Field(min_length=2, max_length=2)
    sales_channel_id: str = Field(min_length=1)


class ProductQuery(_StrictContract):
    region_id: str = Field(min_length=1)
    query: str | None = Field(default=None, min_length=1)
    handle: str | None = Field(default=None, min_length=1)
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class CheckoutAddress(_StrictContract):
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    address_1: str = Field(min_length=1)
    address_2: str | None = None
    company: str | None = None
    postal_code: str = Field(min_length=1)
    city: str = Field(min_length=1)
    country_code: str = Field(min_length=2, max_length=2)
    province: str | None = None
    phone: str | None = None


class CheckoutContact(_StrictContract):
    email: str = Field(min_length=3)
    shipping_address: CheckoutAddress
    billing_address: CheckoutAddress


class RegionCountry(_StoreResource):
    iso_2: str = Field(min_length=2, max_length=2)
    display_name: str | None = None


class Region(_StoreResource):
    id: SecretStr = Field(min_length=1)
    name: str = Field(min_length=1)
    currency_code: str = Field(min_length=3, max_length=3)
    countries: tuple[RegionCountry, ...] = ()


class ProductImage(_StoreResource):
    url: str = Field(min_length=1)


class ProductOptionValue(_StoreResource):
    id: SecretStr | None = None
    value: str = Field(min_length=1)
    option_id: SecretStr | None = None


class ProductOption(_StoreResource):
    id: SecretStr = Field(min_length=1)
    title: str = Field(min_length=1)
    values: tuple[ProductOptionValue, ...] = ()


class CalculatedPrice(_StoreResource):
    calculated_amount: int
    currency_code: str = Field(min_length=3, max_length=3)
    original_amount: int | None = None


class ProductVariant(_StoreResource):
    id: SecretStr = Field(min_length=1)
    title: str = Field(min_length=1)
    sku: str | None = None
    inventory_quantity: int | None = None
    options: tuple[ProductOptionValue, ...] = ()
    calculated_price: CalculatedPrice | None = None


class Product(_StoreResource):
    id: SecretStr = Field(min_length=1)
    handle: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str | None = None
    thumbnail: str | None = None
    images: tuple[ProductImage, ...] = ()
    options: tuple[ProductOption, ...] = ()
    variants: tuple[ProductVariant, ...] = ()


class ProductPage(_StrictContract):
    products: tuple[Product, ...]
    count: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)


class CartLineItem(_StoreResource):
    id: SecretStr = Field(min_length=1)
    variant_id: SecretStr = Field(min_length=1)
    product_id: SecretStr | None = None
    title: str = Field(min_length=1)
    product_title: str | None = None
    variant_title: str | None = None
    quantity: int = Field(ge=1)
    unit_price: int
    total: int | None = None


class StoreAddress(_StoreResource):
    first_name: str | None = None
    last_name: str | None = None
    address_1: str | None = None
    address_2: str | None = None
    company: str | None = None
    postal_code: str | None = None
    city: str | None = None
    country_code: str | None = None
    province: str | None = None
    phone: str | None = None


class CartShippingMethod(_StoreResource):
    shipping_option_id: SecretStr
    name: str | None = None
    amount: int


class PaymentSession(_StoreResource):
    id: SecretStr = Field(min_length=1)
    provider_id: str = Field(min_length=1)
    status: str | None = None
    data: dict[str, Any] | None = None


class PaymentCollection(_StoreResource):
    id: SecretStr = Field(min_length=1)
    currency_code: str = Field(min_length=3, max_length=3)
    amount: int
    payment_sessions: tuple[PaymentSession, ...] = ()


class MedusaCart(_StoreResource):
    """Minimal cart identity retained for the existing cart.create binding."""

    id: SecretStr = Field(min_length=1)
    currency_code: str = Field(min_length=3, max_length=3)


class Cart(MedusaCart):
    region_id: SecretStr = Field(min_length=1)
    sales_channel_id: SecretStr | None = None
    email: str | None = None
    total: int = 0
    subtotal: int = 0
    item_subtotal: int
    tax_total: int = 0
    discount_total: int = 0
    shipping_total: int = 0
    items: tuple[CartLineItem, ...] = ()
    shipping_methods: tuple[CartShippingMethod, ...] = ()
    shipping_address: StoreAddress | None = None
    billing_address: StoreAddress | None = None
    payment_collection: PaymentCollection | None = None


class ShippingOption(_StoreResource):
    id: SecretStr = Field(min_length=1)
    name: str = Field(min_length=1)
    price_type: str = Field(min_length=1)
    amount: int | None = None
    calculated_price: CalculatedPrice | None = None


class PaymentProvider(_StoreResource):
    id: str = Field(min_length=1)
    is_enabled: bool


class OrderLineItem(_StoreResource):
    id: SecretStr = Field(min_length=1)
    variant_id: SecretStr | None = None
    title: str = Field(min_length=1)
    quantity: int = Field(ge=1)
    unit_price: int
    total: int | None = None


class Order(_StoreResource):
    id: SecretStr = Field(min_length=1)
    status: str = Field(min_length=1)
    display_id: int | str
    currency_code: str = Field(min_length=3, max_length=3)
    region_id: SecretStr | None = None
    email: str | None = None
    total: int
    subtotal: int
    item_subtotal: int
    tax_total: int
    discount_total: int
    shipping_total: int
    items: tuple[OrderLineItem, ...] = ()
    shipping_methods: tuple[CartShippingMethod, ...] = ()
    shipping_address: StoreAddress | None = None
    billing_address: StoreAddress | None = None
    payment_collections: tuple[PaymentCollection, ...] = ()


class CreateCartResult(_StrictContract):
    delivery_phase: DeliveryPhase
    cart: MedusaCart | None = None
    failure: MedusaClientFailure | None = None

    @model_validator(mode="after")
    def _cart_or_failure(self) -> CreateCartResult:
        if (self.cart is None) == (self.failure is None):
            raise ValueError("CreateCartResult requires a cart or failure, not both")
        if (
            self.cart is not None
            and self.delivery_phase is not DeliveryPhase.RESPONSE_RECEIVED
        ):
            raise ValueError("successful cart creation requires response_received")
        return self

    @classmethod
    def succeeded(cls, cart: MedusaCart) -> CreateCartResult:
        return cls(delivery_phase=DeliveryPhase.RESPONSE_RECEIVED, cart=cart)

    @classmethod
    def failed(
        cls,
        *,
        delivery_phase: DeliveryPhase,
        failure: MedusaClientFailure,
    ) -> CreateCartResult:
        return cls(delivery_phase=delivery_phase, failure=failure)


class RegionsResult(DeliveryResult[tuple[Region, ...]]):
    pass


class ProductPageResult(DeliveryResult[ProductPage]):
    pass


class ProductResult(DeliveryResult[Product]):
    pass


class CartResult(DeliveryResult[Cart]):
    pass


class ShippingOptionsResult(DeliveryResult[tuple[ShippingOption, ...]]):
    pass


class PaymentProvidersResult(DeliveryResult[tuple[PaymentProvider, ...]]):
    pass


class OrderResult(DeliveryResult[Order]):
    pass


class CompletionError(_StrictContract):
    code: str = Field(min_length=1)
    public_message: str = Field(min_length=1)


class OrderPlaced(_StrictContract):
    delivery_phase: DeliveryPhase = DeliveryPhase.RESPONSE_RECEIVED
    order: Order


class CartCompletionRejected(_StrictContract):
    delivery_phase: DeliveryPhase = DeliveryPhase.RESPONSE_RECEIVED
    cart: Cart
    error: CompletionError


class CartCompletionUnknown(_StrictContract):
    delivery_phase: DeliveryPhase
    failure: MedusaClientFailure


CompleteCartResult: TypeAlias = (
    OrderPlaced | CartCompletionRejected | CartCompletionUnknown
)


__all__ = [
    "CalculatedPrice",
    "Cart",
    "CartCompletionRejected",
    "CartCompletionUnknown",
    "CartLineItem",
    "CartResult",
    "CartShippingMethod",
    "CheckoutAddress",
    "CheckoutContact",
    "CompleteCartResult",
    "CompletionError",
    "CreateCartRequest",
    "CreateCartResult",
    "DeliveryResult",
    "MedusaCart",
    "MedusaClientFailure",
    "MedusaClientFailureKind",
    "Order",
    "OrderLineItem",
    "OrderPlaced",
    "OrderResult",
    "PaymentCollection",
    "PaymentProvider",
    "PaymentProvidersResult",
    "PaymentSession",
    "Product",
    "ProductImage",
    "ProductOption",
    "ProductOptionValue",
    "ProductPage",
    "ProductPageResult",
    "ProductQuery",
    "ProductResult",
    "ProductVariant",
    "Region",
    "RegionCountry",
    "RegionsResult",
    "ShippingOption",
    "ShippingOptionsResult",
    "StoreAddress",
]
