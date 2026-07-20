from __future__ import annotations

from ..contracts.agent import AgentPolicy
from ..contracts.application import Capability, CompiledGraph, Node
from ..contracts.navigation import CompiledTransition
from ..contracts.operations import Guard, Operation, Provider
from ..contracts.surfaces import Surface
from ..navigation.routes import CompiledRoutes
from ..validation import RouteDeckValidationError
from .compiled import CompiledApplication, FrontendSurfaceContract
from .compiler_registry import (
    _all_surfaces,
    _register_canonical,
    _validate_feature_namespaces,
)
from .compiler_validation import (
    _validate_agent_policy_references,
    _validate_capability_references,
    _validate_hierarchy,
    _validate_node_references,
    _validate_operation_references,
    _validate_reachability,
    _validate_suggested_actions,
    _validate_surface_affordances,
    _validate_transitions,
)
from .executable_paths import (
    _derive_executable_test_paths,
    _validate_executable_test_paths,
)
from .feature import Application
from .frontend_contract import _build_frontend_contract
from .route_entries import _compile_route_entry_transitions


def compile_app(application: Application) -> CompiledApplication:
    if not isinstance(application, Application):
        raise RouteDeckValidationError("compile_app requires an Application")
    if not application.features:
        raise RouteDeckValidationError("Application must declare at least one feature")

    _validate_feature_namespaces(application)
    nodes = tuple(node for feature in application.features for node in feature.nodes)
    declared_transitions = tuple(
        CompiledTransition(
            source=node.ref,
            operation=transition.operation,
            outcome=transition.outcome,
            target=transition.target,
        )
        for feature in application.features
        for node in feature.nodes
        for transition in node.outgoing
    )
    feature_by_node_id = {
        node.id: feature.namespace
        for feature in application.features
        for node in feature.nodes
    }

    node_by_id: dict[str, Node] = {}
    operations: dict[str, Operation] = {}
    providers: dict[str, Provider] = {}
    guards: dict[str, Guard] = {}
    capabilities: dict[str, Capability] = {}
    agent_policies: dict[str, AgentPolicy] = {}
    surfaces: dict[str, Surface] = {}

    for feature in application.features:
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

    if application.entry_node.id not in node_by_id:
        raise RouteDeckValidationError(
            f"Entry node is not declared: {application.entry_node.id}"
        )

    routes = CompiledRoutes.from_nodes(nodes)
    _validate_node_references(nodes, node_by_id, surfaces)
    _validate_operation_references(nodes, operations, providers, guards)
    _validate_agent_policy_references(application, nodes, agent_policies)
    _validate_suggested_actions(nodes)
    transitions = _compile_route_entry_transitions(
        nodes=nodes,
        declared_transitions=declared_transitions,
        routes=routes,
    )
    _validate_capability_references(capabilities.values(), operations, surfaces)
    _validate_surface_affordances(surfaces.values(), operations)
    _validate_transitions(
        transitions,
        node_by_id,
        operations,
        feature_by_node_id,
    )
    _validate_hierarchy(nodes, node_by_id)
    _validate_reachability(
        entry_node_id=application.entry_node.id,
        nodes=nodes,
        transitions=transitions,
    )

    incoming_lists: dict[str, list[CompiledTransition]] = {
        node.id: [] for node in nodes
    }
    for transition in transitions:
        incoming_lists[transition.target.id].append(transition)
    incoming = {
        node_id: tuple(edges)
        for node_id, edges in incoming_lists.items()
    }

    compiled_graph = CompiledGraph(
        name=application.name,
        entry_node=application.entry_node,
        nodes=nodes,
        transitions=transitions,
        incoming=incoming,
    )
    frontend_contract = _build_frontend_contract(
        application=application,
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
    return CompiledApplication(
        application=application,
        graph=compiled_graph,
        nodes=node_by_id,
        operations=operations,
        providers=providers,
        guards=guards,
        agent_policies=agent_policies,
        surfaces=surfaces,
        routes=routes,
        frontend_contract=frontend_contract,
        executable_test_paths=executable_paths,
    )


__all__ = ["compile_app"]
