from pathlib import Path

from routedeck_core import (
    RouteDeckActionSpec,
    RouteDeckAvailableEntity,
    RouteDeckBindingExpression,
    RouteDeckCapabilitySpec,
    RouteDeckContextLens,
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
                allowed_actions=["draft.create", "draft.archive"],
            )
        ],
        edges=[],
        actions=[
            RouteDeckActionSpec(id="draft.create", label="Create draft"),
            RouteDeckActionSpec(id="draft.archive", label="Archive draft"),
        ],
    )

    projection = build_projection(
        manifest,
        current_node="dashboard",
        operations=[
            RouteDeckOperation(
                id="draft.create",
                label="Create draft",
                safety_class="navigation",
                execution_mode="auto",
            ),
            RouteDeckOperation(
                id="draft.archive",
                label="Archive draft",
                safety_class="destructive",
                execution_mode="blocked",
                guard="reviewer permission required",
            ),
        ],
        surfaces=[
            RouteDeckSurface(
                name="main", component="DashboardPanel", variant="default", role="frame"
            ),
        ],
        projection_version=3,
    )

    assert projection.current_context == "dashboard"
    assert projection.graph_node == "dashboard"
    assert projection.projection_version == 3
    assert [operation.id for operation in projection.legal_operations] == [
        "draft.create"
    ]
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
        surfaces=[
            RouteDeckSurface(name="main", component="CreatePanel", variant="dense")
        ],
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
                    lane="review",
                    description="Review detail.",
                    allowed_actions=["draft.approve"],
                    capability_id="draft.approve",
                )
            ],
            edges=[],
            actions=[
                RouteDeckActionSpec(
                    id="draft.approve",
                    label="Approve draft",
                    capability_id="draft.approve",
                ),
            ],
            capabilities=[
                RouteDeckCapabilitySpec(
                    capability_id="draft.approve",
                    label="Approve draft",
                    operation_ids=["draft.approve"],
                    entity_kinds=["draft"],
                    surface_ids=["review.detail"],
                )
            ],
        ),
        current_node="detail",
        operations=[
            RouteDeckOperation(
                id="draft.approve",
                label="Approve draft",
                capability_id="draft.approve",
                surface_id="review.detail",
                required_args=["draft_ref", "decision"],
            )
        ],
        available_entities=[
            RouteDeckAvailableEntity(
                kind="draft",
                entity_key="draft:alpha",
                label="Draft Alpha",
                parent_label="Review Queue",
                rendered_on=["review.detail"],
                operations=[
                    RouteDeckEntityOperationBinding(
                        operation_id="draft.approve",
                        args={"draft_ref": "draft_opaque_1", "decision": "approve"},
                    )
                ],
            )
        ],
        surface_affordances=[
            RouteDeckSurfaceAffordance(
                surface_id="review.detail",
                affordance_id="approve_primary",
                event="approve_clicked",
                capability_id="draft.approve",
                operation_id="draft.approve",
                entity_key="draft:alpha",
                arg_bindings={
                    "draft_ref": RouteDeckBindingExpression(
                        source="entity",
                        path="operations.draft.approve.args.draft_ref",
                    ),
                    "decision": RouteDeckBindingExpression(
                        source="event", path="decision"
                    ),
                },
            )
        ],
    )

    payload = projection.model_dump(mode="json")
    assert payload["capabilities"][0]["capability_id"] == "draft.approve"
    assert payload["legal_operations"][0]["capability_id"] == "draft.approve"
    assert payload["available_entities"][0]["entity_key"] == "draft:alpha"
    assert payload["surface_affordances"][0]["arg_bindings"]["decision"] == {
        "from": "event",
        "path": "decision",
    }


def test_projection_contract_exposes_context_lens_as_first_class_projection_context():
    projection = build_projection(
        RouteDeckManifest(
            version="context-lens-contract",
            nodes=[
                RouteDeckNodeSpec(
                    id="dashboard",
                    label="Dashboard",
                    lane="workspace",
                    description="Dashboard node.",
                )
            ],
            edges=[],
            actions=[],
        ),
        current_node="dashboard",
        operations=[
            RouteDeckOperation(
                id="dashboard.refresh",
                label="Refresh dashboard",
            )
        ],
        navigation={
            "current": {
                "node_id": "dashboard",
                "surface_id": "dashboard.active",
                "params": {"tab": "overview"},
            }
        },
        context_lens=RouteDeckContextLens(
            current_node="dashboard",
            working_on="Dashboard",
        ),
    )

    payload = projection.model_dump(mode="json")
    assert payload["context_lens"] == {
        "current_node": "dashboard",
        "working_on": "Dashboard",
        "active_surface_id": "dashboard.active",
        "route_params": {"tab": "overview"},
        "legal_operation_ids": ["dashboard.refresh"],
    }


def test_projection_contract_exposes_navgraph_without_treating_actions_as_nodes():
    projection = build_projection(
        RouteDeckManifest(
            version="navgraph-contract",
            nodes=[
                RouteDeckNodeSpec(
                    id="queue",
                    label="Queue",
                    lane="review",
                    description="Review draft queue.",
                ),
                RouteDeckNodeSpec(
                    id="detail",
                    label="Detail",
                    lane="review",
                    description="Review detail.",
                ),
            ],
            edges=[],
            actions=[RouteDeckActionSpec(id="review.open", label="Open review")],
        ),
        current_node="queue",
        navgraph=RouteDeckNavGraph(
            current={
                "node_id": "queue",
                "deeplink": {"url": "/work/review", "resumable": True},
            },
            nodes=[
                RouteDeckNavGraphNode(
                    id="queue",
                    label="Queue",
                    capability_ids=["review.queue"],
                    deeplink=RouteDeckDeepLink(url="/work/review", resumable=True),
                ),
                RouteDeckNavGraphNode(
                    id="detail",
                    label="Detail",
                    capability_ids=["review.detail"],
                    deeplink=RouteDeckDeepLink(
                        url="/work/review/draft-alpha", resumable=True
                    ),
                ),
            ],
            edges=[
                RouteDeckNavGraphEdge(
                    from_stage="queue", to="detail", action_id="review.open"
                )
            ],
            reachable=["detail"],
        ),
    )

    payload = projection.model_dump(mode="json", by_alias=True)
    node_ids = {node["id"] for node in payload["navgraph"]["nodes"]}
    assert "review.open" not in node_ids
    assert payload["navgraph"]["edges"][0]["action_id"] == "review.open"
    assert payload["navgraph"]["edges"][0]["from"] == "queue"
    assert payload["navgraph"]["current"]["deeplink"]["url"] == "/work/review"
    assert (
        payload["navgraph"]["nodes"][1]["deeplink"]["url"] == "/work/review/draft-alpha"
    )


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
                assert needle not in source, (
                    f"{needle} leaked into framework runtime source: {path}"
                )
