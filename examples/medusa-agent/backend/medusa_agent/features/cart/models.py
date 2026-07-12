from __future__ import annotations

from collections.abc import Callable, Mapping
from enum import StrEnum
from typing import Any, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, model_validator

from routedeck_core.contracts.operations import DeliveryPhase

from ...medusa.client.models import Cart, MedusaClientFailureKind


class _StrictCartContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CartLineProjection(_StrictCartContract):
    """Display-safe facts for one authoritative Medusa cart line."""

    line_item_ref: str = Field(min_length=1)
    title: str = Field(min_length=1)
    product_title: str | None = None
    variant_title: str | None = None
    selected_options: tuple[str, ...] = ()
    quantity: int = Field(ge=1)
    unit_price: int
    line_total: int | None = None


class CartProjection(_StrictCartContract):
    """The complete public cart surface, without Store identifiers."""

    cart_ref: str = Field(min_length=1)
    currency_code: str = Field(min_length=3, max_length=3)
    items: tuple[CartLineProjection, ...] = ()
    subtotal: int
    shipping_total: int
    tax_total: int
    discount_total: int
    total: int

    @model_validator(mode="after")
    def _unique_line_refs(self) -> CartProjection:
        refs = tuple(item.line_item_ref for item in self.items)
        if len(refs) != len(set(refs)):
            raise ValueError("cart line-item references must be unique")
        return self


class CartLineBinding(_StrictCartContract):
    public_handle: str = Field(min_length=1)
    private_id: str = Field(min_length=1)


class CartSnapshot(_StrictCartContract):
    """Internal authoritative cart data passed between provider and handler."""

    private_cart_id: str = Field(min_length=1)
    public_cart_handle: str = Field(min_length=1)
    projection: CartProjection
    line_bindings: tuple[CartLineBinding, ...] = ()

    @model_validator(mode="after")
    def _bindings_match_projection(self) -> CartSnapshot:
        public_handles = tuple(binding.public_handle for binding in self.line_bindings)
        private_ids = tuple(binding.private_id for binding in self.line_bindings)
        projected_handles = tuple(item.line_item_ref for item in self.projection.items)
        if public_handles != projected_handles:
            raise ValueError("cart line bindings must match projected item order")
        if len(private_ids) != len(set(private_ids)):
            raise ValueError("cart line-item private IDs must be unique")
        if self.public_cart_handle != self.projection.cart_ref:
            raise ValueError("cart binding must match the projected cart reference")
        return self


class CartProviderState(StrEnum):
    MISSING = "missing"
    READY = "ready"
    REFRESH_FAILED = "refresh_failed"


class CartProviderContext(_StrictCartContract):
    """Serializable provider result with explicit missing/failure states."""

    state: CartProviderState
    cart: CartSnapshot | None = None
    delivery_phase: DeliveryPhase | None = None
    failure_kind: MedusaClientFailureKind | None = None
    failure_code: str | None = Field(default=None, min_length=1)
    public_message: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _state_payload(self) -> CartProviderContext:
        failure_values = (
            self.delivery_phase,
            self.failure_kind,
            self.failure_code,
            self.public_message,
        )
        if self.state is CartProviderState.READY:
            if self.cart is None or any(value is not None for value in failure_values):
                raise ValueError(
                    "ready cart context requires only an authoritative cart"
                )
            return self
        if self.state is CartProviderState.REFRESH_FAILED:
            if self.cart is not None or any(value is None for value in failure_values):
                raise ValueError(
                    "failed cart context requires complete failure evidence"
                )
            return self
        if self.cart is not None or any(value is not None for value in failure_values):
            raise ValueError("missing cart context cannot contain cart or failure data")
        return self

    def to_provider_values(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)

    @classmethod
    def from_provider_values(
        cls,
        values: Mapping[str, Any],
    ) -> CartProviderContext:
        return cls.model_validate(dict(values))


EntityHandleFactory: TypeAlias = Callable[[], str]


def project_cart(
    cart: Cart,
    *,
    new_entity_handle: EntityHandleFactory,
    existing_handles: Mapping[tuple[str, str], str] | None = None,
) -> CartSnapshot:
    """Convert a real Store cart into private bindings plus public facts."""

    existing = dict(existing_handles or {})
    private_cart_id = cart.id.get_secret_value()
    public_cart_handle = existing.get(("cart", private_cart_id))
    if public_cart_handle is None:
        public_cart_handle = new_entity_handle()
    line_bindings: list[CartLineBinding] = []
    lines: list[CartLineProjection] = []
    for item in cart.items:
        private_line_id = item.id.get_secret_value()
        public_line_handle = existing.get(("line_item", private_line_id))
        if public_line_handle is None:
            public_line_handle = new_entity_handle()
        line_bindings.append(
            CartLineBinding(
                public_handle=public_line_handle,
                private_id=private_line_id,
            )
        )
        lines.append(
            CartLineProjection(
                line_item_ref=public_line_handle,
                title=item.title,
                product_title=item.product_title,
                variant_title=item.variant_title,
                selected_options=(
                    (item.variant_title,) if item.variant_title is not None else ()
                ),
                quantity=item.quantity,
                unit_price=item.unit_price,
                line_total=item.total,
            )
        )
    return CartSnapshot(
        private_cart_id=private_cart_id,
        public_cart_handle=public_cart_handle,
        projection=CartProjection(
            cart_ref=public_cart_handle,
            currency_code=cart.currency_code,
            items=tuple(lines),
            subtotal=cart.item_subtotal,
            shipping_total=cart.shipping_total,
            tax_total=cart.tax_total,
            discount_total=cart.discount_total,
            total=cart.total,
        ),
        line_bindings=tuple(line_bindings),
    )


def snapshot_entity_handles(snapshot: CartSnapshot) -> dict[tuple[str, str], str]:
    """Return the exact private-to-public handle map for a refreshed mutation."""

    values = {
        ("cart", snapshot.private_cart_id): snapshot.public_cart_handle,
    }
    values.update(
        {
            ("line_item", binding.private_id): binding.public_handle
            for binding in snapshot.line_bindings
        }
    )
    return values


__all__ = [
    "CartLineBinding",
    "CartLineProjection",
    "CartProjection",
    "CartProviderContext",
    "CartProviderState",
    "CartSnapshot",
    "EntityHandleFactory",
    "project_cart",
    "snapshot_entity_handles",
]
