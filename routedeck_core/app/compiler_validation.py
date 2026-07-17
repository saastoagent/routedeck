from __future__ import annotations

from collections import deque
from collections.abc import Iterable

from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from jsonschema.validators import validator_for

from ..contracts.agent import AgentPolicyRef, AgentPolicy
from ..contracts.application import Capability, Node
from ..contracts.navigation import CompiledTransition, DeepLinkPolicy
from ..contracts.operations import (
    Guard,
    Operation,
    Provider,
    SafetyClass,
)
from ..contracts.surfaces import Surface
from ..validation import RouteDeckValidationError
from .feature import Application


def _validate_agent_policy_references(
    application: Application,
    nodes: tuple[Node, ...],
    policies: dict[str, AgentPolicy],
) -> None:
    for feature in application.features:
        _validate_policy_refs(
            f"Feature {feature.namespace!r}",
            feature.policy_refs,
            policies,
        )
    for node in nodes:
        _validate_policy_refs(f"Node {node.id!r}", node.policy_refs, policies)
        for operation in node.operations:
            _validate_policy_refs(
                f"Operation {operation.id!r}",
                operation.policy_refs,
                policies,
            )
        for capability in node.capabilities:
            _validate_policy_refs(
                f"Capability {capability.id!r}",
                capability.policy_refs,
                policies,
            )
        for surface in node.surfaces.declared_surfaces():
            _validate_policy_refs(
                f"Surface {surface.id!r}",
                surface.policy_refs,
                policies,
            )


def _validate_policy_refs(
    owner: str,
    refs: tuple[AgentPolicyRef, ...],
    policies: dict[str, AgentPolicy],
) -> None:
    identifiers = tuple(ref.id for ref in refs)
    if len(identifiers) != len(set(identifiers)):
        raise RouteDeckValidationError(
            f"{owner} declares the same agent policy more than once"
        )
    missing = tuple(identifier for identifier in identifiers if identifier not in policies)
    if missing:
        raise RouteDeckValidationError(
            f"{owner} references missing agent policy {missing!r}"
        )


def _validate_suggested_actions(nodes: tuple[Node, ...]) -> None:
    for node in nodes:
        action_ids = tuple(action.id for action in node.suggested_actions)
        if len(action_ids) != len(set(action_ids)):
            raise RouteDeckValidationError(
                f"Node {node.id!r} declares a suggested action more than once"
            )
        operations = {operation.id: operation for operation in node.operations}
        entity_kinds = {provider.entity_kind for provider in node.entity_providers}
        for action in node.suggested_actions:
            operation = operations.get(action.operation_id)
            if operation is None:
                raise RouteDeckValidationError(
                    f"Node {node.id!r} suggested action {action.id!r} references "
                    "an operation outside the node scope"
                )
            try:
                validator_for(operation.input_schema_value())(
                    operation.input_schema_value()
                ).validate(action.arguments_value())
            except JsonSchemaValidationError as exc:
                raise RouteDeckValidationError(
                    f"Node {node.id!r} suggested action {action.id!r} has "
                    "arguments outside the operation input contract"
                ) from exc
            missing_entity_kinds = (
                set(action.visibility.required_entity_kinds) - entity_kinds
            )
            if missing_entity_kinds:
                raise RouteDeckValidationError(
                    f"Node {node.id!r} suggested action {action.id!r} requires "
                    f"undeclared entity kinds {tuple(sorted(missing_entity_kinds))!r}"
                )


def _validate_node_references(
    nodes: tuple[Node, ...],
    node_by_id: dict[str, Node],
    surfaces: dict[str, Surface],
) -> None:
    for node in nodes:
        if node.parent is not None and node.parent.id not in node_by_id:
            raise RouteDeckValidationError(
                f"Node {node.id!r} references missing parent {node.parent.id!r}"
            )
        if (
            node.navigation.cancel_target is not None
            and node.navigation.cancel_target.id not in node_by_id
        ):
            raise RouteDeckValidationError(
                f"Node {node.id!r} references missing cancel target"
            )
        if node.navigation.cancel_target is not None:
            target = node_by_id[node.navigation.cancel_target.id]
            target_segments = tuple(
                segment for segment in target.route.template.split("/") if segment
            )
            has_parameters = any(
                segment.startswith("{") and segment.endswith("}")
                for segment in target_segments
            )
            if (
                target.route.deep_link_policy is not DeepLinkPolicy.SHAREABLE
                or has_parameters
            ):
                raise RouteDeckValidationError(
                    f"Node {node.id!r} cancel target must be a parameterless "
                    "shareable route"
                )
        failure_surface = node.recovery.failure_surface
        if failure_surface is not None and failure_surface.id not in surfaces:
            raise RouteDeckValidationError(
                f"Node {node.id!r} references missing recovery surface"
            )
        if any(not directive for directive in node.recovery.directives):
            raise RouteDeckValidationError(
                f"Node {node.id!r} has an unexecutable recovery directive"
            )


