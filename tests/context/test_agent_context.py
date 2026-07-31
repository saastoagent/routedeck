from __future__ import annotations

from routedeck_core.app import Application, Feature, compile_app
from routedeck_core.context.agent import AgentContextLens
from routedeck_core.context.framework_policies import RouteDeckAgentPolicyType
from routedeck_core.contracts.agent import AgentPolicy
from routedeck_core.contracts.application import Capability, Node
from routedeck_core.contracts.navigation import (
    DeepLinkPolicy,
    NodeRef,
    NodeKind,
    Route,
    Transition,
)
from routedeck_core.contracts.operations import Operation, SafetyClass
from routedeck_core.contracts.suggestions import SuggestedAction
from routedeck_core.contracts.surfaces import SurfaceSlots, Surface
from routedeck_testing.factories import session_factory


def _compiled_app(*, active_surface: bool):
    policies = tuple(
        AgentPolicy(id=f"test.{name}", instruction=f"{name} instruction")
        for name in ("feature", "shared", "node", "capability", "surface", "operation")
    )
    by_id = {policy.id: policy for policy in policies}
    operation = Operation(
        id="test.open",
        title="Open tests",
        description="Open the current test collection.",
        safety_class=SafetyClass.NAVIGATION,
        outcomes=("opened",),
        policy_refs=(by_id["test.operation"].ref, by_id["test.shared"].ref),
    )
    surface = Surface(
        id="test.surface",
        component="test.surface",
        policy_refs=(by_id["test.surface"].ref, by_id["test.shared"].ref),
    )
    capability = Capability(
        id="test.capability",
        title="Test capability",
        operations=(operation.ref,),
        surfaces=(surface.ref,),
        policy_refs=(by_id["test.capability"].ref, by_id["test.shared"].ref),
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
                outcome="opened",
                target=NodeRef(id="test.home"),
            ),
        ),
        capabilities=(capability,),
        surfaces=SurfaceSlots(
            active=surface if active_surface else None,
            frame=() if active_surface else (surface,),
        ),
        policy_refs=(by_id["test.node"].ref, by_id["test.shared"].ref),
        suggested_actions=(
            SuggestedAction(id="test.open_action", operation_id=operation.id),
        ),
    )
    return compile_app(
        Application(
            name="agent-context-test",
            entry_node=node.ref,
            features=(
                Feature(
                    namespace="test",
                    nodes=(node,),
                    agent_policies=policies,
                    policy_refs=(
                        by_id["test.feature"].ref,
                        by_id["test.shared"].ref,
                    ),
                ),
            ),
        )
    )


def test_agent_context_lens_resolves_current_scopes_in_stable_deduplicated_order() -> None:
    app = _compiled_app(active_surface=True)

    context = AgentContextLens(app).resolve(
        session_factory(app=app, node_id="test.home")
    )

    assert tuple(policy.id for policy in context.policies) == (
        RouteDeckAgentPolicyType.EXECUTION_AUTHORITY,
        RouteDeckAgentPolicyType.INTENT_AUTHORITY,
        RouteDeckAgentPolicyType.STATE_AUTHORITY,
        "test.feature",
        "test.shared",
        "test.node",
        "test.capability",
        "test.surface",
        "test.operation",
    )
    assert tuple(
        (item.policy.id, item.scope, item.owner_id, item.source_order)
        for item in context.policy_provenance
    ) == (
        (RouteDeckAgentPolicyType.EXECUTION_AUTHORITY, "framework", "routedeck", 0),
        (RouteDeckAgentPolicyType.INTENT_AUTHORITY, "framework", "routedeck", 1),
        (RouteDeckAgentPolicyType.STATE_AUTHORITY, "framework", "routedeck", 2),
        ("test.feature", "feature", "test", 3),
        ("test.shared", "feature", "test", 4),
        ("test.node", "node", "test.home", 5),
        ("test.capability", "capability", "test.capability", 6),
        ("test.surface", "surface", "test.surface", 7),
        ("test.operation", "operation", "test.open", 8),
    )
    assert context.active_surface is not None
    assert context.active_surface.id == "test.surface"
    assert tuple(action.id for action in context.suggested_actions) == (
        "test.open_action",
    )


def test_agent_context_lens_allows_conversation_only_nodes_and_ignores_frame_policy() -> None:
    app = _compiled_app(active_surface=False)

    context = AgentContextLens(app).resolve(
        session_factory(app=app, node_id="test.home")
    )

    assert context.active_surface is None
    assert "test.surface" not in tuple(policy.id for policy in context.policies)
