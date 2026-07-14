from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from typing import TypeVar

from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from jsonschema.validators import validator_for

from ..contracts.agent import AgentPolicyRef, AgentPolicySpec
from ..contracts.application import (
    CapabilitySpec,
    CompiledApplicationSpec,
    NodeSpec,
)
from ..contracts.navigation import DeepLinkPolicy, TransitionSpec
from ..contracts.operations import (
    GuardSpec,
    OperationSpec,
    ProviderSpec,
    ReviewPolicy,
    SafetyClass,
)
from ..contracts.surfaces import SurfaceSlotsSpec, SurfaceSpec
from ..navigation.routes import CompiledRoutes
from ..validation import RouteDeckValidationError
from .compiled import (
    CompiledRouteDeckApp,
    ExecutableTestPath,
    FrontendContract,
    FrontendNodeContract,
    FrontendSurfaceContract,
    FrontendSurfaceSlots,
    FrontendTransitionContract,
)
from .feature import ApplicationSpec


ContractT = TypeVar("ContractT")


def compile_app(source_spec: ApplicationSpec) -> CompiledRouteDeckApp:
    if not isinstance(source_spec, ApplicationSpec):
        raise RouteDeckValidationError("compile_app requires an ApplicationSpec")
    if not source_spec.features:
        raise RouteDeckValidationError("Application must declare at least one feature")

    _validate_feature_namespaces(source_spec)
    nodes = tuple(node for feature in source_spec.features for node in feature.nodes)
    declared_transitions = (
        tuple(
            transition
            for feature in source_spec.features
            for transition in feature.transitions
        )
        + source_spec.transitions
    )

    node_by_id: dict[str, NodeSpec] = {}
    operations: dict[str, OperationSpec] = {}
    providers: dict[str, ProviderSpec] = {}
    guards: dict[str, GuardSpec] = {}
    capabilities: dict[str, CapabilitySpec] = {}
    agent_policies: dict[str, AgentPolicySpec] = {}
    surfaces: dict[str, SurfaceSpec] = {}

    for feature in source_spec.features:
        for policy in feature.agent_policies:
            _register_canonical("agent policy", agent_policies, policy.id, policy)

    for node in nodes:
        if node.id in node_by_id:
            raise RouteDeckValidationError(f"Duplicate node id: {node.id}")
        node_by_id[node.id] = node
        for operation in node.operations:
            _register_canonical("operation", operations, operation.id, operation)
        for context_provider in node.context_providers:
            _register_canonical(
                "provider",
                providers,
                context_provider.id,
                context_provider,
            )
        for entity_provider in node.entity_providers:
            _register_canonical(
                "provider",
                providers,
                entity_provider.id,
                entity_provider,
            )
        for guard in node.guards:
            _register_canonical("guard", guards, guard.id, guard)
        for capability in node.capabilities:
            _register_canonical("capability", capabilities, capability.id, capability)
        for surface in _all_surfaces(node.surfaces):
            _register_canonical("surface", surfaces, surface.id, surface)

    if source_spec.entry_node.id not in node_by_id:
        raise RouteDeckValidationError(
            f"Entry node is not declared: {source_spec.entry_node.id}"
        )

    routes = CompiledRoutes.from_nodes(nodes)
    _validate_feature_transition_ownership(source_spec)
    _validate_node_references(nodes, node_by_id, surfaces)
    _validate_operation_references(nodes, operations, providers, guards)
    _validate_agent_policy_references(source_spec, nodes, agent_policies)
    _validate_suggested_actions(nodes)
    transitions = _compile_route_entry_transitions(
        nodes=nodes,
        declared_transitions=declared_transitions,
        routes=routes,
    )
    _validate_capability_references(capabilities.values(), operations, surfaces)
    _validate_surface_affordances(surfaces.values(), operations)
    _validate_transitions(transitions, node_by_id, operations)
    _validate_hierarchy(nodes, node_by_id)
    _validate_reachability(
        entry_node_id=source_spec.entry_node.id,
        nodes=nodes,
        transitions=transitions,
    )

    compiled_spec = CompiledApplicationSpec(
        name=source_spec.name,
        entry_node=source_spec.entry_node,
        nodes=nodes,
        transitions=transitions,
    )
    frontend_contract = _build_frontend_contract(
        source_spec=source_spec,
        nodes=nodes,
        transitions=transitions,
        surfaces={
            surface_id: FrontendSurfaceContract(
                id=surface.id,
                component=surface.component,
                lifecycle=surface.lifecycle,
                affordances=surface.affordances,
                public_props_schema=surface.public_props_schema,
            )
            for surface_id, surface in surfaces.items()
        },
    )
    executable_paths = _derive_executable_test_paths(
        nodes=nodes,
        transitions=transitions,
    )
    _validate_executable_test_paths(
        nodes=nodes,
        transitions=transitions,
        paths=executable_paths,
    )
    return CompiledRouteDeckApp(
        source_spec=source_spec,
        spec=compiled_spec,
        operations=operations,
        providers=providers,
        guards=guards,
        agent_policies=agent_policies,
        surfaces=surfaces,
        routes=routes,
        frontend_contract=frontend_contract,
        executable_test_paths=executable_paths,
    )


