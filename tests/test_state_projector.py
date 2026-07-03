from routedeck_core import (
    RouteDeckManifestBuilder,
    RouteDeckStateProjector,
    RouteDeckSurface,
    route_deck_action,
    route_deck_node,
)


def _manifest():
    return (
        RouteDeckManifestBuilder("projector-test")
        .add_nodes(
            [
                route_deck_node(
                    "home",
                    "Home",
                    lane="workspace",
                    description="Home node.",
                    actions=["browse.open"],
                    allowed_surfaces={"main": ["home"]},
                    default_surfaces={"main": "home"},
                ),
                route_deck_node(
                    "browse",
                    "Browse",
                    lane="workspace",
                    description="Browse node.",
                    expected_input="Browse content.",
                    parent="home",
                    capability_id="browse",
                    allowed_surfaces={"active": ["browse"]},
                    default_surfaces={"active": "browse"},
                ),
            ]
        )
        .action("browse.open", "Browse", category="navigation")
        .edge("home", "browse", action_id="browse.open")
        .build()
    )


def test_state_projector_resolves_current_surface_id() -> None:
    projector = RouteDeckStateProjector(manifest=_manifest())

    assert (
        projector.resolve_current_surface_id(
            active_surface_id="operation_review.browse.open",
            pending_operation_id=None,
            default_surface_id="home.active",
        )
        == "home.active"
    )
    assert (
        projector.resolve_current_surface_id(
            active_surface_id="operation_review.browse.open",
            pending_operation_id="browse.open",
            default_surface_id="home.active",
        )
        == "operation_review.browse.open"
    )


def test_state_projector_builds_node_hierarchy_diagnostics() -> None:
    hierarchy = RouteDeckStateProjector(manifest=_manifest()).node_hierarchy(
        default_surface_by_node={"browse": "browse.active"}
    )

    assert hierarchy["browse"]["parent"] == "home"
    assert hierarchy["browse"]["capability_id"] == "browse"
    assert hierarchy["browse"]["default_surface_id"] == "browse.active"


def test_state_projector_projects_actions_surfaces_and_context() -> None:
    manifest = _manifest()
    projection = RouteDeckStateProjector(manifest=manifest).project(
        current_node="home",
        current_context="workspace",
        actions=[route_deck_action("browse.open", "Browse", category="navigation")],
        surfaces=[RouteDeckSurface(name="main", component="HomeSurface", variant="home")],
        navigation={"current": {"node_id": "home", "surface_id": "home.active"}},
        presentation_state={"context": "workspace"},
        diagnostics={"source": "test"},
    )

    assert projection.current_context == "workspace"
    assert projection.legal_operations[0].id == "browse.open"
    assert projection.surfaces["main"].component == "HomeSurface"
    assert projection.navigation.current.surface_id == "home.active"
    assert projection.diagnostics == {"source": "test"}
