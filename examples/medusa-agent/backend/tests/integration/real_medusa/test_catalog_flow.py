from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from medusa_agent.config import Settings
from medusa_agent.features.catalog.declarations import (
    CATALOG_LIST,
    CATALOG_SEARCH,
    OPEN_PRODUCT,
    SELECT_VARIANT,
)
from medusa_agent.features.catalog.providers import CatalogRouteKeyValidator
from medusa_agent.medusa.client import HttpMedusaStoreClient, ProductQuery
from medusa_agent.medusa.client.models import ProductPageResult, ProductResult
from medusa_agent.session import BuyerMarket
from routedeck_core.contracts.operations import (
    OperationDisposition,
    OperationRequest,
    OperationSource,
)
from routedeck_core.contracts.projection import FrozenJsonObject, PublicValue
from routedeck_core.contracts.session import Location
from routedeck_core.navigation.routes import RouteSessionContext
from support.runtime import build_test_runtime


@dataclass
class CountingCatalogClient:
    inner: HttpMedusaStoreClient
    list_queries: list[ProductQuery] = field(default_factory=list)
    product_queries: list[tuple[str, str]] = field(default_factory=list)
    raw_product_ids: set[str] = field(default_factory=set)
    raw_variant_ids: set[str] = field(default_factory=set)

    async def list_products(self, query: ProductQuery) -> ProductPageResult:
        self.list_queries.append(query)
        result = await self.inner.list_products(query)
        if result.value is not None:
            self.raw_product_ids.update(
                product.id.get_secret_value() for product in result.value.products
            )
            self.raw_variant_ids.update(
                variant.id.get_secret_value()
                for product in result.value.products
                for variant in product.variants
            )
        return result

    async def get_product(self, handle: str, region_id: str) -> ProductResult:
        self.product_queries.append((handle, region_id))
        result = await self.inner.get_product(handle, region_id)
        if result.value is not None:
            self.raw_product_ids.add(result.value.id.get_secret_value())
            self.raw_variant_ids.update(
                variant.id.get_secret_value() for variant in result.value.variants
            )
        return result


