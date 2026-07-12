from __future__ import annotations

import pytest
from pydantic import ValidationError

from medusa_agent.composition import compile_medusa_app_spec
from routedeck_core.app import (
    ApplicationSpec,
    FeatureSpec,
    bind_app,
    compile_app,
)
from routedeck_core.contracts.application import NodeSpec
from routedeck_core.contracts.navigation import (
    DeepLinkPolicy,
    NodeKind,
    RecoveryPolicySpec,
    RouteSpec,
    TransitionSpec,
)
from routedeck_core.contracts.operations import (
    OperationRef,
    OperationSpec,
    SafetyClass,
)
from routedeck_core.contracts.surfaces import SurfaceSlotsSpec, SurfaceSpec
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
    assert (
        app.routes.encode("catalog.product", {"product_handle": "t-shirt"})
        == "/products/t-shirt"
    )
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
        "missing_entity_provider",
        "provider_not_on_node",
        "guard_not_on_node",
        "unreachable_node",
        "hierarchy_cycle",
        "parameterized_cancel_target",
    ),
)
def test_compiler_rejects_invalid_specs(mutation: str) -> None:
    with pytest.raises(RouteDeckValidationError):
        compile_app(invalid_app(mutation))


@pytest.mark.parametrize(
    "schemas",
    (
        {"input_schema": {"type": "not-a-json-schema-type"}},
        {
            "outcome_schemas": {
                "done": {
                    "type": "object",
                    "properties": {"value": {"type": "not-a-json-schema-type"}},
                }
            }
        },
    ),
)
def test_operation_specs_reject_malformed_json_schemas(
    schemas: dict[str, object],
) -> None:
    with pytest.raises(ValidationError, match="valid JSON Schema"):
        OperationSpec(
            id="test.invalid_schema",
            title="Invalid schema",
            description="Deliberately malformed contract.",
            safety_class=SafetyClass.READ_EXTERNAL,
            outcomes=("done",),
            **schemas,
        )


def test_compiler_rejects_overlapping_route_templates() -> None:
    with pytest.raises(RouteDeckValidationError):
        compile_app(invalid_app("ambiguous_route"))


def test_compiler_rejects_ambiguous_transition_outcomes() -> None:
    with pytest.raises(RouteDeckValidationError):
        compile_app(invalid_app("ambiguous_transition"))


@pytest.mark.parametrize(
    "mutation, message",
    (
        ("missing_directive", "recovery directive"),
        ("foreign_failure_surface", "failure surface"),
        ("foreign_recovery_operation", "recovery operation"),
        ("self_recovery_operation", "affected operation"),
    ),
)
def test_compiler_rejects_incomplete_write_recovery_contracts(
    mutation: str,
    message: str,
) -> None:
    with pytest.raises(RouteDeckValidationError, match=message):
        compile_app(_write_recovery_app(mutation))


def test_compiler_rejects_repeat_write_graph_missing_one_node_transition() -> None:
    operation = OperationSpec(
        id="test.repeat_write",
        title="Repeat write",
        description="The same canonical write is executable at two nodes.",
        safety_class=SafetyClass.WRITE_EXTERNAL,
        outcomes=("written",),
        unknown_recovery_directive="reconcile_repeat_write",
    )
    error_surface = SurfaceSpec(id="test.error", component="test.error")
    first_surface = SurfaceSpec(id="test.first", component="test.first")
    second_surface = SurfaceSpec(id="test.second", component="test.second")
    recovery = RecoveryPolicySpec(
        directives=("reconcile_repeat_write",),
        failure_surface=error_surface.ref,
    )
    first = NodeSpec(
        id="test.first",
        title="First",
        kind=NodeKind.WORKFLOW,
        route=RouteSpec(template="/", deep_link_policy=DeepLinkPolicy.SHAREABLE),
        operations=(operation,),
        surfaces=SurfaceSlotsSpec(
            active=first_surface,
            error=(error_surface,),
        ),
        recovery=recovery,
    )
    second = NodeSpec(
        id="test.second",
        title="Second",
        kind=NodeKind.WORKFLOW,
        route=RouteSpec(
            template="/second",
            deep_link_policy=DeepLinkPolicy.SHAREABLE,
        ),
        operations=(operation,),
        surfaces=SurfaceSlotsSpec(
            active=second_surface,
            error=(error_surface,),
        ),
        recovery=recovery,
    )
    app = ApplicationSpec(
        name="repeat-write-test",
        entry_node=first.ref,
        features=(
            FeatureSpec(
                namespace="test",
                nodes=(first, second),
                transitions=(
                    TransitionSpec(
                        source=first.ref,
                        operation=operation.ref,
                        outcome="written",
                        target=second.ref,
                    ),
                ),
            ),
        ),
    )

    with pytest.raises(
        RouteDeckValidationError, match="exactly one compiled transition"
    ):
        compile_app(app)


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


