from __future__ import annotations

from pathlib import Path
from typing import Any

from routedeck_core import (
    RouteDeckDispatchInput,
    RouteDeckDispatchResult,
    RouteDeckIntrospection,
    RouteDeckOperation,
    RouteDeckProjection,
    RouteDeckRuntime,
    RouteDeckRuntimeState,
    RouteDeckSurfaceInteractionEvent,
    RouteDeckSurface,
)


def test_runtime_state_wraps_projection_without_product_fields():
    projection = RouteDeckProjection(
        current_context="dashboard",
        graph_node="dashboard",
        projection_version=4,
        legal_operations=[RouteDeckOperation(id="agent.create", label="Create", execution_mode="auto")],
        surfaces={
            "main": RouteDeckSurface(name="main", component="DashboardPanel", variant="default"),
        },
        navigation={
            "current": {"node_id": "dashboard", "surface_id": "dashboard.main"},
            "back_stack": [],
            "forward_stack": [],
        },
    )

    state = RouteDeckRuntimeState(
        projection=projection,
        status="idle",
        graph_state={"node": "dashboard"},
        location="/app/home",
        metadata={"source": "test"},
    )

    assert state.projection.graph_node == "dashboard"
    assert state.status == "idle"
    assert state.graph_state == {"node": "dashboard"}
    assert state.location == "/app/home"
    assert state.metadata == {"source": "test"}


def test_dispatch_result_carries_new_runtime_state_and_active_surface():
    projection = RouteDeckProjection(
        current_context="auth_register",
        graph_node="auth_register",
        surfaces={
            "active": RouteDeckSurface(
                name="active",
                component="AuthSurface",
                variant="register",
                role="active",
            )
        },
        navigation={
            "current": {"node_id": "auth_register", "surface_id": "auth_register.active"},
            "back_stack": [],
            "forward_stack": [],
        },
    )
    runtime_state = RouteDeckRuntimeState(projection=projection, status="idle")

    result = RouteDeckDispatchResult(
        operation_id="auth.register",
        accepted=True,
        state=runtime_state,
        active_surface=projection.surfaces["active"],
        messages=[{"content": "Create your account."}],
    )

    assert result.accepted is True
    assert result.state.projection.graph_node == "auth_register"
    assert result.active_surface is not None
    assert result.messages == [{"content": "Create your account."}]


def test_introspection_contract_is_read_only_graph_context():
    introspection = RouteDeckIntrospection(
        current_node="dashboard",
        reachable_nodes=["auth_register"],
        legal_operations=[{"id": "auth.register"}],
        blocked_operations=[{"id": "agent.open", "reason": "Authentication required"}],
        guard_explanations=["Authentication required"],
        surfaces={"main": {"component": "DashboardPanel"}},
        route_traces=[{"from": "dashboard", "to": "auth_register"}],
    )

    assert introspection.current_node == "dashboard"
    assert introspection.blocked_operations[0]["reason"] == "Authentication required"
    assert "dispatch" not in introspection.model_dump()


def test_dispatch_input_can_carry_surface_interaction_event_without_private_refs():
    request = RouteDeckDispatchInput(
        surface_event=RouteDeckSurfaceInteractionEvent(
            surface_id="detail.product_detail",
            affordance_id="add_to_cart",
            entity_key="variant:s-black",
            payload={"quantity": 1},
        ),
        projection_version=7,
    )

    payload = request.model_dump(mode="json")
    assert payload["operation_id"] is None
    assert payload["surface_event"]["entity_key"] == "variant:s-black"
    assert "variant_" not in str(payload["surface_event"])


def test_runtime_protocol_describes_agentic_state_manager_shape():
    class DemoRuntime:
        async def snapshot(self, context: dict[str, Any] | None = None) -> RouteDeckRuntimeState:
            raise NotImplementedError

        async def projection(self, context: dict[str, Any] | None = None) -> RouteDeckProjection:
            raise NotImplementedError

        async def dispatch(
            self,
            request: RouteDeckDispatchInput,
            context: dict[str, Any] | None = None,
        ) -> RouteDeckDispatchResult:
            raise NotImplementedError

        async def inspect(self, query: dict[str, Any] | None = None, context: dict[str, Any] | None = None) -> RouteDeckIntrospection:
            raise NotImplementedError

        def stream(self, context: dict[str, Any] | None = None):
            raise NotImplementedError

    assert isinstance(DemoRuntime(), RouteDeckRuntime)


def test_framework_runtime_source_has_no_product_literals():
    root = Path(__file__).resolve().parents[1]
    source_roots = [root / "routedeck_core", root / "react" / "src"]
    banned = ["SaaStoAgent", "SaaSAgent", "Corpus", "saas_agent", "database", "/app/"]
    offenders: list[str] = []

    for source_root in source_roots:
        for path in source_root.rglob("*"):
            if path.suffix not in {".py", ".ts", ".tsx"}:
                continue
            text = path.read_text(encoding="utf-8")
            for literal in banned:
                if literal in text:
                    offenders.append(f"{path.relative_to(root)} contains {literal}")

    assert offenders == []
