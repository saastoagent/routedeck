from __future__ import annotations

import routedeck_core.contracts.application as application_contracts
from routedeck_core.app import Application, Feature, compile_app
from routedeck_core.contracts.navigation import (
    DeepLinkPolicy,
    NodeKind,
    NodeRef,
    Route,
    Transition,
)
from routedeck_core.contracts.operations import OperationRef, Operation, SafetyClass
from routedeck_core.contracts.surfaces import SurfaceSlots, Surface
from routedeck_core.validation import RouteDeckValidationError

import pytest


def test_route_entry_contract_is_typed_and_attached_to_node() -> None:
    assert hasattr(application_contracts, "RouteEntry")
    assert hasattr(application_contracts, "RouteParameterBinding")

    operation = Operation(
        id="inventory.open_item",
        title="Open item",
        description="Resolve one public item route.",
        input_schema={
            "type": "object",
            "properties": {"item_handle": {"type": "string"}},
            "required": ["item_handle"],
            "additionalProperties": False,
        },
        safety_class=SafetyClass.READ_EXTERNAL,
        outcomes=("loaded",),
    )
    binding = application_contracts.RouteParameterBinding(
        parameter="item_handle",
        argument="item_handle",
    )
    entry = application_contracts.RouteEntry(
        operation=operation.ref,
        outcome="loaded",
        bindings=(binding,),
    )
    node = application_contracts.Node(
        id="inventory.item",
        title="Item",
        kind=NodeKind.DETAIL,
        route=Route(
            template="/items/{item_handle}",
            deep_link_policy=DeepLinkPolicy.SHAREABLE,
        ),
        entry=entry,
        operations=(operation,),
        surfaces=SurfaceSlots(
            active=Surface(id="inventory.item", component="inventory.item")
        ),
    )

    assert node.entry == entry


def _route_entry_source(
    *,
    entry: application_contracts.RouteEntry | None = None,
    operations: tuple[Operation, ...] | None = None,
    declared_transition: Transition | None = None,
) -> Application:
    operation = _open_operation()
    route_entry = entry or application_contracts.RouteEntry(
        operation=operation.ref,
        outcome="loaded",
        bindings=(
            application_contracts.RouteParameterBinding(
                parameter="item_handle",
                argument="item_handle",
            ),
        ),
    )
    item = application_contracts.Node(
        id="inventory.item",
        title="Item",
        kind=NodeKind.DETAIL,
        route=Route(
            template="/items/{item_handle}",
            deep_link_policy=DeepLinkPolicy.SHAREABLE,
        ),
        entry=route_entry,
        operations=operations if operations is not None else (operation,),
        surfaces=SurfaceSlots(
            active=Surface(id="inventory.item", component="inventory.item")
        ),
    )
    if declared_transition is not None:
        item = item.model_copy(update={"outgoing": (declared_transition,)})
    nodes = (item,)
    if declared_transition is not None and declared_transition.target.id != item.id:
        nodes = (
            item,
            application_contracts.Node(
                id=declared_transition.target.id,
                title="Other",
                kind=NodeKind.SECTION,
                route=Route(
                    template="/other",
                    deep_link_policy=DeepLinkPolicy.SHAREABLE,
                ),
                surfaces=SurfaceSlots(
                    active=Surface(
                        id="inventory.other",
                        component="inventory.other",
                    )
                ),
            ),
        )
    return Application(
        name="route-entry-test",
        entry_node=item.ref,
        features=(
            Feature(
                namespace="inventory",
                nodes=nodes,
            ),
        ),
    )


def _open_operation() -> Operation:
    return Operation(
        id="inventory.open_item",
        title="Open item",
        description="Resolve one public item route.",
        input_schema={
            "type": "object",
            "properties": {"item_handle": {"type": "string"}},
            "required": ["item_handle"],
            "additionalProperties": False,
        },
        safety_class=SafetyClass.READ_EXTERNAL,
        outcomes=("loaded",),
    )


def test_compiler_materializes_one_explicit_route_entry_self_transition() -> None:
    app = compile_app(_route_entry_source())

    assert len(app.graph.transitions) == 1
    transition = app.graph.transitions[0]
    assert (
        transition.source.id,
        transition.operation.id,
        transition.outcome,
        transition.target.id,
    ) == (
        "inventory.item",
        "inventory.open_item",
        "loaded",
        "inventory.item",
    )


def test_compiler_preserves_an_identical_declared_route_entry_transition() -> None:
    operation = _open_operation()
    transition = Transition(
        operation=operation.ref,
        outcome="loaded",
        target=NodeRef(id="inventory.item"),
    )

    app = compile_app(
        _route_entry_source(
            operations=(operation,),
            declared_transition=transition,
        )
    )

    compiled = app.graph.transitions[0]
    assert compiled.source == NodeRef(id="inventory.item")
    assert compiled.operation == transition.operation
    assert compiled.outcome == transition.outcome
    assert compiled.target == transition.target


@pytest.mark.parametrize(
    ("entry", "message"),
    (
        (
            application_contracts.RouteEntry(
                operation=_open_operation().ref,
                outcome="loaded",
                bindings=(),
            ),
            "missing route parameter",
        ),
        (
            application_contracts.RouteEntry(
                operation=_open_operation().ref,
                outcome="loaded",
                bindings=(
                    application_contracts.RouteParameterBinding(
                        parameter="unknown_handle",
                        argument="item_handle",
                    ),
                ),
            ),
            "unknown route parameter",
        ),
        (
            application_contracts.RouteEntry(
                operation=_open_operation().ref,
                outcome="loaded",
                bindings=(
                    application_contracts.RouteParameterBinding(
                        parameter="item_handle",
                        argument="item_handle",
                    ),
                    application_contracts.RouteParameterBinding(
                        parameter="item_handle",
                        argument="item_handle",
                    ),
                ),
            ),
            "route parameter more than once",
        ),
        (
            application_contracts.RouteEntry(
                operation=_open_operation().ref,
                outcome="loaded",
                bindings=(
                    application_contracts.RouteParameterBinding(
                        parameter="item_handle",
                        argument="unknown_argument",
                    ),
                ),
            ),
            "undeclared operation argument",
        ),
        (
            application_contracts.RouteEntry(
                operation=OperationRef(id="inventory.unavailable"),
                outcome="loaded",
                bindings=(
                    application_contracts.RouteParameterBinding(
                        parameter="item_handle",
                        argument="item_handle",
                    ),
                ),
            ),
            "not executable",
        ),
        (
            application_contracts.RouteEntry(
                operation=_open_operation().ref,
                outcome="unknown",
                bindings=(
                    application_contracts.RouteParameterBinding(
                        parameter="item_handle",
                        argument="item_handle",
                    ),
                ),
            ),
            "undeclared outcome",
        ),
    ),
)
def test_compiler_rejects_inexact_route_entry_contracts(
    entry: application_contracts.RouteEntry,
    message: str,
) -> None:
    with pytest.raises(RouteDeckValidationError, match=message):
        compile_app(_route_entry_source(entry=entry))


def test_compiler_rejects_a_conflicting_declared_route_entry_branch() -> None:
    operation = _open_operation()
    conflicting = Transition(
        operation=operation.ref,
        outcome="loaded",
        target=NodeRef(id="inventory.other"),
    )

    with pytest.raises(RouteDeckValidationError, match="conflicting route entry"):
        compile_app(
            _route_entry_source(
                operations=(operation,),
                declared_transition=conflicting,
            )
        )
