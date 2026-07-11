from __future__ import annotations

import json

import pytest

from medusa_agent.composition import compile_medusa_app_spec
from routedeck_core.app import compile_app
from routedeck_core.validation import RouteDeckValidationError
from routedeck_testing.factories import invalid_app


EXPECTED_DOCUMENTS = {
    "compiled-navgraph.json",
    "frontend-contract.json",
    "contract-schema.json",
    "executable-test-paths.json",
}


def test_contract_documents_are_complete_json_and_deterministic() -> None:
    first = compile_medusa_app_spec().contract_documents()
    second = compile_medusa_app_spec().contract_documents()

    assert set(first) == EXPECTED_DOCUMENTS
    assert first == second
    assert all(json.loads(document) for document in first.values())


def test_executable_paths_cover_every_declared_branch() -> None:
    app = compile_medusa_app_spec()

    covered_transitions = {
        (
            path.source_node_id,
            path.operation_id,
            path.outcome,
            path.target_node_id,
        )
        for path in app.executable_test_paths
        if path.source_node_id is not None
        and path.operation_id is not None
        and path.outcome is not None
        and path.target_node_id is not None
    }
    declared_transitions = {
        (
            transition.source.id,
            transition.operation.id,
            transition.outcome,
            transition.target.id,
        )
        for transition in app.spec.transitions
    }
    assert covered_transitions >= declared_transitions

    covered_deep_links = {
        (path.node_id, path.deep_link_policy)
        for path in app.executable_test_paths
        if path.node_id is not None and path.deep_link_policy is not None
    }
    assert covered_deep_links >= {
        (node.id, node.route.deep_link_policy) for node in app.spec.nodes
    }

    covered_safety = {
        (path.operation_id, path.safety_class)
        for path in app.executable_test_paths
        if path.operation_id is not None and path.safety_class is not None
    }
    assert covered_safety >= {
        (operation.id, operation.safety_class)
        for operation in app.operations.values()
    }

    assert {
        path.branch
        for path in app.executable_test_paths
        if path.operation_id == "checkout.place_order"
    } >= {"review_approved", "review_rejected"}
    assert {
        path.node_id
        for path in app.executable_test_paths
        if path.branch == "recovery"
    } >= {
        node.id
        for node in app.spec.nodes
        if node.recovery.directives
    }


def test_compilation_fails_when_an_executable_path_cannot_be_derived() -> None:
    with pytest.raises(RouteDeckValidationError):
        compile_app(invalid_app("unexecutable_path"))


def test_frontend_contract_contains_rich_surface_slots_and_no_private_bindings() -> None:
    contract = compile_medusa_app_spec().frontend_contract
    product = contract.nodes["catalog.product"]

    assert product.surfaces.active == "catalog.product_detail"
    assert product.surfaces.frame
    assert set(type(product.surfaces).model_fields) >= {
        "active",
        "frame",
        "peer",
        "detail",
        "form",
        "review",
        "status",
        "error",
        "diagnostic",
    }
    serialized = contract.model_dump_json().lower()
    for private_term in (
        "medusa_id",
        "cart_id",
        "order_id",
        "line_item_id",
        "shipping_option_id",
        "payment_provider_id",
        "base_url",
        "api_key",
        "authorization",
        "medusa_agent.",
        "/store/",
        "/admin/",
    ):
        assert private_term not in serialized
