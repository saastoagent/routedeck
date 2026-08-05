from __future__ import annotations

import pytest
from pydantic import ValidationError

from routedeck_core.app import (
    Application,
    FeatureBindings,
    Feature,
    bind_app,
    compile_app,
)
from routedeck_core.contracts.application import Node
from routedeck_core.contracts.navigation import (
    DeepLinkPolicy,
    NodeKind,
    NodeRef,
    RecoveryPolicy,
    Route,
    Transition,
)
from routedeck_core.contracts.operations import (
    OperationRef,
    Operation,
    OperationSource,
    SafetyClass,
)
from routedeck_core.contracts.surfaces import SurfaceAffordance, SurfaceSlots, Surface
from routedeck_core.validation import RouteDeckValidationError
from routedeck_testing.factories import invalid_app, invalid_bindings


def compile_medusa_app():
    from medusa_agent.composition import compile_medusa_app as compile_application

    return compile_application()


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
    app = compile_medusa_app()

    assert tuple(node.id for node in app.graph.nodes) == EXPECTED_NODE_IDS
    assert (
        app.routes.encode("catalog.product", {"product_handle": "t-shirt"})
        == "/products/t-shirt"
    )
    assert (
        app.frontend_contract.surfaces["catalog.product_detail"].component
        == "catalog.product_detail"
    )


def test_node_owns_outgoing_and_compiler_derives_incoming() -> None:
    advance = Operation(
        id="test.advance",
        title="Advance",
        description="Advance once.",
        safety_class=SafetyClass.NAVIGATION,
        allowed_sources=frozenset(OperationSource),
        outcomes=("advanced",),
    )
    end = Node(
        id="test.end",
        title="End",
        kind=NodeKind.WORKFLOW,
        route=Route(
            template="/end",
            deep_link_policy=DeepLinkPolicy.SHAREABLE,
        ),
        surfaces=SurfaceSlots(
            active=Surface(id="test.end", component="test.end")
        ),
    )
    start = Node(
        id="test.start",
        title="Start",
        kind=NodeKind.WORKFLOW,
        route=Route(template="/", deep_link_policy=DeepLinkPolicy.SHAREABLE),
        operations=(advance,),
        outgoing=(
            Transition(
                operation=advance.ref,
                outcome="advanced",
                target=end.ref,
            ),
        ),
        surfaces=SurfaceSlots(
            active=Surface(id="test.start", component="test.start")
        ),
    )
    application = Application(
        name="node-owned",
        entry_node=start.ref,
        features=(Feature(namespace="test", nodes=(start, end)),),
    )

    compiled = compile_app(application)

    edge = compiled.graph.transitions[0]
    assert edge.source == start.ref
    assert edge.target == end.ref
    assert compiled.graph.incoming[end.id] == (edge,)
    assert compiled.graph.incoming[start.id] == ()


