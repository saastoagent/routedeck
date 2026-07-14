from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from routedeck_core.contracts.effects import (
    EntityBindingEffect,
    EntityKindEffects,
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

from ....identifiers import MedusaOutcomeType
from ...catalog.feature import (
    CATALOG_PRODUCTS_PROVIDER,
    CONTINUE_SHOPPING,
    OPEN_PRODUCT,
    PRODUCT_GRID,
)
from ...catalog.models import CatalogCollectionProviderValue
from .common import public_values


class OrdersContinueShoppingHandler:
    async def __call__(
        self,
        arguments: Mapping[str, Any],
        context: ExecutionContext,
    ) -> OperationOutcome:
        if arguments:
            raise ValueError(f"{CONTINUE_SHOPPING.id} accepts no arguments")
        raw = context.provider_values.to_dict().get(CATALOG_PRODUCTS_PROVIDER.id)
        if not isinstance(raw, dict):
            raise RuntimeError("continue shopping requires the authoritative catalog")
        catalog = CatalogCollectionProviderValue.model_validate(raw)
        observation = catalog.observation.model_dump(mode="json", exclude_none=True)
        cards = {
            product.interaction_handle: product
            for product in catalog.observation.products
        }
        product_bindings = tuple(
            EntityBindingEffect(
                public=PublicEntityHandle(
                    entity_kind="product",
                    handle=binding.interaction_handle,
                    values=(
                        PublicValue(
                            name="product_handle",
                            value=FrozenJson(
                                cards[binding.interaction_handle].product_handle
                            ),
                        ),
                        PublicValue(
                            name="title",
                            value=FrozenJson(cards[binding.interaction_handle].title),
                        ),
                    ),
                ),
                private_id=binding.private_id,
                allowed_operation_ids=(OPEN_PRODUCT.id,),
            )
            for binding in catalog.bindings
        )
        return OperationOutcome(
            outcome=MedusaOutcomeType.CONTINUED,
            delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
            observation=FrozenJsonObject(observation),
            effects=SessionEffects(
                replace_entities=(
                    EntityKindEffects(entity_kind="order"),
                    EntityKindEffects(entity_kind="cart"),
                    EntityKindEffects(entity_kind="line_item"),
                    EntityKindEffects(entity_kind="shipping_option"),
                    EntityKindEffects(entity_kind="payment_provider"),
                    EntityKindEffects(
                        entity_kind="product",
                        bindings=product_bindings,
                    ),
                ),
                surface_updates=(
                    PublicSurfaceEffect(
                        surface_id=PRODUCT_GRID.id,
                        values=public_values(observation),
                    ),
                ),
            ),
        )
