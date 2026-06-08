from pathlib import Path

from routedeck_core import (
    RouteDeckActionSpec,
    RouteDeckAvailableEntity,
    RouteDeckBindingExpression,
    RouteDeckCapabilitySpec,
    RouteDeckDeepLink,
    RouteDeckEntityOperationBinding,
    RouteDeckManifest,
    RouteDeckNavGraph,
    RouteDeckNavGraphEdge,
    RouteDeckNavGraphNode,
    RouteDeckNodeSpec,
    RouteDeckOperation,
    RouteDeckSurfaceAffordance,
    RouteDeckSurface,
    build_projection,
)


def test_projection_exposes_legal_operations_and_hides_blocked_operations():
    manifest = RouteDeckManifest(
        version="projection-test",
        nodes=[
            RouteDeckNodeSpec(
                id="dashboard",
                label="Dashboard",
                lane="workspace",
                description="Personalized dashboard.",
                allowed_actions=["agent.create", "admin.delete"],
            )
        ],
        edges=[],
        actions=[
            RouteDeckActionSpec(id="agent.create", label="Create SaaS Agent"),
            RouteDeckActionSpec(id="admin.delete", label="Delete account"),
        ],
    )

    projection = build_projection(
        manifest,
        current_node="dashboard",
        operations=[
            RouteDeckOperation(
                id="agent.create",
                label="Create SaaS Agent",
                safety_class="navigation",
                execution_mode="auto",
            ),
            RouteDeckOperation(
                id="admin.delete",
                label="Delete account",
                safety_class="destructive",
                execution_mode="blocked",
                guard="admin permission required",
            ),
        ],
        surfaces=[
            RouteDeckSurface(name="main", component="DashboardPanel", variant="default", role="frame"),
        ],
        projection_version=3,
    )

    assert projection.current_context == "dashboard"
    assert projection.graph_node == "dashboard"
    assert projection.projection_version == 3
    assert [operation.id for operation in projection.legal_operations] == ["agent.create"]
    assert projection.surfaces["main"].component == "DashboardPanel"
    assert projection.surfaces["main"].role == "frame"


def test_projection_falls_back_when_surface_variant_is_not_allowed():
    manifest = RouteDeckManifest(
        version="surface-test",
        nodes=[
            RouteDeckNodeSpec(
                id="create",
                label="Create",
                lane="workspace",
                description="Create flow.",
                allowed_surfaces={"main": ["guided", "compact"]},
                default_surfaces={"main": "guided"},
            )
        ],
        edges=[],
        actions=[],
    )

    projection = build_projection(
        manifest,
        current_node="create",
        operations=[],
        surfaces=[RouteDeckSurface(name="main", component="CreatePanel", variant="dense")],
    )

    assert projection.surfaces["main"].variant == "guided"


