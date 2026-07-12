from __future__ import annotations

import routedeck_core.contracts.application as application_contracts
from routedeck_core.app import ApplicationSpec, FeatureSpec, compile_app
from routedeck_core.contracts.navigation import (
    DeepLinkPolicy,
    NodeKind,
    NodeRef,
    RouteSpec,
    TransitionSpec,
)
from routedeck_core.contracts.operations import OperationRef, OperationSpec, SafetyClass
from routedeck_core.contracts.surfaces import SurfaceSlotsSpec, SurfaceSpec
from routedeck_core.validation import RouteDeckValidationError

import pytest


def test_route_entry_contract_is_typed_and_attached_to_node() -> None:
    assert hasattr(application_contracts, "RouteEntrySpec")
    assert hasattr(application_contracts, "RouteParameterBinding")

    operation = OperationSpec(
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
    entry = application_contracts.RouteEntrySpec(
        operation=operation.ref,
        outcome="loaded",
        bindings=(binding,),
    )
    node = application_contracts.NodeSpec(
        id="inventory.item",
        title="Item",
        kind=NodeKind.DETAIL,
        route=RouteSpec(
            template="/items/{item_handle}",
            deep_link_policy=DeepLinkPolicy.SHAREABLE,
        ),
        entry=entry,
        operations=(operation,),
        surfaces=SurfaceSlotsSpec(
            active=SurfaceSpec(id="inventory.item", component="inventory.item")
        ),
    )

    assert node.entry == entry


def _route_entry_source(
    *,
    entry: application_contracts.RouteEntrySpec | None = None,
    operations: tuple[OperationSpec, ...] | None = None,
    declared_transition: TransitionSpec | None = None,
) -> ApplicationSpec:
    operation = _open_operation()
    route_entry = entry or application_contracts.RouteEntrySpec(
        operation=operation.ref,
        outcome="loaded",
        bindings=(
            application_contracts.RouteParameterBinding(
                parameter="item_handle",
                argument="item_handle",
            ),
        ),
    )
    item = application_contracts.NodeSpec(
        id="inventory.item",
        title="Item",
        kind=NodeKind.DETAIL,
        route=RouteSpec(
            template="/items/{item_handle}",
            deep_link_policy=DeepLinkPolicy.SHAREABLE,
        ),
        entry=route_entry,
        operations=operations if operations is not None else (operation,),
        surfaces=SurfaceSlotsSpec(
            active=SurfaceSpec(id="inventory.item", component="inventory.item")
        ),
    )
    nodes = (item,)
    transitions = (declared_transition,) if declared_transition is not None else ()
    if declared_transition is not None and declared_transition.target.id != item.id:
        nodes = (
            item,
            application_contracts.NodeSpec(
                id=declared_transition.target.id,
                title="Other",
                kind=NodeKind.SECTION,
                route=RouteSpec(
                    template="/other",
                    deep_link_policy=DeepLinkPolicy.SHAREABLE,
                ),
                surfaces=SurfaceSlotsSpec(
                    active=SurfaceSpec(
                        id="inventory.other",
                        component="inventory.other",
                    )
                ),
            ),
        )
    return ApplicationSpec(
        name="route-entry-test",
        entry_node=item.ref,
        features=(
            FeatureSpec(
                namespace="inventory",
                nodes=nodes,
                transitions=transitions,
            ),
        ),
    )


def _open_operation() -> OperationSpec:
    return OperationSpec(
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

    assert len(app.spec.transitions) == 1
    transition = app.spec.transitions[0]
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
    transition = TransitionSpec(
        source=NodeRef(id="inventory.item"),
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

    assert app.spec.transitions == (transition,)


@pytest.mark.parametrize(
    ("entry", "message"),
    (
        (
            application_contracts.RouteEntrySpec(
                operation=_open_operation().ref,
                outcome="loaded",
                bindings=(),
            ),
            "missing route parameter",
        ),
        (
            application_contracts.RouteEntrySpec(
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
            application_contracts.RouteEntrySpec(
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
            application_contracts.RouteEntrySpec(
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
            application_contracts.RouteEntrySpec(
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
            application_contracts.RouteEntrySpec(
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
    entry: application_contracts.RouteEntrySpec,
    message: str,
) -> None:
    with pytest.raises(RouteDeckValidationError, match=message):
        compile_app(_route_entry_source(entry=entry))


def test_compiler_rejects_a_conflicting_declared_route_entry_branch() -> None:
    operation = _open_operation()
    conflicting = TransitionSpec(
        source=NodeRef(id="inventory.item"),
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
