from __future__ import annotations

from dataclasses import dataclass

import pytest
from pydantic import SecretStr

from medusa_agent.features.catalog.declarations import (
    CATALOG_LIST,
    CATALOG_PRODUCT_PROVIDER,
    CATALOG_SEARCH,
    OPEN_PRODUCT_BY_ROUTE,
)
from medusa_agent.features.catalog.feature import (
    CATALOG_BROWSE_NODE,
    CATALOG_PRODUCT_NODE,
    PRODUCT_GRID,
)
from medusa_agent.features.catalog.providers import (
    CatalogProvider,
    CatalogProviderError,
)
from medusa_agent.medusa.client.models import (
    CalculatedPrice,
    CreateCartResult,
    MedusaCart,
    MedusaClientFailure,
    MedusaClientFailureKind,
    Product,
    ProductResult,
    ProductVariant,
)
from medusa_agent.session import (
    BuyerMarket,
    create_medusa_session,
)
from routedeck_core.contracts.operations import (
    DeliveryPhase,
    OperationDisposition,
    OperationRequest,
    OperationSource,
)
from routedeck_core.contracts.projection import FrozenJsonObject
from routedeck_core.contracts.session import Location, LocationParameter
from routedeck_core.supervision.guards import ProviderInvocationContext
from routedeck_core.navigation import NavigationIntent, NavigationRequest
from support.medusa import RecordingMedusaStoreClient
from support.runtime import build_test_runtime


@dataclass
class RouteProductClient(RecordingMedusaStoreClient):
    product_result: ProductResult | None = None

    async def get_product(self, handle: str, region_id: str) -> ProductResult:
        self.calls.append(f"get_product:{handle}:{region_id}")
        if self.product_result is None:
            raise AssertionError("get_product has no selected typed result")
        return self.product_result


def _client(product_result: ProductResult) -> RouteProductClient:
    return RouteProductClient(
        create_cart_result=CreateCartResult.succeeded(
            MedusaCart(
                id=SecretStr("private-cart-route"),
                currency_code="usd",
            )
        ),
        product_result=product_result,
    )


def _market() -> BuyerMarket:
    return BuyerMarket(
        region_handle="private-region-route",
        country_code="us",
        currency_code="usd",
        sales_channel_handle="private-channel-route",
    )


def _product(handle: str) -> Product:
    return Product(
        id=SecretStr("private-product-route"),
        handle=handle,
        title="Linen shirt",
        description="A lightweight shirt.",
        variants=(
            ProductVariant(
                id=SecretStr("private-variant-route"),
                title="Default",
                sku="LINEN-DEFAULT",
                inventory_quantity=4,
                calculated_price=CalculatedPrice(
                    calculated_amount=4900,
                    currency_code="usd",
                ),
            ),
        ),
    )


@pytest.mark.asyncio
async def test_open_product_by_route_hydrates_exact_product_detail() -> None:
    client = _client(ProductResult.succeeded(_product("linen-shirt")))
    runtime = build_test_runtime(
        client=client,
        market=_market(),
        initial_location=Location(
            node_id="catalog.product",
            route_params=(
                LocationParameter(name="product_handle", value="linen-shirt"),
            ),
        ),
    )

    result = await runtime.services.runner.run(
        OperationRequest(
            session_id="session-1",
            request_id="route-product-1",
            expected_session_version=1,
            operation_id=OPEN_PRODUCT_BY_ROUTE.id,
            source=OperationSource.SYSTEM,
            arguments=FrozenJsonObject({"product_handle": "linen-shirt"}),
        )
    )

    assert result.disposition is OperationDisposition.COMPLETED
    assert client.calls == ["get_product:linen-shirt:private-region-route"]
    session = (await runtime.services.store.load("session-1")).state
    assert {
        parameter.name: parameter.value for parameter in session.current.route_params
    } == {"product_handle": "linen-shirt"}, session.operation.journaled_result
    projection = runtime.services.projector.project(session)
    detail = projection.surfaces.active
    assert detail is not None
    assert detail.surface_id == "catalog.product_detail"
    props = {value.name: value.value.to_python() for value in detail.props}
    assert props["product"]["product_handle"] == "linen-shirt"
    assert props["product"]["variants"][0]["title"] == "Default"
    product_entities = tuple(
        entity
        for entity in session.public_state.entity_handles
        if entity.entity_kind == "product"
    )
    variant_entities = tuple(
        entity
        for entity in session.public_state.entity_handles
        if entity.entity_kind == "variant"
    )
    assert len(product_entities) == 1
    assert len(variant_entities) == 1
    assert product_entities[0].handle.startswith("rdh_")
    assert variant_entities[0].handle.startswith("rdh_")
    assert "private-product-route" not in projection.model_dump_json()
    assert "private-variant-route" not in projection.model_dump_json()