def _validate_operation_references(
    nodes: tuple[Node, ...],
    operations: dict[str, Operation],
    providers: dict[str, Provider],
    guards: dict[str, Guard],
) -> None:
    for operation in operations.values():
        if not operation.outcomes or len(operation.outcomes) != len(
            set(operation.outcomes)
        ):
            raise RouteDeckValidationError(
                f"Operation {operation.id!r} must declare unique outcomes"
            )
        for provider_ref in operation.provider_refs:
            if provider_ref.id not in providers:
                raise RouteDeckValidationError(
                    f"Operation {operation.id!r} references missing provider "
                    f"{provider_ref.id!r}"
                )
        for guard_ref in operation.guard_refs:
            if guard_ref.id not in guards:
                raise RouteDeckValidationError(
                    f"Operation {operation.id!r} references missing guard "
                    f"{guard_ref.id!r}"
                )

    for node in nodes:
        operation_ids = [operation.id for operation in node.operations]
        if len(operation_ids) != len(set(operation_ids)):
            raise RouteDeckValidationError(
                f"Node {node.id!r} declares an operation more than once"
            )
        node_provider_ids = {provider.id for provider in node.context_providers}
        node_provider_ids.update(provider.id for provider in node.entity_providers)
        node_guard_ids = {guard.id for guard in node.guards}
        entity_kinds = {provider.entity_kind for provider in node.entity_providers}
        node_surface_ids = {surface.id for surface in node.surfaces.declared_surfaces()}
        for operation in node.operations:
            missing_provider_ids = sorted(
                {
                    provider_ref.id
                    for provider_ref in operation.provider_refs
                    if provider_ref.id not in node_provider_ids
                }
            )
            if missing_provider_ids:
                raise RouteDeckValidationError(
                    f"Node {node.id!r} operation {operation.id!r} requires "
                    "providers outside the node scope "
                    f"{missing_provider_ids!r}"
                )
            missing_guard_ids = sorted(
                {
                    guard_ref.id
                    for guard_ref in operation.guard_refs
                    if guard_ref.id not in node_guard_ids
                }
            )
            if missing_guard_ids:
                raise RouteDeckValidationError(
                    f"Node {node.id!r} operation {operation.id!r} requires "
                    f"guards outside the node scope {missing_guard_ids!r}"
                )
            missing_entity_kinds = sorted(
                {
                    entity_input.entity_kind
                    for entity_input in operation.entity_inputs
                    if entity_input.entity_kind not in entity_kinds
                }
            )
            if missing_entity_kinds:
                raise RouteDeckValidationError(
                    f"Node {node.id!r} operation {operation.id!r} requires "
                    "undeclared entity provider kinds "
                    f"{missing_entity_kinds!r}"
                )
            if operation.safety_class is SafetyClass.WRITE_EXTERNAL:
                _validate_write_recovery_contract(
                    node=node,
                    operation=operation,
                    node_operation_ids=set(operation_ids),
                    node_surface_ids=node_surface_ids,
                )


def _validate_write_recovery_contract(
    *,
    node: Node,
    operation: Operation,
    node_operation_ids: set[str],
    node_surface_ids: set[str],
) -> None:
    directive = operation.unknown_recovery_directive
    if directive is None or directive not in node.recovery.directives:
        raise RouteDeckValidationError(
            f"Node {node.id!r} write operation {operation.id!r} requires "
            f"recovery directive {directive!r}"
        )

    failure_surface = node.recovery.failure_surface
    if failure_surface is None or failure_surface.id not in node_surface_ids:
        raise RouteDeckValidationError(
            f"Node {node.id!r} write operation {operation.id!r} requires a "
            "failure surface declared on that node"
        )

    for recovery_ref in operation.unknown_recovery_operation_refs:
        if recovery_ref.id == operation.id:
            raise RouteDeckValidationError(
                f"Write operation {operation.id!r} cannot use the affected operation "
                "as its own recovery operation"
            )
        if recovery_ref.id not in node_operation_ids:
            raise RouteDeckValidationError(
                f"Node {node.id!r} write operation {operation.id!r} references "
                f"recovery operation {recovery_ref.id!r} outside the node"
            )


