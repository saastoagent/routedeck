from __future__ import annotations

import pytest

from medusa_agent.composition import compile_medusa_app_spec
from routedeck_core.app import bind_app, compile_app
from routedeck_core.validation import RouteDeckValidationError
from routedeck_testing.factories import invalid_app, invalid_bindings


EXPECTED_NODE_IDS = (
    "buyer.home",
    "catalog.browse",
    "catalog.product",
    "cart.summary",
    "checkout.contact",
    "checkout.delivery",
    "checkout.payment",
    "checkout.review",
    "orders.confirmation",
)


def test_medusa_features_compile_to_the_nine_node_graph() -> None:
    app = compile_medusa_app_spec()

    assert tuple(node.id for node in app.spec.nodes) == EXPECTED_NODE_IDS
    assert app.routes.encode(
        "catalog.product", {"product_handle": "t-shirt"}
    ) == "/products/t-shirt"
    assert (
        app.frontend_contract.surfaces["catalog.product_detail"].component
        == "catalog.product_detail"
    )


@pytest.mark.parametrize(
    "mutation",
    (
        "duplicate_node",
        "duplicate_route",
        "dangling_transition",
        "missing_surface",
        "missing_outcome",
        "missing_provider",
        "unreachable_node",
        "hierarchy_cycle",
    ),
)
def test_compiler_rejects_invalid_specs(mutation: str) -> None:
    with pytest.raises(RouteDeckValidationError):
        compile_app(invalid_app(mutation))


@pytest.mark.parametrize(
    "mutation",
    ("conflicting_operation", "conflicting_provider", "conflicting_surface"),
)
def test_compiler_rejects_distinct_definitions_reusing_an_id(
    mutation: str,
) -> None:
    with pytest.raises(RouteDeckValidationError):
        compile_app(invalid_app(mutation))


@pytest.mark.parametrize(
    "mutation",
    (
        "missing_handler",
        "extra_handler",
        "missing_provider",
        "extra_provider",
        "missing_guard",
        "extra_guard",
    ),
)
def test_binding_requires_exactly_one_implementation_per_declaration(
    mutation: str,
) -> None:
    app = compile_medusa_app_spec()

    with pytest.raises(RouteDeckValidationError):
        bind_app(app, invalid_bindings(app, mutation))


def test_declared_objects_are_canonical_across_nodes_and_catalogs() -> None:
    app = compile_medusa_app_spec()

    for node in app.spec.nodes:
        for operation in node.operations:
            assert app.operations[operation.id] is operation
        for provider in (*node.context_providers, *node.entity_providers):
            assert app.providers[provider.id] is provider
        for surface in node.surfaces.declared_surfaces():
            assert app.frontend_contract.surfaces[surface.id] is surface
