from __future__ import annotations

import json

import pytest

from medusa_agent.composition import compile_medusa_app
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
    first = compile_medusa_app().contract_documents()
    second = compile_medusa_app().contract_documents()

    assert set(first) == EXPECTED_DOCUMENTS
    assert first == second
    assert all(json.loads(document) for document in first.values())


def test_compiled_application_exposes_one_immutable_node_index() -> None:
    compiled = compile_medusa_app()

    assert set(compiled.nodes) == {node.id for node in compiled.graph.nodes}
    assert all(compiled.nodes[node.id] is node for node in compiled.graph.nodes)
    assert compiled.require_node("checkout.contact") is compiled.nodes[
        "checkout.contact"
    ]
    with pytest.raises(TypeError):
        compiled.nodes["extra.node"] = compiled.graph.nodes[0]  # type: ignore[index]


def test_compiled_application_require_node_raises_typed_named_error() -> None:
    compiled = compile_medusa_app()

    with pytest.raises(RouteDeckValidationError, match="missing.node"):
        compiled.require_node("missing.node")


def test_executable_paths_cover_every_declared_branch() -> None:
    app = compile_medusa_app()

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
        for transition in app.graph.transitions
    }
    assert covered_transitions >= declared_transitions

    covered_deep_links = {
        (path.node_id, path.deep_link_policy)
        for path in app.executable_test_paths
        if path.node_id is not None and path.deep_link_policy is not None
    }
    assert covered_deep_links >= {
        (node.id, node.route.deep_link_policy) for node in app.graph.nodes
    }

    covered_safety = {
        (path.operation_id, path.safety_class)
        for path in app.executable_test_paths
        if path.operation_id is not None and path.safety_class is not None
    }
    assert covered_safety >= {
        (operation.id, operation.safety_class) for operation in app.operations.values()
    }

    assert {
        path.branch
        for path in app.executable_test_paths
        if path.operation_id == "checkout.place_order"
    } >= {"review_approved", "review_rejected"}
    assert {
        path.node_id for path in app.executable_test_paths if path.branch == "recovery"
    } >= {node.id for node in app.graph.nodes if node.recovery.directives}


def test_compilation_fails_when_an_executable_path_cannot_be_derived() -> None:
    with pytest.raises(RouteDeckValidationError):
        compile_app(invalid_app("unexecutable_path"))


def test_frontend_contract_contains_rich_surface_slots_and_no_private_bindings() -> (
    None
):
    compiled = compile_medusa_app()
    contract = compiled.frontend_contract
    product = contract.nodes["catalog.product"]
    contact_node = next(
        node for node in compiled.graph.nodes if node.id == "checkout.contact"
    )
    review_node = next(
        node for node in compiled.graph.nodes if node.id == "checkout.review"
    )
    contact_binding = contact_node.surfaces.active.private_form_binding
    review_binding = review_node.surfaces.active.private_form_binding

    assert contact_binding is not None
    assert contact_binding.form_id_prop == "form_handle"
    assert contact_binding.allowed_field_names == (
        "email",
        "shipping_address",
        "billing_choice",
        "billing_address",
    )
    assert review_binding == contact_binding
    frontend_contact = contract.surfaces["checkout.contact_form"]
    assert frontend_contact.id == contact_node.surfaces.active.id
    assert frontend_contact.component == contact_node.surfaces.active.component
    assert frontend_contact.lifecycle == contact_node.surfaces.active.lifecycle
    assert frontend_contact.affordances == contact_node.surfaces.active.affordances
    assert product.surfaces.active == "catalog.product_detail"
    assert product.conversation_input.enabled is True
    assert product.conversation_input.disabled_message is None
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
        "private_form_binding",
        "allowed_field_names",
        "/store/",
        "/admin/",
    ):
        assert private_term not in serialized
