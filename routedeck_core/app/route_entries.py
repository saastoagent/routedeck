from __future__ import annotations

from ..contracts.application import Node
from ..contracts.navigation import CompiledTransition
from ..contracts.operations import OperationSource
from ..navigation.routes import CompiledRoutes
from ..validation import RouteDeckValidationError


def _compile_route_entry_transitions(
    *,
    nodes: tuple[Node, ...],
    declared_transitions: tuple[CompiledTransition, ...],
    routes: CompiledRoutes,
) -> tuple[CompiledTransition, ...]:
    """Validate declarative route entries and materialize exact self branches."""

    transitions = list(declared_transitions)
    for node in nodes:
        entry = node.entry
        if entry is None:
            continue
        operation = next(
            (
                candidate
                for candidate in node.operations
                if candidate.id == entry.operation.id
            ),
            None,
        )
        if operation is None:
            raise RouteDeckValidationError(
                f"Node {node.id!r} route entry operation {entry.operation.id!r} "
                "is not executable at that node"
            )
        if OperationSource.ROUTE not in operation.allowed_sources:
            raise RouteDeckValidationError(
                f"Node {node.id!r} route entry operation {operation.id!r} "
                "does not allow route invocation"
            )
        if entry.outcome not in operation.outcomes:
            raise RouteDeckValidationError(
                f"Node {node.id!r} route entry references undeclared outcome "
                f"{entry.outcome!r} for {operation.id!r}"
            )

        declared_parameters = set(routes.path_parameter_names(node.id))
        binding_parameters = tuple(binding.parameter for binding in entry.bindings)
        if len(binding_parameters) != len(set(binding_parameters)):
            raise RouteDeckValidationError(
                f"Node {node.id!r} route entry binds a route parameter more than once"
            )
        unknown_parameters = sorted(set(binding_parameters) - declared_parameters)
        if unknown_parameters:
            raise RouteDeckValidationError(
                f"Node {node.id!r} route entry binds unknown route parameters "
                f"{unknown_parameters!r}"
            )
        missing_parameters = sorted(declared_parameters - set(binding_parameters))
        if missing_parameters:
            raise RouteDeckValidationError(
                f"Node {node.id!r} route entry is missing route parameters "
                f"{missing_parameters!r}"
            )

        binding_arguments = tuple(binding.argument for binding in entry.bindings)
        if len(binding_arguments) != len(set(binding_arguments)):
            raise RouteDeckValidationError(
                f"Node {node.id!r} route entry binds an operation argument more "
                "than once"
            )
        input_properties = operation.input_schema_value().get("properties", {})
        if not isinstance(input_properties, dict):
            input_properties = {}
        unknown_arguments = sorted(set(binding_arguments) - set(input_properties))
        if unknown_arguments:
            raise RouteDeckValidationError(
                f"Node {node.id!r} route entry binds undeclared operation arguments "
                f"{unknown_arguments!r}"
            )

        branch = (node.id, operation.id, entry.outcome)
        declared_targets = {
            transition.target.id
            for transition in transitions
            if (
                transition.source.id,
                transition.operation.id,
                transition.outcome,
            )
            == branch
        }
        if declared_targets and declared_targets != {node.id}:
            raise RouteDeckValidationError(
                f"Node {node.id!r} has a conflicting route entry transition "
                f"for {branch!r}: {sorted(declared_targets)!r}"
            )
        if not declared_targets:
            transitions.append(
                CompiledTransition(
                    source=node.ref,
                    operation=operation.ref,
                    outcome=entry.outcome,
                    target=node.ref,
                )
            )
    return tuple(transitions)
