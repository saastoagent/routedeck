from __future__ import annotations

from pydantic import SecretStr

from routedeck_core.contracts.effects import (
    EntityBindingEffect,
    EntityKindEffects,
    PublicSurfaceEffect,
    SessionEffects,
)
from routedeck_core.contracts.projection import (
    FrozenJson,
    PublicEntityHandle,
    PublicValue,
)

from ..feature import SELECT_SHIPPING, SHIPPING_OPTIONS
from ..models import (
    PaymentProviderBinding,
    PaymentProviderContext,
    PaymentProviderProjection,
    PaymentProviderState,
    ShippingOptionBinding,
    ShippingOptionProjection,
    ShippingOptionsContext,
)
from .common import public_values


def shipping_effects(
    shipping: ShippingOptionsContext,
    *,
    allow_selection: bool,
) -> SessionEffects:
    projections = {
        option.shipping_option_ref: option for option in shipping.projection.options
    }
    allowed_operation_ids = (SELECT_SHIPPING.id,) if allow_selection else ()
    bindings = tuple(
        shipping_binding_effect(
            binding,
            projections[binding.public_handle],
            allowed_operation_ids=allowed_operation_ids,
        )
        for binding in shipping.bindings
    )
    surface = shipping.projection.model_dump(mode="json", exclude_none=True)
    return SessionEffects(
        replace_entities=(
            EntityKindEffects(entity_kind="shipping_option", bindings=bindings),
        ),
        surface_updates=(
            PublicSurfaceEffect(
                surface_id=SHIPPING_OPTIONS.id,
                values=public_values(surface),
            ),
        ),
    )


def shipping_binding_effect(
    binding: ShippingOptionBinding,
    projection: ShippingOptionProjection,
    *,
    allowed_operation_ids: tuple[str, ...],
) -> EntityBindingEffect:
    if binding.public_handle != projection.shipping_option_ref:
        raise ValueError("shipping projection and binding must match")
    return EntityBindingEffect(
        public=PublicEntityHandle(
            entity_kind="shipping_option",
            handle=binding.public_handle,
            values=tuple(
                PublicValue(name=name, value=FrozenJson(value))
                for name, value in projection.model_dump(mode="json").items()
                if name != "shipping_option_ref"
            ),
        ),
        private_id=SecretStr(binding.private_id),
        allowed_operation_ids=allowed_operation_ids,
    )


def payment_binding_effects(
    payment: PaymentProviderContext,
    *,
    allowed_operation_ids: tuple[str, ...],
) -> tuple[EntityBindingEffect, ...]:
    if payment.state is not PaymentProviderState.READY:
        return ()
    projections = {
        provider.payment_provider_ref: provider
        for provider in payment.projection.providers
    }
    return tuple(
        _payment_binding_effect(
            binding,
            projections[binding.public_handle],
            allowed_operation_ids=allowed_operation_ids,
        )
        for binding in payment.bindings
    )


def _payment_binding_effect(
    binding: PaymentProviderBinding,
    projection: PaymentProviderProjection,
    *,
    allowed_operation_ids: tuple[str, ...],
) -> EntityBindingEffect:
    if binding.public_handle != projection.payment_provider_ref:
        raise ValueError("payment projection and binding must match")
    return EntityBindingEffect(
        public=PublicEntityHandle(
            entity_kind="payment_provider",
            handle=binding.public_handle,
            values=(PublicValue(name="label", value=FrozenJson(projection.label)),),
        ),
        private_id=SecretStr(binding.private_id),
        allowed_operation_ids=allowed_operation_ids,
    )


__all__ = [
    "payment_binding_effects",
    "shipping_binding_effect",
    "shipping_effects",
]
