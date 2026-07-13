from __future__ import annotations

from routedeck_core.app import ApplicationSpec, FeatureSpec, compile_app
from routedeck_core.context.agent import AgentContextLens
from routedeck_core.context.framework_policies import RouteDeckAgentPolicyType
from routedeck_core.contracts.agent import AgentPolicySpec
from routedeck_core.contracts.application import CapabilitySpec, NodeSpec
from routedeck_core.contracts.navigation import (
    DeepLinkPolicy,
    NodeKind,
    RouteSpec,
    TransitionSpec,
)
from routedeck_core.contracts.operations import OperationSpec, SafetyClass
from routedeck_core.contracts.suggestions import SuggestedActionSpec
from routedeck_core.contracts.surfaces import SurfaceSlotsSpec, SurfaceSpec
from routedeck_testing.factories import session_factory


def _compiled_app(*, active_surface: bool):
    policies = tuple(
        AgentPolicySpec(id=f"test.{name}", instruction=f"{name} instruction")
        for name in ("feature", "shared", "node", "capability", "surface", "operation")
    )
    by_id = {policy.id: policy for policy in policies}
    operation = OperationSpec(
        id="test.open",
        title="Open tests",
        description="Open the current test collection.",
        safety_class=SafetyClass.NAVIGATION,
        outcomes=("opened",),
        policy_refs=(by_id["test.operation"].ref, by_id["test.shared"].ref),
    )
    surface = SurfaceSpec(
        id="test.surface",
        component="test.surface",
        policy_refs=(by_id["test.surface"].ref, by_id["test.shared"].ref),
    )
    capability = CapabilitySpec(
        id="test.capability",
        title="Test capability",
        operations=(operation.ref,),
        surfaces=(surface.ref,),
        policy_refs=(by_id["test.capability"].ref, by_id["test.shared"].ref),
    )
    node = NodeSpec(
        id="test.home",
        title="Test home",
        kind=NodeKind.SECTION,
        route=RouteSpec(template="/", deep_link_policy=DeepLinkPolicy.SHAREABLE),
        operations=(operation,),
        capabilities=(capability,),
        surfaces=SurfaceSlotsSpec(
            active=surface if active_surface else None,
            frame=() if active_surface else (surface,),
        ),
        policy_refs=(by_id["test.node"].ref, by_id["test.shared"].ref),
        suggested_actions=(
            SuggestedActionSpec(id="test.open_action", operation_id=operation.id),
        ),
    )
    return compile_app(
        ApplicationSpec(
            name="agent-context-test",
            entry_node=node.ref,
            features=(
                FeatureSpec(
                    namespace="test",
                    nodes=(node,),
                    transitions=(
                        TransitionSpec(
                            source=node.ref,
                            operation=operation.ref,
                            outcome="opened",
                            target=node.ref,
                        ),
                    ),
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
