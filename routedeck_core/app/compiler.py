from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from typing import TypeVar

from ..contracts.application import (
    CapabilitySpec,
    CompiledApplicationSpec,
    NodeSpec,
)
from ..contracts.navigation import TransitionSpec
from ..contracts.operations import (
    GuardSpec,
    OperationSpec,
    ProviderSpec,
    ReviewPolicy,
)
from ..contracts.surfaces import SurfaceSlotsSpec, SurfaceSpec
from ..navigation.routes import CompiledRoutes
from ..validation import RouteDeckValidationError
from .compiled import (
    CompiledRouteDeckApp,
    ExecutableTestPath,
    FrontendContract,
    FrontendNodeContract,
    FrontendSurfaceSlots,
)
from .feature import ApplicationSpec


ContractT = TypeVar("ContractT")


def compile_app(source_spec: ApplicationSpec) -> CompiledRouteDeckApp:
    if not isinstance(source_spec, ApplicationSpec):
        raise RouteDeckValidationError("compile_app requires an ApplicationSpec")
    if not source_spec.features:
        raise RouteDeckValidationError("Application must declare at least one feature")

    _validate_feature_namespaces(source_spec)
    nodes = tuple(
        node for feature in source_spec.features for node in feature.nodes
    )
    transitions = tuple(
        transition
        for feature in source_spec.features
        for transition in feature.transitions
    ) + source_spec.transitions

    node_by_id: dict[str, NodeSpec] = {}
    operations: dict[str, OperationSpec] = {}
    providers: dict[str, ProviderSpec] = {}
    guards: dict[str, GuardSpec] = {}
    capabilities: dict[str, CapabilitySpec] = {}
    surfaces: dict[str, SurfaceSpec] = {}

    for node in nodes:
        if node.id in node_by_id:
            raise RouteDeckValidationError(f"Duplicate node id: {node.id}")
        node_by_id[node.id] = node
        for operation in node.operations:
            _register_canonical("operation", operations, operation.id, operation)
        for provider in (*node.context_providers, *node.entity_providers):
            _register_canonical("provider", providers, provider.id, provider)
        for guard in node.guards:
            _register_canonical("guard", guards, guard.id, guard)
        for capability in node.capabilities:
            _register_canonical(
                "capability", capabilities, capability.id, capability
            )
        for surface in _all_surfaces(node.surfaces):
            _register_canonical("surface", surfaces, surface.id, surface)

    if source_spec.entry_node.id not in node_by_id:
        raise RouteDeckValidationError(
            f"Entry node is not declared: {source_spec.entry_node.id}"
        )

    _validate_feature_transition_ownership(source_spec)
    _validate_node_references(nodes, node_by_id, surfaces)
    _validate_operation_references(nodes, operations, providers, guards)
    _validate_capability_references(capabilities.values(), operations, surfaces)
    _validate_surface_affordances(surfaces.values(), operations)
    _validate_transitions(transitions, node_by_id, operations)
    _validate_hierarchy(nodes, node_by_id)
    _validate_reachability(
        entry_node_id=source_spec.entry_node.id,
        nodes=nodes,
        transitions=transitions,
    )

    routes = CompiledRoutes.from_nodes(nodes)
    compiled_spec = CompiledApplicationSpec(
        name=source_spec.name,
        entry_node=source_spec.entry_node,
        nodes=nodes,
        transitions=transitions,
    )
    frontend_contract = _build_frontend_contract(
        source_spec=source_spec,
        nodes=nodes,
        surfaces=surfaces,
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
    return (
        slots.active,
        *slots.frame,
        *slots.peer,
        *slots.detail,
        *slots.form,
        *slots.review,
        *slots.status,
        *slots.error,
        *slots.diagnostic,
    )


def _validate_feature_transition_ownership(source_spec: ApplicationSpec) -> None:
    for feature in source_spec.features:
        for transition in feature.transitions:
            if transition.source.feature != transition.target.feature:
                raise RouteDeckValidationError(
                    "Feature specs may declare only feature-internal transitions"
                )
    for transition in source_spec.transitions:
        if transition.source.feature == transition.target.feature:
            raise RouteDeckValidationError(
                "Application composition transitions must be cross-feature"
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
    seen: set[tuple[str, str, str, str]] = set()
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
        key = (
            transition.source.id,
            transition.operation.id,
            transition.outcome,
            transition.target.id,
        )
        if key in seen:
            raise RouteDeckValidationError(f"Duplicate transition: {key!r}")
        seen.add(key)


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
        destinations.setdefault(transition.source.id, []).append(
            transition.target.id
        )
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
        surfaces=surfaces,
    )


def _frontend_surface_slots(slots: SurfaceSlotsSpec) -> FrontendSurfaceSlots:
    return FrontendSurfaceSlots(
        active=slots.active.id,
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
    required_deep_links = {
        (node.id, node.route.deep_link_policy) for node in nodes
    }
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
        (node.id, directive)
        for node in nodes
        for directive in node.recovery.directives
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
