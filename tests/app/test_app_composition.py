from __future__ import annotations

import ast
import importlib.util
import inspect
from collections.abc import Mapping
from types import ModuleType

from medusa_agent.composition import compile_medusa_app_spec
from medusa_agent.features.cart import feature as cart_feature
from medusa_agent.features.catalog import feature as catalog_feature
from medusa_agent.features.checkout import feature as checkout_feature
from medusa_agent.features.orders import feature as orders_feature
from pydantic import BaseModel
from routedeck_core.contracts.navigation import DeepLinkPolicy


EXPECTED_NODES = (
    ("buyer.home", "/", None, DeepLinkPolicy.SHAREABLE),
    (
        "catalog.browse",
        "/products",
        "catalog.product_grid",
        DeepLinkPolicy.SHAREABLE,
    ),
    (
        "catalog.product",
        "/products/{product_handle}",
        "catalog.product_detail",
        DeepLinkPolicy.SHAREABLE,
    ),
    ("cart.summary", "/cart", "cart.summary", DeepLinkPolicy.SESSION_BOUND),
    (
        "checkout.contact",
        "/checkout/contact",
        "checkout.contact_form",
        DeepLinkPolicy.SESSION_BOUND,
    ),
    (
        "checkout.delivery",
        "/checkout/delivery",
        "checkout.shipping_options",
        DeepLinkPolicy.SESSION_BOUND,
    ),
    (
        "checkout.payment",
        "/checkout/payment",
        "checkout.payment_method",
        DeepLinkPolicy.SESSION_BOUND,
    ),
    (
        "checkout.review",
        "/checkout/review",
        "checkout.order_review",
        DeepLinkPolicy.SESSION_BOUND,
    ),
    (
        "orders.confirmation",
        "/orders/{confirmation_handle}/confirmation",
        "orders.confirmation",
        DeepLinkPolicy.SESSION_BOUND,
    ),
)

EXPECTED_OPERATION_IDS = {
    "catalog.list",
    "catalog.search",
    "catalog.open_product",
    "catalog.open_product_by_route",
    "catalog.select_variant",
    "cart.create",
    "cart.add_item",
    "cart.open",
    "cart.update_item",
    "cart.remove_item",
    "checkout.start",
    "checkout.save_contact",
    "checkout.select_shipping",
    "checkout.select_payment",
    "checkout.place_order",
    "orders.reconcile",
    "catalog.continue_shopping",
}


def test_composition_declares_exact_nodes_routes_surfaces_and_policies() -> None:
    app = compile_medusa_app_spec()

    assert (
        tuple(
            (
                node.id,
                node.route.template,
                node.surfaces.active.id if node.surfaces.active else None,
                node.route.deep_link_policy,
            )
            for node in app.spec.nodes
        )
        == EXPECTED_NODES
    )


def test_composition_declares_each_product_operation_once() -> None:
    app = compile_medusa_app_spec()

    assert set(app.operations) == EXPECTED_OPERATION_IDS
    assert (
        sum(
            operation.id == "checkout.place_order"
            for node in app.spec.nodes
            for operation in node.operations
        )
        == 1
    )


def test_feature_specs_are_data_only_and_cross_feature_edges_live_in_composition() -> (
    None
):
    app = compile_medusa_app_spec()

    raw_values = tuple(_walk_model_fields(app.source_spec))
    rendered = repr(app.source_spec.model_dump(mode="json")).lower()
    assert "http://" not in rendered
    assert "https://" not in rendered
    assert "/store/" not in rendered
    assert "/admin/" not in rendered
    assert "endpoint" not in rendered
    assert all(not callable(value) for value in raw_values)
    assert all(
        transition.source.feature == transition.target.feature
        for feature in app.source_spec.features
        for transition in feature.transitions
    )
    feature_transitions = {
        (transition.source.id, transition.operation.id, transition.target.id)
        for feature in app.source_spec.features
        for transition in feature.transitions
    }
    compiled_cross_feature = {
        (transition.source.id, transition.operation.id, transition.target.id)
        for transition in app.spec.transitions
        if transition.source.feature != transition.target.feature
    }
    assert compiled_cross_feature
    assert compiled_cross_feature.isdisjoint(feature_transitions)