@pytest.mark.parametrize(
    "mutation",
    ("sync_handler", "sync_provider", "sync_guard"),
)
def test_binding_requires_async_product_implementations(mutation: str) -> None:
    app = compile_medusa_app_spec()

    with pytest.raises(RouteDeckValidationError, match="async"):
        bind_app(app, invalid_bindings(app, mutation))


@pytest.mark.parametrize(
    "mutation",
    ("wrong_handler_signature", "wrong_handler_return"),
)
def test_binding_rejects_nonconforming_async_handlers(mutation: str) -> None:
    app = compile_medusa_app_spec()

    with pytest.raises(RouteDeckValidationError, match="signature|return"):
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


def _write_recovery_app(mutation: str) -> ApplicationSpec:
    recovery_operation = OperationSpec(
        id="test.reconcile",
        title="Reconcile",
        description="Read authoritative state after an uncertain write.",
        safety_class=SafetyClass.READ_EXTERNAL,
        outcomes=("reconciled",),
    )
    recovery_refs = (recovery_operation.ref,)
    node_directives = ("reconcile_external_write",)
    if mutation == "missing_directive":
        node_directives = ("different_directive",)
    elif mutation == "foreign_recovery_operation":
        recovery_refs = (recovery_operation.ref,)

    write_operation = OperationSpec(
        id="test.write",
        title="Write",
        description="Perform one externally mutating request.",
        safety_class=SafetyClass.WRITE_EXTERNAL,
        outcomes=("written",),
        unknown_recovery_directive="reconcile_external_write",
        unknown_recovery_operation_refs=(
            (OperationRef(id="test.write"),)
            if mutation == "self_recovery_operation"
            else recovery_refs
        ),
    )
    active_surface = SurfaceSpec(id="test.active", component="test.active")
    result_surface = SurfaceSpec(id="test.result", component="test.result")
    error_surface = SurfaceSpec(id="test.error", component="test.error")
    write_node_operations = (write_operation, recovery_operation)
    result_node_operations: tuple[OperationSpec, ...] = ()
    write_node_error_surfaces = (error_surface,)
    if mutation == "foreign_failure_surface":
        write_node_error_surfaces = ()
    if mutation == "foreign_recovery_operation":
        write_node_operations = (write_operation,)
        result_node_operations = (recovery_operation,)

    write_node = NodeSpec(
        id="test.write_node",
        title="Write node",
        kind=NodeKind.WORKFLOW,
        route=RouteSpec(template="/", deep_link_policy=DeepLinkPolicy.SHAREABLE),
        operations=write_node_operations,
        surfaces=SurfaceSlotsSpec(
            active=active_surface,
            error=write_node_error_surfaces,
        ),
        recovery=RecoveryPolicySpec(
            directives=node_directives,
            failure_surface=error_surface.ref,
        ),
    )
    result_node = NodeSpec(
        id="test.result_node",
        title="Result node",
        kind=NodeKind.WORKFLOW,
        route=RouteSpec(
            template="/result",
            deep_link_policy=DeepLinkPolicy.SHAREABLE,
        ),
        operations=result_node_operations,
        surfaces=SurfaceSlotsSpec(active=result_surface, error=(error_surface,)),
    )
    transitions = [
        TransitionSpec(
            source=write_node.ref,
            operation=write_operation.ref,
            outcome="written",
            target=result_node.ref,
        )
    ]
    recovery_source = (
        result_node if mutation == "foreign_recovery_operation" else write_node
    )
    transitions.append(
        TransitionSpec(
            source=recovery_source.ref,
            operation=recovery_operation.ref,
            outcome="reconciled",
            target=result_node.ref,
        )
    )
    return ApplicationSpec(
        name="write-recovery-test",
        entry_node=write_node.ref,
        features=(
            FeatureSpec(
                namespace="test",
                nodes=(write_node, result_node),
                transitions=tuple(transitions),
            ),
        ),
    )
