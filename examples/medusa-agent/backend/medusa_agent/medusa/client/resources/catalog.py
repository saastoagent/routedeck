from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from routedeck_core.contracts.operations import DeliveryPhase

from ..errors import MedusaClientContractError
from ..models import (
    MedusaClientFailure,
    MedusaClientFailureKind,
    Product,
    ProductPage,
    ProductPageResult,
    ProductQuery,
    ProductResult,
    Region,
    RegionsResult,
)
from ..transport import protocol_failure
from ..wire import required_body, required_int, required_list
from .base import MedusaResourceClient


_REGIONS = "/store/regions"
_PRODUCTS = "/store/products"
_PRODUCT_FIELDS = (
    "id,handle,title,description,thumbnail,*images,*options,*options.values,"
    "*variants,*variants.options,*variants.calculated_price,+variants.inventory_quantity"
)


class CatalogResource:
    def __init__(self, base: MedusaResourceClient) -> None:
        self._base = base

    async def list_regions(self) -> RegionsResult:
        outcome = await self._base.request("GET", _REGIONS)
        if outcome.failure is not None:
            return RegionsResult.failed(
                delivery_phase=outcome.delivery_phase,
                failure=outcome.failure,
            )
        try:
            regions = tuple(
                Region.model_validate(item)
                for item in required_list(outcome.body, "regions")
            )
        except (ValidationError, TypeError, ValueError):
            return RegionsResult.failed(
                delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                failure=protocol_failure("regions_schema_invalid"),
            )
        return RegionsResult.succeeded(regions)

    async def list_products(self, query: ProductQuery) -> ProductPageResult:
        params: dict[str, Any] = {
            "region_id": query.region_id,
            "limit": query.limit,
            "offset": query.offset,
            "fields": _PRODUCT_FIELDS,
        }
        if query.query is not None:
            params["q"] = query.query
        if query.handle is not None:
            params["handle"] = query.handle
        outcome = await self._base.request("GET", _PRODUCTS, params=params)
        if outcome.failure is not None:
            return ProductPageResult.failed(
                delivery_phase=outcome.delivery_phase,
                failure=outcome.failure,
            )
        try:
            body = required_body(outcome.body)
            page = ProductPage(
                products=tuple(
                    Product.model_validate(item)
                    for item in required_list(body, "products")
                ),
                count=required_int(body, "count"),
                offset=required_int(body, "offset"),
                limit=required_int(body, "limit"),
            )
        except (ValidationError, TypeError, ValueError):
            return ProductPageResult.failed(
                delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                failure=protocol_failure("products_schema_invalid"),
            )
        return ProductPageResult.succeeded(page)

    async def get_product(self, handle: str, region_id: str) -> ProductResult:
        if not handle or not region_id:
            raise MedusaClientContractError(
                "handle and region_id must be non-empty"
            )
        result = await self.list_products(
            ProductQuery(region_id=region_id, handle=handle, limit=2)
        )
        if result.failure is not None:
            return ProductResult.failed(
                delivery_phase=result.delivery_phase,
                failure=result.failure,
            )
        if result.value is None:
            raise RuntimeError("Successful product page result is missing its value")
        if not result.value.products:
            return ProductResult.failed(
                delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                failure=MedusaClientFailure(
                    kind=MedusaClientFailureKind.BUSINESS,
                    code="product_not_found",
                    public_message="That product is unavailable.",
                ),
            )
        if len(result.value.products) != 1:
            return ProductResult.failed(
                delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                failure=protocol_failure("product_handle_not_unique"),
            )
        return ProductResult.succeeded(result.value.products[0])


__all__ = ["CatalogResource"]