def test_projection_contract_exposes_capabilities_entities_and_affordances():
    projection = build_projection(
        RouteDeckManifest(
            version="projection-contract",
            nodes=[
                RouteDeckNodeSpec(
                    id="detail",
                    label="Detail",
                    lane="shopping",
                    description="Product detail.",
                    allowed_actions=["cart.add_item"],
                    capability_id="cart.add_item",
                )
            ],
            edges=[],
            actions=[
                RouteDeckActionSpec(id="cart.add_item", label="Add item", capability_id="cart.add_item"),
            ],
            capabilities=[
                RouteDeckCapabilitySpec(
                    capability_id="cart.add_item",
                    label="Add item to cart",
                    operation_ids=["cart.add_item"],
                    entity_kinds=["variant"],
                    surface_ids=["detail.product_detail"],
                )
            ],
        ),
        current_node="detail",
        operations=[
            RouteDeckOperation(
                id="cart.add_item",
                label="Add item",
                capability_id="cart.add_item",
                surface_id="detail.product_detail",
                required_args=["variant_ref", "quantity"],
            )
        ],
        available_entities=[
            RouteDeckAvailableEntity(
                kind="variant",
                entity_key="variant:s-black",
                label="S / Black",
                parent_label="Medusa T-Shirt",
                rendered_on=["detail.product_detail"],
                operations=[
                    RouteDeckEntityOperationBinding(
                        operation_id="cart.add_item",
                        args={"variant_ref": "variant_opaque_1", "quantity": 1},
                    )
                ],
            )
        ],
        surface_affordances=[
            RouteDeckSurfaceAffordance(
                surface_id="detail.product_detail",
                affordance_id="add_to_cart",
                event="add_clicked",
                capability_id="cart.add_item",
                operation_id="cart.add_item",
                entity_key="variant:s-black",
                arg_bindings={
                    "variant_ref": RouteDeckBindingExpression(
                        source="entity",
                        path="operations.cart.add_item.args.variant_ref",
                    ),
                    "quantity": RouteDeckBindingExpression(source="event", path="quantity"),
                },
            )
        ],
    )

    payload = projection.model_dump(mode="json")
    assert payload["capabilities"][0]["capability_id"] == "cart.add_item"
    assert payload["legal_operations"][0]["capability_id"] == "cart.add_item"
    assert payload["available_entities"][0]["entity_key"] == "variant:s-black"
    assert payload["surface_affordances"][0]["arg_bindings"]["quantity"] == {"from": "event", "path": "quantity"}


def test_projection_contract_exposes_navgraph_without_treating_actions_as_nodes():
    projection = build_projection(
        RouteDeckManifest(
            version="navgraph-contract",
            nodes=[
                RouteDeckNodeSpec(id="browse", label="Browse", lane="shopping", description="Browse products."),
                RouteDeckNodeSpec(id="detail", label="Detail", lane="shopping", description="Product detail."),
            ],
            edges=[],
            actions=[RouteDeckActionSpec(id="catalog.open", label="View product")],
        ),
        current_node="browse",
        navgraph=RouteDeckNavGraph(
            current={"node_id": "browse", "deeplink": {"url": "/shop/browse", "resumable": True}},
            nodes=[
                RouteDeckNavGraphNode(
                    id="browse",
                    label="Browse",
                    capability_ids=["catalog.browse"],
                    deeplink=RouteDeckDeepLink(url="/shop/browse", resumable=True),
                ),
                RouteDeckNavGraphNode(
                    id="detail",
                    label="Detail",
                    capability_ids=["catalog.detail"],
                    deeplink=RouteDeckDeepLink(url="/shop/detail/t-shirt", resumable=True),
                ),
            ],
            edges=[RouteDeckNavGraphEdge(from_stage="browse", to="detail", action_id="catalog.open")],
            reachable=["detail"],
        ),
    )

    payload = projection.model_dump(mode="json", by_alias=True)
    node_ids = {node["id"] for node in payload["navgraph"]["nodes"]}
    assert "catalog.open" not in node_ids
    assert payload["navgraph"]["edges"][0]["action_id"] == "catalog.open"
    assert payload["navgraph"]["edges"][0]["from"] == "browse"
    assert payload["navgraph"]["current"]["deeplink"]["url"] == "/shop/browse"
    assert payload["navgraph"]["nodes"][1]["deeplink"]["url"] == "/shop/detail/t-shirt"


def test_framework_runtime_sources_have_no_product_literals():
    framework_roots = [
        Path(__file__).parents[1] / "routedeck_core",
        Path(__file__).parents[1] / "react" / "src",
    ]
    banned = ["SaaStoAgent", "SaaSAgent", "saas_agent", "Corpus"]

    for root in framework_roots:
        for path in root.rglob("*"):
            if path.suffix not in {".py", ".ts", ".tsx"}:
                continue
            source = path.read_text(encoding="utf-8")
            for needle in banned:
                assert needle not in source, f"{needle} leaked into framework runtime source: {path}"
