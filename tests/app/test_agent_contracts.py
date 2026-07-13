from __future__ import annotations

import pytest

from routedeck_core.app import ApplicationSpec, FeatureSpec, compile_app
from routedeck_core.contracts.agent import AgentPolicyRef, AgentPolicySpec
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
from routedeck_core.validation import RouteDeckValidationError


def _app(
    *,
    feature_policy_refs: tuple[AgentPolicyRef, ...] = (),
    node_policy_refs: tuple[AgentPolicyRef, ...] = (),
    operation_policy_refs: tuple[AgentPolicyRef, ...] = (),
    capability_policy_refs: tuple[AgentPolicyRef, ...] = (),
    surface_policy_refs: tuple[AgentPolicyRef, ...] = (),
    suggested_operation_id: str = "test.open",
) -> ApplicationSpec:
    policy = AgentPolicySpec(
        id="test.agent_policy",
        instruction="Explain the current test workflow succinctly.",
    )
    operation = OperationSpec(
        id="test.open",
        title="Open test workflow",
        description="Open the test-only workflow.",
        safety_class=SafetyClass.NAVIGATION,
        outcomes=("opened",),
        policy_refs=operation_policy_refs,
    )
    surface = SurfaceSpec(
        id="test.surface",
        component="test.surface",
        policy_refs=surface_policy_refs,
    )
    capability = CapabilitySpec(
        id="test.capability",
        title="Test capability",
        operations=(operation.ref,),
        surfaces=(surface.ref,),
        policy_refs=capability_policy_refs,
    )
    node = NodeSpec(
        id="test.home",
        title="Test home",
        kind=NodeKind.SECTION,
        route=RouteSpec(template="/", deep_link_policy=DeepLinkPolicy.SHAREABLE),
        operations=(operation,),
        capabilities=(capability,),
        surfaces=SurfaceSlotsSpec(active=None, frame=(surface,)),
        policy_refs=node_policy_refs,
        suggested_actions=(
            SuggestedActionSpec(
                id="test.open_action",
                operation_id=suggested_operation_id,
            ),
        ),
    )
    return ApplicationSpec(
        name="agent-contract-test",
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
                agent_policies=(policy,),
                policy_refs=feature_policy_refs,
            ),
        ),
    )


def test_compiler_builds_a_private_policy_catalog_and_allows_no_active_surface() -> None:
    policy_ref = AgentPolicyRef(id="test.agent_policy")

    app = compile_app(
        _app(
            feature_policy_refs=(policy_ref,),
            node_policy_refs=(policy_ref,),
            operation_policy_refs=(policy_ref,),
            capability_policy_refs=(policy_ref,),
            surface_policy_refs=(policy_ref,),
        )
    )

    assert tuple(app.agent_policies) == ("test.agent_policy",)
    assert app.frontend_contract.nodes["test.home"].surfaces.active is None
    frontend = app.frontend_contract.model_dump(mode="json")
    assert "agent_policies" not in frontend
    assert "policy_refs" not in frontend["surfaces"]["test.surface"]


@pytest.mark.parametrize(
    "scope",
    ("feature", "node", "operation", "capability", "surface"),
)
def test_compiler_rejects_missing_policy_references_at_every_scope(scope: str) -> None:
    missing = (AgentPolicyRef(id="test.missing_policy"),)
    arguments = {
        "feature_policy_refs": missing if scope == "feature" else (),
        "node_policy_refs": missing if scope == "node" else (),
        "operation_policy_refs": missing if scope == "operation" else (),
        "capability_policy_refs": missing if scope == "capability" else (),
        "surface_policy_refs": missing if scope == "surface" else (),
    }

    with pytest.raises(RouteDeckValidationError, match="missing agent policy"):
        compile_app(_app(**arguments))


def test_compiler_rejects_a_suggested_action_outside_the_node_operation_scope() -> None:
    with pytest.raises(RouteDeckValidationError, match="suggested action"):
        compile_app(_app(suggested_operation_id="test.missing_operation"))