def _validate_feature_namespaces(source_spec: ApplicationSpec) -> None:
    namespaces = [feature.namespace for feature in source_spec.features]
    if len(namespaces) != len(set(namespaces)):
        raise RouteDeckValidationError("Feature namespaces must be unique")


def _register_canonical(
    kind: str,
    catalog: dict[str, ContractT],
    identifier: str,
    value: ContractT,
) -> None:
    existing = catalog.get(identifier)
    if existing is None:
        catalog[identifier] = value
        return
    if existing is not value:
        raise RouteDeckValidationError(
            f"Distinct {kind} definitions reuse id {identifier!r}"
        )


def _all_surfaces(slots: SurfaceSlotsSpec) -> tuple[SurfaceSpec, ...]:
    return slots.declared_surfaces()


def _validate_agent_policy_references(
    source_spec: ApplicationSpec,
    nodes: tuple[NodeSpec, ...],
    policies: dict[str, AgentPolicySpec],
) -> None:
    for feature in source_spec.features:
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
    policies: dict[str, AgentPolicySpec],
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


def _validate_suggested_actions(nodes: tuple[NodeSpec, ...]) -> None:
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


def _validate_feature_transition_ownership(source_spec: ApplicationSpec) -> None:
    for feature in source_spec.features:
        feature_node_ids = {node.id for node in feature.nodes}
        for transition in feature.transitions:
            if (
                transition.source.id not in feature_node_ids
                or transition.target.id not in feature_node_ids
            ):
                raise RouteDeckValidationError(
                    "Feature specs may declare transitions only between their own nodes"
                )


def _validate_node_references(
    nodes: tuple[NodeSpec, ...],
    node_by_id: dict[str, NodeSpec],
    surfaces: dict[str, SurfaceSpec],
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
    nodes: tuple[NodeSpec, ...],
    operations: dict[str, OperationSpec],
    providers: dict[str, ProviderSpec],
    guards: dict[str, GuardSpec],
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
    node: NodeSpec,
    operation: OperationSpec,
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


def _compile_route_entry_transitions(
    *,
    nodes: tuple[NodeSpec, ...],
    declared_transitions: tuple[TransitionSpec, ...],
    routes: CompiledRoutes,
) -> tuple[TransitionSpec, ...]:
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
                TransitionSpec(
                    source=node.ref,
                    operation=operation.ref,
                    outcome=entry.outcome,
                    target=node.ref,
                )
            )
    return tuple(transitions)


def _validate_capability_references(
    capabilities: Iterable[CapabilitySpec],
    operations: dict[str, OperationSpec],
    surfaces: dict[str, SurfaceSpec],
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
    surfaces: Iterable[SurfaceSpec],
    operations: dict[str, OperationSpec],
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
    transitions: tuple[TransitionSpec, ...],
    node_by_id: dict[str, NodeSpec],
    operations: dict[str, OperationSpec],
) -> None:
    branch_targets: dict[tuple[str, str, str], str] = {}
    for transition in transitions:
        if transition.source.id not in node_by_id:
            raise RouteDeckValidationError(
                f"Transition has missing source {transition.source.id!r}"
            )
        if transition.target.id not in node_by_id:
            raise RouteDeckValidationError(
                f"Transition has missing target {transition.target.id!r}"
            )
        operation = operations.get(transition.operation.id)
        if operation is None:
            raise RouteDeckValidationError(
                f"Transition references missing operation {transition.operation.id!r}"
            )
        source_operation_ids = {
            candidate.id for candidate in node_by_id[transition.source.id].operations
        }
        if operation.id not in source_operation_ids:
            raise RouteDeckValidationError(
                f"Transition operation {operation.id!r} is not executable at "
                f"{transition.source.id!r}"
            )
        if transition.outcome not in operation.outcomes:
            raise RouteDeckValidationError(
                f"Transition references undeclared outcome {transition.outcome!r} "
                f"for {operation.id!r}"
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
                    f"Duplicate transition branch: {branch!r} -> {previous_target!r}"
                )
            raise RouteDeckValidationError(
                f"Ambiguous transition branch {branch!r} targets both "
                f"{previous_target!r} and {transition.target.id!r}"
            )
        branch_targets[branch] = transition.target.id

    for node in node_by_id.values():
        for operation in node.operations:
            for outcome in operation.outcomes:
                branch = (node.id, operation.id, outcome)
                if branch not in branch_targets:
                    raise RouteDeckValidationError(
                        "Every declared operation outcome must have exactly one "
                        f"compiled transition; missing {branch!r}"
                    )


