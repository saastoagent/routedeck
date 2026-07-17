from __future__ import annotations

from dataclasses import dataclass

from ..app.compiled import CompiledApplication
from ..contracts.application import Node
from ..contracts.failures import FailureKind
from ..contracts.operations import Operation
from ..contracts.projection import PublicEntityHandle
from ..contracts.session import RouteDeckSession
from ..contracts.suggestions import SuggestedAction
from ..contracts.surfaces import Surface
from ..validation import RouteDeckValidationError


@dataclass(frozen=True)
class ProjectionMode:
    """Canonical operation and surface policy for one session projection."""

    legal_operations: tuple[Operation, ...]
    active_surface: Surface | None


def resolve_projection_mode(
    app: CompiledApplication,
    node: Node,
    session: RouteDeckSession,
) -> ProjectionMode:
    failure = session.public_state.failure
    disabled_operation_ids = set(session.public_state.disabled_operation_ids)
    if failure is None or failure.kind is not FailureKind.EXTERNAL_OUTCOME_UNKNOWN:
        return ProjectionMode(
            legal_operations=tuple(
                operation
                for operation in node.operations
                if operation.id not in disabled_operation_ids
            ),
            active_surface=node.surfaces.active,
        )

    if failure.operation_id is None:
        raise RouteDeckValidationError(
            "External-outcome recovery requires a failure operation ID"
        )
    operation = _node_operation(node, failure.operation_id)
    if operation is None:
        raise RouteDeckValidationError(
            "External-outcome recovery operation is not declared at the current node"
        )
    if app.operations.get(operation.id) != operation:
        raise RouteDeckValidationError(
            "External-outcome recovery operation is not canonical"
        )

    recovery_directive = operation.unknown_recovery_directive
    if recovery_directive is None:
        raise RouteDeckValidationError(
            "External-outcome operation has no declared recovery directive"
        )
    if failure.recovery_directive != recovery_directive:
        raise RouteDeckValidationError(
            "External-outcome failure recovery directive does not match the "
            "operation declaration"
        )
    if recovery_directive not in node.recovery.directives:
        raise RouteDeckValidationError(
            "External-outcome recovery directive is not declared at the current node"
        )

    failure_surface_ref = node.recovery.failure_surface
    if failure_surface_ref is None:
        raise RouteDeckValidationError(
            "External-outcome recovery requires a node failure surface"
        )
    failure_surface = next(
        (
            surface
            for surface in node.surfaces.declared_surfaces()
            if surface.id == failure_surface_ref.id
        ),
        None,
    )
    if failure_surface is None:
        raise RouteDeckValidationError(
            "External-outcome failure surface is not declared at the current node"
        )

    recovery_operations: list[Operation] = []
    for operation_ref in operation.unknown_recovery_operation_refs:
        recovery_operation = _node_operation(node, operation_ref.id)
        if recovery_operation is None:
            raise RouteDeckValidationError(
                "External-outcome recovery operation is not declared at the current node"
            )
        if app.operations.get(recovery_operation.id) != recovery_operation:
            raise RouteDeckValidationError(
                "External-outcome recovery operation is not canonical"
            )
        if (
            recovery_operation.id not in disabled_operation_ids
            and _entity_inputs_are_available(session, recovery_operation)
        ):
            recovery_operations.append(recovery_operation)

    return ProjectionMode(
        legal_operations=tuple(recovery_operations),
        active_surface=failure_surface,
    )


def visible_entity_handles(
    session: RouteDeckSession,
    legal_operation_ids: set[str] | frozenset[str],
    declared_entity_kinds: set[str] | frozenset[str],
) -> tuple[PublicEntityHandle, ...]:
    """Expose only handles backed by an operation-authorized private binding."""

    allowed_bindings = {
        (binding.public_handle, binding.entity_kind)
        for binding in session.private_state.entity_bindings
        if legal_operation_ids.intersection(binding.allowed_operation_ids)
        and binding.entity_kind in declared_entity_kinds
    }
    return tuple(
        entity
        for entity in session.public_state.entity_handles
        if (entity.handle, entity.entity_kind) in allowed_bindings
    )


def visible_suggested_actions(
    node: Node,
    session: RouteDeckSession,
    legal_operation_ids: set[str] | frozenset[str],
) -> tuple[SuggestedAction, ...]:
    """Resolve actions whose operations and declared state requirements are present."""

    bound_entities = {
        (binding.entity_kind, binding.public_handle)
        for binding in session.private_state.entity_bindings
    }
    present_entity_kinds = {
        entity.entity_kind
        for entity in session.public_state.entity_handles
        if (entity.entity_kind, entity.handle) in bound_entities
    }
    return tuple(
        action
        for action in node.suggested_actions
        if action.operation_id in legal_operation_ids
        and set(action.visibility.required_entity_kinds) <= present_entity_kinds
    )


def _node_operation(node: Node, operation_id: str) -> Operation | None:
    return next(
        (operation for operation in node.operations if operation.id == operation_id),
        None,
    )


def _entity_inputs_are_available(
    session: RouteDeckSession,
    operation: Operation,
) -> bool:
    public_entities = {
        (entity.entity_kind, entity.handle)
        for entity in session.public_state.entity_handles
    }
    authorized_entity_kinds = {
        binding.entity_kind
        for binding in session.private_state.entity_bindings
        if operation.id in binding.allowed_operation_ids
        and (binding.entity_kind, binding.public_handle) in public_entities
    }
    return all(
        entity_input.entity_kind in authorized_entity_kinds
        for entity_input in operation.entity_inputs
    )


__all__ = [
    "ProjectionMode",
    "resolve_projection_mode",
    "visible_entity_handles",
    "visible_suggested_actions",
]
