from routedeck_core import RouteDeckSurface, RouteDeckSurfaceRegistry, route_deck_node


class ProductSurface(RouteDeckSurface):
    product: str = "demo"


class ProductSurfaceRegistry(RouteDeckSurfaceRegistry):
    Surface = ProductSurface


class SurfaceSpec:
    name = "active"
    surface_id = "orders.active"
    component = "OrdersSurface"
    variant = "orders"
    role = "active"
    slot = "active"
    surface_kind = "embedded"
    label = "Orders"
    props = {"title": "Orders"}
    lifecycle = "stable"


class ContextSurfaceSpec(SurfaceSpec):
    props = {}

    def resolve_props(self, *, title: str, count: int) -> dict[str, object]:
        return {"title": title, "count": count}


def test_surface_registry_maps_components_defaults_and_review_ids() -> None:
    registry = RouteDeckSurfaceRegistry(
        active_components_by_node={"browse": "BrowseSurface"},
        default_surface_ids_by_node={"learning": "learning.policy_gaps"},
        surface_hosted_operations_by_node={"browse": ["product.open"]},
    )

    assert registry.active_surface_component_for_node("browse") == "BrowseSurface"
    assert registry.default_surface_id_for("browse") == "browse.active"
    assert registry.default_surface_id_for("learning") == "learning.policy_gaps"
    assert registry.default_surface_id_for("browse", pending_operation_id="product.open") == "operation_review.product.open"
    assert registry.operation_id_from_surface_id("operation_review.product.open") == "product.open"
    assert registry.operation_id_from_surface_id("browse.active") is None
    assert registry.is_surface_hosted_operation(node_id="browse", operation_id="product.open") is True
    assert registry.is_surface_hosted_operation(node_id="browse", operation_id="cart.add") is False


def test_surface_registry_builds_operation_review_surface() -> None:
    surface = RouteDeckSurfaceRegistry().operation_review_surface(
        node_id="browse",
        operation_id="product.open",
        operation_args={"product_id": "public_1"},
        component="ReviewSurface",
        props={"source": "test"},
    )

    assert surface.name == "review"
    assert surface.surface_id == "operation_review.product.open"
    assert surface.component == "ReviewSurface"
    assert surface.surface_kind == "peer"
    assert surface.props["operation_args"] == {"product_id": "public_1"}
    assert surface.props["source"] == "test"


def test_surface_registry_builds_surface_from_product_descriptor() -> None:
    surface = RouteDeckSurfaceRegistry().build_surface_from_spec(
        SurfaceSpec(),
        props={"title": "Live orders", "count": 3},
    )

    assert surface.name == "active"
    assert surface.surface_id == "orders.active"
    assert surface.component == "OrdersSurface"
    assert surface.role == "active"
    assert surface.props == {"title": "Live orders", "count": 3}


def test_surface_registry_builds_declared_surface_subclass() -> None:
    surface = ProductSurfaceRegistry().build_surface_from_spec(SurfaceSpec())
    review_surface = ProductSurfaceRegistry().operation_review_surface(
        node_id="orders",
        operation_id="orders.refresh",
        component="ReviewSurface",
    )

    assert isinstance(surface, ProductSurface)
    assert isinstance(review_surface, ProductSurface)
    assert surface.product == "demo"


def test_surface_registry_builds_surface_lists_from_product_specs() -> None:
    surfaces = ProductSurfaceRegistry().surfaces_from_specs(
        [ContextSurfaceSpec(), SurfaceSpec()],
        title="Live orders",
        count=3,
    )

    assert [surface.surface_id for surface in surfaces] == ["orders.active", "orders.active"]
    assert all(isinstance(surface, ProductSurface) for surface in surfaces)
    assert surfaces[0].props == {"title": "Live orders", "count": 3}
    assert surfaces[1].props == {"title": "Orders"}


def test_surface_registry_validates_requested_variant_against_node() -> None:
    node = route_deck_node(
        "create",
        "Create",
        lane="workspace",
        description="Create flow.",
        expected_input="Create details.",
        allowed_surfaces={"main": ["guided", "compact"]},
        default_surfaces={"main": "guided"},
    )
    registry = RouteDeckSurfaceRegistry()

    assert (
        registry.surface_variant_for_node(
            node_id="create",
            presentation_state={"surface_variants": {"main": "compact"}},
            surface_name="main",
            default="guided",
            node_by_id={"create": node},
        )
        == "compact"
    )
    assert (
        registry.surface_variant_for_node(
            node_id="create",
            presentation_state={"surface_variants": {"main": "dense"}},
            surface_name="main",
            default="guided",
            node_by_id={"create": node},
        )
        == "guided"
    )


def test_surface_registry_stores_only_accepted_surface_intents() -> None:
    node = route_deck_node(
        "create",
        "Create",
        lane="workspace",
        description="Create flow.",
        expected_input="Create details.",
        allowed_surfaces={"main": ["guided"], "active": ["detail"]},
        default_surfaces={"main": "guided", "active": "detail"},
    )
    presentation_state = {"surface_variants": {"main": "guided"}}

    stored = RouteDeckSurfaceRegistry().store_surface_intent_for_node(
        node_id="create",
        surface_intent={"main": "dense", "active": "detail", 3: "bad"},
        node_by_id={"create": node},
        presentation_state=presentation_state,
    )

    assert stored is True
    assert presentation_state["surface_variants"] == {"main": "guided", "active": "detail"}
