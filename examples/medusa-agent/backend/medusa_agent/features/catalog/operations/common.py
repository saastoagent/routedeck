from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from routedeck_core.contracts.effects import (
    EntityBindingEffect,
    EntityKindEffects,
    ExactRouteParameter,
    PublicSurfaceEffect,
    SessionEffects,
)
from routedeck_core.contracts.operations import DeliveryPhase, OperationOutcome
from routedeck_core.contracts.projection import (
    FrozenJson,
    FrozenJsonObject,
    PublicEntityHandle,
    PublicValue,
)
from routedeck_core.ports.executor import ExecutionContext

from ....identifiers import MedusaOperationType, MedusaOutcomeType
from ..feature import (
    CATALOG_PRODUCTS_PROVIDER,
    OPEN_PRODUCT,
    PRODUCT_DETAIL,
    PRODUCT_GRID,
    SELECT_VARIANT,
)
from ..models import (
    CatalogCollectionProviderValue,
    CatalogPrivateBinding,
    CatalogProductDetail,
    CatalogProductProviderValue,
)


def collection_value(context: ExecutionContext) -> CatalogCollectionProviderValue:
    return CatalogCollectionProviderValue.model_validate(
        context.provider_values.to_dict()[CATALOG_PRODUCTS_PROVIDER.id]
    )


def collection_outcome(
    value: CatalogCollectionProviderValue,
    *,
    outcome: MedusaOutcomeType,
) -> OperationOutcome:
    observation = value.observation.model_dump(mode="json", exclude_none=True)
    cards = {
        product.interaction_handle: product for product in value.observation.products
    }
    entities = EntityKindEffects(
        entity_kind="product",
        bindings=tuple(
            _binding_effect(
                binding,
                public=_product_card_entity(cards[binding.interaction_handle]),
                allowed_operation_ids=(OPEN_PRODUCT.id,),
            )
            for binding in value.bindings
        ),
    )
    return OperationOutcome(
        outcome=outcome,
        delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
        observation=FrozenJsonObject(observation),
        effects=SessionEffects(
            replace_entities=(entities,),
            surface_updates=(
                PublicSurfaceEffect(
                    surface_id=PRODUCT_GRID.id,
                    values=public_values(observation),
                ),
            ),
        ),
    )


def open_product_outcome(value: CatalogProductProviderValue) -> OperationOutcome:
    detail = value.observation.product
    product_effect = EntityKindEffects(
        entity_kind="product",
        bindings=(
            _binding_effect(
                value.product_binding,
                public=_product_entity(detail),
                allowed_operation_ids=(),
            ),
        ),
    )
    variant_effect = EntityKindEffects(
        entity_kind="variant",
        bindings=tuple(
            _binding_effect(
                binding,
                public=_variant_entity(detail, binding.interaction_handle),
                allowed_operation_ids=(
                    SELECT_VARIANT.id,
                    MedusaOperationType.CART_ADD_ITEM,
                ),
            )
            for binding in value.variant_bindings
        ),
    )
    observation = value.observation.model_dump(mode="json", exclude_none=True)
    return OperationOutcome(
        outcome=MedusaOutcomeType.OPENED,
        delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
        observation=FrozenJsonObject(observation),
        effects=SessionEffects(
            replace_entities=(product_effect, variant_effect),
            surface_updates=(
                PublicSurfaceEffect(
                    surface_id=PRODUCT_DETAIL.id,
                    values=public_values(observation),
                ),
            ),
            route_params=(
                ExactRouteParameter(
                    name="product_handle",
                    value=detail.product_handle,
                ),
            ),
        ),
    )


def public_values(values: Mapping[str, Any]) -> tuple[PublicValue, ...]:
    return tuple(
        PublicValue(name=name, value=FrozenJson(value))
        for name, value in values.items()
    )


def _binding_effect(
    binding: CatalogPrivateBinding,
    *,
    public: PublicEntityHandle,
    allowed_operation_ids: tuple[str, ...],
) -> EntityBindingEffect:
    if public.handle != binding.interaction_handle:
        raise ValueError("public and private catalog bindings must match")
    return EntityBindingEffect(
        public=public,
        private_id=binding.private_id,
        allowed_operation_ids=allowed_operation_ids,
    )


def _product_card_entity(product: Any) -> PublicEntityHandle:
    return PublicEntityHandle(
        entity_kind="product",
        handle=product.interaction_handle,
        values=(
            PublicValue(
                name="product_handle",
                value=FrozenJson(product.product_handle),
            ),
            PublicValue(name="title", value=FrozenJson(product.title)),
        ),
    )


def _product_entity(product: CatalogProductDetail) -> PublicEntityHandle:
    return PublicEntityHandle(
        entity_kind="product",
        handle=product.interaction_handle,
        values=(
            PublicValue(
                name="product_handle",
                value=FrozenJson(product.product_handle),
            ),
            PublicValue(name="title", value=FrozenJson(product.title)),
        ),
    )


def _variant_entity(
    product: CatalogProductDetail,
    interaction_handle: str,
) -> PublicEntityHandle:
    variant = next(
        candidate
        for candidate in product.variants
        if candidate.interaction_handle == interaction_handle
    )
    values = [
        PublicValue(name="title", value=FrozenJson(variant.title)),
        PublicValue(
            name="product_handle",
            value=FrozenJson(product.product_handle),
        ),
    ]
    if variant.sku is not None:
        values.append(PublicValue(name="sku", value=FrozenJson(variant.sku)))
    return PublicEntityHandle(
        entity_kind="variant",
        handle=interaction_handle,
        values=tuple(values),
    )
