from routedeck_core import (
    RouteDeckManifestBuilder,
    route_deck_action,
    route_deck_edge,
    route_deck_field,
    route_deck_node,
    validate_manifest,
)


def test_manifest_builder_authors_valid_manifest() -> None:
    field = route_deck_field(key="name", label="Name", required=True)

    manifest = (
        RouteDeckManifestBuilder("authoring-test")
        .node(
            "start",
            "Start",
            lane="main",
            description="Start node.",
            actions=["draft.create"],
            allowed_surfaces={"main": ["start"]},
            default_surfaces={"main": "start"},
        )
        .node(
            "done",
            "Done",
            lane="main",
            description="Done node.",
            expected_input="Completion state.",
            allowed_surfaces={"main": ["done"]},
            default_surfaces={"main": "done"},
        )
        .action(
            "draft.create",
            "Create draft",
            category="setup",
            fields=[field],
            allowed_nodes=["start"],
            placement="next_best",
        )
        .edge("start", "done", action_id="draft.create")
        .policy("navigation", {"source_of_truth": "runtime"})
        .test_path("happy_path", ["start", "done"])
        .build()
    )

    assert validate_manifest(manifest) == []
    assert manifest.edges[0].edge_type == "action"
    assert manifest.test_paths == [{"id": "happy_path", "nodes": ["start", "done"]}]


def test_edge_defaults_to_runtime_without_action() -> None:
    edge = route_deck_edge("start", "done")

    assert edge.edge_type == "runtime"


def test_authoring_helpers_copy_mutable_inputs() -> None:
    actions = ["draft.create"]
    allowed_nodes = ["start"]
    payload = {"intent": "create"}
    surfaces = {"main": ["start"]}
    defaults = {"main": "start"}

    node = route_deck_node(
        "start",
        "Start",
        lane="main",
        description="Start node.",
        actions=actions,
        allowed_surfaces=surfaces,
        default_surfaces=defaults,
    )
    action = route_deck_action(
        "draft.create",
        "Create draft",
        allowed_nodes=allowed_nodes,
        payload=payload,
    )

    actions.append("draft.delete")
    allowed_nodes.append("done")
    payload["intent"] = "delete"
    surfaces["main"].append("compact")
    defaults["main"] = "compact"

    assert node.allowed_actions == ["draft.create"]
    assert node.allowed_surfaces == {"main": ["start"]}
    assert node.default_surfaces == {"main": "start"}
    assert action.allowed_nodes == ["start"]
    assert action.payload == {"intent": "create"}
