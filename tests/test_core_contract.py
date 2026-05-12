from routedeck_core import (
    RouteDeckActionSpec,
    RouteDeckEdgeSpec,
    RouteDeckManifest,
    RouteDeckNodeSpec,
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
