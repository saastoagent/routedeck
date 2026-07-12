from __future__ import annotations

from pathlib import Path
from typing import Any

from routedeck_core import (
    RouteDeckActionSpec,
    RouteDeckCapabilitySpec,
    RouteDeckDispatchInput,
    RouteDeckDispatchResult,
    RouteDeckEdgeSpec,
    RouteDeckIntrospection,
    RouteDeckManifest,
    RouteDeckNodeSpec,
    RouteDeckOperation,
    RouteDeckProjection,
    RouteDeckRuntime,
    RouteDeckRuntimeState,
    RouteDeckSurfaceInteractionEvent,
    RouteDeckSurface,
    build_dispatch_result,
    build_dispatch_state_event,
    build_operation_completed_event,
    build_projection,
    build_projection_update_event,
    build_runtime_state,
)


def test_runtime_state_wraps_projection_without_product_fields():
    projection = RouteDeckProjection(
        current_context="dashboard",
        graph_node="dashboard",
        projection_version=4,
        legal_operations=[
            RouteDeckOperation(id="agent.create", label="Create", execution_mode="auto")
        ],
        surfaces={
            "main": RouteDeckSurface(
                name="main", component="DashboardPanel", variant="default"
            ),
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
            "current": {
                "node_id": "auth_register",
                "surface_id": "auth_register.active",
            },
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


def test_build_runtime_state_inherits_projection_diagnostics_by_default():
    projection = RouteDeckProjection(
        current_context="auth_register",
        graph_node="auth_register",
        projection_version=3,
        navigation={
            "current": {"node_id": "auth_register"},
            "back_stack": [],
            "forward_stack": [],
        },
        diagnostics={"blocked": ["auth required"]},
    )

    state = build_runtime_state(
        projection=projection,
        graph_state={"node": "auth_register"},
        location="/register",
    )

    assert state.status == "idle"
    assert state.graph_state == {"node": "auth_register"}
    assert state.location == "/register"
    assert state.diagnostics == {"blocked": ["auth required"]}


def test_build_projection_update_event_carries_runtime_state_and_projection():
    projection = RouteDeckProjection(
        current_context="dashboard",
        graph_node="dashboard",
        projection_version=9,
        navigation={
            "current": {"node_id": "dashboard"},
            "back_stack": [],
            "forward_stack": [],
        },
    )
    state = build_runtime_state(
        projection=projection, graph_state={"node": "dashboard"}
    )

    event = build_projection_update_event(state=state, payload={"source": "test"})
    payload = event.model_dump(mode="json", by_alias=True)

    assert payload["event_type"] == "projection_update"
    assert payload["projection_version"] == 9
    assert payload["payload"]["projection"]["graph_node"] == "dashboard"
    assert payload["payload"]["state"]["graph_state"] == {"node": "dashboard"}
    assert payload["payload"]["source"] == "test"


def test_build_dispatch_result_defaults_to_operation_completed_event():
    projection = RouteDeckProjection(
        current_context="dashboard",
        graph_node="dashboard",
        projection_version=11,
        navigation={
            "current": {"node_id": "dashboard"},
            "back_stack": [],
            "forward_stack": [],
        },
        surfaces={
            "main": RouteDeckSurface(
                name="main",
                component="DashboardPanel",
                role="active",
            )
        },
    )
    state = build_runtime_state(
        projection=projection, graph_state={"node": "dashboard"}
    )

    result = build_dispatch_result(
        operation_id="dashboard.open",
        state=state,
        active_surface=projection.surfaces["main"],
        messages=[{"content": "Opened dashboard."}],
        metadata={"replace_path": "/dashboard"},
    )
    payload = result.model_dump(mode="json", by_alias=True)

    assert result.accepted is True
    assert result.active_surface == projection.surfaces["main"]
    assert payload["messages"] == [{"content": "Opened dashboard."}]
    assert payload["metadata"] == {"replace_path": "/dashboard"}
    assert payload["events"][0]["event_type"] == "operation_completed"
    assert payload["events"][0]["projection_version"] == 11
    assert payload["events"][0]["payload"]["operation_id"] == "dashboard.open"
    assert payload["events"][0]["payload"]["state"] == {"node": "dashboard"}
    assert payload["events"][0]["payload"]["projection"]["graph_node"] == "dashboard"
    assert (
        payload["events"][0]["payload"]["active_surface"]["component"]
        == "DashboardPanel"
    )
    assert payload["events"][0]["payload"]["messages"] == [
        {"content": "Opened dashboard."}
    ]
    assert payload["events"][0]["payload"]["replace_path"] == "/dashboard"


def test_build_operation_completed_event_accepts_payload_overlay():
    projection = RouteDeckProjection(
        current_context="review",
        graph_node="review",
        projection_version=5,
        navigation={
            "current": {"node_id": "review"},
            "back_stack": [],
            "forward_stack": [],
        },
    )

    event = build_operation_completed_event(
        operation_id="review.approve",
        projection=projection,
        payload={"result": "approved"},
    )
    payload = event.model_dump(mode="json", by_alias=True)

    assert payload["event_type"] == "operation_completed"
    assert payload["projection_version"] == 5
    assert payload["payload"]["operation_id"] == "review.approve"
    assert payload["payload"]["projection"]["graph_node"] == "review"
    assert payload["payload"]["result"] == "approved"


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


def test_build_projection_defaults_manifest_capabilities_and_empty_pools():
    manifest = RouteDeckManifest(
        version="runtime-helper",
        nodes=[
            RouteDeckNodeSpec(
                id="queue", label="Queue", lane="review", description="Review queue."
            ),
        ],
        edges=[],
        actions=[],
        capabilities=[
            RouteDeckCapabilitySpec(
                capability_id="review.queue",
                label="Review queue",
                operation_ids=["review.open"],
                entity_kinds=["draft"],
                surface_ids=["review.queue"],
            )
        ],
    )

    projection = build_projection(manifest, current_node="queue")

    assert [capability.capability_id for capability in projection.capabilities] == [
        "review.queue"
    ]
    assert projection.available_entities == []
    assert projection.surface_affordances == []
    assert projection.legal_operations == []


def test_build_projection_derives_navgraph_from_manifest_nodes_and_edges():
    manifest = RouteDeckManifest(
        version="runtime-navgraph",
        nodes=[
            RouteDeckNodeSpec(
                id="queue",
                label="Queue",
                lane="review",
                description="Review queue.",
                capability_id="review.queue",
            ),
            RouteDeckNodeSpec(
                id="detail",
                label="Detail",
                lane="review",
                description="Review detail.",
                capability_id="review.detail",
            ),
        ],
        edges=[
            RouteDeckEdgeSpec(
                from_stage="queue",
                to_stage="detail",
                type="action",
                action_id="review.open",
                capability_id="review.detail",
            )
        ],
        actions=[RouteDeckActionSpec(id="review.open", label="Open review")],
    )

    projection = build_projection(manifest, current_node="queue")
    payload = projection.model_dump(mode="json", by_alias=True)

    assert payload["navgraph"]["current"]["node_id"] == "queue"
    assert [node["id"] for node in payload["navgraph"]["nodes"]] == ["queue", "detail"]
    assert payload["navgraph"]["nodes"][1]["capability_ids"] == ["review.detail"]
    assert payload["navgraph"]["edges"] == [
        {
            "from": "queue",
            "to": "detail",
            "action_id": "review.open",
            "capability_id": "review.detail",
            "metadata": {},
        }
    ]
    assert payload["navgraph"]["reachable"] == ["detail"]


def test_build_projection_filters_blocked_operations_at_runtime_boundary():
    manifest = RouteDeckManifest(
        version="runtime-operations",
        nodes=[
            RouteDeckNodeSpec(
                id="detail", label="Detail", lane="review", description="Review detail."
            ),
        ],
        edges=[],
        actions=[],
    )

    projection = build_projection(
        manifest,
        current_node="detail",
        operations=[
            RouteDeckOperation(
                id="draft.approve", label="Approve draft", execution_mode="auto"
            ),
            RouteDeckOperation(
                id="draft.escalate",
                label="Escalate draft",
                execution_mode="blocked",
                guard="Reviewer permission required",
            ),
        ],
    )

    assert [operation.id for operation in projection.legal_operations] == [
        "draft.approve"
    ]


def test_dispatch_state_events_include_runtime_state_projection_payload():
    manifest = RouteDeckManifest(
        version="runtime-event",
        nodes=[
            RouteDeckNodeSpec(
                id="detail", label="Detail", lane="review", description="Review detail."
            ),
        ],
        edges=[],
        actions=[],
    )
    projection = build_projection(
        manifest, current_node="detail", projection_version=12
    )
    state = RouteDeckRuntimeState(
        projection=projection,
        status="dispatching",
        graph_state={"node": "detail"},
    )

    event = build_dispatch_state_event(operation_id="draft.approve", state=state)
    payload = event.model_dump(mode="json", by_alias=True)

    assert payload["event_type"] == "operation_completed"
    assert payload["projection_version"] == 12
    assert payload["payload"]["operation_id"] == "draft.approve"
    assert payload["payload"]["state"]["projection"]["graph_node"] == "detail"
    assert payload["payload"]["state"]["graph_state"] == {"node": "detail"}


def test_runtime_protocol_describes_agentic_state_manager_shape():
    class DemoRuntime:
        async def snapshot(
            self, context: dict[str, Any] | None = None
        ) -> RouteDeckRuntimeState:
            raise NotImplementedError

        async def projection(
            self, context: dict[str, Any] | None = None
        ) -> RouteDeckProjection:
            raise NotImplementedError

        async def dispatch(
            self,
            request: RouteDeckDispatchInput,
            context: dict[str, Any] | None = None,
        ) -> RouteDeckDispatchResult:
            raise NotImplementedError

        async def inspect(
            self,
            query: dict[str, Any] | None = None,
            context: dict[str, Any] | None = None,
        ) -> RouteDeckIntrospection:
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
