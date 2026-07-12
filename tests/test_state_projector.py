from routedeck_core import (
    RouteDeckContextLens,
    RouteDeckGraphNavigationLocation,
    RouteDeckGraphState,
    RouteDeckManifestBuilder,
    RouteDeckStateProjector,
    RouteDeckSurface,
    RouteDeckSurfaceRegistry,
    route_deck_action,
    route_deck_node,
)


class HookedStateProjector(RouteDeckStateProjector):
    def current_context_for_state(
        self, state: RouteDeckGraphState, **context: object
    ) -> str:
        return str(context["current_context"])

    def actions_for_state(
        self, state: RouteDeckGraphState, **context: object
    ) -> list[object]:
        return [route_deck_action("browse.open", "Browse", category="navigation")]

    def surfaces_for_state(
        self, state: RouteDeckGraphState, **context: object
    ) -> list[RouteDeckSurface]:
        return [
            RouteDeckSurface(
                name="main",
                surface_id="home.active",
                component="HomeSurface",
                variant="home",
                role="active",
            )
        ]

    def presentation_state_for_state(
        self, state: RouteDeckGraphState, **context: object
    ) -> dict[str, object]:
        return {"context": context["current_context"]}

    def diagnostics_for_state(
        self, state: RouteDeckGraphState, **context: object
    ) -> dict[str, object]:
        return {"source": "hooked"}


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


def test_state_projector_resolves_default_surface_ids_from_graph_state() -> None:
    projector = RouteDeckStateProjector(
        manifest=_manifest(),
        surface_registry=RouteDeckSurfaceRegistry(
            active_components_by_node={"browse": "BrowseSurface"},
            default_surface_ids_by_node={"browse": "browse.active"},
        ),
    )

    assert (
        projector.default_surface_id_for_state(RouteDeckGraphState(node="browse"))
        == "browse.active"
    )
    assert (
        projector.default_surface_id_for_state(
            RouteDeckGraphState(node="browse", pending_operation_id="browse.open")
        )
        == "operation_review.browse.open"
    )
    assert projector.default_surface_by_node_for_state(
        RouteDeckGraphState(node="home")
    ) == {"browse": "browse.active"}


def test_state_projector_builds_navigation_from_graph_state() -> None:
    projector = RouteDeckStateProjector(
        manifest=_manifest(),
        surface_registry=RouteDeckSurfaceRegistry(
            active_components_by_node={"browse": "BrowseSurface"},
            default_surface_ids_by_node={"browse": "browse.active"},
        ),
    )
    state = RouteDeckGraphState(
        node="browse",
        route_params={"tab": "recent"},
        navigation_back_stack=[
            RouteDeckGraphNavigationLocation(
                node_id="home",
                surface_id="home.active",
                params={"from": "landing"},
            )
        ],
        navigation_forward_stack=[
            RouteDeckGraphNavigationLocation(
                node_id="detail",
                surface_id="detail.active",
                params={"id": "42"},
            )
        ],
    )

    navigation = projector.navigation_for_state(state)

    assert navigation["current"] == {
        "node_id": "browse",
        "surface_id": "browse.active",
        "params": {"tab": "recent"},
    }
    assert navigation["back_stack"] == [
        {"node_id": "home", "surface_id": "home.active", "params": {"from": "landing"}}
    ]
    assert navigation["forward_stack"] == [
        {"node_id": "detail", "surface_id": "detail.active", "params": {"id": "42"}}
    ]


def test_state_projector_prepends_operation_review_surface() -> None:
    projector = RouteDeckStateProjector(
        manifest=_manifest(),
        surface_registry=RouteDeckSurfaceRegistry(
            active_components_by_node={"browse": "BrowseSurface"},
            default_surface_ids_by_node={"browse": "browse.active"},
        ),
    )
    state = RouteDeckGraphState(
        node="browse",
        pending_operation_id="browse.open",
        pending_operation_args={"tab": "recent"},
    )
    active_surface = RouteDeckSurface(
        name="active",
        surface_id="browse.active",
        component="BrowseSurface",
        role="active",
    )

    surfaces = projector.active_surfaces_with_review(
        state,
        [active_surface],
        props={"copy": "Review browse"},
        component="BrowseReviewSurface",
    )

    assert [surface.surface_id for surface in surfaces] == [
        "operation_review.browse.open",
        "browse.active",
    ]
    assert surfaces[0].component == "BrowseReviewSurface"
    assert surfaces[0].props["operation_args"] == {"tab": "recent"}
    assert surfaces[0].props["copy"] == "Review browse"


def test_state_projector_builds_node_hierarchy_diagnostics() -> None:
    hierarchy = RouteDeckStateProjector(manifest=_manifest()).node_hierarchy(
        default_surface_by_node={"browse": "browse.active"}
    )

    assert hierarchy["browse"]["parent"] == "home"
    assert hierarchy["browse"]["capability_id"] == "browse"
    assert hierarchy["browse"]["default_surface_id"] == "browse.active"


def test_state_projector_projects_actions_surfaces_and_context() -> None:
    manifest = _manifest()
    context_lens = RouteDeckContextLens(
        current_node="home",
        working_on="Home",
    )
    projection = RouteDeckStateProjector(manifest=manifest).project(
        current_node="home",
        current_context="workspace",
        actions=[route_deck_action("browse.open", "Browse", category="navigation")],
        surfaces=[
            RouteDeckSurface(name="main", component="HomeSurface", variant="home")
        ],
        navigation={
            "current": {
                "node_id": "home",
                "surface_id": "home.active",
                "params": {"tab": "overview"},
            }
        },
        context_lens=context_lens,
        presentation_state={"context": "workspace"},
        diagnostics={"source": "test"},
    )

    assert projection.current_context == "workspace"
    assert projection.legal_operations[0].id == "browse.open"
    assert projection.surfaces["main"].component == "HomeSurface"
    assert projection.navigation.current.surface_id == "home.active"
    assert projection.context_lens == context_lens.model_copy(
        update={
            "active_surface_id": "home.active",
            "route_params": {"tab": "overview"},
            "legal_operation_ids": ["browse.open"],
        }
    )
    assert projection.diagnostics == {"source": "test"}


def test_state_projector_owns_store_projection_assembly_with_product_hooks() -> None:
    projection = HookedStateProjector(
        manifest=_manifest(),
        surface_registry=RouteDeckSurfaceRegistry(
            active_components_by_node={"home": "HomeSurface"},
            default_surface_ids_by_node={"home": "home.active"},
        ),
    ).project_state(
        RouteDeckGraphState(node="home"),
        current_context="workspace",
        projection_version=3,
    )

    assert projection.current_context == "workspace"
    assert projection.graph_node == "home"
    assert projection.projection_version == 3
    assert projection.legal_operations[0].id == "browse.open"
    assert projection.surfaces["main"].component == "HomeSurface"
    assert projection.navigation.current.surface_id == "home.active"
    assert projection.presentation_state == {"context": "workspace"}
    assert projection.diagnostics == {"source": "hooked"}