@pytest.mark.asyncio
async def test_real_catalog_projection_and_journal_replay() -> None:
    settings = Settings.from_env()
    expected_base_url = os.environ.get(
        "ROUTEDECK_EXPECTED_MEDUSA_BASE_URL",
        "http://127.0.0.1:9100",
    ).rstrip("/")
    assert str(settings.medusa_base_url).rstrip("/") == expected_base_url
    http_client = HttpMedusaStoreClient(settings)
    regions = await http_client.list_regions()
    assert regions.failure is None
    assert regions.value is not None
    region = next(
        candidate
        for candidate in regions.value
        if candidate.id.get_secret_value() == settings.medusa_region_id
    )
    assert region.countries

    client = CountingCatalogClient(http_client)
    runtime = build_test_runtime(
        client=client,  # type: ignore[arg-type]
        market=BuyerMarket(
            region_handle=settings.medusa_region_id,
            country_code=region.countries[0].iso_2,
            currency_code=region.currency_code,
            sales_channel_handle=settings.medusa_sales_channel_id,
        ),
        initial_location=Location(node_id="buyer.home"),
    )

    listed = await runtime.services.runner.run(
        _request(
            operation_id=CATALOG_LIST.id,
            request_id="catalog-list-real",
            expected_session_version=1,
        )
    )
    assert listed.disposition is OperationDisposition.COMPLETED
    listed_session = (await runtime.services.store.load("session-1")).state
    listed_projection = runtime.services.projector.project(listed_session)
    listed_props = _values(listed_projection.surfaces.active.props)
    products = listed_props["products"]
    assert isinstance(products, list)
    assert len(products) == 4
    assert listed_props["count"] == 4
    first_title = products[0]["title"]

    searched = await runtime.services.runner.run(
        _request(
            operation_id=CATALOG_SEARCH.id,
            request_id="catalog-search-real",
            expected_session_version=listed.session_version,
            arguments={"query": first_title},
        )
    )
    assert searched.disposition is OperationDisposition.COMPLETED
    searched_session = (await runtime.services.store.load("session-1")).state
    searched_projection = runtime.services.projector.project(searched_session)
    searched_props = _values(searched_projection.surfaces.active.props)
    assert searched_props["query"] == first_title
    assert searched_props["products"]
    selected_card = searched_props["products"][0]
    selected_entity = next(
        entity
        for entity in searched_projection.entities
        if _values(entity.values).get("product_handle")
        == selected_card["product_handle"]
    )
    assert selected_entity.handle.startswith("rdh_")
    assert selected_entity.handle != selected_card["product_handle"]

    open_request = _request(
        operation_id=OPEN_PRODUCT.id,
        request_id="catalog-open-real",
        expected_session_version=searched.session_version,
        arguments={"product_ref": selected_entity.handle},
    )
    runtime.services.store.fail_next_commit_attempt = True
    interrupted = await runtime.services.runner.run(open_request)
    assert interrupted.disposition is OperationDisposition.FAILED
    assert interrupted.failure is not None
    assert interrupted.failure.code == "state_commit_failed"
    assert client.product_queries == [
        (selected_card["product_handle"], settings.medusa_region_id)
    ]

    opened = await runtime.services.runner.run(open_request)
    assert opened.disposition is OperationDisposition.COMPLETED
    assert client.product_queries == [
        (selected_card["product_handle"], settings.medusa_region_id)
    ]
    product_session = (await runtime.services.store.load("session-1")).state
    product_projection = runtime.services.projector.project(product_session)
    product_props = _values(product_projection.surfaces.active.props)
    detail = product_props["product"]
    assert product_projection.current.node_id == "catalog.product"
    assert _values(product_projection.current.route_params) == {
        "product_handle": selected_card["product_handle"]
    }
    assert detail["product_handle"] == selected_card["product_handle"]
    assert detail["variants"]

    validator = CatalogRouteKeyValidator.from_session(product_session)
    encoded = runtime.services.app.app.routes.encode(
        "catalog.product",
        {"product_handle": detail["product_handle"]},
    )
    decoded = runtime.services.app.app.routes.decode(
        encoded,
        RouteSessionContext(
            now=datetime(2030, 1, 1, tzinfo=UTC),
            public_key_validator=validator,
        ),
    )
    assert encoded == f"/products/{detail['product_handle']}"
    assert decoded.node_id == "catalog.product"
    assert decoded.route_bindings["product_handle"] == detail["product_handle"]

    history_only_session = product_session.model_copy(
        update={
            "public_state": product_session.public_state.model_copy(
                update={"surface_state": ()}
            )
        }
    )
    history_validator = CatalogRouteKeyValidator.from_session(history_only_session)
    assert history_validator.is_valid(
        "product_handle",
        detail["product_handle"],
    )

    variant = detail["variants"][0]
    selected = await runtime.services.runner.run(
        _request(
            operation_id=SELECT_VARIANT.id,
            request_id="catalog-select-real",
            expected_session_version=opened.session_version,
            arguments={"variant_ref": variant["interaction_handle"]},
        )
    )
    assert selected.disposition is OperationDisposition.COMPLETED
    assert len(client.product_queries) == 1
    selected_session = (await runtime.services.store.load("session-1")).state
    selected_projection = runtime.services.projector.project(selected_session)
    selected_detail = _values(selected_projection.surfaces.active.props)["product"]
    assert selected_detail["selected_variant_handle"] == variant["interaction_handle"]

    public_json = selected_projection.model_dump_json()
    assert all(raw_id not in public_json for raw_id in client.raw_product_ids)
    assert all(raw_id not in public_json for raw_id in client.raw_variant_ids)
    assert len(client.list_queries) == 2


def _request(
    *,
    operation_id: str,
    request_id: str,
    expected_session_version: int,
    arguments: dict[str, object] | None = None,
) -> OperationRequest:
    return OperationRequest(
        session_id="session-1",
        request_id=request_id,
        expected_session_version=expected_session_version,
        operation_id=operation_id,
        source=OperationSource.SURFACE,
        arguments=FrozenJsonObject(arguments or {}),
    )


def _values(values: tuple[PublicValue, ...]) -> dict[str, object]:
    return {value.name: value.value.to_python() for value in values}