@pytest.mark.asyncio
async def test_fresh_product_path_runs_declared_entry_and_commits_history() -> None:
    client = _client(ProductResult.succeeded(_product("linen-shirt")))
    runtime = build_test_runtime(
        client=client,
        market=_market(),
        initial_location=Location(node_id="buyer.home"),
    )

    request = NavigationRequest(
        session_id="session-1",
        request_id="route-navigation-1",
        expected_session_version=1,
        intent=NavigationIntent(
            kind="open_path",
            path="/products/linen-shirt",
        ),
    )
    snapshot = await runtime.services.navigation.navigate(request)
    replay = await runtime.services.navigation.navigate(request)

    assert client.calls == ["get_product:linen-shirt:private-region-route"]
    assert replay == snapshot
    assert snapshot.state.current.node_id == "catalog.product"
    assert snapshot.state.current.entry_id == 2
    assert snapshot.state.back_stack == (Location(node_id="buyer.home", entry_id=1),)
    assert snapshot.state.forward_stack == ()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("product_result", "message"),
    (
        (
            ProductResult.failed(
                delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                failure=MedusaClientFailure(
                    kind=MedusaClientFailureKind.BUSINESS,
                    code="product_not_found",
                    public_message="That product is unavailable.",
                ),
            ),
            "product_not_found: That product is unavailable.",
        ),
        (
            ProductResult.failed(
                delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                failure=MedusaClientFailure(
                    kind=MedusaClientFailureKind.PROVIDER_PROTOCOL,
                    code="product_handle_not_unique",
                    public_message="The commerce service returned an invalid response.",
                ),
            ),
            "product_handle_not_unique: The commerce service returned an invalid response.",
        ),
        (
            ProductResult.succeeded(_product("different-product")),
            "Medusa product handle did not match the request",
        ),
    ),
)
async def test_open_product_by_route_fails_loudly_for_invalid_lookup(
    product_result: ProductResult,
    message: str,
) -> None:
    client = _client(product_result)
    runtime = build_test_runtime(client=client, market=_market())
    session = create_medusa_session(
        app=runtime.services.app.app,
        session_id="session-1",
        market=_market(),
    )
    request = OperationRequest(
        session_id=session.session_id,
        request_id="route-product-invalid",
        expected_session_version=session.session_version,
        operation_id=OPEN_PRODUCT_BY_ROUTE.id,
        source=OperationSource.SYSTEM,
        arguments=FrozenJsonObject({"product_handle": "linen-shirt"}),
    )

    with pytest.raises(CatalogProviderError) as raised:
        await CatalogProvider(client)(
            ProviderInvocationContext(
                session=session,
                request=request,
                attempt_id="attempt-route-product",
            )
        )
    assert str(raised.value) == message


def test_route_product_operation_uses_product_provider_without_entity_guard() -> None:
    assert OPEN_PRODUCT_BY_ROUTE.id == "catalog.open_product_by_route"
    assert OPEN_PRODUCT_BY_ROUTE.provider_refs == (CATALOG_PRODUCT_PROVIDER.ref,)
    assert OPEN_PRODUCT_BY_ROUTE.entity_inputs == ()
    assert OPEN_PRODUCT_BY_ROUTE.guard_refs == ()
    assert all(
        OPEN_PRODUCT_BY_ROUTE.ref not in capability.operations
        for capability in CATALOG_PRODUCT_NODE.capabilities
    )


def test_catalog_nodes_declare_exact_route_entry_operations() -> None:
    assert CATALOG_BROWSE_NODE.entry is not None
    assert CATALOG_BROWSE_NODE.entry.operation == CATALOG_LIST.ref
    assert CATALOG_BROWSE_NODE.entry.outcome == "listed"
    assert CATALOG_BROWSE_NODE.entry.bindings == ()

    assert CATALOG_PRODUCT_NODE.entry is not None
    assert CATALOG_PRODUCT_NODE.entry.operation == OPEN_PRODUCT_BY_ROUTE.ref
    assert CATALOG_PRODUCT_NODE.entry.outcome == "opened"
    assert tuple(
        (binding.parameter, binding.argument)
        for binding in CATALOG_PRODUCT_NODE.entry.bindings
    ) == (("product_handle", "product_handle"),)


def test_product_grid_declares_search_and_clear_affordances() -> None:
    affordances = {
        affordance.id: affordance.operation for affordance in PRODUCT_GRID.affordances
    }

    assert affordances["search_products"] == CATALOG_SEARCH.ref
    assert affordances["clear_search"] == CATALOG_LIST.ref
