from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from routedeck_core.contracts.operations import OperationOutcome
from routedeck_core.ports.executor import ExecutionContext

from ..feature import CATALOG_PRODUCT_PROVIDER, OPEN_PRODUCT_BY_ROUTE
from ..models import CatalogProductProviderValue
from .common import open_product_outcome


class OpenProductByRouteHandler:
    async def __call__(
        self,
        arguments: Mapping[str, Any],
        context: ExecutionContext,
    ) -> OperationOutcome:
        product_handle = arguments.get("product_handle")
        if (
            not isinstance(product_handle, str)
            or not product_handle
            or set(arguments) != {"product_handle"}
        ):
            raise ValueError(
                f"{OPEN_PRODUCT_BY_ROUTE.id} requires one exact public product handle"
            )
        value = CatalogProductProviderValue.model_validate(
            context.provider_values.to_dict()[CATALOG_PRODUCT_PROVIDER.id]
        )
        if value.observation.product.product_handle != product_handle:
            raise ValueError(
                "catalog detail does not match the requested product route"
            )
        return open_product_outcome(value)
