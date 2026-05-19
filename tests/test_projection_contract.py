from pathlib import Path

from routedeck_core import (
    RouteDeckActionSpec,
    RouteDeckManifest,
    RouteDeckNodeSpec,
    RouteDeckOperation,
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
