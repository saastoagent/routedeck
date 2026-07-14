from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from routedeck_core.contracts.effects import PublicSurfaceEffect, SessionEffects
from routedeck_core.contracts.operations import DeliveryPhase, OperationOutcome
from routedeck_core.contracts.projection import FrozenJsonObject
from routedeck_core.ports.executor import ExecutionContext

from ....identifiers import MedusaOutcomeType
from ..feature import CATALOG_VARIANTS_PROVIDER, PRODUCT_DETAIL, SELECT_VARIANT
from ..models import CatalogProductObservation, CatalogSelectionObservation
from .common import public_values


class SelectVariantHandler:
    async def __call__(
        self,
        arguments: Mapping[str, Any],
        context: ExecutionContext,
    ) -> OperationOutcome:
        interaction_handle = arguments.get("variant_ref")
        if not isinstance(interaction_handle, str) or set(arguments) != {"variant_ref"}:
            raise ValueError(f"{SELECT_VARIANT.id} requires one variant reference")
        current = CatalogProductObservation.model_validate(
            context.provider_values.to_dict()[CATALOG_VARIANTS_PROVIDER.id]
        )
        if interaction_handle not in {
            variant.interaction_handle for variant in current.product.variants
        }:
            raise ValueError(
                "selected variant is not present in current product detail"
            )
        selected = current.product.model_copy(
            update={"selected_variant_handle": interaction_handle}
        )
        projected = CatalogProductObservation(product=selected).model_dump(
            mode="json", exclude_none=True
        )
        observation = CatalogSelectionObservation(
            product_handle=selected.product_handle,
            variant_handle=interaction_handle,
        )
        return OperationOutcome(
            outcome=MedusaOutcomeType.SELECTED,
            delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
            observation=FrozenJsonObject(observation.model_dump(mode="json")),
            effects=SessionEffects(
                surface_updates=(
                    PublicSurfaceEffect(
                        surface_id=PRODUCT_DETAIL.id,
                        values=public_values(projected),
                    ),
                )
            ),
        )