def test_compiler_rejects_surface_affordance_without_surface_source() -> None:
    operation = Operation(
        id="test.agent_only",
        title="Agent only",
        description="Operation that cannot be dispatched by a surface.",
        safety_class=SafetyClass.READ_EXTERNAL,
        allowed_sources=frozenset({OperationSource.AGENT}),
        outcomes=("done",),
    )
    surface = Surface(
        id="test.surface",
        component="test.surface",
        affordances=(
            SurfaceAffordance(
                id="submit",
                event="submit",
                operation=operation.ref,
            ),
        ),
    )
    node = Node(
        id="test.home",
        title="Test home",
        kind=NodeKind.SECTION,
        route=Route(template="/", deep_link_policy=DeepLinkPolicy.SHAREABLE),
        operations=(operation,),
        outgoing=(
            Transition(
                operation=operation.ref,
                outcome="done",
                target=NodeRef(id="test.home"),
            ),
        ),
        surfaces=SurfaceSlots(active=surface),
    )

    with pytest.raises(RouteDeckValidationError, match="allow surface invocation"):
        compile_app(
            Application(
                name="surface-source-test",
                entry_node=node.ref,
                features=(Feature(namespace="test", nodes=(node,)),),
            )
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


def test_transition_error_identifies_the_complete_source_branch() -> None:
    with pytest.raises(
        RouteDeckValidationError,
        match=(
            "feature='test'.*source='test.start'.*operation='test.advance'.*"
            "outcome='advanced'.*target='test.missing'"
        ),
    ):
        compile_app(invalid_app("dangling_transition"))


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
        Operation(
            id="test.invalid_schema",
            title="Invalid schema",
            description="Deliberately malformed contract.",
            safety_class=SafetyClass.READ_EXTERNAL,
            allowed_sources=frozenset(OperationSource),
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
    operation = Operation(
        id="test.repeat_write",
        title="Repeat write",
        description="The same canonical write is executable at two nodes.",
        safety_class=SafetyClass.WRITE_EXTERNAL,
        allowed_sources=frozenset(OperationSource),
        outcomes=("written",),
        unknown_recovery_directive="reconcile_repeat_write",
    )
    error_surface = Surface(id="test.error", component="test.error")
    first_surface = Surface(id="test.first", component="test.first")
    second_surface = Surface(id="test.second", component="test.second")
    recovery = RecoveryPolicy(
        directives=("reconcile_repeat_write",),
        failure_surface=error_surface.ref,
    )
    first = Node(
        id="test.first",
        title="First",
        kind=NodeKind.WORKFLOW,
        route=Route(template="/", deep_link_policy=DeepLinkPolicy.SHAREABLE),
        operations=(operation,),
        surfaces=SurfaceSlots(
            active=first_surface,
            error=(error_surface,),
        ),
        recovery=recovery,
    )
    second = Node(
        id="test.second",
        title="Second",
        kind=NodeKind.WORKFLOW,
        route=Route(
            template="/second",
            deep_link_policy=DeepLinkPolicy.SHAREABLE,
        ),
        operations=(operation,),
        surfaces=SurfaceSlots(
            active=second_surface,
            error=(error_surface,),
        ),
        recovery=recovery,
    )
    first = first.model_copy(
        update={
            "outgoing": (
                Transition(
                    operation=operation.ref,
                    outcome="written",
                    target=second.ref,
                ),
            )
        }
    )
    app = Application(
        name="repeat-write-test",
        entry_node=first.ref,
        features=(
            Feature(
                namespace="test",
                nodes=(first, second),
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
    app = compile_medusa_app()

    with pytest.raises(RouteDeckValidationError):
        bind_app(app, invalid_bindings(app, mutation))


@pytest.mark.parametrize(
    "mutation",
    ("sync_handler", "sync_provider", "sync_guard"),
)
def test_binding_requires_async_product_implementations(mutation: str) -> None:
    app = compile_medusa_app()

    with pytest.raises(RouteDeckValidationError, match="async"):
        bind_app(app, invalid_bindings(app, mutation))


@pytest.mark.parametrize(
    "mutation",
    ("wrong_handler_signature", "wrong_handler_return"),
)
def test_binding_rejects_nonconforming_async_handlers(mutation: str) -> None:
    app = compile_medusa_app()

    with pytest.raises(RouteDeckValidationError, match="signature|return"):
        bind_app(app, invalid_bindings(app, mutation))


def test_declared_objects_are_canonical_across_nodes_and_catalogs() -> None:
    app = compile_medusa_app()

    for node in app.graph.nodes:
        for operation in node.operations:
            assert app.operations[operation.id] is operation
        for provider in (*node.context_providers, *node.entity_providers):
            assert app.providers[provider.id] is provider
        for surface in node.surfaces.declared_surfaces():
            contract = app.frontend_contract.surfaces[surface.id]
            assert contract.id == surface.id
            assert contract.component == surface.component
            assert contract.lifecycle is surface.lifecycle
            assert contract.affordances == surface.affordances
            assert contract.public_props_schema == surface.public_props_schema


def test_feature_binding_merge_rejects_duplicate_ownership() -> None:
    app = compile_medusa_app()
    bindings = invalid_bindings(app, "missing_handler")
    ref, handler = next(iter(bindings.handlers.items()))

    with pytest.raises(RouteDeckValidationError, match="Duplicate handler"):
        FeatureBindings.merge(
            bindings,
            FeatureBindings(handlers={ref: handler}, providers={}, guards={}),
        )


def _write_recovery_app(mutation: str) -> Application:
    recovery_operation = Operation(
        id="test.reconcile",
        title="Reconcile",
        description="Read authoritative state after an uncertain write.",
        safety_class=SafetyClass.READ_EXTERNAL,
        allowed_sources=frozenset(OperationSource),
        outcomes=("reconciled",),
    )
    recovery_refs = (recovery_operation.ref,)
    node_directives = ("reconcile_external_write",)
    if mutation == "missing_directive":
        node_directives = ("different_directive",)
    elif mutation == "foreign_recovery_operation":
        recovery_refs = (recovery_operation.ref,)

    write_operation = Operation(
        id="test.write",
        title="Write",
        description="Perform one externally mutating request.",
        safety_class=SafetyClass.WRITE_EXTERNAL,
        allowed_sources=frozenset(OperationSource),
        outcomes=("written",),
        unknown_recovery_directive="reconcile_external_write",
        unknown_recovery_operation_refs=(
            (OperationRef(id="test.write"),)
            if mutation == "self_recovery_operation"
            else recovery_refs
        ),
    )
    active_surface = Surface(id="test.active", component="test.active")
    result_surface = Surface(id="test.result", component="test.result")
    error_surface = Surface(id="test.error", component="test.error")
    write_node_operations = (write_operation, recovery_operation)
    result_node_operations: tuple[Operation, ...] = ()
    write_node_error_surfaces = (error_surface,)
    if mutation == "foreign_failure_surface":
        write_node_error_surfaces = ()
    if mutation == "foreign_recovery_operation":
        write_node_operations = (write_operation,)
        result_node_operations = (recovery_operation,)

    write_node = Node(
        id="test.write_node",
        title="Write node",
        kind=NodeKind.WORKFLOW,
        route=Route(template="/", deep_link_policy=DeepLinkPolicy.SHAREABLE),
        operations=write_node_operations,
        surfaces=SurfaceSlots(
            active=active_surface,
            error=write_node_error_surfaces,
        ),
        recovery=RecoveryPolicy(
            directives=node_directives,
            failure_surface=error_surface.ref,
        ),
    )
    result_node = Node(
        id="test.result_node",
        title="Result node",
        kind=NodeKind.WORKFLOW,
        route=Route(
            template="/result",
            deep_link_policy=DeepLinkPolicy.SHAREABLE,
        ),
        operations=result_node_operations,
        surfaces=SurfaceSlots(active=result_surface, error=(error_surface,)),
    )
    transitions = [
        Transition(
            operation=write_operation.ref,
            outcome="written",
            target=result_node.ref,
        )
    ]
    recovery_source = (
        result_node if mutation == "foreign_recovery_operation" else write_node
    )
    transitions.append(
        Transition(
            operation=recovery_operation.ref,
            outcome="reconciled",
            target=result_node.ref,
        )
    )
    write_outgoing = (transitions[0],)
    result_outgoing: tuple[Transition, ...] = ()
    if recovery_source is write_node:
        write_outgoing = tuple(transitions)
    else:
        result_outgoing = (transitions[1],)
    write_node = write_node.model_copy(update={"outgoing": write_outgoing})
    result_node = result_node.model_copy(update={"outgoing": result_outgoing})
    return Application(
        name="write-recovery-test",
        entry_node=write_node.ref,
        features=(
            Feature(
                namespace="test",
                nodes=(write_node, result_node),
            ),
        ),
    )