def _validate_hierarchy(
    nodes: tuple[NodeSpec, ...],
    node_by_id: dict[str, NodeSpec],
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
    nodes: tuple[NodeSpec, ...],
    transitions: tuple[TransitionSpec, ...],
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


def _build_frontend_contract(
    *,
    source_spec: ApplicationSpec,
    nodes: tuple[NodeSpec, ...],
    transitions: tuple[TransitionSpec, ...],
    surfaces: dict[str, SurfaceSpec],
) -> FrontendContract:
    return FrontendContract(
        name=source_spec.name,
        entry_node_id=source_spec.entry_node.id,
        nodes={
            node.id: FrontendNodeContract(
                id=node.id,
                title=node.title,
                route_template=node.route.template,
                deep_link_policy=node.route.deep_link_policy,
                surfaces=_frontend_surface_slots(node.surfaces),
                operation_ids=tuple(operation.id for operation in node.operations),
            )
            for node in nodes
        },
        transitions=tuple(
            FrontendTransitionContract(
                source=transition.source.id,
                operation_id=transition.operation.id,
                outcome=transition.outcome,
                target=transition.target.id,
            )
            for transition in transitions
        ),
        surfaces=surfaces,
    )


def _frontend_surface_slots(slots: SurfaceSlotsSpec) -> FrontendSurfaceSlots:
    return FrontendSurfaceSlots(
        active=slots.active.id if slots.active is not None else None,
        frame=tuple(surface.id for surface in slots.frame),
        peer=tuple(surface.id for surface in slots.peer),
        detail=tuple(surface.id for surface in slots.detail),
        form=tuple(surface.id for surface in slots.form),
        review=tuple(surface.id for surface in slots.review),
        status=tuple(surface.id for surface in slots.status),
        error=tuple(surface.id for surface in slots.error),
        diagnostic=tuple(surface.id for surface in slots.diagnostic),
    )


def _derive_executable_test_paths(
    *,
    nodes: tuple[NodeSpec, ...],
    transitions: tuple[TransitionSpec, ...],
) -> tuple[ExecutableTestPath, ...]:
    paths: list[ExecutableTestPath] = []
    for transition in transitions:
        paths.append(
            ExecutableTestPath(
                node_id=transition.source.id,
                source_node_id=transition.source.id,
                target_node_id=transition.target.id,
                operation_id=transition.operation.id,
                outcome=transition.outcome,
                branch="transition",
            )
        )
    for node in nodes:
        paths.append(
            ExecutableTestPath(
                node_id=node.id,
                deep_link_policy=node.route.deep_link_policy,
                branch="deep_link",
            )
        )
        for operation in node.operations:
            paths.append(
                ExecutableTestPath(
                    node_id=node.id,
                    operation_id=operation.id,
                    safety_class=operation.safety_class,
                    branch="safety",
                )
            )
            if operation.review_policy is ReviewPolicy.REQUIRED:
                paths.extend(
                    (
                        ExecutableTestPath(
                            node_id=node.id,
                            operation_id=operation.id,
                            branch="review_approved",
                        ),
                        ExecutableTestPath(
                            node_id=node.id,
                            operation_id=operation.id,
                            branch="review_rejected",
                        ),
                    )
                )
        for directive in node.recovery.directives:
            paths.append(
                ExecutableTestPath(
                    node_id=node.id,
                    branch="recovery",
                    recovery_directive=directive,
                )
            )
    return tuple(paths)


def _validate_executable_test_paths(
    *,
    nodes: tuple[NodeSpec, ...],
    transitions: tuple[TransitionSpec, ...],
    paths: tuple[ExecutableTestPath, ...],
) -> None:
    covered_transitions = {
        (
            path.source_node_id,
            path.operation_id,
            path.outcome,
            path.target_node_id,
        )
        for path in paths
        if path.branch == "transition"
    }
    required_transitions = {
        (
            transition.source.id,
            transition.operation.id,
            transition.outcome,
            transition.target.id,
        )
        for transition in transitions
    }
    covered_deep_links = {
        (path.node_id, path.deep_link_policy)
        for path in paths
        if path.branch == "deep_link"
    }
    required_deep_links = {(node.id, node.route.deep_link_policy) for node in nodes}
    covered_safety = {
        (path.node_id, path.operation_id, path.safety_class)
        for path in paths
        if path.branch == "safety"
    }
    required_safety = {
        (node.id, operation.id, operation.safety_class)
        for node in nodes
        for operation in node.operations
    }
    covered_review = {
        (path.node_id, path.operation_id, path.branch)
        for path in paths
        if path.branch in {"review_approved", "review_rejected"}
    }
    required_review = {
        (node.id, operation.id, branch)
        for node in nodes
        for operation in node.operations
        if operation.review_policy is ReviewPolicy.REQUIRED
        for branch in ("review_approved", "review_rejected")
    }
    covered_recovery = {
        (path.node_id, path.recovery_directive)
        for path in paths
        if path.branch == "recovery"
    }
    required_recovery = {
        (node.id, directive) for node in nodes for directive in node.recovery.directives
    }
    if not (
        covered_transitions >= required_transitions
        and covered_deep_links >= required_deep_links
        and covered_safety >= required_safety
        and covered_review >= required_review
        and covered_recovery >= required_recovery
    ):
        raise RouteDeckValidationError(
            "Executable test paths do not cover every declared branch"
        )


__all__ = ["compile_app"]