def _validate_capability_references(
    capabilities: Iterable[Capability],
    operations: dict[str, Operation],
    surfaces: dict[str, Surface],
) -> None:
    for capability in capabilities:
        for operation_ref in capability.operations:
            if operation_ref.id not in operations:
                raise RouteDeckValidationError(
                    f"Capability {capability.id!r} references missing operation"
                )
        for surface_ref in capability.surfaces:
            if surface_ref.id not in surfaces:
                raise RouteDeckValidationError(
                    f"Capability {capability.id!r} references missing surface"
                )


def _validate_surface_affordances(
    surfaces: Iterable[Surface],
    operations: dict[str, Operation],
) -> None:
    for surface in surfaces:
        affordance_ids = [affordance.id for affordance in surface.affordances]
        if len(affordance_ids) != len(set(affordance_ids)):
            raise RouteDeckValidationError(
                f"Surface {surface.id!r} has duplicate affordances"
            )
        for affordance in surface.affordances:
            if (
                affordance.operation is not None
                and affordance.operation.id not in operations
            ):
                raise RouteDeckValidationError(
                    f"Surface {surface.id!r} references missing operation"
                )


def _validate_transitions(
    transitions: tuple[CompiledTransition, ...],
    node_by_id: dict[str, Node],
    operations: dict[str, Operation],
    feature_by_node_id: dict[str, str],
) -> None:
    branch_targets: dict[tuple[str, str, str], str] = {}
    for transition in transitions:
        context = _transition_context(transition, feature_by_node_id)
        if transition.source.id not in node_by_id:
            raise RouteDeckValidationError(
                f"Transition has a missing source: {context}"
            )
        if transition.target.id not in node_by_id:
            raise RouteDeckValidationError(
                f"Transition has a missing target: {context}"
            )
        operation = operations.get(transition.operation.id)
        if operation is None:
            raise RouteDeckValidationError(
                f"Transition references a missing operation: {context}"
            )
        source_operation_ids = {
            candidate.id for candidate in node_by_id[transition.source.id].operations
        }
        if operation.id not in source_operation_ids:
            raise RouteDeckValidationError(
                f"Transition operation is not executable at its source: {context}"
            )
        if transition.outcome not in operation.outcomes:
            raise RouteDeckValidationError(
                f"Transition references an undeclared outcome: {context}"
            )
        branch = (
            transition.source.id,
            transition.operation.id,
            transition.outcome,
        )
        previous_target = branch_targets.get(branch)
        if previous_target is not None:
            if previous_target == transition.target.id:
                raise RouteDeckValidationError(
                    f"Duplicate transition branch: {context}"
                )
            raise RouteDeckValidationError(
                "Ambiguous transition branch targets both "
                f"{previous_target!r} and {transition.target.id!r}: {context}"
            )
        branch_targets[branch] = transition.target.id

    for node in node_by_id.values():
        for operation in node.operations:
            for outcome in operation.outcomes:
                branch = (node.id, operation.id, outcome)
                if branch not in branch_targets:
                    raise RouteDeckValidationError(
                        "Every declared operation outcome must have exactly one "
                        "compiled transition; "
                        f"feature={feature_by_node_id[node.id]!r}, "
                        f"source={node.id!r}, operation={operation.id!r}, "
                        f"outcome={outcome!r}, target='<missing>'"
                    )


def _transition_context(
    transition: CompiledTransition,
    feature_by_node_id: dict[str, str],
) -> str:
    return (
        f"feature={feature_by_node_id.get(transition.source.id, '<missing>')!r}, "
        f"source={transition.source.id!r}, "
        f"operation={transition.operation.id!r}, "
        f"outcome={transition.outcome!r}, "
        f"target={transition.target.id!r}"
    )


def _validate_hierarchy(
    nodes: tuple[Node, ...],
    node_by_id: dict[str, Node],
) -> None:
    for node in nodes:
        visited: set[str] = set()
        current = node
        while current.parent is not None:
            if current.id in visited:
                raise RouteDeckValidationError("Node hierarchy contains a cycle")
            visited.add(current.id)
            current = node_by_id[current.parent.id]


def _validate_reachability(
    *,
    entry_node_id: str,
    nodes: tuple[Node, ...],
    transitions: tuple[CompiledTransition, ...],
) -> None:
    destinations: dict[str, list[str]] = {}
    for transition in transitions:
        destinations.setdefault(transition.source.id, []).append(transition.target.id)
    reachable = {entry_node_id}
    pending = deque([entry_node_id])
    while pending:
        source = pending.popleft()
        for target in destinations.get(source, []):
            if target not in reachable:
                reachable.add(target)
                pending.append(target)
    missing = [node.id for node in nodes if node.id not in reachable]
    if missing:
        raise RouteDeckValidationError(f"Unreachable nodes: {missing!r}")