def test_feature_modules_are_isolated_and_composition_owns_contributions() -> None:
    modules = (
        catalog_feature,
        cart_feature,
        checkout_feature,
        orders_feature,
    )
    sibling_imports = {
        module.__name__: _sibling_feature_imports(module) for module in modules
    }
    assert sibling_imports == {module.__name__: set() for module in modules}

    catalog_nodes = {node.id: node for node in catalog_feature.FEATURE_SPEC.nodes}
    cart_node = cart_feature.FEATURE_SPEC.nodes[0]
    orders_node = orders_feature.FEATURE_SPEC.nodes[0]
    assert {
        operation.id for operation in catalog_nodes["catalog.browse"].operations
    } == {
        "catalog.list",
        "catalog.search",
        "catalog.open_product",
    }
    assert {
        operation.id for operation in catalog_nodes["catalog.product"].operations
    } == {"catalog.open_product_by_route", "catalog.select_variant"}
    assert {operation.id for operation in cart_node.operations} == {
        "cart.open",
        "cart.update_item",
        "cart.remove_item",
    }
    assert orders_node.operations == ()

    app = compile_medusa_app_spec()
    compiled_nodes = {node.id: node for node in app.spec.nodes}
    composition_transitions = {
        (
            transition.source.id,
            transition.operation.id,
            transition.outcome,
            transition.target.id,
        )
        for transition in app.source_spec.transitions
    }
    assert (
        "catalog.product",
        "cart.create",
        "created",
        "catalog.product",
    ) in composition_transitions
    assert (
        "catalog.product",
        "cart.add_item",
        "added",
        "catalog.product",
    ) in composition_transitions
    assert {
        operation.id for operation in compiled_nodes["catalog.product"].operations
    } >= {"cart.create", "cart.add_item", "cart.open"}
    assert {
        operation.id for operation in compiled_nodes["cart.summary"].operations
    } >= {"checkout.start"}
    assert {
        operation.id for operation in compiled_nodes["orders.confirmation"].operations
    } == {"catalog.continue_shopping"}

    assert _affordance_operation_ids(
        catalog_nodes["catalog.product"].surfaces.active
    ) == {"catalog.select_variant"}
    assert _affordance_operation_ids(
        compiled_nodes["catalog.product"].surfaces.active
    ) >= {"cart.create", "cart.add_item", "cart.open"}
    assert _affordance_operation_ids(cart_node.surfaces.active) == {
        "cart.update_item",
        "cart.remove_item",
    }
    assert _affordance_operation_ids(
        compiled_nodes["cart.summary"].surfaces.active
    ) >= {"checkout.start"}
    assert _affordance_operation_ids(orders_node.surfaces.active) == set()
    assert _affordance_operation_ids(
        compiled_nodes["orders.confirmation"].surfaces.active
    ) == {"catalog.continue_shopping"}


def test_medusa_entity_arguments_are_explicit_and_node_scoped() -> None:
    app = compile_medusa_app_spec()
    expected = {
        "catalog.open_product": {"product_ref": "product"},
        "catalog.select_variant": {"variant_ref": "variant"},
        "cart.add_item": {"variant_ref": "variant"},
        "cart.update_item": {"line_item_ref": "line_item"},
        "cart.remove_item": {"line_item_ref": "line_item"},
        "checkout.select_shipping": {"shipping_option_ref": "shipping_option"},
        "checkout.select_payment": {"payment_provider_ref": "payment_provider"},
    }

    assert {
        operation_id: {
            entity.argument_name: entity.entity_kind
            for entity in app.operations[operation_id].entity_inputs
        }
        for operation_id in expected
    } == expected
    for node in app.spec.nodes:
        declared_kinds = {provider.entity_kind for provider in node.entity_providers}
        for operation in node.operations:
            assert {
                entity.entity_kind for entity in operation.entity_inputs
            } <= declared_kinds


def _sibling_feature_imports(module: ModuleType) -> set[str]:
    imports: set[str] = set()
    current_feature = module.__package__.rsplit(".", 1)[-1]
    for node in ast.walk(ast.parse(inspect.getsource(module))):
        targets: tuple[str, ...] = ()
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            if node.level:
                targets = (
                    importlib.util.resolve_name(
                        f"{'.' * node.level}{node.module}", module.__package__
                    ),
                )
            else:
                targets = (node.module,)
        elif isinstance(node, ast.Import):
            targets = tuple(alias.name for alias in node.names)
        for target in targets:
            parts = target.split(".")
            if (
                len(parts) >= 4
                and parts[:2] == ["medusa_agent", "features"]
                and parts[2] != current_feature
            ):
                imports.add(target)
    return imports


def _affordance_operation_ids(surface) -> set[str]:
    return {
        affordance.operation.id
        for affordance in surface.affordances
        if affordance.operation is not None
    }


def _walk_model_fields(value: object):
    if isinstance(value, BaseModel):
        for field_name in type(value).model_fields:
            child = getattr(value, field_name)
            yield child
            yield from _walk_model_fields(child)
    elif isinstance(value, Mapping):
        for child in value.values():
            yield child
            yield from _walk_model_fields(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield child
            yield from _walk_model_fields(child)
