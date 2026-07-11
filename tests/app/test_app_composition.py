from __future__ import annotations

from collections.abc import Mapping

from medusa_agent.composition import compile_medusa_app_spec
from pydantic import BaseModel
from routedeck_core.contracts.navigation import DeepLinkPolicy


EXPECTED_NODES = (
    ("buyer.home", "/", "buyer.welcome", DeepLinkPolicy.SHAREABLE),
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
    "catalog.continue_shopping",
}


def test_composition_declares_exact_nodes_routes_surfaces_and_policies() -> None:
    app = compile_medusa_app_spec()

    assert tuple(
        (
            node.id,
            node.route.template,
            node.surfaces.active.id,
            node.route.deep_link_policy,
        )
        for node in app.spec.nodes
    ) == EXPECTED_NODES


def test_composition_declares_each_product_operation_once() -> None:
    app = compile_medusa_app_spec()

    assert set(app.operations) == EXPECTED_OPERATION_IDS
    assert sum(
        operation.id == "checkout.place_order"
        for node in app.spec.nodes
        for operation in node.operations
    ) == 1


def test_feature_specs_are_data_only_and_cross_feature_edges_live_in_composition() -> None:
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
