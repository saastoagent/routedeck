from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from routedeck_core.contracts.operations import OperationOutcome
from routedeck_core.ports.executor import ExecutionContext

from ..feature import CATALOG_PRODUCT_PROVIDER, OPEN_PRODUCT
from ..models import CatalogProductProviderValue
from .common import open_product_outcome


class OpenProductHandler:
    async def __call__(
        self,
        arguments: Mapping[str, Any],
        context: ExecutionContext,
    ) -> OperationOutcome:
        interaction_handle = arguments.get("product_ref")
        if not isinstance(interaction_handle, str) or set(arguments) != {"product_ref"}:
            raise ValueError(
                f"{OPEN_PRODUCT.id} requires one product interaction handle"
            )
        value = CatalogProductProviderValue.model_validate(
            context.provider_values.to_dict()[CATALOG_PRODUCT_PROVIDER.id]
        )
        if value.observation.product.interaction_handle != interaction_handle:
            raise ValueError("catalog detail does not match the selected product")
        return open_product_outcome(value)
