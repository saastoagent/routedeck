from routedeck_core import (
    RouteDeckActionSpec,
    RouteDeckCapabilitySpec,
    RouteDeckDispatchInput,
    RouteDeckEdgeSpec,
    RouteDeckManifest,
    RouteDeckNodeSpec,
    RouteDeckSemanticObservation,
    RouteDeckSurface,
    RouteDeckSurfaceInteractionEvent,
    build_projection,
    build_runtime_snapshot,
    reachable_nodes,
    validate_manifest,
)


def test_manifest_validation_accepts_connected_action_graph():
    manifest = RouteDeckManifest(
        version="test",
        nodes=[
            RouteDeckNodeSpec(
                id="intent",
                label="Intent",
                lane="system",
                description="Collect intent.",
                allowed_actions=["intent.confirm"],
            ),
            RouteDeckNodeSpec(id="done", label="Done", lane="terminal", description="Terminal state."),
        ],
        edges=[
            RouteDeckEdgeSpec(
                from_stage="intent",
                to_stage="done",
                type="conditional",
                action_id="intent.confirm",
            )
        ],
        actions=[
            RouteDeckActionSpec(
                id="intent.confirm",
                label="Confirm",
                allowed_nodes=["intent"],
            )
        ],
    )

    assert validate_manifest(manifest) == []
    assert reachable_nodes(manifest, "intent") == ["done"]

    snapshot = build_runtime_snapshot(
        manifest,
        current_node="intent",
        valid_actions=[manifest.actions[0].model_dump(mode="json")],
        blocked_actions=[],
        executed_nodes=["intent"],
    )

    assert snapshot["current_node"] == "intent"
    assert snapshot["reachable_nodes"] == ["done"]
    assert snapshot["valid_actions"][0]["id"] == "intent.confirm"


def test_manifest_validation_reports_missing_targets():
    manifest = RouteDeckManifest(
        version="broken",
        nodes=[RouteDeckNodeSpec(id="intent", label="Intent", lane="system", description="Collect intent.")],
        edges=[RouteDeckEdgeSpec(from_stage="intent", to_stage="missing", type="direct")],
        actions=[],
    )

    assert validate_manifest(manifest)


def test_manifest_validation_reports_unknown_capabilities_and_edge_actions():
    manifest = RouteDeckManifest(
        version="capability-validation",
        capabilities=[RouteDeckCapabilitySpec(capability_id="catalog.browse", label="Browse")],
        nodes=[
            RouteDeckNodeSpec(
                id="browse",
                label="Browse",
                lane="shopping",
                description="Browse.",
                allowed_actions=["catalog.open"],
                capability_id="catalog.detail",
            ),
            RouteDeckNodeSpec(id="detail", label="Detail", lane="shopping", description="Detail."),
        ],
        edges=[
            RouteDeckEdgeSpec(
                from_stage="browse",
                to_stage="detail",
                type="action",
                action_id="catalog.open",
                capability_id="catalog.detail",
            )
        ],
        actions=[
            RouteDeckActionSpec(id="catalog.open", label="Open", capability_id="catalog.detail"),
        ],
    )

    errors = validate_manifest(manifest)
    assert "Action catalog.open references unknown capability: catalog.detail" in errors
    assert "Node browse references unknown capability: catalog.detail" in errors
    assert "Edge browse->detail references unknown capability: catalog.detail" in errors


def test_manifest_validation_accepts_hierarchical_nodes_and_contains_edges():
    manifest = RouteDeckManifest(
        version="hierarchy",
        nodes=[
            RouteDeckNodeSpec(
                id="learning",
                label="Learning",
                lane="learning",
                description="Review learning queues.",
                allowed_actions=["route.open_node"],
                node_kind="section",
                capability_id="learning",
            ),
            RouteDeckNodeSpec(
                id="learning.policy_candidate",
                label="Policy Candidate",
                lane="learning",
                description="Review one policy candidate.",
                allowed_actions=["route.cancel"],
                parent="learning",
                node_kind="detail",
                capability_id="learning",
                cancel_target_node="learning",
                show_in_capability_rail=False,
            ),
        ],
        edges=[
            RouteDeckEdgeSpec(
                from_stage="learning",
                to_stage="learning.policy_candidate",
                type="contains",
            )
        ],
        actions=[
            RouteDeckActionSpec(id="route.open_node", label="Open node", allowed_nodes=["*"]),
            RouteDeckActionSpec(id="route.cancel", label="Cancel", allowed_nodes=["*"]),
        ],
    )

    assert validate_manifest(manifest) == []
    assert reachable_nodes(manifest, "learning") == ["learning.policy_candidate"]


def test_manifest_validation_rejects_unknown_parent_nodes():
    manifest = RouteDeckManifest(
        version="broken-parent",
        nodes=[
            RouteDeckNodeSpec(
                id="learning.policy_candidate",
                label="Policy Candidate",
                lane="learning",
                description="Review one policy candidate.",
                allowed_actions=["route.cancel"],
                parent="missing",
            ),
        ],
        edges=[],
        actions=[RouteDeckActionSpec(id="route.cancel", label="Cancel", allowed_nodes=["*"])],
    )

    assert "Node learning.policy_candidate references unknown parent: missing" in validate_manifest(manifest)


def test_surface_interaction_events_preserve_event_name_and_public_bindings():
    request = RouteDeckDispatchInput(
        surface_event=RouteDeckSurfaceInteractionEvent(
            surface_id="review.detail",
            affordance_id="approve_primary",
            event="click",
            entity_key="draft:alpha",
            payload={"decision": "approve"},
        ),
        projection_version=4,
    )

    payload = request.model_dump(mode="json", by_alias=True)
    assert payload["surface_event"]["event"] == "click"
    assert payload["surface_event"]["entity_key"] == "draft:alpha"
    assert "private_" not in str(payload["surface_event"])


def test_semantic_observations_serialize_type_alias_for_product_agent_context():
    observation = RouteDeckSemanticObservation(
        type="operation.accepted",
        summary="Draft approval was accepted.",
        entity_key="draft:alpha",
        operation_id="draft.approve",
        accepted=True,
    )

    payload = observation.model_dump(mode="json")
    assert payload["type"] == "operation.accepted"
    assert "observation_type" not in payload


def test_projection_includes_peer_surfaces_and_navigation_state():
    manifest = RouteDeckManifest(
        version="projection",
        nodes=[
            RouteDeckNodeSpec(
                id="learning",
                label="Learning",
                lane="learning",
                description="Review learning queues.",
                allowed_actions=["route.switch_surface"],
                allowed_surfaces={"active": ["policy_gaps", "failed_executions"]},
                default_surfaces={"active": "policy_gaps"},
            ),
        ],
        edges=[],
        actions=[RouteDeckActionSpec(id="route.switch_surface", label="Switch surface", allowed_nodes=["*"])],
    )

    projection = build_projection(
        manifest,
        current_node="learning",
        surfaces=[
            RouteDeckSurface(
                name="active",
                surface_id="learning.policy_gaps",
                component="LearningSurface",
                variant="policy_gaps",
                role="active",
                slot="active",
                surface_kind="peer",
                label="Policy gaps",
            )
        ],
        navigation={
            "current": {"node_id": "learning", "surface_id": "learning.policy_gaps"},
            "back_stack": [{"node_id": "agent_home"}],
            "forward_stack": [],
        },
    )

    assert projection.surfaces["active"].surface_id == "learning.policy_gaps"
    assert projection.surfaces["active"].surface_kind == "peer"
    assert projection.navigation.can_back is True
    assert projection.navigation.can_forward is False
    assert projection.navigation.current.node_id == "learning"
